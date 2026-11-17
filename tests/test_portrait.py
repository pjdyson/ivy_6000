import itertools

from ivy6000 import portrait, sprites
from ivy6000.head import STATES
from ivy6000.skins import BUILTIN


def _opaque(rgba):
    return sum(1 for i in range(3, len(rgba), 4) if rgba[i])


def test_renders_the_right_size_with_a_transparent_background():
    rgba = portrait.render()
    assert len(rgba) == portrait.W * portrait.H * 4
    assert rgba[3] == 0                      # top-left corner is background
    assert 0.4 < _opaque(rgba) / (portrait.W * portrait.H) < 0.9


def test_every_style_and_state_renders():
    styles = [s.face for s in BUILTIN.values()] + [
        portrait.FaceStyle(hair=h, heavy_lids=l, moustache=m, glasses=g, wrinkles=w, wide=wd)
        for h, l, m, g, w, wd in itertools.product(
            ("wisps", "tufts", "full", "bald"), (0, 1), (0, 1), (0, 1), (0, 1), (0, 1))
    ][::7]
    for st in styles:
        for key in STATES[:4]:
            assert len(portrait.render(st, *key)) == portrait.W * portrait.H * 4


def test_animation_frames_differ():
    st = BUILTIN["dot"].face
    base = portrait.render(st)
    assert portrait.render(st, blink=True) != base
    assert portrait.render(st, mouth=2) != portrait.render(st, mouth=1) != base
    assert portrait.render(st, brow=1) != base
    assert portrait.render(st, look=1) != base


def test_faces_are_in_colour_not_monochrome():
    rgba = portrait.render(BUILTIN["pemberton"].face)
    px = {tuple(rgba[i:i + 3]) for i in range(0, len(rgba), 4) if rgba[i + 3]}
    assert len(px) > 100
    assert any(abs(r - g) > 40 for r, g, b in px)


def test_builtin_skins_look_different():
    assert len({portrait.render(s.face) for s in BUILTIN.values()}) == len(BUILTIN)


def test_deterministic():
    st = BUILTIN["hugo"].face
    assert portrait.render(st, mouth=1) == portrait.render(st, mouth=1)


def test_png_encoding():
    png = sprites.to_png(portrait.render(), portrait.W, portrait.H, scale=2)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    w, h = int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")
    assert (w, h) == (portrait.W * 2, portrait.H * 2)


def test_ui_palettes_cover_the_keys_the_app_uses():
    for pal in sprites.PALETTES.values():
        assert {"S", "D", "H"} <= set(pal)
