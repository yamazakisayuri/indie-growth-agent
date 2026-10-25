"""Make a failed model request explain itself, and say whether one retry may help.

Strands wraps the provider's exception (often in EventLoopException), and a streamed
error keeps the runtime's error object only in openai.APIError.body, so str(exc)
alone loses the reason.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

try:
    import openai
except ImportError:  # Bedrock-only installs
    openai = None  # type: ignore[assignment]

_SECRET_ENV = ("METERLESS_RUNTIME_TOKEN", "OPENAI_COMPATIBLE_API_KEY")
MAX_BODY_CHARS = 1000
# A reason is kept only if it looks like an error code, never free text from a response body.
_SAFE_REASON = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,63}$")


def find_api_error(exc: BaseException) -> BaseException | None:
    """The openai.APIError in exc's cause chain, if any."""
    if openai is None:
        return None
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, openai.APIError):
            return current
        current = current.__cause__ or current.__context__
    return None


def is_retryable(exc: BaseException) -> bool:
    """Lost connections, timeouts, 5xx, 429, and errors streamed mid-answer; not 4xx client errors."""
    api = find_api_error(exc)
    if api is None:
        return False
    return not isinstance(
        api,
        (
            openai.AuthenticationError,
            openai.PermissionDeniedError,
            openai.BadRequestError,
            openai.NotFoundError,
            openai.UnprocessableEntityError,
            openai.ConflictError,
        ),
    )


def _redact(text: str) -> str:
    for name in _SECRET_ENV:
        secret = os.environ.get(name, "").strip()
        if secret:
            text = text.replace(secret, "<redacted>")
    return text


def describe_model_error(exc: BaseException) -> str:
    """One line: error type and message, HTTP status, request, and the runtime's error body."""
    api = find_api_error(exc)
    if api is None:
        return _redact(f"{type(exc).__name__}: {exc}")
    parts = [f"{type(api).__name__}: {getattr(api, 'message', api)}"]
    status = getattr(api, "status_code", None)
    if status is not None:
        parts.append(f"HTTP {status}")
    request = getattr(api, "request", None)
    if request is not None:
        parts.append(f"{request.method} {request.url}")
    request_id = getattr(api, "request_id", None)
    if request_id:
        parts.append(f"request_id={request_id}")
    body = getattr(api, "body", None)
    if body is not None:
        parts.append("body=" + json.dumps(body, ensure_ascii=False, default=str)[:MAX_BODY_CHARS])
    cause = api.__cause__
    if cause is not None:
        parts.append(f"cause={type(cause).__name__}: {cause}")
    return _redact(" | ".join(parts))


@dataclass(frozen=True)
class ModelErrorSummary:
    """A model provider failure reduced to fields safe to log and show: no body text, no keys."""

    reason: str
    status: int | None = None


def _chain(exc: BaseException):
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _safe(value: object) -> str | None:
    return value if isinstance(value, str) and _SAFE_REASON.match(value) else None


def summarize_model_error(exc: BaseException) -> ModelErrorSummary | None:
    """Reason and HTTP status of a failed model request (OpenAI-compatible or Bedrock).

    The reason is the runtime's error code (e.g. Meterless' meterless_detail, Bedrock's
    error code) or the exception class name. None when exc is not a model provider error.
    """
    api = find_api_error(exc)
    if api is not None:
        body = getattr(api, "body", None)
        if isinstance(body, dict) and isinstance(body.get("error"), dict):
            body = body["error"]
        reason = None
        if isinstance(body, dict):
            reason = next(
                (r for key in ("meterless_detail", "code", "type") if (r := _safe(body.get(key)))),
                None,
            )
        return ModelErrorSummary(reason or type(api).__name__, getattr(api, "status_code", None))
    try:
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError:
        return None
    for current in _chain(exc):
        if isinstance(current, ClientError):
            error = current.response.get("Error", {}) if isinstance(current.response, dict) else {}
            meta = current.response.get("ResponseMetadata", {}) if isinstance(current.response, dict) else {}
            return ModelErrorSummary(
                _safe(error.get("Code")) or "ClientError", meta.get("HTTPStatusCode")
            )
        if isinstance(current, BotoCoreError):
            return ModelErrorSummary(type(current).__name__)
    return None
