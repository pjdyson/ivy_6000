"""Shaded, full-colour pixel portraits of a floating head (pure Python, no Kivy or numpy).

The head is a height field: a skull with a jaw, plus soft forms for brow, eye sockets,
cheekbones, nose, lips, chin and the folds beside the mouth. It is lit like a portrait
photo: a soft,
warm key light from the upper left that wraps round the forms, a cool fill, warmth in
the shadows (light scattering under skin) and a faint rim light in the screen's colour.
The result is quantised with an ordered dither so it reads as pixel art.

``render`` returns RGBA bytes, top row first.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

W, H = 60, 72
CX, CY = 30.0, 40.0        # head centre
EYE_Y, EYE_DX = 40.0, 8.5  # eye line and half the distance between the eyes
BROW_Y = 35.2
NOSE_BASE_Y = 51.0
MOUTH_Y = 56.4

Color = tuple  # (r, g, b) in 0..1


@dataclass(frozen=True)
class FaceStyle:
    hair: str = "full"              # full | curly | wisps | tufts | bald
    heavy_lids: bool = False         # weary, hooded eyes
    moustache: bool = False
    glasses: bool = False
    wrinkles: bool = False           # forehead lines, crow's feet, deeper folds
    wide: bool = False               # broader face
    stubble: bool = False
    smile: float = 0.35              # 0 = neutral, 1 = clearly smiling
    skin: Color = (0.92, 0.73, 0.62)
    hair_color: Color = (0.30, 0.20, 0.12)
    eye_color: Color = (0.32, 0.45, 0.58)
    lip_color: Color = (0.72, 0.43, 0.42)
    tint: Color = (0.55, 0.95, 0.65)  # screen colour, for the rim light and tint
    tint_amount: float = 0.1          # 0 = natural colour, 1 = monochrome screen
    levels: int = 24                  # colour steps per channel (lower = chunkier)
    seed: int = 7                     # for hair and skin texture

    @classmethod
    def from_dict(cls, d: dict | None) -> "FaceStyle":
        d = dict(d or {})
        for k, v in list(d.items()):
            if isinstance(v, list):
                d[k] = tuple(v)
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


# --------------------------------------------------------------------------- maths


def _g(x, y, cx, cy, sx, sy):
    return math.exp(-(((x - cx) / sx) ** 2 + ((y - cy) / sy) ** 2))


def _ss(e0, e1, v):
    t = (v - e0) / (e1 - e0)
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return t * t * (3 - 2 * t)


def _norm(v):
    m = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / m, v[1] / m, v[2] / m)


def _mix(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def _scale(c, k):
    return (c[0] * k, c[1] * k, c[2] * k)


def _clamp(v):
    return 0.0 if v < 0 else 1.0 if v > 1 else v


BAYER4 = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


# --------------------------------------------------------------------------- render


def render(style: FaceStyle | None = None, blink: bool = False, mouth: int = 0,
           brow: int = 0, look: int = 0) -> bytes:
    """RGBA bytes (W*H*4), top row first.

    blink: eyes closed. mouth: 0 closed, 1 slightly open, 2 open.
    brow: 1 raises the right eyebrow. look: -1 left, 0 ahead, 1 right.
    """
    st = style or FaceStyle()
    rng = random.Random(st.seed)
    noise = [[rng.random() for _ in range(W)] for _ in range(H)]
    rx0 = 20.5 if st.wide else 19.0
    ry = 27.0
    opening = (0.0, 1.4, 2.8)[mouth]
    age = 1.0 if st.wrinkles else 0.35

    def rx_at(y):
        below = max(0.0, (y - 47) / 20)
        return rx0 * (1.0 - 0.24 * below ** 1.8)

    def head_d(x, y):
        return ((x - CX) / rx_at(y)) ** 2 + ((y - CY) / ry) ** 2

    ear_x = rx_at(44) + 0.6

    def ear_d(x, y):
        dx = abs(x - CX) - ear_x
        return (dx / 2.6) ** 2 + ((y - 44.5) / 5.8) ** 2

    def hair_d(x, y):
        # hair sits slightly outside the skull, giving volume
        grow = {"full": 2.2, "curly": 2.6, "wisps": 0.6}.get(st.hair, 0.0)
        return ((x - CX) / (rx_at(min(y, 40)) + grow)) ** 2 + ((y - CY + 0.5) / (ry + grow * 0.8)) ** 2

    def hairline(x):
        dx = x - CX
        if st.hair == "curly":
            return 24.0 + 0.012 * dx * dx
        return 23.0 + 0.016 * dx * dx + (0.8 if dx < -5 else 0.0)  # side parting

    def has_hair(x, y):
        dx, n = abs(x - CX), noise[int(y)][int(x)]
        if st.hair in ("full", "curly"):
            if hair_d(x, y) > 1:
                return False
            if y < hairline(x):
                return True
            # down the sides to just above the ears
            return dx > rx_at(y) - 2.6 and y < 41 and head_d(x, y) > 0.72
        if st.hair == "wisps":
            if hair_d(x, y) > 1:
                return False
            if dx > rx_at(y) - 3.2 and 22 < y < 41 and head_d(x, y) > 0.66:
                return True
            return y < 21 and n > 0.62
        if st.hair == "tufts":
            # fluffy grey tufts over the ears, standing out from the head
            for side in (-1, 1):
                cx = CX + side * (rx_at(38) - 0.5)
                if ((x - cx) / 3.0) ** 2 + ((y - 37.0) / 6.0) ** 2 < 0.7 + 0.45 * n:
                    return True
            return dx > rx_at(y) - 2.2 and 28 < y < 44 and 0.7 < head_d(x, y) < 1.0 and n > 0.2
        return False

    # ---- shape: region map and height field
    region = [[None] * W for _ in range(H)]
    hf = [[0.0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            px, py = x + 0.5, y + 0.5
            dx = px - CX
            z = None
            reg = None
            d = head_d(px, py)
            if d < 1:
                reg = "face"
                z = math.sqrt(1 - d) * 18 + 12
                z += 1.6 * _g(px, py, CX, BROW_Y + 0.6, 12, 2.0)
                z -= 2.0 * (_g(px, py, CX - EYE_DX, EYE_Y, 3.8, 2.6) + _g(px, py, CX + EYE_DX, EYE_Y, 3.8, 2.6))
                z += 1.4 * (_g(px, py, CX - 11, 46, 4, 3) + _g(px, py, CX + 11, 46, 4, 3))
                z += 2.2 * _g(px, py, CX, 45.0, 2.3, 5.0) + 2.4 * _g(px, py, CX, 49.3, 2.4, 1.9)
                z += 1.0 * (_g(px, py, CX - 2.6, 50.4, 1.3, 1.1) + _g(px, py, CX + 2.6, 50.4, 1.3, 1.1))
                z -= 0.8 * (_g(px, py, CX - 1.8, 51.3, 0.8, 0.5) + _g(px, py, CX + 1.8, 51.3, 0.8, 0.5))
                z -= 0.5 * _g(px, py, CX, 53.3, 0.9, 1.0)
                z += 1.0 * _g(px, py, CX, MOUTH_Y - 1.0, 4.5, 0.9)
                z += 1.3 * _g(px, py, CX, MOUTH_Y + 1.4 + opening, 4.0, 1.0)
                z -= (0.4 + 0.5 * age) * (_g(px, py, CX - 4.8, 54, 0.8, 2.4) + _g(px, py, CX + 4.8, 54, 0.8, 2.4))
                z += 1.6 * _g(px, py, CX, 63.5, 6.5, 2.5)
                if mouth and _in_mouth(dx, py, opening, st.smile):
                    z -= 2.5
                if st.wrinkles:
                    for wy in (25.5, 28.0, 30.5):
                        z -= 0.35 * _g(px, py, CX, wy, 8, 0.4)
                    for ex in (CX - EYE_DX - 4.6, CX + EYE_DX + 4.6):
                        z -= 0.35 * _g(px, py, ex, EYE_Y + 0.5, 0.5, 1.8)
            elif ear_d(px, py) < 1:
                reg, z = "ear", 9 + math.sqrt(1 - ear_d(px, py)) * 3
            if has_hair(px, py) and reg in (None, "face", "ear"):
                hd = hair_d(px, py)
                hz = math.sqrt(max(0.0, 1 - hd)) * 20 + 12.5
                if reg is None or hz > (z or 0) - 2 or st.hair in ("full", "curly", "wisps"):
                    reg, z = "hair", max(hz, (z or 0) + 0.6)
            region[y][x] = reg
            if z is not None:
                hf[y][x] = z

    key = _norm((-0.45, -0.55, 0.70))
    fill = _norm((0.75, 0.0, 0.65))
    half = _norm((key[0], key[1], key[2] + 1))
    warm, cool = (1.0, 0.94, 0.86), (0.70, 0.78, 0.95)
    brow_col = _scale(st.hair_color, 0.75) if sum(st.hair_color) < 1.8 else _scale(st.hair_color, 0.85)

    out = bytearray(W * H * 4)
    for y in range(H):
        for x in range(W):
            reg = region[y][x]
            if reg is None:
                continue
            px, py = x + 0.5, y + 0.5
            dx = px - CX
            n_ = noise[y][x]
            z = hf[y][x]

            def at(xx, yy):
                if 0 <= xx < W and 0 <= yy < H and region[yy][xx] is not None:
                    return hf[yy][xx]
                return z - 1.5  # fall away at silhouettes
            zl, zr, zu, zd = at(x - 1, y), at(x + 1, y), at(x, y - 1), at(x, y + 1)
            n = _norm((-(zr - zl) / 2, -(zd - zu) / 2, 1.0))
            cavity = (zl + zr + zu + zd) / 4 - z   # positive in creases

            gloss, sss = 0.12, 0.0
            if reg in ("face", "ear"):
                col = st.skin
                sss = 1.0
                # natural colour variation: rosier cheeks, nose and ears; cooler, darker under eyes
                rosy = 0.30 * (_g(px, py, CX - 11, 47, 4.5, 3.5) + _g(px, py, CX + 11, 47, 4.5, 3.5)) \
                    + 0.22 * _g(px, py, CX, 49.5, 2.2, 2.2) + (0.25 if reg == "ear" else 0.0)
                col = _mix(col, (col[0] * 1.0, col[1] * 0.78, col[2] * 0.74), _clamp(rosy))
                under = _g(px, py, CX - EYE_DX, EYE_Y + 2.3, 3.2, 1.2) + _g(px, py, CX + EYE_DX, EYE_Y + 2.3, 3.2, 1.2)
                col = _mix(col, (col[0] * 0.82, col[1] * 0.72, col[2] * 0.78), _clamp(under * (0.25 + 0.2 * age)))
                col = _scale(col, 0.97 + 0.06 * n_)   # skin texture
                if st.hair in ("tufts", "bald") and py < 30 and reg == "face":
                    gloss = 0.35                         # shiny scalp
                if st.stubble and reg == "face" and py > 50 and abs(dx) < rx_at(py) - 0.5 \
                        and not (abs(dx) < 4.6 and MOUTH_Y - 2 < py < MOUTH_Y + 3):
                    if n_ > 0.45:
                        col = _mix(col, _scale(st.hair_color, 1.3), 0.35)
                if reg == "ear" and abs(dx) - ear_x < 0.6 and 41 < py < 48:
                    col = _scale(col, 0.78)              # inner ear
            else:  # hair
                col = _hair_albedo(st, px, py, n_)
                gloss = 0.3

            # ---- facial features (painted over the skin)
            if reg == "face":
                col, gloss, n = _features(st, col, gloss, n, px, py, dx, n_, blink, mouth,
                                          opening, brow, look, brow_col)

            # ---- lighting
            ndl = n[0] * key[0] + n[1] * key[1] + n[2] * key[2]
            diff = _clamp((ndl + 0.22) / 1.22)               # wrap lighting: soft shadows
            fil = _clamp(n[0] * fill[0] + n[1] * fill[1] + n[2] * fill[2])
            spec = max(0.0, n[0] * half[0] + n[1] * half[1] + n[2] * half[2]) ** 30 * gloss
            occl = _clamp(1.0 - max(0.0, cavity) * 0.18)
            rim = (1 - n[2]) ** 3 * 0.35
            shade = []
            for i in range(3):
                v = col[i] * (0.24 + 0.92 * diff * warm[i] + 0.16 * fil * cool[i]) * occl
                v += spec * warm[i] + rim * st.tint[i] * 0.6
                if sss:  # light scattering under skin warms the shadows
                    v += (1 - diff) * col[i] * (0.16, 0.05, 0.02)[i]
                shade.append(v)

            # glasses are drawn over everything, unlit
            if reg == "face" and st.glasses:
                shade = _glasses(shade, px, py, dx, rx_at(py))

            # ---- screen tint, dither, quantise
            lum = 0.3 * shade[0] + 0.59 * shade[1] + 0.11 * shade[2]
            shade = [shade[i] * (1 - st.tint_amount) + lum * st.tint[i] * 1.1 * st.tint_amount
                     for i in range(3)]
            dither = (BAYER4[y % 4][x % 4] / 16 - 0.5) / st.levels
            q = [int(round(_clamp(c + dither) * (st.levels - 1))) * 255 // (st.levels - 1) for c in shade]
            o = (y * W + x) * 4
            out[o:o + 4] = bytes((q[0], q[1], q[2], 255))
    return bytes(out)


# --------------------------------------------------------------------------- pieces


def _in_mouth(dx, py, opening, smile):
    if opening <= 0:
        return False
    w = 3.6
    line = MOUTH_Y - smile * 0.6 * (dx / 4.2) ** 2
    if abs(dx) >= w:
        return False
    depth = opening * (1 - (dx / w) ** 2)
    return line < py < line + depth + 0.3


def _hair_albedo(st, px, py, n_):
    c = st.hair_color
    if st.hair == "curly" or st.hair == "tufts":
        k = 0.72 + 0.5 * n_
    else:
        # strands flowing back from the hairline
        k = 0.80 + 0.18 * math.sin(px * 1.7 + py * 0.25 + n_ * 2.5) + 0.12 * n_
        if st.hair == "full" and abs(px - (CX - 5.5)) < 0.7 and py < 28:
            k *= 0.7  # parting
    return _scale(c, k)


def _features(st, col, gloss, n, px, py, dx, n_, blink, mouth, opening, brow, look, brow_col):
    flat = (0.0, 0.0, 1.0)
    for side in (-1, 1):
        ex = CX + side * EYE_DX
        edx = px - ex
        # eyebrow: a thick arc, tapering towards the outer end
        lift = brow * 2.0 if side > 0 else 0.0
        if abs(edx + side * -0.4) < 4.2:
            t = (edx * side + 4.2) / 8.4                      # 0 inner .. 1 outer
            by = BROW_Y - lift - 0.9 * (1 - ((edx - side * 0.5) / 4.0) ** 2)
            thick = 1.25 - 0.55 * t
            if abs(py - by) < thick and n_ > 0.08:
                col = _mix(col, _scale(brow_col, 0.8 + 0.4 * n_), 0.9)
                gloss = 0.05

        hw = 3.7
        if abs(edx) > hw + 0.6:
            continue
        lid_drop = 0.7 if st.heavy_lids else 0.0
        curve = max(0.0, 1 - (edx / hw) ** 2)
        top = EYE_Y - 1.45 * curve + lid_drop
        bot = EYE_Y + 1.05 * curve
        # crease above the eye, and the hooded lid
        crease_y = EYE_Y - 2.6 * curve + lid_drop * 0.4
        if abs(edx) < hw and abs(py - crease_y) < 0.45:
            col = _scale(col, 0.84)
        if blink:
            if abs(edx) < hw and abs(py - (EYE_Y + 0.35)) < 0.55:
                col, gloss = _mix(col, (0.18, 0.11, 0.09), 0.75), 0.0
            continue
        if abs(edx) < hw + 0.3 and top - 0.75 < py <= top + 0.15:
            # upper lash line, heavier at the outer corner
            k = 0.7 + 0.3 * _clamp(edx * side / hw)
            col, gloss = _mix(col, (0.12, 0.08, 0.07), k), 0.0
            continue
        if not (top < py < bot):
            continue
        n = flat
        sclera = (0.87, 0.83, 0.80)
        shade = 0.72 if py < top + 0.9 else 0.94          # lid shadow on the eyeball
        shade *= 0.85 if abs(edx) > hw - 1.0 else 1.0       # corners
        col, gloss = _scale(sclera, shade), 0.0
        ix, iy = ex + look * 1.3, EYE_Y + 0.15
        r = math.hypot(px - ix, py - iy)
        if r < 1.8:
            col = _scale(st.eye_color, (0.55 if r > 1.4 else 0.9) * (0.75 if py < top + 0.9 else 1.0))
        if r < 0.7:
            col = (0.05, 0.04, 0.04)
        if abs(px - (ix - 0.55)) < 0.5 and abs(py - (iy - 0.55)) < 0.5:
            col = (0.95, 0.95, 0.95)                       # catchlight

    # mouth
    adx = abs(dx)
    line = MOUTH_Y - st.smile * 0.6 * (dx / 4.2) ** 2
    if adx < 4.4:
        curve = max(0.0, 1 - (dx / 4.4) ** 2)
        if mouth and _in_mouth(dx, py, opening, st.smile):
            if py < line + 0.9 and adx < 2.6:
                return (0.88, 0.85, 0.78), 0.15, (0.0, 0.0, 1.0)   # top teeth
            return (0.24, 0.07, 0.07), 0.0, (0.0, 0.0, 1.0)
        low_line = line + (opening + 0.3 if mouth else 0.0)
        if not mouth and abs(py - line) < 0.5:
            col = _mix(st.lip_color, (0.20, 0.08, 0.08), 0.55)      # lips meeting
        elif line - 1.4 * curve - 0.2 < py < line:
            col = _mix(col, _scale(st.lip_color, 0.88), _clamp(0.35 + curve))
            gloss = 0.2
        elif low_line < py < low_line + 1.9 * curve + 0.3:
            col = _mix(col, st.lip_color, _clamp(0.3 + curve))
            gloss = 0.4
        if adx > 3.9 and abs(py - (line - 0.2)) < 0.6:
            col = _scale(col, 0.85)                                 # corners

    if st.moustache:
        top = NOSE_BASE_Y + 0.6 + 0.03 * adx * adx
        bottom = line - 0.4 + max(0.0, adx - 3.6) * 1.15
        if adx < 7.3 + n_ * 0.8 and top < py < bottom:
            col = _scale(st.hair_color, 0.75 + 0.45 * n_)
            gloss = 0.15
    return col, gloss, n


def _glasses(rgb, px, py, dx, rx):
    frame = [0.10, 0.09, 0.09]
    for side in (-1, 1):
        ex = CX + side * EYE_DX
        ux, uy = (px - ex) / 4.5, (py - (EYE_Y + 0.3)) / 3.0
        r = (ux ** 4 + uy ** 4) ** 0.25                      # rounded rectangle
        if 0.86 < r < 1.08:
            return [0.45, 0.45, 0.48] if (uy < -0.7 and ux * side < -0.2) else frame
        if r <= 0.86 and -0.5 < ux - uy * 0.6 < -0.2:
            return [min(1.0, c * 0.85 + 0.18) for c in rgb]  # glint on the lens
    if abs(py - (EYE_Y - 0.9)) < 0.5 and abs(dx) < EYE_DX - 4.0:
        return frame                                         # bridge
    if abs(py - (EYE_Y - 0.9)) < 0.45 and EYE_DX + 4.4 < abs(dx) < rx + 0.5:
        return frame                                         # arms
    return rgb


def frames(style: FaceStyle) -> dict[str, bytes]:
    """The five named frames used for image-based skins."""
    return {
        "idle": render(style),
        "blink": render(style, blink=True),
        "think": render(style, brow=1, look=1),
        "talk1": render(style, mouth=1),
        "talk2": render(style, mouth=2),
    }
