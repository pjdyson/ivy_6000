import json
import sys
import threading
import types
import wave
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler

import pytest

from ivy6000 import neural, tts
from ivy6000.skins import BUILTIN, VoiceStyle


def test_voice_url():
    assert neural.voice_url("en_GB-semaine-medium", ".onnx") == (
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
        "en/en_GB/semaine/medium/en_GB-semaine-medium.onnx?download=true")
    assert "/en_GB/northern_english_male/medium/" in neural.voice_url(
        "en_GB-northern_english_male-medium", ".onnx.json")


def test_every_character_has_a_valid_piper_voice():
    for skin in BUILTIN.values():
        assert tts._is_piper_id(skin.voice.piper), skin.voice.piper


def test_override_parsing():
    assert tts._is_piper_id("en_GB-semaine-medium:poppy")
    assert not tts._is_piper_id("Daniel")
    assert not tts._is_piper_id("en-gb+m3")


def test_download_from_a_server_and_speaker_lookup(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "v.onnx").write_bytes(b"model")
    (src / "v.onnx.json").write_text(json.dumps(
        {"num_speakers": 4, "speaker_id_map": {"prudence": 0, "spike": 1, "obadiah": 2}}))
    httpd = HTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(src)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        url = lambda vid, ext: f"http://127.0.0.1:{httpd.server_port}/v{ext}"  # noqa: E731
        model, config = neural.download("en_GB-x-medium", tmp_path / "voices", url_for=url)
        assert model.read_bytes() == b"model"
        assert neural.speaker_id(config, "obadiah") == 2
        assert neural.speaker_id(config, "nobody") == 0
    finally:
        httpd.shutdown()
    single = tmp_path / "s.json"
    single.write_text('{"num_speakers": 1}')
    assert neural.speaker_id(single, "anyone") is None


@pytest.fixture
def fake_piper(monkeypatch, tmp_path):
    """A stand-in piper module that writes a short silent WAV."""
    calls = {}

    class SynthesisConfig:
        def __init__(self, speaker_id=None, length_scale=None):
            calls["config"] = (speaker_id, length_scale)

    class PiperVoice:
        @staticmethod
        def load(model, config_path=None):
            calls["loaded"] = str(model)
            return PiperVoice()

        def synthesize_wav(self, text, wav, syn_config=None):
            calls["text"] = text
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(22050)
            wav.writeframes(b"\x00\x00" * 2205)

    mod = types.ModuleType("piper")
    mod.PiperVoice, mod.SynthesisConfig = PiperVoice, SynthesisConfig
    monkeypatch.setitem(sys.modules, "piper", mod)
    monkeypatch.setattr(neural, "available", lambda: True)
    monkeypatch.setattr(neural.Player, "_find_command", staticmethod(lambda: [sys.executable, "-c", "pass"]))
    voices = tmp_path / "voices"
    voices.mkdir()
    for vid, speakers in (("en_GB-semaine-medium", {"obadiah": 2, "spike": 1}), ("en_GB-alan-medium", None)):
        (voices / f"{vid}.onnx").write_bytes(b"m")
        cfg = {"num_speakers": len(speakers)} if speakers else {"num_speakers": 1}
        if speakers:
            cfg["speaker_id_map"] = speakers
        (voices / f"{vid}.onnx.json").write_text(json.dumps(cfg))
    return calls, voices


def test_neural_speaker_is_preferred_and_speaks(fake_piper):
    calls, voices = fake_piper
    sp = tts.make_speaker(BUILTIN["hugo"].voice, "", "auto", voices)
    assert sp.name == "piper semaine/obadiah"
    sp.speak("Hello. It's very quiet out here.")
    assert calls["config"] == (2, 1.25)
    assert calls["text"].startswith("Hello")


def test_override_and_system_engine(fake_piper):
    calls, voices = fake_piper
    sp = tts.make_speaker(BUILTIN["dot"].voice, "en_GB-alan-medium", "auto", voices)
    assert sp.name == "piper alan"
    assert not tts.make_speaker(VoiceStyle(), "", "system", voices).name.startswith("piper")


def test_neural_failure_falls_back_to_system_voice(fake_piper):
    calls, voices = fake_piper
    sp = tts.make_speaker(BUILTIN["hugo"].voice, "", "auto", voices)
    assert not tts.fallback(sp, BUILTIN["hugo"].voice).name.startswith("piper")


def test_stopping_cuts_playback_short(fake_piper, monkeypatch):
    calls, voices = fake_piper
    monkeypatch.setattr(neural.Player, "_find_command",
                        staticmethod(lambda: [sys.executable, "-c", "import time; time.sleep(5)"]))
    sp = tts.make_speaker(BUILTIN["hugo"].voice, "", "auto", voices)
    sp.prepare()
    threading.Timer(0.3, sp.stop).start()
    import time
    t = time.time()
    sp.speak("A long sentence that would take a while.")
    assert time.time() - t < 3
