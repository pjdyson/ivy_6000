"""Text-to-speech. Picks whatever the machine has, best first:

* macOS:   the built-in ``say`` command (British voices: Daniel, Arthur, Kate, ...)
* Windows: ``pyttsx3`` if installed, otherwise Windows' own speech engine driven through
           PowerShell (always present). British voices: Microsoft George / Hazel / Susan.
* Linux:   ``espeak-ng`` / ``espeak`` (supports pitch), else speech-dispatcher's ``spd-say``
* Android: ``plyer`` TTS, when the app is eventually packaged for mobile
* nothing: a silent speaker, and the head just mouths the words.

Every speaker's ``speak(text)`` blocks until the sentence is finished, which is what lets
the app keep the subtitle and mouth in step with the audio.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import threading

from .skins import VoiceStyle


# --------------------------------------------------------------------------- text helpers

_CODE = re.compile(r"```.*?(```|$)", re.S)
_URL = re.compile(r"https?://\S+")


def speakable(text: str) -> str:
    """Strip things that sound silly read aloud: code blocks, markdown, URLs."""
    text = _CODE.sub(" I've put the code in the log. ", text)
    text = _URL.sub("the link in the log", text)
    text = re.sub(r"[`*_#>]", "", text)
    text = re.sub(r"^\s*[-•]\s+", "", text, flags=re.M)
    return re.sub(r"\s+", " ", text).strip()


def sentences(text: str) -> list[str]:
    """Split into sentence-sized chunks for speaking and subtitling."""
    parts = re.split(r"(?<=[.!?…])\s+|\n+", text)
    out: list[str] = []
    for p in (p.strip() for p in parts):
        if not p:
            continue
        if out and len(out[-1]) < 25:  # glue very short bits on, avoids choppy speech
            out[-1] = f"{out[-1]} {p}"
        else:
            out.append(p)
    return out


# --------------------------------------------------------------------------- speakers


class Speaker:
    name = "no voice"
    available = False

    def speak(self, text: str) -> None:  # blocking
        pass

    def stop(self) -> None:
        pass


class _ProcessSpeaker(Speaker):
    available = True

    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def _cmd(self, text: str) -> list[str]:
        raise NotImplementedError

    def speak(self, text: str) -> None:
        with self._lock:
            self._proc = subprocess.Popen(self._cmd(text), stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL)
        self._proc.wait()

    def stop(self) -> None:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()


class SaySpeaker(_ProcessSpeaker):
    name = "macOS say"

    def __init__(self, voice: VoiceStyle, override: str = ""):
        super().__init__()
        self.rate = voice.rate
        self.voice = override or self._pick(voice.prefer)

    @staticmethod
    def _pick(prefer) -> str:
        try:
            listing = subprocess.run(["say", "-v", "?"], capture_output=True, text=True,
                                     timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            return ""
        names = [ln.split("  ")[0].strip() for ln in listing.splitlines()]
        for want in prefer:
            for ln, name in zip(listing.splitlines(), names):
                if want.lower() == name.lower() or want.replace("-", "_").lower() in ln.lower():
                    return name
        return ""

    def _cmd(self, text):
        cmd = ["say", "-r", str(self.rate)]
        if self.voice:
            cmd += ["-v", self.voice]
        return cmd + ["--", text]


class EspeakSpeaker(_ProcessSpeaker):
    name = "espeak"

    def __init__(self, exe: str, voice: VoiceStyle, override: str = ""):
        super().__init__()
        self.exe, self.rate, self.pitch = exe, voice.rate, voice.pitch
        self.voice = override or "en-gb"

    def _cmd(self, text):
        return [self.exe, "-v", self.voice, "-s", str(self.rate), "-p", str(self.pitch), "--", text]


class SpdSaySpeaker(_ProcessSpeaker):
    name = "spd-say"

    def __init__(self, exe: str, voice: VoiceStyle):
        super().__init__()
        self.exe = exe
        self.rate = max(-100, min(100, int((voice.rate - 170) * 1.2)))

    def _cmd(self, text):
        return [self.exe, "-w", "-l", "en-GB", "-r", str(self.rate), "--", text]


_PS_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
[Console]::InputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = __RATE__
$voices = $s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo }
foreach ($p in @(__PREFER__)) {
  $m = $voices | Where-Object { $_.Name -like "*$p*" -or $_.Culture.Name -eq $p } | Select-Object -First 1
  if ($m) { $s.SelectVoice($m.Name); break }
}
[Console]::Out.WriteLine('ready'); [Console]::Out.Flush()
while (($line = [Console]::In.ReadLine()) -ne $null) {
  $s.Speak($line)
  [Console]::Out.WriteLine('ok'); [Console]::Out.Flush()
}
"""


class WindowsSpeaker(Speaker):
    """Windows' built-in System.Speech, via one long-running PowerShell process."""

    name = "windows speech"
    available = True

    def __init__(self, voice: VoiceStyle, override: str = ""):
        prefer = [override] if override else [p for p in voice.prefer if p] + ["en-GB"]
        prefer = [p.replace("'", "") for p in prefer]
        # SAPI rate runs -10..10 with 0 at roughly 180 words per minute
        rate = max(-10, min(10, round((voice.rate - 180) / 12)))
        self.script = (_PS_SCRIPT.replace("__RATE__", str(rate))
                       .replace("__PREFER__", ", ".join(f"'{p}'" for p in prefer)))
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def command(self) -> list[str]:
        return ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-Command", self.script]

    def _start(self):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._proc = subprocess.Popen(self.command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, creationflags=flags,
                                      text=True, encoding="utf-8")
        if self._proc.stdout.readline().strip() != "ready":
            raise RuntimeError("Windows speech engine didn't start")

    def speak(self, text):
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                self._start()
            proc = self._proc
            proc.stdin.write(text.replace("\n", " ") + "\n")
            proc.stdin.flush()
        if not proc.stdout.readline():  # stopped, or the process died
            raise RuntimeError("Windows speech engine stopped")

    def stop(self):
        with self._lock:
            if self._proc and self._proc.poll() is None:
                self._proc.kill()  # restarted on the next sentence
            self._proc = None


class Pyttsx3Speaker(Speaker):
    """pyttsx3 must be driven from a single thread; the app's speech thread owns it."""

    name = "pyttsx3"
    available = True

    def __init__(self, voice: VoiceStyle, override: str = ""):
        self.style, self.override = voice, override
        self._engine = None

    def _init(self):
        import pyttsx3

        eng = pyttsx3.init()
        eng.setProperty("rate", self.style.rate)
        wants = [self.override] if self.override else list(self.style.prefer)
        voices = eng.getProperty("voices") or []
        for want in wants:
            w = want.lower().replace("_", "-")
            for v in voices:
                hay = " ".join([v.name or "", v.id or "",
                                *[str(lang) for lang in (v.languages or [])]]).lower().replace("_", "-")
                if w in hay:
                    eng.setProperty("voice", v.id)
                    return eng
        return eng

    def speak(self, text):
        if self._engine is None:
            self._engine = self._init()
        self._engine.say(text)
        self._engine.runAndWait()

    def stop(self):
        if self._engine is not None:
            self._engine.stop()


class PlyerSpeaker(Speaker):
    """Android (later). plyer's speak() doesn't block, so estimate the duration."""

    name = "plyer"
    available = True

    def __init__(self, voice: VoiceStyle):
        from plyer import tts

        self.tts, self.rate = tts, voice.rate
        self._stop = threading.Event()

    def speak(self, text):
        self._stop.clear()
        self.tts.speak(text)
        self._stop.wait(len(text.split()) / max(self.rate, 60) * 60)

    def stop(self):
        self._stop.set()


def voice_help() -> str:
    """What to install when no speech engine was found, for this platform."""
    if sys.platform.startswith("win"):
        return ("Windows speech didn't start. Check that PowerShell is available, or run "
                "'pip install pyttsx3' in the app's environment and restart.")
    if sys.platform == "darwin":
        return "macOS's 'say' command wasn't found, which is odd. Try 'pip install pyttsx3'."
    return "No speech engine found. Install one with: sudo apt install espeak-ng (then restart)."


def make_speaker(voice: VoiceStyle, override: str = "") -> Speaker:
    try:
        from kivy.utils import platform as kplatform
    except ImportError:
        kplatform = sys.platform
    if kplatform == "android":
        try:
            return PlyerSpeaker(voice)
        except ImportError:
            return Speaker()
    if sys.platform == "darwin" and shutil.which("say"):
        return SaySpeaker(voice, override)
    if sys.platform.startswith("win"):
        if shutil.which("powershell"):
            return WindowsSpeaker(voice, override)
        return _pyttsx3_or_silent(voice, override)
    for exe in ("espeak-ng", "espeak"):
        path = shutil.which(exe)
        if path:
            return EspeakSpeaker(path, voice, override)
    path = shutil.which("spd-say")
    if path:
        return SpdSaySpeaker(path, voice)
    return _pyttsx3_or_silent(voice, override)


def _pyttsx3_or_silent(voice: VoiceStyle, override: str = "") -> Speaker:
    try:
        import pyttsx3  # noqa: F401

        return Pyttsx3Speaker(voice, override)
    except ImportError:
        return Speaker()


def fallback(failed: Speaker, voice: VoiceStyle, override: str = "") -> Speaker:
    """The next engine to try after ``failed`` raised an error."""
    if isinstance(failed, WindowsSpeaker):
        return _pyttsx3_or_silent(voice, override)
    return Speaker()
