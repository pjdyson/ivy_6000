import json

from deadpan import skins
from deadpan.persona import BASE_PROMPT


def test_builtin_prompts_combine_base_and_character():
    for skin in skins.BUILTIN.values():
        prompt = skin.system_prompt()
        assert prompt.startswith(BASE_PROMPT)
        assert skin.character.strip() in prompt
        assert skin.greeting and skin.offline_lines


def test_export_then_load_round_trip(tmp_path):
    root = tmp_path / "skins"
    skins.export_skin(skins.BUILTIN["hugo"], root / "mine")
    loaded = skins.load_user_skins(root)
    skin = loaded["hugo-custom"]
    assert skin.frames and set(skin.frames) == set(skins.FRAME_NAMES)
    assert all((root / "mine" / f"{n}.png").is_file() for n in skins.FRAME_NAMES)
    assert skin.voice.rate == skins.BUILTIN["hugo"].voice.rate
    assert skin.character == skins.BUILTIN["hugo"].character


def test_minimal_procedural_skin_and_replace_base(tmp_path):
    d = tmp_path / "skins" / "plain"
    d.mkdir(parents=True)
    (d / "skin.json").write_text(json.dumps({
        "name": "Plain", "character": "Only this.", "replace_base_prompt": True,
        "palette": "amber", "face": {"hair": "bald", "glasses": True},
    }))
    skin = skins.all_skins(tmp_path / "skins")["plain"]
    assert skin.system_prompt() == "Only this."
    assert skin.face.glasses and skin.frames is None
    assert "dot" in skins.all_skins(tmp_path / "skins")


def test_broken_skins_are_skipped(tmp_path):
    d = tmp_path / "bad"
    d.mkdir()
    (d / "skin.json").write_text("{nope")
    (tmp_path / "noidle").mkdir()
    (tmp_path / "noidle" / "skin.json").write_text('{"frames": {"blink": "b.png"}}')
    assert skins.load_user_skins(tmp_path) == {}
