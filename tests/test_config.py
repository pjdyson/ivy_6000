from deadpan import config


def test_round_trip(tmp_path):
    p = tmp_path / "s.json"
    s = config.Settings().with_provider("ollama")
    s.skin = "hugo"
    s.voice_enabled = False
    config.save(s, p)
    assert config.load(p) == s


def test_unknown_keys_and_bad_json_are_tolerated(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    p = tmp_path / "s.json"
    p.write_text('{"provider": "openai", "nonsense": 1}')
    assert config.load(p).provider == "openai"
    p.write_text("{not json")
    assert config.load(p).provider == "offline"


def test_env_key_and_default_provider(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    s = config.default_settings()
    assert s.provider == "anthropic"
    assert s.model == "claude-opus-5-5"
    assert s.resolved_api_key() == "sk-test"
