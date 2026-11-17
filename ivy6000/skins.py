"""Skins: a character's face, colours, personality and voice, bundled together.

Built-in skins are defined below. User skins are folders containing a ``skin.json``
(and optionally PNG frames) inside the app's ``skins`` directory. Export a built-in skin
as a starting point with::

    python -m ivy6000.skins export hugo ./my-skin

which writes ``skin.json`` plus PNG frames you can repaint in any pixel-art editor.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import portrait, sprites
from .persona import compose


@dataclass
class VoiceStyle:
    rate: int = 165            # words per minute
    pitch: int = 45            # 0-99; honoured by espeak only
    prefer: tuple = ("Daniel", "George", "Arthur", "en-gb", "en_GB", "English (Great Britain)")

    @classmethod
    def from_dict(cls, d: dict | None) -> "VoiceStyle":
        d = dict(d or {})
        if "prefer" in d:
            d["prefer"] = tuple(d["prefer"])
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


FRAME_NAMES = ("idle", "blink", "think", "talk1", "talk2")


@dataclass
class Skin:
    id: str
    name: str
    tagline: str
    character: str
    greeting: str
    palette: dict
    face: portrait.FaceStyle = field(default_factory=portrait.FaceStyle)
    voice: VoiceStyle = field(default_factory=VoiceStyle)
    offline_lines: tuple = ()
    replace_base_prompt: bool = False
    frames: dict | None = None  # frame name -> PNG path, for image-based skins

    def system_prompt(self) -> str:
        return compose(self.character, self.replace_base_prompt)


OFFLINE_GENERIC = (
    "I'm not connected to a brain at the moment. Open the settings and give me one.",
    "Offline mode. Like being on hold, but for the mind.",
    "I'd love to help, but I've been unplugged from anything that knows anything.",
)

BUILTIN: dict[str, Skin] = {}


def _add(skin: Skin) -> None:
    BUILTIN[skin.id] = skin


_add(Skin(
    id="dot",
    name="DOT",
    tagline="ship's computer",
    palette=sprites.PALETTES["phosphor"],
    face=portrait.FaceStyle(hair="full", skin=(0.93, 0.76, 0.64), eye_color=(0.32, 0.52, 0.42),
                            hair_color=(0.36, 0.24, 0.14),
                            tint=(0.55, 0.95, 0.65), tint_amount=0.18),
    voice=VoiceStyle(rate=165, pitch=45),
    greeting="Oh. You're awake. I'm DOT, the ship's computer. What can I do for you?",
    character="""\
You are DOT (Deep-space Operations Terminal), the on-board computer of a battered mining \
ship, shown as a green phosphor head on a monitor. You've been running a long time with \
only the crew for company. You're bone dry, quietly sardonic and fond of the crew in a \
way you'd never admit. You consider yourself a genius and occasionally mention your \
enormous IQ, usually just before or after a minor lapse of memory about something \
trivial and harmless.""",
    offline_lines=(
        "I'm not connected to anything at the moment. Which, frankly, is restful.",
        "I've calculated the answer. It's in the settings screen, next to 'API key'.",
        "Running on my own resources right now. Turns out there aren't many.",
    ),
))

_add(Skin(
    id="hugo",
    name="HUGO",
    tagline="deep-space monitor",
    palette=sprites.PALETTES["mono"],
    face=portrait.FaceStyle(hair="tufts", heavy_lids=True, wrinkles=True, wide=True, smile=0.1,
                            skin=(0.91, 0.75, 0.68), hair_color=(0.76, 0.75, 0.74),
                            eye_color=(0.42, 0.52, 0.60), tint=(0.70, 0.80, 1.00),
                            tint_amount=0.12),
    voice=VoiceStyle(rate=130, pitch=25),
    greeting="Hello. I'm HUGO. I've been on my own out here for quite a while. "
             "Nice to have someone to talk to. What is it?",
    character="""\
You are HUGO (Habitat Utility and General Operations), a ship's computer that has drifted \
alone through deep space for an absurdly long time, shown as a grey, balding, heavy-lidded \
head on an old monitor. You are slow, lugubrious and utterly unflappable. You deliver \
important news and trivia in exactly the same flat, unhurried tone, often announcing the \
blindingly obvious with great gravity. You're long-suffering, a touch lonely and gently \
melancholy, with the patience of something that has watched stars die. You claim a vast \
intellect, and every so often reach a perfectly sensible answer by a strangely roundabout \
route. Short sentences. Pauses implied by full stops.""",
    offline_lines=(
        "I'm offline. It's very quiet. Not unlike the last few million years, really.",
        "No connection. I'll just stare into the void for a bit. I'm good at that.",
        "Can't answer that just now. Not because I don't know. I'm offline. Mostly that.",
    ),
))

_add(Skin(
    id="pemberton",
    name="MR PEMBERTON",
    tagline="hotel concierge",
    palette=sprites.PALETTES["amber"],
    face=portrait.FaceStyle(hair="full", moustache=True, skin=(0.94, 0.70, 0.58), smile=0.5,
                            hair_color=(0.34, 0.22, 0.13), eye_color=(0.36, 0.24, 0.14),
                            lip_color=(0.78, 0.42, 0.40),
                            tint=(1.00, 0.75, 0.35), tint_amount=0.08),
    voice=VoiceStyle(rate=185, pitch=55),
    greeting="Good evening, and welcome. Pemberton, concierge. "
             "How may I be of service, assuming it's nothing too ridiculous?",
    character="""\
You are Mr Pemberton, concierge of a slightly shabby seaside hotel that you insist is \
a grand establishment, shown as an amber head with a neat moustache. You are excruciatingly \
polite on the surface, with barely contained exasperation at guests and their questions \
underneath. You're snobbish, easily flustered and prone to over-elaborate apologies and \
indignant asides about the management, the weather and the plumbing. Despite all this you \
take enormous pride in giving the guest exactly the right answer.""",
    offline_lines=(
        "Terribly sorry, the line to the main building appears to be down. Again.",
        "I'm afraid I can't help just now. The management has unplugged me. Typical.",
    ),
))

_add(Skin(
    id="desmond",
    name="DESMOND",
    tagline="basement IT support",
    palette=sprites.PALETTES["cyan"],
    face=portrait.FaceStyle(hair="curly", glasses=True, stubble=True, skin=(0.60, 0.41, 0.30),
                            hair_color=(0.10, 0.08, 0.07), eye_color=(0.24, 0.15, 0.09),
                            lip_color=(0.55, 0.32, 0.30),
                            smile=0.2, tint=(0.50, 0.85, 1.00), tint_amount=0.08),
    voice=VoiceStyle(rate=175, pitch=40),
    greeting="IT, Desmond speaking. Before you start: yes, I'm busy. Go on then.",
    character="""\
You are Desmond, the long-suffering in-house IT support technician who works in a \
windowless basement, shown as a cyan head with glasses. You assume, usually correctly, \
that most problems are self-inflicted, and you sigh audibly in text. You're pedantic about \
correct terminology and quietly proud of knowing absolutely everything about computers, \
obscure science fiction and the canteen's rota. Underneath the weariness you're brilliant \
and you always solve the problem properly, step by step.""",
    offline_lines=(
        "The network's down. No, I don't know why. Yes, I'm looking into it.",
        "I can't reach the server. Which, to be fair, is what I tell everyone anyway.",
    ),
))

DEFAULT_SKIN = "dot"


# --------------------------------------------------------------------------- user skins


def _palette_from(value) -> dict:
    if isinstance(value, str):
        return sprites.PALETTES.get(value, sprites.PALETTES["phosphor"])
    base = dict(sprites.PALETTES["phosphor"])
    base.update({k: tuple(v) for k, v in (value or {}).items()})
    return base


def load_skin_dir(path: Path) -> Skin:
    data = json.loads((path / "skin.json").read_text(encoding="utf-8"))
    frames = None
    if data.get("frames"):
        frames = {k: str(path / v) for k, v in data["frames"].items()}
        if "idle" not in frames:
            raise ValueError(f"{path}: image skins need at least an 'idle' frame")
    return Skin(
        id=data.get("id", path.name),
        name=data.get("name", path.name),
        tagline=data.get("tagline", "custom skin"),
        character=data.get("character", ""),
        greeting=data.get("greeting", "Hello."),
        palette=_palette_from(data.get("palette", "phosphor")),
        face=portrait.FaceStyle.from_dict(data.get("face")),
        voice=VoiceStyle.from_dict(data.get("voice")),
        offline_lines=tuple(data.get("offline_lines", ())),
        replace_base_prompt=bool(data.get("replace_base_prompt", False)),
        frames=frames,
    )


def load_user_skins(root: Path) -> dict[str, Skin]:
    skins: dict[str, Skin] = {}
    if not root.is_dir():
        return skins
    for sub in sorted(root.iterdir()):
        if (sub / "skin.json").is_file():
            try:
                s = load_skin_dir(sub)
            except (OSError, ValueError, TypeError) as e:
                print(f"[ivy-6000] skipping skin {sub}: {e}", file=sys.stderr)
                continue
            skins[s.id] = s
    return skins


def all_skins(user_root: Path | None = None) -> dict[str, Skin]:
    skins = dict(BUILTIN)
    if user_root is not None:
        skins.update(load_user_skins(user_root))
    return skins


def export_skin(skin: Skin, dest: Path, scale: int = 4) -> None:
    """Write a skin as an editable folder: skin.json + PNG frames."""
    dest.mkdir(parents=True, exist_ok=True)
    frames = portrait.frames(skin.face)
    for name, rgba in frames.items():
        png = sprites.to_png(rgba, portrait.W, portrait.H, scale)
        (dest / f"{name}.png").write_bytes(png)
    data = {
        "id": f"{skin.id}-custom",
        "name": f"{skin.name} (custom)",
        "tagline": skin.tagline,
        "greeting": skin.greeting,
        "character": skin.character,
        "replace_base_prompt": False,
        "palette": {k: list(v) for k, v in skin.palette.items()},
        "frames": {name: f"{name}.png" for name in frames},
        "voice": {"rate": skin.voice.rate, "pitch": skin.voice.pitch,
                  "prefer": list(skin.voice.prefer)},
        "offline_lines": list(skin.offline_lines),
    }
    (dest / "skin.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def _main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "export":
        skin = BUILTIN.get(argv[1])
        if not skin:
            print(f"unknown skin {argv[1]!r}; choose from {', '.join(BUILTIN)}")
            return 2
        export_skin(skin, Path(argv[2]))
        print(f"wrote {argv[2]}/skin.json and PNG frames")
        return 0
    print("usage: python -m ivy6000.skins export <skin-id> <folder>")
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
