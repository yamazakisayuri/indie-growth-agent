"""Talk to the Meterless Runtime directly: connection status, Auto Detect, one text request.

Status follows the contract: GET /v1/models decides, /healthz only proves the process is up.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

from .settings import MeterlessSettings, normalize_base_url

State = Literal["online", "unauthorized", "offline"]
DETECT_PORTS = (8088, 8090, 8787, 11434)
DETECT_HOSTS = ("127.0.0.1", "localhost", "[::1]")
STATUS_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class RuntimeStatus:
    state: State
    base_url: str
    model_ids: tuple[str, ...] = ()
    detail: str = ""


def probe(
    base_url: str,
    token: str,
    *,
    app: str,
    timeout: float = STATUS_TIMEOUT_SECONDS,
    client: httpx.Client | None = None,
) -> RuntimeStatus:
    """401 / 403 is unauthorized, 200 listing meterless/* ids is online, anything else offline."""
    url = normalize_base_url(base_url)
    owned = client is None
    http = client or httpx.Client(timeout=timeout)
    try:
        response = http.get(
            f"{url}/models",
            headers={"Authorization": f"Bearer {token}", "meterless-app": app},
        )
    except httpx.HTTPError as exc:
        return RuntimeStatus("offline", url, detail=f"{type(exc).__name__}: {exc}")
    finally:
        if owned:
            http.close()
    if response.status_code in (401, 403):
        return RuntimeStatus("unauthorized", url, detail=f"HTTP {response.status_code}")
    if response.status_code != 200:
        return RuntimeStatus("offline", url, detail=f"HTTP {response.status_code}")
    try:
        data = response.json().get("data") or []
        ids = tuple(str(m["id"]) for m in data if isinstance(m, dict) and m.get("id"))
    except (ValueError, AttributeError, TypeError):
        return RuntimeStatus("offline", url, detail="HTTP 200 without a model list")
    if not any(i.startswith("meterless/") for i in ids):
        return RuntimeStatus("offline", url, ids, "HTTP 200 but no meterless/* model ids")
    return RuntimeStatus("online", url, ids)


def detect(token: str, *, app: str, client: httpx.Client | None = None) -> RuntimeStatus | None:
    """First online or unauthorized runtime on the contract's ports and hosts, else None."""
    for port in DETECT_PORTS:
        for host in DETECT_HOSTS:
            status = probe(f"http://{host}:{port}", token, app=app, client=client)
            if status.state != "offline":
                return status
    return None


@dataclass(frozen=True)
class TextReply:
    status_code: int
    seconds: float
    text: str = ""
    routing: dict[str, Any] = field(default_factory=dict)
    error: Any = None


def text_request(
    settings: MeterlessSettings,
    prompt: str,
    *,
    max_tokens: int = 200,
    client: httpx.Client | None = None,
) -> TextReply:
    """One non-streaming chat request; routing holds what the runtime says it did."""
    owned = client is None
    http = client or httpx.Client(timeout=settings.timeout_seconds)
    started = time.monotonic()
    try:
        response = http.post(
            f"{settings.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.token}", **settings.headers()},
            json={
                "model": settings.model_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            },
        )
    finally:
        if owned:
            http.close()
    seconds = round(time.monotonic() - started, 1)
    try:
        body = response.json()
    except ValueError:
        return TextReply(response.status_code, seconds, error=response.text[:500])
    meterless = body.get("meterless") if isinstance(body, dict) else None
    routing: dict[str, Any] = {}
    if isinstance(meterless, dict):
        routing = {
            k: meterless[k]
            for k in ("requested_model", "provider_model", "mode", "scope", "app")
            if k in meterless
        }
        receipt = meterless.get("compute_receipt")
        if isinstance(receipt, dict) and receipt.get("winning_route") is not None:
            routing["winning_route"] = receipt["winning_route"]
    if response.status_code != 200 or not isinstance(body, dict) or body.get("error"):
        error = body.get("error") if isinstance(body, dict) else body
        return TextReply(response.status_code, seconds, routing=routing, error=error)
    choices = body.get("choices") or [{}]
    text = str((choices[0].get("message") or {}).get("content") or "")
    return TextReply(response.status_code, seconds, text=text, routing=routing)
