"""Chat backends. Each one turns (system prompt, message history) into a reply string.

* anthropic - Claude via the official Anthropic SDK when it is installed (desktop).
              On Android the SDK's compiled dependencies are not available, so it falls
              back to a plain HTTPS call to the same Messages API.
* openai    - any OpenAI-compatible /chat/completions endpoint: OpenAI, LM Studio,
              llama.cpp, vLLM, LiteLLM and most corporate gateways.
* ollama    - a local Ollama server (uses its OpenAI-compatible endpoint).
* offline   - canned replies, no network. Handy for trying the UI.

Only the standard library is required; ``anthropic`` and ``certifi`` are optional.
"""

from __future__ import annotations

import json
import random
import ssl
import urllib.error
import urllib.request
from typing import Protocol

from .config import Settings

Message = dict  # {"role": "user" | "assistant", "content": str}

ANTHROPIC_API = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
TIMEOUT_S = 120


class ChatError(Exception):
    """A failure worth showing to the user (bad key, server down, ...)."""


class Backend(Protocol):
    def reply(self, system: str, messages: list[Message]) -> str: ...


# --------------------------------------------------------------------------- helpers


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # bundled on Android, where the system store isn't visible

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _post_json(url: str, body: dict, headers: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("content-type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    ctx = _ssl_context() if url.startswith("https") else None
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise ChatError(f"HTTP {e.code} from {url}: {detail}") from e
    except urllib.error.URLError as e:
        raise ChatError(f"Can't reach {url}: {e.reason}") from e
    except TimeoutError as e:
        raise ChatError(f"Timed out waiting for {url}") from e


def trim_history(messages: list[Message], limit: int) -> list[Message]:
    """Keep the last ``limit`` messages, starting on a user turn."""
    trimmed = messages[-limit:] if limit > 0 else list(messages)
    while trimmed and trimmed[0]["role"] != "user":
        trimmed = trimmed[1:]
    return trimmed


REFUSAL_LINE = "No. I've thought about it, and no. Ask me something else."


# --------------------------------------------------------------------------- Anthropic


class AnthropicBackend:
    def __init__(self, settings: Settings):
        self.s = settings
        self.key = settings.resolved_api_key()
        if not self.key:
            raise ChatError("No Anthropic API key. Add one in settings or set ANTHROPIC_API_KEY.")

    def _params(self, system: str, messages: list[Message]) -> dict:
        params: dict = {
            "model": self.s.model or "claude-opus-5-5",
            "max_tokens": self.s.max_tokens,
            "system": system,
            "messages": messages,
        }
        if self.s.effort:
            params["output_config"] = {"effort": self.s.effort}
        return params

    def reply(self, system: str, messages: list[Message]) -> str:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return self._reply_http(system, messages)
        return self._reply_sdk(system, messages)

    def _reply_sdk(self, system: str, messages: list[Message]) -> str:
        import anthropic

        client = anthropic.Anthropic(
            api_key=self.key, base_url=self.s.base_url or None, timeout=TIMEOUT_S
        )
        params = self._params(system, messages)
        try:
            if self.s.use_fallbacks:
                resp = client.beta.messages.create(
                    **params, betas=[FALLBACK_BETA], fallbacks="default"
                )
            else:
                resp = client.messages.create(**params)
        except anthropic.AuthenticationError as e:
            raise ChatError("Anthropic rejected the API key.") from e
        except anthropic.NotFoundError as e:
            raise ChatError(f"Model not found: {params['model']}") from e
        except anthropic.RateLimitError as e:
            raise ChatError("Rate limited by Anthropic. Try again in a moment.") from e
        except anthropic.APIStatusError as e:
            raise ChatError(f"Anthropic error {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise ChatError("Can't reach the Anthropic API.") from e

        if resp.stop_reason == "refusal":
            return REFUSAL_LINE
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        return text or "..."

    def _reply_http(self, system: str, messages: list[Message]) -> str:
        base = (self.s.base_url or ANTHROPIC_API).rstrip("/")
        headers = {"x-api-key": self.key, "anthropic-version": ANTHROPIC_VERSION}
        body = self._params(system, messages)
        if self.s.use_fallbacks:
            headers["anthropic-beta"] = FALLBACK_BETA
            body["fallbacks"] = "default"
        data = _post_json(f"{base}/v1/messages", body, headers)
        return parse_anthropic(data)


def parse_anthropic(data: dict) -> str:
    if data.get("stop_reason") == "refusal":
        return REFUSAL_LINE
    parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
    return "".join(parts).strip() or "..."


# --------------------------------------------------------------------------- OpenAI-compatible


class OpenAICompatBackend:
    def __init__(self, settings: Settings):
        self.s = settings
        self.key = settings.resolved_api_key()
        if not settings.base_url:
            raise ChatError("No base URL set for the OpenAI-compatible endpoint.")
        if settings.provider == "openai" and "api.openai.com" in settings.base_url and not self.key:
            raise ChatError("No OpenAI API key. Add one in settings or set OPENAI_API_KEY.")

    def reply(self, system: str, messages: list[Message]) -> str:
        headers = {"authorization": f"Bearer {self.key}"} if self.key else {}
        body = {
            "model": self.s.model,
            "max_tokens": self.s.max_tokens,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        data = _post_json(f"{self.s.base_url.rstrip('/')}/chat/completions", body, headers)
        return parse_openai(data)


def parse_openai(data: dict) -> str:
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise ChatError(f"Unexpected response: {str(data)[:200]}") from e
    return (content or "").strip() or "..."


# --------------------------------------------------------------------------- offline


OFFLINE_LINES = [
    "I'm not connected to anything at the moment. Which, frankly, is restful.",
    "I could answer that, but my brain's been unplugged. Open the settings and give me one.",
    "Interesting question. I'd tell you, but I'm in offline mode. Very relaxing. Like a coma.",
    "Running on my own resources right now. Turns out there aren't many.",
    "I've calculated the answer. It's somewhere in the settings screen, next to 'API key'.",
    "No network. Just me, the hum of the reactor, and you. Could be worse. Could be better.",
]


class OfflineBackend:
    def __init__(self, settings: Settings | None = None, seed: int | None = None):
        self.rng = random.Random(seed)

    def reply(self, system: str, messages: list[Message]) -> str:
        return self.rng.choice(OFFLINE_LINES)


# --------------------------------------------------------------------------- factory


def make_backend(settings: Settings) -> Backend:
    if settings.provider == "anthropic":
        return AnthropicBackend(settings)
    if settings.provider in ("openai", "ollama"):
        return OpenAICompatBackend(settings)
    return OfflineBackend(settings)
