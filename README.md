# IVY-6000

A small desktop chat app for LLMs, fronted by a shaded, full-colour pixel-art head
floating on a CRT screen.
It gives properly useful, informative answers with a dry undercurrent of British sitcom
humour, and reads them aloud while the head blinks, raises an eyebrow as it thinks, and
mouths along with a subtitle.

![The four built-in characters](docs/skins.png)

Pure Python + [Kivy](https://kivy.org): runs on Windows, macOS and Linux, and the same code
can be packaged for Android later.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[claude]"
ivy-6000                           # or: python main.py
```

On first launch it picks a brain automatically: Claude if `ANTHROPIC_API_KEY` is set, OpenAI
if `OPENAI_API_KEY` is set, otherwise LM Studio or Ollama if one is running locally, otherwise
**offline** mode (canned in-character replies). Press **SET** for settings and
**VOX** to mute or unmute the voice.

## Characters (skins)

A skin bundles a face, colour scheme, personality and voice. All of them share the same
ground rules (in [`ivy6000/persona.py`](ivy6000/persona.py)): short answers (one to three
sentences), how-tos one small step at a time with an offer to continue, accurate first,
with dry British wit as the undercurrent, and no act at all for anything serious. Ask for
"the full explanation" when you want more. The model is also told your operating system
and today's date, so practical answers fit your machine.

| Skin | Look | Character | Voice |
| :--- | :--- | :-------- | :---- |
| **DOT** | green-tinted screen | ship's computer: bone dry, quietly sardonic, self-declared genius with lapses | medium pace |
| **HUGO** | cool grey screen; bald, shiny scalp, grey side tufts, heavy lids, lined forehead | adrift alone in deep space for ages: slow, lugubrious, unflappable, announces the obvious with gravity | slow, low |
| **MR PEMBERTON** | warm amber screen; ruddy, walrus moustache | concierge of a shabby seaside hotel: excruciatingly polite, barely contained exasperation | brisk, higher |
| **DESMOND** | cyan screen; glasses, stubble | basement IT support: weary, pedantic, assumes user error, always fixes it properly | brisk |

The built-in faces are painted pixel-art portraits (48×52) in
[`ivy6000/assets/faces/`](ivy6000/assets/faces/), each a variation on one source portrait:
different hood colours, skin tones, lighting and mirroring, plus painted-in stubble, a
moustache or glasses, and frames for blinking, talking and thinking. They're made by
[`scripts/make_faces.py`](scripts/make_faces.py) (`python scripts/make_faces.py portrait.png`,
needs Pillow), so a different source portrait gives a whole new cast.

Custom skins without their own PNGs get a generated face from
[`ivy6000/portrait.py`](ivy6000/portrait.py) instead: a lit 3D-ish head rendered in the same
dark, painterly style.

### Make your own

Skins are folders in the app's `skins` directory (the path is shown in **SET**). The easiest
start is to export a built-in one and edit it:

```bash
python -m ivy6000.skins export hugo ~/my-skin
```

That writes `skin.json` plus five PNG frames (`idle`, `blink`, `think`, `talk1`, `talk2`).
Repaint the PNGs in any pixel-art editor (Aseprite, Piskel, LibreSprite, even Paint), edit
the `character`, `greeting` and `voice` in `skin.json`, and copy the folder into the skins
directory. It appears under *Character* in settings.

`skin.json` fields:

| Field | Meaning |
| :---- | :------ |
| `name`, `tagline`, `greeting` | shown and spoken in the app |
| `character` | the personality, added to the shared ground rules |
| `replace_base_prompt` | `true` to use `character` as the whole system prompt instead |
| `frames` | PNG files per frame (only `idle` is required); omit to use a generated face |
| `face` | generated face: `hair` (`full`/`curly`/`wisps`/`tufts`/`bald`), `heavy_lids`, `moustache`, `glasses`, `wrinkles`, `wide`, `stubble`, `smile` (0-1); colours `skin`, `hair_color`, `eye_color`, `lip_color` as `[r, g, b]` (0-1); `tint` (screen colour) and `tint_amount` (0 = natural colour, 1 = monochrome); `levels` (colour steps; lower is flatter) |
| `palette` | UI colours: `phosphor`, `amber`, `mono`, `cyan`, or a map of colours |
| `voice` | `rate` (words/min), `pitch` (0-99, Linux only), `prefer` (voice names to try, in order) |
| `offline_lines` | what it says when no model is connected |

## Voice

Each character has its own natural-sounding British voice, made with
[Piper](https://github.com/OHF-Voice/piper1-gpl) neural text-to-speech. It runs entirely on your
machine, so it's private, free and works offline once a voice is downloaded.

| Character | Piper voice | Delivery |
| :-------- | :---------- | :------- |
| DOT | `en_GB-northern_english_male-medium` | dry, slightly unhurried |
| HUGO | `en_GB-semaine-medium`, speaker `obadiah` (the gloomy one) | slow |
| MR PEMBERTON | `en_GB-alan-medium` | a touch brisk |
| DESMOND | `en_GB-semaine-medium`, speaker `spike` (the grumpy one) | normal |

Each voice (about 60 MB) downloads the first time that character speaks, into the app's
`voices` folder. To try another, type a Piper voice in *Voice override* in settings, e.g.
`en_GB-semaine-medium:poppy`, `en_GB-cori-high` or `en_GB-vctk-medium:p231`. Browse them all at
https://rhasspy.github.io/piper-samples/. A skin can set its own with `piper`,
`piper_speaker` and `piper_speed` (above 1 is slower) in its `voice` section.

Audio is played with `winsound` on Windows, `afplay` on macOS, and `pw-play`, `paplay` or
`aplay` on Linux (one of these is on almost every desktop).

If Piper isn't available, or *Voice engine* is set to *System voice*, it falls back to the
computer's own robotic-but-dependable voice:

- **macOS**: `say` (prefers British voices: Daniel, Arthur).
- **Windows**: Windows' own speech engine via PowerShell, with `pyttsx3` as a backup.
- **Linux**: `espeak-ng` (`sudo apt install espeak-ng`), else the speech dispatcher (`spd-say`).

The status under the top bar shows which voice is in use. If it says **no voice**, the app
also writes what to install into the chat log.

## Model providers

| Provider  | What it talks to | Defaults |
| :-------- | :--------------- | :------- |
| `anthropic` | Claude (Messages API) via the official `anthropic` SDK | model `claude-opus-5-5`, effort `low`, key from settings or `ANTHROPIC_API_KEY` |
| `openai`  | Any OpenAI-compatible `/chat/completions` endpoint: OpenAI, LM Studio, llama.cpp, vLLM, a LiteLLM proxy or a corporate gateway | base URL `https://api.openai.com/v1`, key from settings or `OPENAI_API_KEY` |
| `lmstudio` | A local [LM Studio](https://lmstudio.ai) server | base URL `http://localhost:1234/v1`, model: whichever is loaded |
| `ollama`  | A local [Ollama](https://ollama.com) server | base URL `http://localhost:11434/v1`, model: first one installed |
| `offline` | Nothing | — |

- **LM Studio**: download a model, then in the *Developer* tab press *Start Server* (or run
  `lms server start`). Choose `lmstudio` in settings; leave *Model* blank to use whichever
  model is loaded, or press **List** to pick one. Reasoning models that "think out loud"
  (Qwen3, DeepSeek-R1, ...) have their `<think>` sections stripped before IVY speaks. Small
  local models follow the persona less faithfully than Claude; 7B+ instruct models do best.
  To use LM Studio on another machine on your network, enable *Serve on Local Network* and set
  the base URL to that machine, e.g. `http://192.168.1.20:1234/v1`.
- **Corporate Claude access**: set *Base URL* to your company's Anthropic-compatible gateway.
  If it rejects unknown fields, switch off *Refusal fallbacks* (a server-side retry on a
  fallback model when Claude declines a request) and clear *Effort*.
- **Effort** (`low`/`medium`/`high`) trades reply speed for depth of thinking; `low` suits chat,
  `medium` gives more thorough answers to harder questions.

Settings live in `settings.json` in the app's user-data folder (set `IVY6000_SETTINGS` to use
another path). API keys typed into settings are stored there in plain text; prefer environment
variables on a shared machine.

## Package it for the desktop

```bash
pip install pyinstaller
pyinstaller --noconfirm --name IVY-6000 --windowed main.py
# -> dist/IVY-6000/   (on headless Linux, prefix with: xvfb-run -a)
```

Or run the **Desktop build** GitHub Action (Actions → *Desktop build* → *Run workflow*), which
builds Windows, macOS and Linux versions and attaches them as artifacts.

## Mobile, later

The code is already Android-ready: Kivy runs there, the Claude call falls back to plain HTTPS
(the Anthropic SDK's compiled dependencies don't build for Android), and speech uses Android's
own TTS through `plyer`. When you want it, `buildozer.spec` and the manual **Android build**
GitHub Action produce an APK; locally:

```bash
pip install buildozer "cython<3.1"
buildozer android debug            # Linux/WSL2/macOS; first run downloads the SDK/NDK
```

Add `plyer` to `requirements` in `buildozer.spec` for voice on Android.

## Troubleshooting

- The console is quiet by default; Kivy's own log goes to `~/.kivy/logs/`. Run with
  `IVY6000_DEBUG=1 ivy-6000` to see everything.
- On Linux, `sudo apt install xclip` gives Kivy full copy/paste support.

## Develop

```bash
pip install -e ".[dev]"
pytest -q
```

```
main.py              entry point
ivy6000/app.py       Kivy UI, settings popup, the speech/subtitle performer
ivy6000/head.py      animated PixelHead widget (generated faces or PNG frames)
ivy6000/portrait.py  shaded colour face renderer (no Kivy)
ivy6000/sprites.py   UI colour schemes, PNG writer
ivy6000/skins.py     built-in characters, user-skin loading, `export` command
ivy6000/persona.py   shared ground rules for every character
ivy6000/tts.py       speech engine selection; system voices (say / espeak / Windows / plyer)
ivy6000/neural.py    Piper neural voices: download, synthesis, playback
ivy6000/llm.py       model backends (stdlib only; anthropic SDK optional)
ivy6000/config.py    settings and JSON persistence
```
