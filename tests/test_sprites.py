from deadpan import sprites


def test_every_frame_has_the_right_shape_and_keys():
    keys = set(".") | set(sprites.PALETTES["phosphor"])
    for blink in (False, True):
        for mouth in (0, 1, 2):
            for brow in (0, 1):
                for look in (-1, 0, 1):
                    grid = sprites.face(blink, mouth, brow, look)
                    assert len(grid) == sprites.H
                    assert all(len(r) == sprites.W for r in grid)
                    assert set("".join(grid)) <= keys


def test_animation_frames_differ():
    base = sprites.face()
    assert sprites.face(blink=True) != base
    assert sprites.face(mouth=1) != base
    assert sprites.face(mouth=2) != sprites.face(mouth=1)
    assert sprites.face(brow=1) != base
    assert sprites.face(look=1) != base


def test_palettes_cover_the_same_keys():
    ref = set(sprites.PALETTES["phosphor"])
    for pal in sprites.PALETTES.values():
        assert set(pal) == ref
