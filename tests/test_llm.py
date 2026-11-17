import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from deadpan import llm
from deadpan.config import Settings


@pytest.fixture
def server():
    """A local HTTP server that records the request and returns a canned body."""
    state = {"response": {}, "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            state["requests"].append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
            out = json.dumps(state["response"]).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{httpd.server_port}"
    yield state
    httpd.shutdown()


def test_trim_history_starts_on_user():
    msgs = [{"role": r, "content": str(i)} for i, r in enumerate(["user", "assistant"] * 5)]
    out = llm.trim_history(msgs, 3)
    assert out[0]["role"] == "user" and len(out) == 2


def test_openai_compatible(server):
    server["response"] = {"choices": [{"message": {"content": " Flatly, yes. "}}]}
    s = Settings(provider="ollama", model="llama3.2", base_url=server["url"] + "/v1")
    reply = llm.make_backend(s).reply("SYS", [{"role": "user", "content": "hi"}])
    assert reply == "Flatly, yes."
    req = server["requests"][0]
    assert req["path"] == "/v1/chat/completions"
    assert req["body"]["messages"][0] == {"role": "system", "content": "SYS"}


def test_anthropic_raw_http(server, monkeypatch):
    # Simulate Android, where the SDK isn't installed.
    monkeypatch.setitem(sys.modules, "anthropic", None)
    server["response"] = {
        "stop_reason": "end_turn",
        "content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": "Hello."}],
    }
    s = Settings(provider="anthropic", model="claude-opus-5-5", api_key="k", base_url=server["url"])
    assert llm.make_backend(s).reply("SYS", [{"role": "user", "content": "hi"}]) == "Hello."
    req = server["requests"][0]
    assert req["path"] == "/v1/messages"
    assert req["headers"]["x-api-key"] == "k"
    assert req["headers"]["anthropic-beta"] == llm.FALLBACK_BETA
    assert req["body"]["fallbacks"] == "default"
    assert req["body"]["output_config"] == {"effort": "low"}
    assert req["body"]["system"] == "SYS"


def test_anthropic_sdk_path(server):
    pytest.importorskip("anthropic")
    server["response"] = {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "stop_reason": "end_turn", "stop_sequence": None,
        "content": [{"type": "text", "text": "Via the SDK."}],
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    s = Settings(provider="anthropic", model="claude-opus-5-5", api_key="k", base_url=server["url"])
    assert llm.make_backend(s).reply("SYS", [{"role": "user", "content": "hi"}]) == "Via the SDK."
    req = server["requests"][0]
    assert req["body"]["fallbacks"] == "default"
    assert llm.FALLBACK_BETA in req["headers"]["anthropic-beta"]


def test_refusal_is_answered_in_character():
    assert llm.parse_anthropic({"stop_reason": "refusal", "content": []}) == llm.REFUSAL_LINE


def test_missing_key_is_a_chat_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(llm.ChatError):
        llm.make_backend(Settings(provider="anthropic"))


def test_unreachable_server_is_a_chat_error():
    s = Settings(provider="ollama", model="m", base_url="http://127.0.0.1:9/v1")
    with pytest.raises(llm.ChatError):
        llm.make_backend(s).reply("S", [{"role": "user", "content": "x"}])


def test_offline():
    assert llm.OfflineBackend(seed=1).reply("S", []) in llm.OFFLINE_LINES
    assert llm.OfflineBackend(["only"]).reply("S", []) == "only"
