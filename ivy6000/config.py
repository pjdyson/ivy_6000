"""Settings: a small JSON file in the app's user-data directory."""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import asdict, dataclass, fields
from pathlib import Path

PROVIDERS = ("anthropic", "lmstudio", "ollama", "openai", "offline")

# Sensible defaults per provider, applied when the user switches provider.
PROVIDER_DEFAULTS = {
    "anthropic": {"model": "claude-opus-5-5", "base_url": ""},
    "openai": {"model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1"},
    # Blank model = use whichever model the local server has loaded.
    "lmstudio": {"model": "", "base_url": "http://localhost:1234/v1"},
    "ollama": {"model": "", "base_url": "http://localhost:11434/v1"},
    "offline": {"model": "", "base_url": ""},
}

ENV_KEYS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


@dataclass
class Settings:
    provider: str = "offline"
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    # A ceiling, not a target: the persona keeps replies short. Generous enough that a
    # model which thinks first (Claude, Qwen3, DeepSeek-R1) still has room to answer.
    max_tokens: int = 1200
    # Anthropic only. "low" keeps chat snappy; blank leaves it to the model default.
    effort: str = "low"
    # Anthropic only: let the API retry a declined request on a fallback model.
    use_fallbacks: bool = True
    skin: str = "dot"
    voice_enabled: bool = True
    # "auto": natural neural voice (Piper) if installed, else the system voice.
    voice_engine: str = "auto"
    # Exact voice name to use instead of the skin's preference (e.g. "Daniel", "en-gb+m3").
    voice_name: str = ""
    # Voice input: the MIC button listens through the microphone (needs vosk + sounddevice).
    mic_enabled: bool = True
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


LOCAL_PROVIDERS = ("lmstudio", "ollama")


def _local_server_up(base_url: str, timeout: float = 0.4) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url}/models", timeout=timeout) as resp:
            return resp.status == 200
    except (OSError, ValueError):
        return False


def default_settings(probe=_local_server_up) -> Settings:
    """First launch: use a cloud key if one is set, else a local server if one is running."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return Settings().with_provider("anthropic")
    if os.environ.get("OPENAI_API_KEY"):
        return Settings().with_provider("openai")
    for provider in LOCAL_PROVIDERS:
        if probe(PROVIDER_DEFAULTS[provider]["base_url"]):
            return Settings().with_provider(provider)
    return Settings()


def load(path: Path) -> Settings:
    if not path.exists():
        return default_settings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default_settings()
    if raw.get("max_tokens") in (1024, 2048):  # old defaults: move to the new one
        raw.pop("max_tokens")
    known = {f.name for f in fields(Settings)}
    return Settings(**{k: v for k, v in raw.items() if k in known})


def save(settings: Settings, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
