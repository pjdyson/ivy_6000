"""Screen colour schemes for the UI, and a dependency-free PNG writer.

Palette keys used by the UI: S main text, D dim text / buttons, H dark accents.
(The faces themselves are drawn by ``portrait.py``.)
"""

from __future__ import annotations

import struct
import zlib

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


def to_png(rgba: bytes, width: int, height: int, scale: int = 1) -> bytes:
    """Encode RGBA bytes (top row first) as a PNG, enlarged ``scale`` times. No dependencies."""
    rows = []
    for y in range(height):
        line = rgba[y * width * 4:(y + 1) * width * 4]
        px = b"".join(line[i:i + 4] * scale for i in range(0, len(line), 4))
        rows.extend([b"\x00" + px] * scale)
    w, h = width * scale, height * scale

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))
