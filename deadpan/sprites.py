"""The pixel-art head, generated as a grid of palette keys (pure Python, no Kivy).

Keys: '.' empty, S skin, D shade/outline, H hair/brows, W eye white, P pupil,
M mouth, T teeth.
"""

from __future__ import annotations

W, H = 32, 36

PALETTES = {
    # Green CRT phosphor.
    "phosphor": {
        "S": (0.55, 0.95, 0.62), "D": (0.20, 0.55, 0.28), "H": (0.12, 0.38, 0.18),
        "W": (0.85, 1.00, 0.88), "P": (0.03, 0.15, 0.06), "M": (0.05, 0.22, 0.09),
        "T": (0.80, 1.00, 0.84),
    },
    "amber": {
        "S": (1.00, 0.72, 0.30), "D": (0.62, 0.38, 0.10), "H": (0.40, 0.22, 0.05),
        "W": (1.00, 0.92, 0.75), "P": (0.15, 0.07, 0.00), "M": (0.25, 0.12, 0.02),
        "T": (1.00, 0.90, 0.70),
    },
    "mono": {
        "S": (0.78, 0.80, 0.84), "D": (0.42, 0.44, 0.48), "H": (0.26, 0.27, 0.30),
        "W": (0.97, 0.97, 1.00), "P": (0.05, 0.05, 0.07), "M": (0.12, 0.12, 0.14),
        "T": (0.92, 0.92, 0.95),
    },
}

CX, CY = 15.5, 17.5
RX, RY = 11.5, 15.5


def face(blink: bool = False, mouth: int = 0, brow: int = 0, look: int = 0) -> list[str]:
    """Return H rows of W characters.

    blink: eyes closed. mouth: 0 closed, 1 half open, 2 open.
    brow: 0 level, 1 raised (one eyebrow, sceptical). look: -1 left, 0 ahead, 1 right.
    """
    g = [["."] * W for _ in range(H)]

    def put(x: int, y: int, k: str) -> None:
        if 0 <= x < W and 0 <= y < H:
            g[y][x] = k

    # Head: an ellipse, darker at the rim.
    for y in range(H):
        for x in range(W):
            d = ((x - CX) / RX) ** 2 + ((y - CY) / RY) ** 2
            if d <= 1.0:
                g[y][x] = "D" if d > 0.86 else "S"

    # Ears.
    for y in range(15, 22):
        for x in (4, 27):
            put(x, y, "D")
        if 16 <= y <= 20:
            put(3, y, "S")
            put(28, y, "S")
            put(2, y, "D")
            put(29, y, "D")

    # Receding hair: tufts on the sides, a few strands on top.
    for y in range(5, 13):
        for x in range(W):
            d = ((x - CX) / RX) ** 2 + ((y - CY) / RY) ** 2
            if 0.72 < d <= 1.0 and abs(x - CX) > 8:
                g[y][x] = "H"
    for x in (12, 14, 17, 19):
        put(x, 3, "H")

    # Eyebrows.
    ly = 11
    ry = 11 - brow
    for x in range(9, 13):
        put(x, ly, "H")
    for x in range(19, 23):
        put(x, ry, "H")
    if brow:
        put(22, ry + 1, "H")

    # Eyes.
    for ex in (9, 19):
        if blink:
            for x in range(ex, ex + 4):
                put(x, 14, "D")
        else:
            for y in (13, 14):
                for x in range(ex, ex + 4):
                    put(x, y, "W")
            px = ex + 1 + look
            for y in (13, 14):
                put(px, y, "P")
                put(px + 1, y, "P")
        # bags under the eyes: the look of someone up for three million years
        for x in range(ex, ex + 4):
            put(x, 16, "D")

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

    # Chin line.
    for x in range(13, 19):
        put(x, 30, "D")

    return ["".join(r) for r in g]
