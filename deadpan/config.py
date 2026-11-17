"""Settings: a small JSON file in the app's user-data directory."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

PROVIDERS = ("anthropic", "openai", "ollama", "offline")

# Sensible defaults per provider, applied when the user switches provider.
PROVIDER_DEFAULTS = {
    "anthropic": {"model": "claude-opus-5-5", "base_url": ""},
    "openai": {"model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1"},
    "ollama": {"model": "llama3.2", "base_url": "http://localhost:11434/v1"},
    "offline": {"model": "", "base_url": ""},
}

ENV_KEYS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


@dataclass
class Settings:
    provider: str = "offline"
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    max_tokens: int = 1024
    # Anthropic only. "low" keeps chat snappy; blank leaves it to the model default.
    effort: str = "low"
    # Anthropic only: let the API retry a declined request on a fallback model.
    use_fallbacks: bool = True
    # Empty means use deadpan.persona.SYSTEM_PROMPT.
    persona: str = ""
    palette: str = "phosphor"
    history_limit: int = 20

    def resolved_api_key(self) -> str:
        if self.api_key:
            return self.api_key
        env = ENV_KEYS.get(self.provider)
        return os.environ.get(env, "") if env else ""

    def with_provider(self, provider: str) -> "Settings":
        data = asdict(self)
        data["provider"] = provider
        data.update(PROVIDER_DEFAULTS.get(provider, {}))
        return Settings(**data)


def default_settings() -> Settings:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return Settings().with_provider("anthropic")
    if os.environ.get("OPENAI_API_KEY"):
        return Settings().with_provider("openai")
    return Settings()


def load(path: Path) -> Settings:
    if not path.exists():
        return default_settings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default_settings()
    known = {f.name for f in fields(Settings)}
    return Settings(**{k: v for k, v in raw.items() if k in known})


def save(settings: Settings, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
