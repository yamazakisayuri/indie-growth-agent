"""Meterless Runtime (Nightshift) connection settings (METERLESS_* environment variables).

Contract: Meterless Runtime 0.90.0, docs/agent-ready/add-meterless-provider.md upstream.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from config import load_env

DEFAULT_BASE_URL = "http://127.0.0.1:8088/v1"
# meterless/auto routes this machine's NVIDIA lane to a model that answers 404, so the
# app pins Nemotron 3 Ultra. Any meterless/* routing mode also works here.
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
DEFAULT_APP = "indie-growth-agent"
# One Analyst answer is several tool rounds plus a long structured output; the contract's
# 180 s is the floor for a cold model load.
DEFAULT_TIMEOUT_SECONDS = 600.0
# Nightshift's cloud lanes give up waiting for the first token before Nemotron starts
# writing a long answer unless the app allows more.
DEFAULT_TTFB_MS = 240_000
PLACEHOLDER_TOKEN = "rt-local"
_APP_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_PATH_SUFFIXES = ("/chat/completions", "/models", "/healthz", "/v1")


def normalize_base_url(raw: str) -> str:
    """Any pasted runtime URL as <scheme>://<host>/v1; never /v1/v1."""
    text = raw.strip()
    if not text:
        return DEFAULT_BASE_URL
    if "://" not in text:
        text = "http://" + text
    parts = urlsplit(text)
    path = parts.path.rstrip("/")
    stripped = True
    while stripped:
        stripped = False
        for suffix in _PATH_SUFFIXES:
            if path.endswith(suffix):
                path = path[: -len(suffix)].rstrip("/")
                stripped = True
    return urlunsplit((parts.scheme, parts.netloc, f"{path}/v1", "", ""))


@dataclass(frozen=True)
class MeterlessSettings:
    base_url: str
    token: str
    model_id: str = DEFAULT_MODEL
    app: str = DEFAULT_APP
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    ttfb_ms: int = DEFAULT_TTFB_MS

    def __repr__(self) -> str:
        return (
            f"MeterlessSettings(base_url={self.base_url!r}, token='***', "
            f"model_id={self.model_id!r}, app={self.app!r})"
        )

    def headers(self, *, chat: bool = True) -> dict[str, str]:
        """Headers besides Authorization: meterless-app always, scope and TTFB on chat."""
        headers = {"meterless-app": self.app}
        if chat:
            headers["meterless-scope"] = "user"
            headers["meterless-ttfb-ms"] = str(self.ttfb_ms)
        return headers


def _positive(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    try:
        value = float(raw) if raw else default
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be > 0")
    return value


def get_meterless_settings() -> MeterlessSettings:
    """Settings for LLM_PROVIDER=meterless. Raises ValueError when incomplete or invalid."""
    load_env()
    token = os.getenv("METERLESS_RUNTIME_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "LLM_PROVIDER=meterless needs METERLESS_RUNTIME_TOKEN "
            "(the token Nightshift writes to <stateDir>/proxy-token)"
        )
    if token == PLACEHOLDER_TOKEN:
        raise ValueError(
            f"METERLESS_RUNTIME_TOKEN is the placeholder {PLACEHOLDER_TOKEN!r}; "
            "the runtime rejects it. Use the token from <stateDir>/proxy-token."
        )
    app = os.getenv("METERLESS_APP", "").strip() or DEFAULT_APP
    if not _APP_ID.match(app):
        raise ValueError("METERLESS_APP must be a lowercase id (letters, digits, hyphen)")
    return MeterlessSettings(
        base_url=normalize_base_url(os.getenv("METERLESS_BASE_URL", "")),
        token=token,
        model_id=os.getenv("METERLESS_MODEL", "").strip() or DEFAULT_MODEL,
        app=app,
        timeout_seconds=_positive("METERLESS_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS),
        ttfb_ms=int(_positive("METERLESS_TTFB_MS", DEFAULT_TTFB_MS)),
    )
