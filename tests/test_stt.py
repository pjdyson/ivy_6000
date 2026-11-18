import json
import sys
import threading
import time
import types
import zipfile
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler

import pytest

from ivy6000 import stt

LOUD = bytes([1, 16]) * stt.BLOCK   # int16 amplitude 4097: clearly speech
SILENT = b"\x00" * (stt.BLOCK * 2)


@pytest.fixture
def fake_stt(monkeypatch, tmp_path):
    """Stand-in vosk and sounddevice modules; the fake mic plays scripted blocks."""
    state = {"queue": [], "loud_forever": False}

    class KaldiRecognizer:
        def __init__(self, model, rate):
            self.model, self.rate, self.fed = model, rate, 0

        def AcceptWaveform(self, data):
            self.fed += 1
            return self.fed == 2  # "end of utterance" on the second block

        def Result(self):
            return json.dumps({"text": "hello there"})

        def FinalResult(self):
            return json.dumps({"text": state.get("tail", "")})

    class Model:
        def __init__(self, path):
            self.path = str(path)

    vosk = types.ModuleType("vosk")
    vosk.Model, vosk.KaldiRecognizer = Model, KaldiRecognizer

    class RawInputStream:
        def __init__(self, **kw):
            self.kw = kw

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, n):
            if state["queue"]:
                return state["queue"].pop(0), False
            return (LOUD if state["loud_forever"] else SILENT), False

    sd = types.ModuleType("sounddevice")
    sd.RawInputStream = RawInputStream
    monkeypatch.setitem(sys.modules, "vosk", vosk)
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    monkeypatch.setattr(stt, "available", lambda: True)
    monkeypatch.setattr(stt, "SILENCE_SECONDS", 0.5)  # keep the tests quick
    models = tmp_path / "models"
    model = stt.model_dir(models)
    (model / "am").mkdir(parents=True)  # pretend the model is already downloaded
    return state, models


def test_model_url_and_dir():
    assert stt.MODEL_ID in stt.MODEL_URL
    assert stt.model_dir("/tmp/x") == stt.Path("/tmp/x") / stt.MODEL_ID


def test_download_extracts_zip_once(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    zpath = src / f"{stt.MODEL_ID}.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr(f"{stt.MODEL_ID}/am/final.mdl", "model-bytes")
    httpd = HTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(src)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{httpd.server_port}/{stt.MODEL_ID}.zip"
        dest = stt.download(tmp_path / "models", url_for=lambda: url)
        assert (dest / "am" / "final.mdl").read_bytes() == b"model-bytes"
        # already there: a second call must not hit the network
        assert stt.download(tmp_path / "models", url_for=lambda: 1 / 0) == dest
    finally:
        httpd.shutdown()


def test_make_listener_without_engine_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(stt, "available", lambda: False)
    lis = stt.make_listener(tmp_path)
    assert not lis.available and lis.listen() == "" and lis.name == "no mic"
    assert stt.listen_help()


def test_listen_returns_transcript(fake_stt):
    state, models = fake_stt
    state["queue"] = [LOUD, LOUD, LOUD]  # speech, then the fake mic goes silent
    lis = stt.make_listener(models)
    assert lis.available and lis.name.startswith("vosk")
    assert lis.listen() == "hello there"


def test_listen_accepts_buffer_objects(fake_stt):
    # sounddevice's RawInputStream.read returns a cffi buffer, not bytes; vosk rejects
    # those ("initialiser for ctype 'char *' must be a cdata pointer"), so listen() must
    # convert. A memoryview stands in for the buffer here.
    state, models = fake_stt
    state["queue"] = [memoryview(LOUD), memoryview(LOUD), memoryview(LOUD)]
    lis = stt.make_listener(models)
    assert lis.listen() == "hello there"


def test_final_result_flushes_the_tail(fake_stt):
    state, models = fake_stt
    state["queue"] = [LOUD, LOUD, LOUD]
    state["tail"] = "and goodbye"
    sys.modules["vosk"].KaldiRecognizer.AcceptWaveform = lambda self, data: False
    lis = stt.make_listener(models)
    assert lis.listen() == "and goodbye"


def test_stop_ends_listen_early(fake_stt):
    state, models = fake_stt
    state["loud_forever"] = True  # speech that never pauses
    lis = stt.make_listener(models)
    threading.Timer(0.2, lis.stop).start()
    t = time.time()
    lis.listen()
    assert time.time() - t < 5


def test_max_seconds_caps_the_recording(fake_stt, monkeypatch):
    state, models = fake_stt
    state["loud_forever"] = True
    monkeypatch.setattr(stt, "MAX_SECONDS", 0.5)
    lis = stt.make_listener(models)
    t = time.time()
    lis.listen()
    assert time.time() - t < 5
