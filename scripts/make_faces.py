"""Build the built-in character faces from a single pixel-art portrait.

    python scripts/make_faces.py path/to/portrait.png

The portrait is resampled to a 64x64 grid, then each character is made as a variation of
it (hood colour, skin tone, lighting, mirroring, and painted additions such as a moustache,
glasses or stubble), with animation frames painted in: blink, two talking mouths and a
thinking glance with a raised eyebrow. The shoulders and background fade out so the head
floats. Output: ivy6000/assets/faces/<character>/{idle,blink,think,talk1,talk2}.png

Needs Pillow (a development dependency only; the app itself just loads the PNGs).
The feature coordinates below are for the original source portrait.
"""

from __future__ import annotations

import colorsys
import random
import sys
from pathlib import Path

from PIL import Image

GRID = 64
CROP = (8, 0, 56, 52)          # x0, y0, x1, y1 of the head within the grid -> 48x52 output
HEAD_CENTRE, HEAD_RADII = (32.0, 26.0), (21.0, 26.0)
FADE_FROM_Y = 43               # shoulders fade out below here

LEFT_EYE = range(26, 30)       # x columns
RIGHT_EYE = range(34, 39)
EYE_ROWS = (23, 24, 25)
RIGHT_BROW_X = range(35, 42)   # lit brow band above the right eye (viewer's right)
MOUTH_X = range(31, 37)
MOUTH_ROW = 37                 # the dark line between the lips
LIP_ROW = 38                   # lit lower lip

OUT = Path(__file__).resolve().parent.parent / "ivy6000" / "assets" / "faces"


# --------------------------------------------------------------------------- helpers


def lum(c):
    return 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]


def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def scale(c, k):
    return tuple(max(0, min(255, int(round(v * k)))) for v in c)


def is_hood(c):
    r, g, b = c
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return (0.40 < h < 0.75 and s > 0.12) or (lum(c) < 30 and b > r + 2)


def is_skin(c, x, y):
    r, g, b = c
    inside = ((x - 33) / 13) ** 2 + ((y - 31) / 16) ** 2 < 1
    return inside and r > b + 6 and not is_hood(c)


def recolour(c, hue=None, sat=None, val=1.0):
    h, s, v = colorsys.rgb_to_hsv(*(ch / 255 for ch in c))
    if hue is not None:
        h = hue
    if sat is not None:
        s = s * sat
    v = min(1.0, v * val)
    return tuple(int(round(ch * 255)) for ch in colorsys.hsv_to_rgb(h, min(1.0, s), v))


# --------------------------------------------------------------------------- animation


def animate(px, frame):
    """Paint eyes and mouth for a frame, in place. px[y][x] = (r, g, b)."""
    glint = (74, 56, 44)
    if frame == "blink":
        for x in list(LEFT_EYE) + list(RIGHT_EYE):
            lid = scale(px[22][x], 0.85)
            for y in (23, 24):
                px[y][x] = lid
            px[25][x] = scale(px[25][x], 0.7)  # lash line
    else:
        shift = 1 if frame == "think" else 0
        px[24][28 + shift] = glint
        px[24][36 + shift] = glint
    if frame == "think":  # raise the right eyebrow by a row
        for x in RIGHT_BROW_X:
            for y in (18, 19, 20):
                px[y][x] = px[y + 1][x]
            px[21][x] = mix(px[21][x], px[22][x], 0.7)
    if frame in ("talk1", "talk2"):
        dark, teeth = (22, 10, 8), (84, 70, 58)
        lip = [px[LIP_ROW][x] for x in MOUTH_X]
        for x in MOUTH_X:
            px[MOUTH_ROW][x] = dark
        if frame == "talk2":
            for i, x in enumerate(MOUTH_X):
                px[LIP_ROW][x] = dark
                px[LIP_ROW + 1][x] = lip[i]          # lower lip drops a row
            for x in (32, 33, 34):
                px[MOUTH_ROW][x] = teeth


# --------------------------------------------------------------------------- additions


def moustache(px, rng):
    base, lit = (34, 19, 11), (72, 42, 22)
    rows = {35: range(29, 39), 36: range(28, 40), 37: (28, 29, 38, 39), 38: (28, 39)}
    for y, xs in rows.items():
        for x in xs:
            c = lit if (x >= 33 and y == 35) else base
            px[y][x] = scale(c, 0.85 + 0.3 * rng.random())


def glasses(px):
    frame, shine, lens = (14, 14, 18), (120, 110, 100), (70, 92, 118)
    for x0, x1 in ((25, 30), (33, 39)):
        for x in range(x0, x1 + 1):
            px[22][x] = frame
            px[26][x] = frame
        for y in range(22, 27):
            px[y][x0] = frame
            px[y][x1] = frame
        px[23][x1 - 1] = mix(px[23][x1 - 1], lens, 0.6)  # reflection on the lens
    for x in (31, 32):
        px[23][x] = frame
    px[22][38] = shine  # light catching the frame


def stubble(px, rng, colour=(150, 146, 140)):
    for y in range(34, 46):
        for x in range(23, 43):
            c = px[y][x]
            if is_skin(c, x, y) and not (y in (MOUTH_ROW, LIP_ROW) and x in MOUTH_X):
                if rng.random() < 0.55:
                    px[y][x] = mix(c, scale(colour, lum(c) / 110 + 0.25), 0.45)


# --------------------------------------------------------------------------- characters


def character(name):
    """Returns (recolour_fn, additions_fn, grade, mirror)."""
    if name == "dot":
        def rc(c, x, y):
            return recolour(c, hue=0.47, sat=0.9) if is_hood(c) else c
        return rc, None, (0.96, 1.04, 0.98, (0, 5, 2)), False
    if name == "hugo":
        def rc(c, x, y):
            if is_hood(c):
                return recolour(c, sat=0.15, val=1.1)
            if is_skin(c, x, y):
                return mix(recolour(c, sat=0.55, val=1.12), (lum(c),) * 3, 0.15)
            return c
        return rc, stubble, (0.92, 0.97, 1.08, (0, 1, 5)), True
    if name == "pemberton":
        def rc(c, x, y):
            if is_hood(c):
                return recolour(c, hue=0.98, sat=1.1)
            if is_skin(c, x, y):
                return mix(c, recolour(c, hue=0.025, sat=1.0, val=1.06), 0.35)  # a little ruddier
            return c
        return rc, moustache, (1.08, 0.97, 0.84, (4, 1, 0)), False
    if name == "desmond":
        def rc(c, x, y):
            if is_hood(c):
                return recolour(c, hue=0.63, sat=0.5, val=0.7)
            if is_skin(c, x, y):
                return recolour(c, sat=0.85, val=0.72)
            return c
        return rc, lambda px, rng: glasses(px), (0.95, 0.98, 1.06, (0, 2, 7)), False
    raise ValueError(name)


def build(src: Image.Image, name: str, frame: str) -> Image.Image:
    rng = random.Random(f"{name}-{frame}")
    feature_rng = random.Random(name)  # same moustache/stubble pattern in every frame
    g = src.resize((GRID, GRID), Image.BOX).convert("RGB")
    px = [[g.getpixel((x, y)) for x in range(GRID)] for y in range(GRID)]

    animate(px, frame)
    rc, additions, (gr, gg, gb, lift), mirror = character(name)
    px = [[rc(px[y][x], x, y) for x in range(GRID)] for y in range(GRID)]
    if additions:
        additions(px, feature_rng)
    px = [[tuple(max(0, min(255, int(round(c[i] * (gr, gg, gb)[i] + lift[i] * (1 - lum(c) / 255)))))
                 for i in range(3)) for c in row] for row in px]
    if mirror:
        px = [list(reversed(row)) for row in px]

    x0, y0, x1, y1 = CROP
    out = Image.new("RGBA", (x1 - x0, y1 - y0))
    cx, cy = HEAD_CENTRE
    rx, ry = HEAD_RADII
    for y in range(y0, y1):
        for x in range(x0, x1):
            d = ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2
            a = 1.0 - max(0.0, min(1.0, (d - 0.72) / 0.35))
            if y >= FADE_FROM_Y:
                a *= max(0.0, 1 - (y - FADE_FROM_Y + 1) / 6)
            a = round(a * 4) / 4  # stepped alpha keeps the pixel-art edge
            out.putpixel((x - x0, y - y0), (*px[y][x], int(a * 255)))
    return out


FRAMES = ("idle", "blink", "think", "talk1", "talk2")
CHARACTERS = ("dot", "hugo", "pemberton", "desmond")


def main(argv):
    if len(argv) != 1:
        print(__doc__)
        return 2
    src = Image.open(argv[0]).convert("RGB")
    for name in CHARACTERS:
        folder = OUT / name
        folder.mkdir(parents=True, exist_ok=True)
        for frame in FRAMES:
            build(src, name, frame).save(folder / f"{frame}.png", optimize=True)
        print(f"wrote {folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
