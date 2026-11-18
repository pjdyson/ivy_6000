# Architecture

How IVY-6000 fits together. For the file-by-file map see [AGENTS.md](../AGENTS.md); for
user-facing docs see [README.md](../README.md).

## Module dependency graph

```
main.py ──► ivy6000.app ──┬──► ivy6000.head ──────► ivy6000.portrait
                          │         │                  (generated faces)
                          │         └── PNG frames in ivy6000/assets/faces/
                          ├──► ivy6000.config ──► settings.json
                          ├──► ivy6000.skins ───┬──► ivy6000.persona (system prompt)
                          │                     ├──► ivy6000.portrait (FaceStyle)
                          │                     ├──► ivy6000.sprites (palettes)
                          │                     └── user skins dir (skin.json + PNGs)
                          ├──► ivy6000.llm ─────┬──► anthropic SDK (optional, desktop)
                          │                     └── stdlib urllib (Android / fallback)
                          ├──► ivy6000.tts ─────┬──► ivy6000.neural ──► piper-tts (optional)
                          │                     └── system voices (say / espeak / SAPI / pyttsx3)
                          ├──► ivy6000.stt ────────► vosk + sounddevice (optional, MIC button)
                          └──► ivy6000.sprites (PNG writer, used by skins export)
```

Runtime dependencies are Kivy + stdlib only. `anthropic`, `piper-tts`, `certifi`,
`pyttsx3` (Windows), and `vosk` + `sounddevice` (voice input) are optional and imported
lazily.

## Chat flow

```
User types ──► ChatScreen.send()
                 │  append to history, set head.state = "thinking"
                 ▼
           worker thread: llm.make_backend(settings).reply(system_prompt, history)
                 │  system_prompt = skin.system_prompt(persona.context())
                 │  persona.context() = OS name + today's date
                 ▼
           ChatScreen._on_reply()  (via Clock.schedule_once)
                 │  append reply to history, say(reply)
                 ▼
           Performer.perform(text)  (own thread, sentence queue)
                 │  tts.sentences(tts.speakable(text))  — strips code/URLs/markdown
                 ▼
           for each sentence: speaker.speak(line)   (blocking)
                 │  Piper neural → synthesize WAV → play audio
                 │  fallback: system voice (say / espeak-ng / Windows SAPI)
                 ▼
           Clock-scheduled callbacks update subtitle + head.state = "talking"
```

## Skin loading

```
Ivy6000App.reload_skins()
  ├── skins.BUILTIN          (4 characters defined in skins.py)
  │     └── if assets/faces/<id>/idle.png exists → skin.frames = PNG paths
  │         else → skin.face (FaceStyle) drives portrait.render()
  └── skins.load_user_skins(user_skins_dir)
        └── each subfolder with skin.json → Skin (frames optional)
              broken folders are skipped with a stderr message
```

`python -m ivy6000.skins export <id> <dir>` writes a built-in skin as an editable folder
(skin.json + 5 PNG frames) to start a custom one.

## Voice selection

```
tts.make_speaker(skin.voice, settings.voice_name, settings.voice_engine, voices_dir)
  ├── engine auto/neural + piper-tts installed + audio player found
  │     └── neural.PiperSpeaker(voice.piper, voice.piper_speaker, voice.piper_speed)
  │           first speak() downloads the ~60 MB voice into voices_dir/
  └── otherwise system_speaker()
        ├── macOS    → say (prefers British voices)
        ├── Windows  → PowerShell System.Speech (pyttsx3 backup)
        ├── Linux    → espeak-ng / espeak / spd-say
        └── Android  → plyer TTS
```

If a speaker fails mid-sentence, `tts.fallback()` picks the next engine and the UI logs it.
If nothing is available, the head mouths along silently with timed subtitles.

## Voice input

```
MIC button (toggle) ──► ChatScreen._start_listening()
                           │  stt.make_listener(models_dir)  — Vosk if vosk+sounddevice
                           │  are installed, else an unavailable listener + listen_help()
                           ▼
                     listener thread: VoskListener.listen()  (blocking)
                           │  sounddevice RawInputStream (16 kHz mono int16)
                           │  → vosk KaldiRecognizer, until a pause after speech,
                           │    stop(), or MAX_SECONDS
                           ▼
                     ChatScreen._on_transcript()  (via Clock.schedule_once)
                           │  transcript → entry → send()  (same path as typing)
                           ▼
                     head.state = "listening" while recording (brow raised, like thinking)
```

The ~40 MB Vosk model downloads on first use into the app's `models` folder; recognition
is then fully offline. If the engine isn't installed, the MIC button logs install hints
instead of recording.

## Settings & persistence

- `Settings` dataclass in `config.py`; saved as JSON via `config.save()`.
- Location: `IVY6000_SETTINGS` env var, else `<user_data_dir>/settings.json`.
- First launch (`default_settings()`): Anthropic if `ANTHROPIC_API_KEY` set → OpenAI if
  `OPENAI_API_KEY` set → LM Studio/Ollama if a local server responds → offline.
- API keys: settings field first, then environment variable (`resolved_api_key()`).

## Face rendering (portrait.py)

Pure Python, no numpy/Kivy. The head is a height field (skull + jaw + brow, eye sockets,
cheekbones, nose, lips, chin) lit like a portrait photo: warm key light upper-left, cool
fill, subsurface scattering in shadows, rim light in the screen colour. Rendered at 3×
then averaged into 40×48 chunky blocks with per-block variation, tinted, and posterised.
`render(style, blink, mouth, brow, look)` returns RGBA bytes; `frames(style)` produces the
five named frames. `head.py` maps animation state → frame and draws it with CRT scanlines.

## Testing

`pytest -q` — 53 tests, no display needed. HTTP backends use a local `HTTPServer` fixture;
Piper uses a fake `piper` module injected via `monkeypatch`; Vosk/sounddevice use fake
modules the same way; portrait tests check size, colour, determinism, and that all
style/state combinations render.
