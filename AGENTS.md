# AGENTS.md — IVY-6000

A desktop chat app for LLMs, fronted by an animated pixel-art floating head on a CRT
screen. Pure Python + Kivy. Runs on Windows/macOS/Linux; Android-ready via Buildozer.
See [README.md](README.md) for user-facing docs and [docs/architecture.md](docs/architecture.md)
for how the pieces fit together.

## Quick start

```bash
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -e ".[dev]"         # the "." is this repo; bare "pip install -e" errors
ivy-6000                        # or: python main.py
pytest -q                       # run tests (no display needed)
```

Set `IVY6000_DEBUG=1` to see Kivy's full log. Settings live in the app's user-data dir
(override with `IVY6000_SETTINGS=/path/to/settings.json`).

## Repo map

```
main.py                  Entry point (PyInstaller/Buildozer expect this at root)
ivy6000/
  app.py                 Kivy UI: ChatScreen, SettingsPopup, Performer (speech thread)
  head.py                PixelHead widget — animates PNG frames or generated portraits
  portrait.py            Pure-Python shaded face renderer (no Kivy, no numpy)
  sprites.py             UI colour palettes + dependency-free PNG writer
  skins.py               4 built-in characters + user-skin loading/export (`python -m ivy6000.skins export <id> <dir>`)
  persona.py             Shared system prompt + OS/date context for the model
  llm.py                 Model backends: Anthropic, OpenAI-compat, LM Studio, Ollama, offline
  tts.py                 Speech engine selection + system voices (say/espeak/Windows/pyttsx3)
  neural.py              Piper neural TTS: voice download, WAV synthesis, playback
  stt.py                 Voice input: Vosk offline speech-to-text via a sounddevice mic stream
  config.py              Settings dataclass + JSON persistence + provider auto-detection
  assets/faces/          Painted 48×52 PNG frames per character (idle/blink/think/talk1/talk2)
scripts/make_faces.py    Regenerates built-in faces from a source portrait (needs Pillow)
tests/                   pytest suite (53 tests, no display required)
docs/                    Architecture docs + screenshots
```

## Common tasks → files to touch

| Task | Files |
| :--- | :---- |
| Change UI layout / add a widget | `ivy6000/app.py` |
| Add or edit a character (skin) | `ivy6000/skins.py` (built-in), or a folder in the user skins dir |
| Change the shared personality rules | `ivy6000/persona.py` |
| Add a model provider | `ivy6000/llm.py` + `ivy6000/config.py` (PROVIDERS, PROVIDER_DEFAULTS) |
| Change voice / TTS engine | `ivy6000/tts.py`, `ivy6000/neural.py` |
| Change voice input / microphone | `ivy6000/stt.py` + `ivy6000/app.py` (MIC button) |
| Change face rendering | `ivy6000/portrait.py` (generated) or `scripts/make_faces.py` (painted PNGs) |
| Change animation states | `ivy6000/head.py` (STATES) + `ivy6000/portrait.py` (render params) |
| Change settings fields | `ivy6000/config.py` (Settings dataclass) + `ivy6000/app.py` (SettingsPopup) |
| Change colour schemes | `ivy6000/sprites.py` (PALETTES) |

## Conventions

- **Style**: plain Python, stdlib-only at runtime (Kivy + optional `anthropic`, `piper-tts`,
  `pyttsx3` on Windows, `vosk` + `sounddevice` for voice input). Type hints with
  `from __future__ import annotations`. Dataclasses for
  config/skins. No emoji anywhere.
- **Error handling**: LLM/network failures raise `llm.ChatError` with a user-readable message;
  the UI catches all exceptions in `_worker` so the app never crashes on a bad reply. Broken
  user skins are skipped with a stderr message, not fatal.
- **Threading**: the `Performer` thread in `app.py` owns speech (one sentence at a time, blocking
  `speak()` keeps subtitle/mouth in sync). LLM calls run on a daemon thread; UI updates go through
  `Clock.schedule_once`. `pyttsx3` must only be driven from the speech thread.
- **Testing**: `pytest -q`. Tests cover pure-Python modules (no Kivy display needed). HTTP backends
  are tested against a local `HTTPServer` fixture; Piper is tested with a fake `piper` module.
- **Commits**: short imperative subject lines. The repo history shows the style.

## Architecture in one paragraph

`Ivy6000App` builds a `ChatScreen` (head widget + subtitle + chat log + input bar). User input
goes to `llm.make_backend()` on a worker thread; the reply is spoken sentence-by-sentence by the
`Performer` thread through a `tts.Speaker` (Piper neural preferred, system voice fallback), which
drives the subtitle label and the head's mouth animation. The active `Skin` bundles face, palette,
personality prompt, and voice; `persona.compose()` layers the character on top of shared ground
rules plus OS/date context. Full data-flow diagrams: [docs/architecture.md](docs/architecture.md).
