"""Natural-sounding offline speech with Piper neural voices.

Voices come from https://huggingface.co/rhasspy/piper-voices and are downloaded the first
time a character speaks (about 60 MB each), into the app's ``voices`` folder. Synthesis
runs locally; the resulting audio is played with whatever the system has:
``winsound`` on Windows, ``afplay`` on macOS, PipeWire/PulseAudio/ALSA players on Linux.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import urllib.request
import wave
from pathlib import Path

URL = ("https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
       "{family}/{code}/{name}/{quality}/{voice_id}{ext}?download=true")


def available() -> bool:
    return importlib.util.find_spec("piper") is not None


def voice_url(voice_id: str, ext: str) -> str:
    """'en_GB-semaine-medium' -> the Hugging Face URL of its .onnx or .onnx.json file."""
    code, rest = voice_id.split("-", 1)
    name, quality = rest.rsplit("-", 1)
    return URL.format(family=code.split("_")[0], code=code, name=name, quality=quality,
                      voice_id=voice_id, ext=ext)


def voice_files(voice_id: str, folder: Path) -> tuple[Path, Path]:
    return folder / f"{voice_id}.onnx", folder / f"{voice_id}.onnx.json"


def _ssl_context():
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def download(voice_id: str, folder: Path, url_for=voice_url) -> tuple[Path, Path]:
    """Fetch a voice if it isn't already in ``folder``. Returns (model, config) paths."""
    folder.mkdir(parents=True, exist_ok=True)
    model, config = voice_files(voice_id, folder)
    for path, ext in ((config, ".onnx.json"), (model, ".onnx")):
        if path.exists() and path.stat().st_size > 0:
            continue
        url = url_for(voice_id, ext)
        part = path.with_suffix(path.suffix + ".part")
        ctx = _ssl_context() if url.startswith("https") else None
        with urllib.request.urlopen(url, timeout=60, context=ctx) as resp, open(part, "wb") as f:
            shutil.copyfileobj(resp, f, length=1 << 16)
        part.replace(path)
    return model, config


def speaker_id(config: Path, speaker: str) -> int | None:
    """Look up a named speaker in a multi-speaker voice; None for single-speaker voices."""
    data = json.loads(config.read_text(encoding="utf-8"))
    if data.get("num_speakers", 1) <= 1:
        return None
    ids = data.get("speaker_id_map", {})
    if speaker in ids:
        return ids[speaker]
    if speaker.isdigit():
        return int(speaker)
    return 0


# --------------------------------------------------------------------------- playback


class Player:
    """Plays a WAV file, blocking until it ends; ``stop`` cuts it short."""

    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._done = threading.Event()
        self.command = self._find_command()

    @staticmethod
    def _find_command() -> list[str] | None:
        if sys.platform.startswith("win"):
            return None  # winsound
        if sys.platform == "darwin":
            return ["afplay"]
        for exe, args in (("pw-play", []), ("paplay", []), ("aplay", ["-q"]), ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet"])):
            if shutil.which(exe):
                return [exe, *args]
        return []

    @property
    def available(self) -> bool:
        return self.command is None or bool(self.command)

    def play(self, path: str, seconds: float) -> None:
        self._done.clear()
        if self.command is None:
            import winsound

            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            self._done.wait(seconds + 0.1)
            return
        if not self.command:
            raise RuntimeError("no audio player found (install pipewire, pulseaudio-utils or alsa-utils)")
        self._proc = subprocess.Popen([*self.command, path], stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
        self._proc.wait()

    def stop(self) -> None:
        self._done.set()
        if self.command is None:
            try:
                import winsound

                winsound.PlaySound(None, 0)
            except Exception:
                pass
        elif self._proc and self._proc.poll() is None:
            self._proc.terminate()


# --------------------------------------------------------------------------- speaker


class PiperSpeaker:
    available = True

    def __init__(self, voice_id: str, speaker: str, speed: float, folder: Path, on_status=None):
        self.voice_id, self.speaker, self.speed = voice_id, speaker, speed
        self.folder, self.on_status = folder, on_status or (lambda msg: None)
        self.name = f"piper {voice_id.split('-')[1]}" + (f"/{speaker}" if speaker else "")
        self._voice = None
        self._config = None
        self._error: Exception | None = None  # a failed download isn't retried this session
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        self.player = Player()
        if not self.player.available:
            self.available = False

    def prepare(self) -> None:
        """Download (first time only) and load the model. Safe to call from any thread."""
        with self._lock:
            if self._voice is not None:
                return
            if self._error is not None:
                raise self._error
            from piper import PiperVoice, SynthesisConfig

            model, config = voice_files(self.voice_id, self.folder)
            try:
                if not model.exists():
                    self.on_status(f"Downloading the {self.name} voice (about 60 MB, first time only)...")
                    model, config = download(self.voice_id, self.folder)
                    self.on_status("Voice downloaded.")
                self._voice = PiperVoice.load(model, config_path=config)
            except Exception as e:
                self._error = e
                raise
            self._config = SynthesisConfig(speaker_id=speaker_id(config, self.speaker),
                                           length_scale=self.speed)

    def speak(self, text: str) -> None:
        self._stopped.clear()
        self.prepare()
        if self._stopped.is_set():
            return
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="ivy6000-")
        os.close(fd)
        try:
            with wave.open(path, "wb") as wav:
                self._voice.synthesize_wav(text, wav, syn_config=self._config)
            with wave.open(path, "rb") as wav:
                seconds = wav.getnframes() / float(wav.getframerate() or 1)
            if not self._stopped.is_set():
                self.player.play(path, seconds)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def stop(self) -> None:
        self._stopped.set()
        self.player.stop()
