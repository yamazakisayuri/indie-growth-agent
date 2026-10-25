"""Verify LLM_PROVIDER=meterless, the runtime status check, and model error handling. No network.

Run: python scripts/verify_meterless.py

A local fake server stands in for Nightshift; httpx.MockTransport stands in for /v1/models.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import openai

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from strands import Agent  # noqa: E402
from strands.models.openai import OpenAIModel  # noqa: E402
from strands.types.exceptions import EventLoopException  # noqa: E402

import evidence.agents as agents  # noqa: E402
from evidence import AnalystOutput, SQLiteEvidenceStore  # noqa: E402
from evidence.loop import run_evidence_loop  # noqa: E402
from evidence.sources import ASC_DAILY, EXTERNAL_TABLE_NAMES, INTERNAL_TABLE_NAMES  # noqa: E402
from integrations.meterless import (  # noqa: E402
    detect,
    get_meterless_settings,
    normalize_base_url,
    probe,
    text_request,
)
from llm import (  # noqa: E402
    build_model,
    describe_model_error,
    describe_provider,
    is_retryable,
    model_label,
)

ENV_NAMES = (
    "LLM_PROVIDER",
    "METERLESS_BASE_URL",
    "METERLESS_RUNTIME_TOKEN",
    "METERLESS_MODEL",
    "METERLESS_APP",
    "METERLESS_TIMEOUT_SECONDS",
    "METERLESS_TTFB_MS",
)
TOKEN = "test-runtime-token-not-a-secret"
REPLY = "pong"
STREAM_ERROR = {"message": "Meterless provider request failed.", "type": "provider_error",
                "code": "lane_failed", "lane": "nvidia"}


def _set_env(values: dict[str, str]) -> None:
    for name in ENV_NAMES:
        # Empty string wins over .env (load_dotenv does not override).
        os.environ[name] = values.get(name, "")


class _FakeNightshift(BaseHTTPRequestHandler):
    requests: list[dict] = []

    def log_message(self, *_args) -> None:
        pass

    def do_POST(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler API
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        self.requests.append({"headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})

        def chunk(delta: dict, finish: str | None) -> bytes:
            payload = {
                "id": "chatcmpl-fake", "object": "chat.completion.chunk", "created": 0,
                "model": body.get("model"),
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }
            return f"data: {json.dumps(payload)}\n\n".encode()

        if "status500" in json.dumps(body.get("messages")):
            payload = json.dumps({"error": {"message": "runtime down"}}).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        if "fail" in json.dumps(body.get("messages")):
            self.wfile.write(f"data: {json.dumps({'error': STREAM_ERROR})}\n\n".encode())
            return
        self.wfile.write(chunk({"role": "assistant", "content": REPLY}, None))
        self.wfile.write(chunk({}, "stop"))
        self.wfile.write(b"data: [DONE]\n\n")


def check_urls() -> None:
    cases = {
        "": "http://127.0.0.1:8088/v1",
        "127.0.0.1:8088": "http://127.0.0.1:8088/v1",
        "http://127.0.0.1:8088/": "http://127.0.0.1:8088/v1",
        "http://127.0.0.1:8088/v1": "http://127.0.0.1:8088/v1",
        "http://127.0.0.1:8088/v1/": "http://127.0.0.1:8088/v1",
        "http://127.0.0.1:8088/v1/chat/completions": "http://127.0.0.1:8088/v1",
        "http://127.0.0.1:8088/v1/models": "http://127.0.0.1:8088/v1",
        "http://127.0.0.1:8088/healthz": "http://127.0.0.1:8088/v1",
        "http://localhost:8090/v1/v1": "http://localhost:8090/v1",
        "[::1]:8787": "http://[::1]:8787/v1",
        "https://box.example/v1/models": "https://box.example/v1",
    }
    for raw, expected in cases.items():
        assert normalize_base_url(raw) == expected, (raw, normalize_base_url(raw))
    print("OK pasted URLs (no scheme, /v1, /v1/chat/completions, /v1/models, /healthz) → <host>/v1")


def check_settings() -> None:
    _set_env({"LLM_PROVIDER": "meterless"})
    for env, needle in (({}, "METERLESS_RUNTIME_TOKEN"),
                        ({"METERLESS_RUNTIME_TOKEN": "rt-local"}, "placeholder"),
                        ({"METERLESS_RUNTIME_TOKEN": TOKEN, "METERLESS_APP": "Indie Growth"},
                         "METERLESS_APP"),
                        ({"METERLESS_RUNTIME_TOKEN": TOKEN, "METERLESS_TIMEOUT_SECONDS": "0"},
                         "METERLESS_TIMEOUT_SECONDS")):
        _set_env({"LLM_PROVIDER": "meterless", **env})
        try:
            build_model()
        except ValueError as exc:
            assert needle in str(exc) and TOKEN not in str(exc), exc
        else:
            raise AssertionError(f"must raise ValueError for {env}")
    _set_env({"LLM_PROVIDER": "meterless", "METERLESS_RUNTIME_TOKEN": TOKEN})
    s = get_meterless_settings()
    assert (s.base_url, s.model_id, s.app) == (
        "http://127.0.0.1:8088/v1", "nvidia/nemotron-3-ultra-550b-a55b", "indie-growth-agent"
    )
    assert s.timeout_seconds == 600 and s.ttfb_ms == 240_000
    assert TOKEN not in repr(s)
    assert s.headers() == {
        "meterless-app": "indie-growth-agent", "meterless-scope": "user", "meterless-ttfb-ms": "240000"
    }
    assert s.headers(chat=False) == {"meterless-app": "indie-growth-agent"}
    assert model_label() == "meterless:nvidia/nemotron-3-ultra-550b-a55b"
    line = describe_provider()
    assert "Nightshift" in line and "127.0.0.1:8088" in line and TOKEN not in line, line
    print("OK settings: token required, rt-local rejected, Nemotron Ultra pinned by default, "
          "token never in repr / errors / log line")


def check_status() -> None:
    seen: list[httpx.Request] = []

    def responder(status: int, body: object = None):
        def handle(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(status, json=body)
        return httpx.Client(transport=httpx.MockTransport(handle))

    models = {"data": [{"id": "meterless/auto"}, {"id": "nvidia/nemotron-3-ultra-550b-a55b"}]}
    online = probe("127.0.0.1:8088", TOKEN, app="indie-growth-agent", client=responder(200, models))
    assert online.state == "online" and "meterless/auto" in online.model_ids, online
    assert str(seen[-1].url) == "http://127.0.0.1:8088/v1/models"
    assert seen[-1].headers["authorization"] == f"Bearer {TOKEN}"
    assert seen[-1].headers["meterless-app"] == "indie-growth-agent"
    for code in (401, 403):
        state = probe("x:1", TOKEN, app="a", client=responder(code, {"error": "no"})).state
        assert state == "unauthorized", (code, state)
    assert probe("x:1", TOKEN, app="a", client=responder(500, {})).state == "offline"
    assert probe("x:1", TOKEN, app="a", client=responder(200, {"data": [{"id": "gpt"}]})).state == "offline"

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    down = probe("x:1", TOKEN, app="a", client=httpx.Client(transport=httpx.MockTransport(refuse)))
    assert down.state == "offline" and "ConnectError" in down.detail

    def only_8090(request: httpx.Request) -> httpx.Response:
        if request.url.port == 8090 and request.url.host == "localhost":
            return httpx.Response(401)
        raise httpx.ConnectError("refused", request=request)

    found = detect(TOKEN, app="a", client=httpx.Client(transport=httpx.MockTransport(only_8090)))
    assert found is not None and found.state == "unauthorized"
    assert found.base_url == "http://localhost:8090/v1", found
    print("OK status: 200 with meterless ids online, 401/403 unauthorized, else offline; "
          "Auto Detect finds the first answering port")

    receipt = {
        "choices": [{"message": {"content": "OK"}}],
        "meterless": {"requested_model": "nvidia/nemotron-3-ultra-550b-a55b",
                      "provider_model": "nemotron-3-ultra", "app": "indie-growth-agent",
                      "compute_receipt": {"winning_route": {"model": "nemotron-3-ultra"}}},
    }
    reply = text_request(get_meterless_settings(), "hi", client=responder(200, receipt))
    assert reply.text == "OK" and reply.routing["winning_route"] == {"model": "nemotron-3-ultra"}
    assert seen[-1].headers["meterless-scope"] == "user"
    failed = text_request(get_meterless_settings(), "hi", client=responder(502, {"error": STREAM_ERROR}))
    assert failed.error == STREAM_ERROR and not failed.text
    print("OK text request: reply and compute_receipt route are read; an error body is kept")


def check_model_round_trip() -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeNightshift)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"127.0.0.1:{server.server_address[1]}/v1/models"
    _set_env({"LLM_PROVIDER": "meterless", "METERLESS_BASE_URL": base,
              "METERLESS_RUNTIME_TOKEN": TOKEN, "METERLESS_APP": "igrowth-test"})
    model = build_model()
    assert isinstance(model, OpenAIModel), type(model)
    assert model.client_args["base_url"] == f"http://127.0.0.1:{server.server_address[1]}/v1"
    result = Agent(model=model, callback_handler=None)("ping")
    assert REPLY in str(result), str(result)
    sent = _FakeNightshift.requests[-1]
    assert sent["headers"]["authorization"] == f"Bearer {TOKEN}"
    assert sent["headers"]["meterless-app"] == "igrowth-test"
    assert sent["headers"]["meterless-scope"] == "user"
    assert sent["headers"]["meterless-ttfb-ms"] == "240000"
    assert sent["body"]["model"] == "nvidia/nemotron-3-ultra-550b-a55b"
    print("OK Agent round trip: Bearer token, meterless-app / -scope / -ttfb-ms and the pinned "
          "model reach the runtime")

    try:
        Agent(model=build_model(), callback_handler=None)("please fail")
    except Exception as exc:  # noqa: BLE001
        detail = describe_model_error(exc)
        assert is_retryable(exc)
        assert "Meterless provider request failed." in detail and "lane_failed" in detail, detail
        assert "/chat/completions" in detail and TOKEN not in detail
    else:
        raise AssertionError("a streamed error must raise")
    print("OK a streamed runtime error keeps its body (type, code, lane) and request URL, "
          "and counts as retryable")
    check_sdk_retries()
    server.shutdown()
    return base


def check_sdk_retries() -> None:
    """Evidence agents turn the openai client's retries off; other agents keep the default."""

    def sent_500s() -> int:
        return sum("status500" in json.dumps(r["body"].get("messages")) for r in _FakeNightshift.requests)

    default = build_model()
    assert "max_retries" not in default.client_args, default.client_args
    before = sent_500s()
    try:
        Agent(model=default, callback_handler=None)("status500 default")
    except Exception:  # noqa: BLE001
        pass
    assert sent_500s() - before == 3, "SDK default: one request plus two silent retries"

    seen: list[dict] = []

    class CaptureAgent:
        def __init__(self, **kwargs) -> None:
            seen.append(kwargs)

        def __call__(self, prompt, **kwargs):
            return _Result(GOOD)

    original = agents.Agent
    agents.Agent = CaptureAgent
    store = SQLiteEvidenceStore()
    try:
        agents.StrandsAnalyst(store)("p")
        agents.StrandsCritic(store)("p")
    finally:
        agents.Agent = original
        store.close()
    assert [kw["model"].client_args["max_retries"] for kw in seen] == [0, 0], seen

    before = sent_500s()
    try:
        Agent(model=seen[0]["model"], callback_handler=None)("status500 evidence")
    except Exception as exc:  # noqa: BLE001
        assert is_retryable(exc), exc
    else:
        raise AssertionError("HTTP 500 must raise")
    assert sent_500s() - before == 1, "Evidence agents: no silent SDK retry"
    print("OK Analyst / Critic models send one request per attempt (SDK max_retries=0; the app "
          "retries once); other agents keep the SDK default of 2 retries")


def _api_error(message: str = "Meterless provider request failed.") -> Exception:
    request = httpx.Request("POST", "http://127.0.0.1:8088/v1/chat/completions")
    error = openai.APIError(message, request, body=STREAM_ERROR)
    wrapped = EventLoopException(error, {})
    wrapped.__cause__ = error
    return wrapped


def _auth_error() -> Exception:
    request = httpx.Request("POST", "http://127.0.0.1:8088/v1/chat/completions")
    response = httpx.Response(401, request=request, json={"error": {"message": "bad token"}})
    return openai.AuthenticationError("bad token", response=response, body={"message": "bad token"})


class _Result:
    def __init__(self, output) -> None:
        self.structured_output = output


GOOD = AnalystOutput.model_validate({"most_important_finding": "f", "claims": [], "actions": []})


def _fake_agent(behaviour: list):
    """An Agent stand-in that raises or answers from behaviour, one item per call."""
    calls: list[str] = []

    class FakeAgent:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def __call__(self, prompt, **kwargs):
            calls.append(prompt)
            item = behaviour.pop(0)
            if isinstance(item, Exception):
                raise item
            return _Result(item)

    return FakeAgent, calls


def check_retry() -> None:
    store = SQLiteEvidenceStore()
    original = agents.Agent
    records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Capture()
    agents.logger.addHandler(handler)
    try:
        agents.Agent, calls = _fake_agent([_api_error(), GOOD])
        output, _ = agents.StrandsAnalyst(store)("p")
        assert output is GOOD and len(calls) == 2
        warning = records[-1].getMessage()
        assert "retrying once" in warning and "lane_failed" in warning, warning
        print("OK a provider error streamed mid-answer is retried once with a fresh Agent and logged")

        agents.Agent, calls = _fake_agent([_api_error(), _api_error()])
        try:
            agents.StrandsCritic(store)("p")
        except agents.ModelCallError as exc:
            assert "Critic" in str(exc) and "attempt 2 of 2" in str(exc) and "lane_failed" in str(exc)
        else:
            raise AssertionError("two provider errors must raise ModelCallError")
        assert len(calls) == 2

        agents.Agent, calls = _fake_agent([_auth_error()])
        try:
            agents.StrandsAnalyst(store)("p")
        except agents.ModelCallError as exc:
            assert "AuthenticationError" in str(exc) and "HTTP 401" in str(exc), exc
        else:
            raise AssertionError("auth errors must raise ModelCallError")
        assert len(calls) == 1

        agents.Agent, calls = _fake_agent([ValueError("not a provider problem")])
        try:
            agents.StrandsAnalyst(store)("p")
        except ValueError as exc:
            assert not isinstance(exc, agents.ModelCallError)
        else:
            raise AssertionError("non-provider errors must propagate unchanged")
        assert len(calls) == 1
        print("OK no retry for 401 or non-provider errors; a second failure raises ModelCallError "
              "with the details")

        store.replace_table(
            ASC_DAILY,
            [{"date": f"2026-10-{d:02d}", "app_id": "1", "territory": "ALL", "impressions": 1,
              "product_page_views": 1, "first_time_downloads": 1, "source": "s"} for d in range(9, 23)],
        )
        agents.Agent, _ = _fake_agent([_api_error(), _api_error()])
        run = run_evidence_loop(
            run_id="t", product_id="p", product_name="P", store=store,
            analyst=agents.StrandsAnalyst(store), critic=agents.StrandsCritic(store),
            internal_tables=INTERNAL_TABLE_NAMES, external_tables=EXTERNAL_TABLE_NAMES,
        )
        assert run.status == "error" and run.error and run.error.startswith("ModelCallError"), run.error
        assert "Meterless provider request failed." in run.error and "lane_failed" in run.error
        print("OK a failed run stores why the runtime refused, not just its one-line message")
    finally:
        agents.Agent = original
        agents.logger.removeHandler(handler)
        store.close()


def check_error_summary() -> None:
    from botocore.exceptions import ClientError, NoCredentialsError

    from llm import summarize_model_error

    request = httpx.Request("POST", "http://127.0.0.1:8088/v1/chat/completions")
    key_missing = openai.APIError(
        "Meterless provider request failed.",
        request,
        body={"message": "secret-ish free text", "type": "api_error", "code": "provider_error",
              "meterless_detail": "nvidia_key_missing"},
    )
    wrapped = EventLoopException(key_missing, {})
    wrapped.__cause__ = key_missing
    summary = summarize_model_error(wrapped)
    assert summary is not None and summary.reason == "nvidia_key_missing", summary
    free_text = openai.APIError("x", request, body={"code": "not a code; free text", "type": "api_error"})
    assert summarize_model_error(free_text).reason == "api_error"
    assert summarize_model_error(openai.APIError("x", request, body=None)).reason == "APIError"
    assert summarize_model_error(_auth_error()).status == 401

    denied = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "account 123 has no access"},
         "ResponseMetadata": {"HTTPStatusCode": 403}},
        "ConverseStream",
    )
    try:
        raise RuntimeError("wrapped") from denied
    except RuntimeError as exc:
        summary = summarize_model_error(exc)
    assert summary is not None and (summary.reason, summary.status) == ("AccessDeniedException", 403)
    assert summarize_model_error(NoCredentialsError()).reason == "NoCredentialsError"
    assert summarize_model_error(ValueError("not a model error")) is None
    print("OK model errors are summarized as a code-like reason and status only (Meterless "
          "meterless_detail, Bedrock error code or credential error), never body text")


def main() -> None:
    original = {name: os.environ.get(name) for name in ENV_NAMES}
    try:
        check_urls()
        check_settings()
        check_status()
        check_model_round_trip()
        check_retry()
        check_error_summary()
        print("\nAll Meterless checks passed.")
    finally:
        for name, value in original.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


if __name__ == "__main__":
    main()
