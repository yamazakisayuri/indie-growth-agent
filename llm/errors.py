"""Make a failed model request explain itself, and say whether one retry may help.

Strands wraps the provider's exception (often in EventLoopException), and a streamed
error keeps the runtime's error object only in openai.APIError.body, so str(exc)
alone loses the reason.
"""

from __future__ import annotations

import json
import os

try:
    import openai
except ImportError:  # Bedrock-only installs
    openai = None  # type: ignore[assignment]

_SECRET_ENV = ("METERLESS_RUNTIME_TOKEN", "OPENAI_COMPATIBLE_API_KEY")
MAX_BODY_CHARS = 1000


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
