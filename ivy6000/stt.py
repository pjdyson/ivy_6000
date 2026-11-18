"""Speech-to-text: hear the user through the microphone.

The engine is Vosk (https://alphacephei.com/vosk/models), a small offline recogniser,
fed by a ``sounddevice`` microphone stream. Both are optional dependencies; when they
aren't installed, ``make_listener`` returns an unavailable listener and the UI shows
``listen_help()`` instead. The model (about 40 MB) is downloaded the first time the
mic is used, into the app's ``models`` folder, and recognition then runs fully offline.

``listen()`` blocks until the user stops talking (a pause after speech), the stop()
event is set, or MAX_SECONDS elapse, and returns the transcript.
"""

from __future__ import annotations

import array
import importlib.util
import json
import shutil
import ssl
import sys
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

MODEL_ID = "vosk-model-small-en-us-0.15"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_ID}.zip"

SAMPLE_RATE = 16000
BLOCK = 4000            # samples per read (~0.25 s)
SPEECH_LEVEL = 500      # int16 amplitude above which a block counts as speech
SILENCE_SECONDS = 1.8   # a pause this long after speech ends the utterance
MAX_SECONDS = 30        # never record longer than this in one go


def available() -> bool:
    return (importlib.util.find_spec("vosk") is not None
            and importlib.util.find_spec("sounddevice") is not None)


def model_dir(folder: Path) -> Path:
    return Path(folder) / MODEL_ID


def _ssl_context():
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def download(folder: Path, url_for=lambda: MODEL_URL) -> Path:
    """Fetch and unzip the model if it isn't already in ``folder``. Returns the model dir."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    dest = model_dir(folder)
    if dest.is_dir() and any(dest.iterdir()):
        return dest
    url = url_for()
    part = folder / f"{MODEL_ID}.zip.part"
    ctx = _ssl_context() if url.startswith("https") else None
    with urllib.request.urlopen(url, timeout=60, context=ctx) as resp, open(part, "wb") as f:
        shutil.copyfileobj(resp, f, length=1 << 16)
    with zipfile.ZipFile(part) as z:  # the zip contains a top-level MODEL_ID folder
        z.extractall(folder)
    part.unlink()
    return dest


def _peak(data: bytes) -> int:
    """Loudest sample in an int16 block."""
    if not data:
        return 0
    return max((abs(s) for s in array.array("h", data)), default=0)


class Listener:
    name = "no mic"
    available = False

    def listen(self) -> str:  # blocking; returns the transcript
        return ""

    def stop(self) -> None:
        pass


class VoskListener(Listener):
    def __init__(self, folder: Path, on_status=None):
        self.folder = Path(folder)
        self.on_status = on_status or (lambda msg: None)
        self.name = "vosk " + "-".join(MODEL_ID.split("-")[2:-1])
        self.available = available()
        self._model = None
        self._error: Exception | None = None  # a failed download isn't retried this session
        self._lock = threading.Lock()
        self._stopped = threading.Event()

    def prepare(self) -> None:
        """Download (first time only) and load the model. Safe to call from any thread."""
        with self._lock:
            if self._model is not None:
                return
            if self._error is not None:
                raise self._error
            import vosk

            try:
                path = model_dir(self.folder)
                if not path.is_dir() or not any(path.iterdir()):
                    self.on_status(f"Downloading the {self.name} speech model "
                                   "(about 40 MB, first time only)...")
                    path = download(self.folder)
                    self.on_status("Speech model downloaded.")
                self._model = vosk.Model(str(path))
            except Exception as e:
                self._error = e
                raise

    def listen(self) -> str:
        self._stopped.clear()
        self.prepare()
        import sounddevice as sd
        import vosk

        rec = vosk.KaldiRecognizer(self._model, SAMPLE_RATE)
        heard: list[str] = []
        speech = False
        silent = 0.0
        started = time.monotonic()
        try:
            stream = sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK,
                                       dtype="int16", channels=1)
        except Exception as e:
            raise RuntimeError(f"couldn't open the microphone: {e}") from e
        with stream:
            while not self._stopped.is_set():
                data, _ = stream.read(BLOCK)
                data = bytes(data)  # sounddevice returns a cffi buffer; vosk wants bytes
                if self._stopped.is_set():
                    break
                if rec.AcceptWaveform(data):
                    heard.append(json.loads(rec.Result()).get("text", ""))
                if _peak(data) >= SPEECH_LEVEL:
                    speech, silent = True, 0.0
                elif speech:
                    silent += BLOCK / SAMPLE_RATE
                    if silent >= SILENCE_SECONDS:
                        break
                if time.monotonic() - started >= MAX_SECONDS:
                    break
        tail = json.loads(rec.FinalResult()).get("text", "")
        if tail:
            heard.append(tail)
        return " ".join(t for t in heard if t).strip()

    def stop(self) -> None:
        self._stopped.set()


def make_listener(models_dir: Path, on_status=None) -> Listener:
    if available():
        return VoskListener(models_dir, on_status)
    return Listener()


def listen_help() -> str:
    """What to install when no speech-to-text engine was found, for this platform."""
    base = ("Voice input needs the offline engine: from the repo run pip install -e \".[stt]\", "
            "or just pip install vosk sounddevice (then restart).")
    if sys.platform.startswith("linux"):
        return base + " On Linux also: sudo apt install libportaudio2."
    if sys.platform == "darwin":
        return base + " On macOS also: brew install portaudio."
    return base + " (the Windows wheels bundle PortAudio.)"
