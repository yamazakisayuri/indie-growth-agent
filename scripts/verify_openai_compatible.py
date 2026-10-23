"""Verify LLM_PROVIDER=openai_compatible against a local fake server (no external calls).

Run: python scripts/verify_openai_compatible.py
"""

from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from strands import Agent  # noqa: E402
from strands.models.openai import OpenAIModel  # noqa: E402

from llm import build_model  # noqa: E402

ENV_NAMES = (
    "LLM_PROVIDER",
    "OPENAI_COMPATIBLE_BASE_URL",
    "OPENAI_COMPATIBLE_API_KEY",
    "OPENAI_COMPATIBLE_MODEL",
    "OPENAI_COMPATIBLE_HEADERS",
    "OPENAI_COMPATIBLE_TIMEOUT_SECONDS",
)
API_KEY = "test-key-not-a-secret"
MODEL_ID = "fake/model"
REPLY = "pong"


class _FakeChatCompletions(BaseHTTPRequestHandler):
    requests: list[dict] = []

    def log_message(self, *_args) -> None:
        pass

    def do_POST(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler API
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        self.requests.append(
            {"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body}
        )
        if self.path != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            return

        def chunk(delta: dict, finish: str | None) -> bytes:
            payload = {
                "id": "chatcmpl-fake",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": body.get("model"),
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }
            return f"data: {json.dumps(payload)}\n\n".encode()

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(chunk({"role": "assistant", "content": REPLY}, None))
        self.wfile.write(chunk({}, "stop"))
        self.wfile.write(b"data: [DONE]\n\n")


def _set_env(values: dict[str, str]) -> None:
    for name in ENV_NAMES:
        # Empty string wins over .env (load_dotenv does not override).
        os.environ[name] = values.get(name, "")


def main() -> None:
    original = {name: os.environ.get(name) for name in ENV_NAMES}
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeChatCompletions)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}/v1/"
    try:
        _set_env({"LLM_PROVIDER": "openai_compatible"})
        try:
            build_model()
        except ValueError as exc:
            message = str(exc)
            for name in ENV_NAMES[1:4]:
                assert name in message, (name, message)
        else:
            raise AssertionError("missing settings must raise ValueError")
        print("OK missing settings → ValueError naming each missing variable")

        full = {
            "LLM_PROVIDER": "openai_compatible",
            "OPENAI_COMPATIBLE_BASE_URL": base_url,
            "OPENAI_COMPATIBLE_API_KEY": API_KEY,
            "OPENAI_COMPATIBLE_MODEL": MODEL_ID,
            "OPENAI_COMPATIBLE_HEADERS": '{"x-test-app": "indie-growth-agent"}',
        }
        for bad in ("not json", '["a"]', '{"x": 1}'):
            _set_env({**full, "OPENAI_COMPATIBLE_HEADERS": bad})
            try:
                build_model()
            except ValueError as exc:
                assert API_KEY not in str(exc)
            else:
                raise AssertionError(f"invalid headers must raise ValueError: {bad!r}")
        _set_env({**full, "OPENAI_COMPATIBLE_TIMEOUT_SECONDS": "0"})
        try:
            build_model()
        except ValueError:
            pass
        else:
            raise AssertionError("non-positive timeout must raise ValueError")
        print("OK invalid headers / timeout → ValueError without echoing the API key")

        _set_env(full)
        model = build_model()
        assert isinstance(model, OpenAIModel), type(model)
        assert model.get_config()["model_id"] == MODEL_ID
        assert model.client_args["base_url"] == base_url.rstrip("/")
        assert model.client_args["timeout"] == 180.0
        print("OK settings → OpenAIModel (model id, base URL without trailing slash, 180 s default timeout)")

        result = Agent(model=model, callback_handler=None)("ping")
        assert REPLY in str(result), str(result)
        chat = [r for r in _FakeChatCompletions.requests if r["path"] == "/v1/chat/completions"]
        assert len(chat) == 1, _FakeChatCompletions.requests
        sent = chat[0]
        assert sent["headers"].get("authorization") == f"Bearer {API_KEY}", sent["headers"]
        assert sent["headers"].get("x-test-app") == "indie-growth-agent", sent["headers"]
        assert sent["body"].get("model") == MODEL_ID, sent["body"]
        print("OK Agent round trip: Bearer key, extra headers and model id reach the server")

        print("\nAll OpenAI-compatible provider checks passed.")
    finally:
        server.shutdown()
        for name, value in original.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


if __name__ == "__main__":
    main()
