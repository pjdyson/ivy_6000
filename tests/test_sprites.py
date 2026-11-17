import itertools

from deadpan import sprites
from deadpan.skins import BUILTIN

STYLES = [s.face for s in BUILTIN.values()] + [
    sprites.FaceStyle(hair=h, heavy_lids=l, moustache=m, glasses=g, wrinkles=w, wide=wd)
    for h, l, m, g, w, wd in itertools.product(
        ("wisps", "tufts", "full", "bald"), (0, 1), (0, 1), (0, 1), (0, 1), (0, 1))
]


def test_every_frame_has_the_right_shape_and_keys():
    keys = set(".") | set(sprites.KEYS)
    for st in STYLES:
        for blink, mouth, brow, look in itertools.product((0, 1), (0, 1, 2), (0, 1), (-1, 0, 1)):
            grid = sprites.face(st, blink, mouth, brow, look)
            assert len(grid) == sprites.H
            assert all(len(r) == sprites.W for r in grid)
            assert set("".join(grid)) <= keys


def test_animation_frames_differ():
    for st in STYLES[:4]:
        base = sprites.face(st)
        assert sprites.face(st, blink=True) != base
        assert sprites.face(st, mouth=2) != sprites.face(st, mouth=1) != base
        assert sprites.face(st, brow=1) != base


def test_builtin_skins_look_different():
    faces = {tuple(sprites.face(s.face)) for s in BUILTIN.values()}
    assert len(faces) == len(BUILTIN)


def test_palettes_cover_every_key():
    for pal in sprites.PALETTES.values():
        assert set(sprites.KEYS) <= set(pal)


def test_png_encoding():
    png = sprites.to_png(sprites.face(), sprites.PALETTES["mono"], scale=2)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    w, h = int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")
    assert (w, h) == (sprites.W * 2, sprites.H * 2)
