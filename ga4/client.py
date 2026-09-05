"""Minimal GA4 Data API client (runReport)."""

from __future__ import annotations

from typing import Any

import httpx

BASE = "https://analyticsdata.googleapis.com/v1beta"


class Ga4ApiError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class Ga4Client:
    def __init__(self, access_token: str, *, timeout: float = 60.0) -> None:
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        self._timeout = timeout

    def run_report(self, property_resource: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{BASE}/{property_resource}:runReport"
        response = httpx.post(url, headers=self._headers, json=body, timeout=self._timeout)
        try:
            payload = response.json()
        except Exception:
            payload = None
        if response.status_code >= 400:
            message = f"GA4 Data API error (HTTP {response.status_code})"
            if isinstance(payload, dict):
                err = payload.get("error") or {}
                if isinstance(err, dict) and err.get("message"):
                    message = str(err["message"])
            raise Ga4ApiError(response.status_code, message)
        if not isinstance(payload, dict):
            raise Ga4ApiError(response.status_code, "Unexpected non-JSON response from GA4")
        return payload
