"""Minimal App Store Connect HTTP client."""

from __future__ import annotations

from typing import Any

import httpx

BASE_URL = "https://api.appstoreconnect.apple.com/v1"


class AscApiError(RuntimeError):
    def __init__(self, status: int, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class AscClient:
    def __init__(self, bearer_jwt: str, *, timeout: float = 60.0) -> None:
        self._headers = {
            "Authorization": f"Bearer {bearer_jwt}",
            "Accept": "application/json",
        }
        self._timeout = timeout

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        response = httpx.get(url, headers=self._headers, params=params, timeout=self._timeout)
        return self._parse(response)

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        response = httpx.post(
            url,
            headers={**self._headers, "Content-Type": "application/json"},
            json=body,
            timeout=self._timeout,
        )
        return self._parse(response)

    def get_bytes(self, url: str) -> bytes:
        response = httpx.get(url, timeout=self._timeout, follow_redirects=True)
        if response.status_code >= 400:
            raise AscApiError(response.status_code, f"Download failed (HTTP {response.status_code})")
        return response.content

    @staticmethod
    def _parse(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except Exception:
            payload = None
        if response.status_code >= 400:
            message = f"App Store Connect API error (HTTP {response.status_code})"
            code = None
            if isinstance(payload, dict):
                errors = payload.get("errors") or []
                if errors:
                    first = errors[0]
                    message = first.get("detail") or first.get("title") or message
                    code = first.get("code")
            raise AscApiError(response.status_code, message, code=code)
        if not isinstance(payload, dict):
            raise AscApiError(response.status_code, "Unexpected non-JSON response from ASC API")
        return payload
