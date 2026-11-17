"""Shaded, full-colour pixel portraits (pure Python, no Kivy or numpy).

Each face is modelled as a height field: an ellipsoid head plus soft bumps and hollows
for brow ridge, eye sockets, cheekbones, nose, lips and chin. Normals from that surface
are lit like a photo (warm key light from the upper left, cool fill, a rim light in the
monitor's colour), coloured with a skin/hair/eye/lip albedo map, then quantised and
dithered so it reads as pixel art. Returns RGBA bytes, top row first.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

W, H = 64, 72
CX, CY = 32.0, 37.0

Color = tuple  # (r, g, b) in 0..1


@dataclass(frozen=True)
class FaceStyle:
    hair: str = "wisps"            # wisps | tufts | full | bald
    heavy_lids: bool = False        # half-closed, weary eyes
    moustache: bool = False
    glasses: bool = False
    wrinkles: bool = False          # forehead and eye lines
    wide: bool = False              # broader, rounder head
    stubble: bool = False
    skin: Color = (0.93, 0.74, 0.62)
    hair_color: Color = (0.28, 0.18, 0.11)
    eye_color: Color = (0.30, 0.45, 0.62)
    lip_color: Color = (0.74, 0.42, 0.42)
    tint: Color = (0.55, 0.95, 0.65)  # monitor phosphor colour
    tint_amount: float = 0.15         # 0 = natural colour, 1 = monochrome screen
    levels: int = 20                  # colour steps per channel (lower = chunkier)
    seed: int = 7                     # for hair texture

    @classmethod
    def from_dict(cls, d: dict | None) -> "FaceStyle":
        d = dict(d or {})
        for k in ("skin", "hair_color", "eye_color", "lip_color", "tint"):
            if k in d:
                d[k] = tuple(d[k])
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


# --------------------------------------------------------------------------- maths


def _g(x, y, cx, cy, sx, sy):
    return math.exp(-(((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2))


def _norm(v):
    m = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / m for c in v)


def _mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def _clamp(v):
    return 0.0 if v < 0 else 1.0 if v > 1 else v


BAYER4 = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


@dataclass
class _Frame:
    blink: bool
    mouth: int
    brow: int
    look: int
    height: list = field(default_factory=list)


# --------------------------------------------------------------------------- render


def render(style: FaceStyle | None = None, blink: bool = False, mouth: int = 0,
           brow: int = 0, look: int = 0) -> bytes:
    """RGBA bytes (W*H*4), top row first.

    blink: eyes closed. mouth: 0 closed, 1 half open, 2 open.
    brow: 1 raises the right eyebrow. look: -1 left, 0 ahead, 1 right.
    """
    st = style or FaceStyle()
    rx, ry = (25.0, 30.0) if st.wide else (22.5, 30.0)
    open_px = (0, 2, 4)[mouth]
    rng = random.Random(st.seed)
    hair_noise = [[rng.random() for _ in range(W)] for _ in range(H)]

    ex_l, ex_r, ey = CX - 9.5, CX + 9.5, 33.0       # eye centres
    mouth_y = 53.0

    def rx_at(y):
        # widest at the cheekbones, tapering to a jaw and slightly at the crown
        below = max(0.0, (y - CY - 3) / ry)
        above = max(0.0, (CY - 8 - y) / ry)
        return rx * (1.0 - 0.30 * below ** 1.4 - 0.08 * above)

    def inside_head(x, y):
        return ((x - CX) / rx_at(y)) ** 2 + ((y - CY) / ry) ** 2

    def ear(x, y):
        for ex in (CX - rx_at(39) - 0.5, CX + rx_at(39) + 0.5):
            d = ((x - ex) / 3.2) ** 2 + ((y - 39) / 7.5) ** 2
            if d < 1:
                return d
        return None

    # ---- height field (in pixels)
    def height(x, y):
        d = inside_head(x, y)
        if d < 1:
            z = math.sqrt(1 - d) * 22
            z += 2.0 * _g(x, y, CX, 28, 13, 2.5)                         # brow ridge
            z -= 3.2 * (_g(x, y, ex_l, ey, 4.5, 3.2) + _g(x, y, ex_r, ey, 4.5, 3.2))
            z += 1.8 * (_g(x, y, CX - 13, 42, 4, 3) + _g(x, y, CX + 13, 42, 4, 3))
            z += 5.5 * _g(x, y, CX, 38, 1.8, 7.5) + 3.5 * _g(x, y, CX, 45, 3.0, 2.2)
            z -= 1.2 * (_g(x, y, CX - 2.6, 47, 1.2, 0.9) + _g(x, y, CX + 2.6, 47, 1.2, 0.9))
            z -= 1.2 * _g(x, y, CX, 49.5, 1.5, 1.2)                      # philtrum
            z += 1.6 * _g(x, y, CX, mouth_y - 0.8, 6, 1.2)               # upper lip
            z += 1.8 * _g(x, y, CX, mouth_y + 1.6 + open_px, 5.5, 1.4)   # lower lip
            z += 2.2 * _g(x, y, CX, 63, 7, 3.5)                          # chin
            if mouth and abs(x - CX) < 5.5 - abs(y - mouth_y - open_px / 2) * 0.7 \
                    and mouth_y - 0.2 < y < mouth_y + open_px + 0.6:
                z -= 4
            if st.wrinkles:
                for wy in (19.5, 22.5):
                    z -= 0.6 * _g(x, y, CX, wy, 9, 0.45)
                for ex in (ex_l - 6, ex_r + 6):
                    z -= 0.5 * _g(x, y, ex, ey + 1, 0.6, 2.5)
            return z
        e = ear(x, y)
        if e is not None:
            return math.sqrt(1 - e) * 4 + 4
        return None

    hf = [[height(x + 0.5, y + 0.5) for x in range(W)] for y in range(H)]

    key = _norm((-0.55, -0.65, 0.75))   # upper-left, in front (y points down)
    fill = _norm((0.7, 0.1, 0.6))
    view = (0.0, 0.0, 1.0)
    warm, cool = (1.0, 0.95, 0.88), (0.65, 0.72, 0.9)

    out = bytearray(W * H * 4)
    for y in range(H):
        for x in range(W):
            z = hf[y][x]
            if z is None:
                continue
            px, py = x + 0.5, y + 0.5

            # normal from central differences (edges fall back to one side)
            zl = hf[y][x - 1] if x > 0 and hf[y][x - 1] is not None else z
            zr = hf[y][x + 1] if x < W - 1 and hf[y][x + 1] is not None else z
            zu = hf[y - 1][x] if y > 0 and hf[y - 1][x] is not None else z
            zd = hf[y + 1][x] if y < H - 1 and hf[y + 1][x] is not None else z
            n = _norm((-(zr - zl) / 2, -(zd - zu) / 2, 1.0))

            # ---- albedo
            base = st.skin
            # warmth: cheeks, nose and ears redder; eye sockets slightly darker, purpler
            blush = 0.35 * (_g(px, py, CX - 12, 44, 4.5, 3.5) + _g(px, py, CX + 12, 44, 4.5, 3.5)) \
                + 0.25 * _g(px, py, CX, 45, 2.5, 2.5)
            col = _mix(base, (base[0] * 1.02, base[1] * 0.72, base[2] * 0.68), _clamp(blush))
            sock = _g(px, py, ex_l, ey + 2.5, 4, 2) + _g(px, py, ex_r, ey + 2.5, 4, 2)
            col = _mix(col, (base[0] * 0.78, base[1] * 0.64, base[2] * 0.7), _clamp(sock * 0.35))
            is_ear = inside_head(px, py) >= 1
            if is_ear:
                col = _mix(col, (base[0], base[1] * 0.75, base[2] * 0.72), 0.4)
            gloss = 0.25   # skin specular strength

            if st.stubble and py > 46 and not is_ear:
                jaw = _clamp((py - 46) / 6) * (0.25 + 0.15 * hair_noise[y][x])
                col = _mix(col, (base[0] * 0.62, base[1] * 0.6, base[2] * 0.64), jaw)

            # ---- hair
            hn = hair_noise[y][x]
            d = inside_head(px, py)
            hair_here = False
            if st.hair == "full":
                hairline = 19.5 + 0.012 * (px - CX) ** 2 + 1.2 * math.sin((px - CX) / 3.5) * (hn - 0.5)
                if py < hairline or (d > 0.72 and py < 33 and abs(px - CX) > 12):
                    hair_here = True
            elif st.hair == "wisps":
                if (d > 0.68 and py < 33 and abs(px - CX) > 12) or (py < 12 and hn > 0.55):
                    hair_here = True
            elif st.hair == "tufts":
                if d > 0.5 and 22 < py < 40 and abs(px - CX) > 13.5 and hn > 0.12:
                    hair_here = True
                if is_ear and py < 38 and hn > 0.35:
                    hair_here = True
            if hair_here:
                streak = 0.75 + 0.5 * hn
                col = tuple(_clamp(c * streak) for c in st.hair_color)
                gloss = 0.35
            elif st.hair in ("tufts", "bald") and py < 24 and not is_ear:
                gloss = 0.7   # shiny scalp

            # ---- eyebrows (follow brow ridge; right one may lift)
            for ex, lift in ((ex_l, 0), (ex_r, brow * 2.5)):
                by = 28.3 - lift + 0.06 * (px - ex) ** 2 * (1 if ex > CX else 1)
                if abs(px - ex) < 5.5 and abs(py - by) < 1.1:
                    col = tuple(c * (0.8 + 0.3 * hn) for c in st.hair_color)
                    gloss = 0.1

            # ---- eyes
            for ex in (ex_l, ex_r):
                dx, dy = px - ex, py - ey
                in_eye = (dx / 3.6) ** 2 + (dy / 1.9) ** 2 < 1
                if not in_eye:
                    continue
                if blink:
                    col = _mix(st.skin, (0, 0, 0), 0.25)
                    if abs(dy) < 0.6:
                        col = _mix(st.skin, (0.15, 0.08, 0.06), 0.7)
                    continue
                if st.heavy_lids and dy < -0.1:
                    col = _mix(st.skin, (0.3, 0.2, 0.2), 0.3 if dy < -0.9 else 0.55)
                    continue
                col, gloss = (0.93, 0.9, 0.86), 0.1
                ix = ex + look * 1.6
                ir = math.hypot(px - ix, py - ey - 0.2)
                if ir < 1.9:
                    col = tuple(c * (0.75 + 0.25 * (ir / 1.9)) for c in st.eye_color)
                if ir < 0.85:
                    col = (0.04, 0.03, 0.03)
                if abs(px - (ix - 0.6)) < 0.5 and abs(py - (ey - 0.7)) < 0.5:
                    col, gloss = (1, 1, 1), 0
                n = (0.0, 0.0, 1.0)   # keep eyes from being shaded like skin

            # ---- mouth
            if mouth and abs(px - CX) < 5.5 - abs(py - mouth_y - open_px / 2) * 0.7 \
                    and mouth_y - 0.2 < py < mouth_y + open_px + 0.6:
                col, gloss = (0.22, 0.05, 0.06), 0.0
                if py < mouth_y + 1.2 and abs(px - CX) < 4:
                    col, gloss = (0.92, 0.9, 0.82), 0.2   # upper teeth
            elif abs(px - CX) < 6.5:
                if abs(py - (mouth_y - 0.7)) < 0.9 or abs(py - (mouth_y + 1.6 + open_px)) < 1.1:
                    t = 1 - abs(px - CX) / 6.5
                    col = _mix(col, st.lip_color, _clamp(0.4 + t))
                    gloss = 0.45
                elif not mouth and abs(py - mouth_y - 0.4) < 0.5:
                    col = _mix(st.lip_color, (0.15, 0.05, 0.05), 0.65)

            dxm = abs(px - CX)
            m_top = 47.2 + 0.03 * dxm ** 2 + 0.6 * (hn - 0.5)
            m_bot = mouth_y - 0.3 + max(0.0, dxm - 4.5) * 1.1
            if st.moustache and dxm < 10 + hn and m_top < py < m_bot:  # broad walrus moustache
                col = tuple(c * (0.75 + 0.4 * hn) for c in st.hair_color)
                gloss = 0.25

            # ---- lighting
            diff = max(0.0, sum(n[i] * key[i] for i in range(3)))
            fil = max(0.0, sum(n[i] * fill[i] for i in range(3)))
            ao = _clamp(0.55 + z / 30)        # crevices darker
            half = _norm(tuple(key[i] + view[i] for i in range(3)))
            spec = max(0.0, sum(n[i] * half[i] for i in range(3))) ** 24 * gloss
            rim = (1 - n[2]) ** 2.5 * 0.55
            rgb = []
            for i in range(3):
                v = col[i] * (0.22 * ao + 0.95 * diff * warm[i] + 0.3 * fil * cool[i]) \
                    + spec * warm[i] + rim * st.tint[i]
                rgb.append(v)

            # ---- glasses on top (frames are flat dark plastic with a glint)
            if st.glasses:
                for ex in (ex_l, ex_r):
                    r = ((px - ex) / 5.2) ** 2 + ((py - ey) / 3.6) ** 2
                    if 0.78 < r < 1.15:
                        rgb = [0.08, 0.07, 0.08]
                        if py < ey - 2.5 and px < ex:
                            rgb = [0.5, 0.5, 0.55]
                    elif r <= 0.78:
                        rgb = [c * 0.92 + 0.04 for c in rgb]
                if abs(py - (ey - 1)) < 0.6 and abs(px - CX) < 4.3:
                    rgb = [0.08, 0.07, 0.08]

            # ---- monitor tint, quantise with ordered dither
            lum = 0.3 * rgb[0] + 0.59 * rgb[1] + 0.11 * rgb[2]
            rgb = [rgb[i] * (1 - st.tint_amount) + lum * st.tint[i] * 1.15 * st.tint_amount
                   for i in range(3)]
            dither = (BAYER4[y % 4][x % 4] / 16 - 0.5) / st.levels
            q = [int(round(_clamp(c + dither) * (st.levels - 1))) * 255 // (st.levels - 1) for c in rgb]
            o = (y * W + x) * 4
            out[o:o + 4] = bytes((q[0], q[1], q[2], 255))
    return bytes(out)


def frames(style: FaceStyle) -> dict[str, bytes]:
    """The five named frames used for image-based skins."""
    return {
        "idle": render(style),
        "blink": render(style, blink=True),
        "think": render(style, brow=1, look=1),
        "talk1": render(style, mouth=1),
        "talk2": render(style, mouth=2),
    }
