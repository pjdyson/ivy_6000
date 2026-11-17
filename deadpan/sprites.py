"""Pixel-art heads, generated as grids of palette keys (pure Python, no Kivy).

Keys: '.' empty, S skin, D shade/outline, H hair/brows, W eye white, P pupil,
M mouth, T teeth, G glasses frame.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

W, H = 32, 36
KEYS = "SDHWPMTG"


def _pal(S, D, H, W, P, M, T, G=None):
    return {"S": S, "D": D, "H": H, "W": W, "P": P, "M": M, "T": T, "G": G or H}


PALETTES = {
    "phosphor": _pal((0.55, 0.95, 0.62), (0.20, 0.55, 0.28), (0.12, 0.38, 0.18),
                     (0.85, 1.00, 0.88), (0.03, 0.15, 0.06), (0.05, 0.22, 0.09), (0.80, 1.00, 0.84)),
    "amber": _pal((1.00, 0.72, 0.30), (0.62, 0.38, 0.10), (0.40, 0.22, 0.05),
                  (1.00, 0.92, 0.75), (0.15, 0.07, 0.00), (0.25, 0.12, 0.02), (1.00, 0.90, 0.70)),
    # Washed-out grey-blue monitor.
    "mono": _pal((0.78, 0.80, 0.84), (0.42, 0.44, 0.48), (0.30, 0.31, 0.34),
                 (0.97, 0.97, 1.00), (0.05, 0.05, 0.07), (0.12, 0.12, 0.14), (0.92, 0.92, 0.95),
                 (0.18, 0.19, 0.22)),
    "cyan": _pal((0.50, 0.85, 1.00), (0.18, 0.45, 0.62), (0.10, 0.28, 0.42),
                 (0.88, 0.97, 1.00), (0.02, 0.08, 0.14), (0.04, 0.15, 0.25), (0.85, 0.96, 1.00),
                 (0.06, 0.18, 0.30)),
}


@dataclass(frozen=True)
class FaceStyle:
    hair: str = "wisps"      # wisps | tufts | full | bald
    heavy_lids: bool = False  # half-closed, weary eyes
    moustache: bool = False
    glasses: bool = False
    wrinkles: bool = False    # forehead lines
    wide: bool = False        # broader, rounder head

    @classmethod
    def from_dict(cls, d: dict | None) -> "FaceStyle":
        d = d or {}
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


def face(style: FaceStyle | None = None, blink: bool = False, mouth: int = 0,
         brow: int = 0, look: int = 0) -> list[str]:
    """Return H rows of W palette keys.

    blink: eyes closed. mouth: 0 closed, 1 half open, 2 open.
    brow: 1 raises one eyebrow (sceptical). look: -1 left, 0 ahead, 1 right.
    """
    st = style or FaceStyle()
    g = [["."] * W for _ in range(H)]
    cx, cy = 15.5, 17.5
    rx, ry = (12.5, 15.5) if st.wide else (11.5, 15.5)

    def put(x: int, y: int, k: str) -> None:
        if 0 <= x < W and 0 <= y < H:
            g[y][x] = k

    def dist(x, y):
        return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2

    # Head: an ellipse, darker at the rim.
    for y in range(H):
        for x in range(W):
            d = dist(x, y)
            if d <= 1.0:
                g[y][x] = "D" if d > 0.86 else "S"

    # Ears, just outside the head's widest point.
    lx, rx_ = int(cx - rx) - 1, int(cx + rx) + 1
    for y in range(15, 22):
        put(lx + 1, y, "D")
        put(rx_ - 1 + (1 if st.wide else 0), y, "D")
        if 16 <= y <= 20:
            put(lx, y, "S")
            put(lx - 1, y, "D")
            put(rx_ + (1 if st.wide else 0), y, "S")
            put(rx_ + 1 + (1 if st.wide else 0), y, "D")

    # Hair.
    if st.hair == "wisps":
        for y in range(5, 13):
            for x in range(W):
                if 0.72 < dist(x, y) <= 1.0 and abs(x - cx) > 8:
                    g[y][x] = "H"
        for x in (12, 14, 17, 19):
            put(x, 3, "H")
    elif st.hair == "tufts":  # bald dome, tufts over the ears
        for y in range(10, 17):
            for x in range(W):
                if 0.70 < dist(x, y) <= 1.0 and abs(x - cx) > 9:
                    g[y][x] = "H"
        for y in range(11, 16):  # a little fluff sticking out
            put(lx, y, "H") if y % 2 else None
            put(rx_ + (1 if st.wide else 0), y, "H") if y % 2 else None
    elif st.hair == "full":
        for y in range(H):
            for x in range(W):
                d = dist(x, y)
                if d <= 1.0 and (y < 8 or (y < 13 and abs(x - cx) > 9)):
                    g[y][x] = "H"
        for y in range(2, 8):  # side parting
            put(11, y, "D")
        for x in range(4, 12):
            put(x, 8, "H") if dist(x, 8) <= 1.0 else None

    if st.wrinkles:
        for y, (a, b) in ((6, (12, 20)), (8, (11, 21))):
            for x in range(a, b):
                put(x, y, "D") if x % 3 else None

    # Eyebrows.
    for x in range(9, 13):
        put(x, 11, "H")
    for x in range(19, 23):
        put(x, 11 - brow, "H")
    if brow:
        put(22, 11, "H")

    # Eyes.
    for ex in (9, 19):
        if blink:
            for x in range(ex, ex + 4):
                put(x, 14, "D")
        else:
            top = "D" if st.heavy_lids else "W"
            for x in range(ex, ex + 4):
                put(x, 13, top)
                put(x, 14, "W")
            px = ex + 1 + look
            for x in (px, px + 1):
                put(x, 14, "P")
                if not st.heavy_lids:
                    put(x, 13, "P")
        for x in range(ex, ex + 4):  # bags under the eyes
            put(x, 16, "D")
        if st.glasses:
            for x in range(ex - 1, ex + 5):
                put(x, 12, "G")
                put(x, 15, "G")
            for y in (13, 14):
                put(ex - 1, y, "G")
                put(ex + 4, y, "G")
    if st.glasses:
        for x in range(14, 18):
            put(x, 13, "G")

    # Nose.
    for y in range(16, 21):
        put(16, y, "D")
    for x in range(14, 18):
        put(x, 21, "D")

    # Mouth.
    if mouth == 0:
        for x in range(11, 21):
            put(x, 25, "M")
        put(10, 24, "D")
        put(21, 24, "D")
    elif mouth == 1:
        for x in range(11, 21):
            put(x, 25, "M")
        for x in range(12, 20):
            put(x, 26, "M")
    else:
        for x in range(12, 20):
            put(x, 24, "M")
        for x in range(11, 21):
            put(x, 25, "T" if 12 < x < 19 else "M")
            put(x, 26, "M")
        for x in range(12, 20):
            put(x, 27, "M")

    if st.moustache:
        for x in range(11, 21):
            put(x, 23, "H")
        for x in range(13, 19):
            put(x, 22, "H")

    for x in range(13, 19):  # chin line
        put(x, 30, "D")

    return ["".join(r) for r in g]


def to_png(grid: list[str], palette: dict, scale: int = 1) -> bytes:
    """Encode a grid as an RGBA PNG (transparent background). No dependencies."""
    rows = []
    for line in grid:
        px = b""
        for k in line:
            if k == ".":
                px += b"\x00\x00\x00\x00"
            else:
                r, g_, b = (int(round(c * 255)) for c in palette[k])
                px += bytes((r, g_, b, 255))
        px = b"".join(px[i:i + 4] * scale for i in range(0, len(px), 4))
        rows.extend([b"\x00" + px] * scale)
    w, h = len(grid[0]) * scale, len(grid) * scale

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))
