"""Minimal AdMob API client (accounts, apps, networkReport)."""

from __future__ import annotations

from typing import Any

import httpx

from .stream import each_admob_stream_message

BASE = "https://admob.googleapis.com/v1"


class AdMobApiError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class AdMobClient:
    def __init__(self, access_token: str, *, timeout: float = 60.0) -> None:
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        self._timeout = timeout

    def _raise_for_status(self, response: httpx.Response, payload: Any) -> None:
        if response.status_code < 400:
            return
        message = f"AdMob API error (HTTP {response.status_code})"
        if isinstance(payload, dict):
            err = payload.get("error") or {}
            if isinstance(err, dict) and err.get("message"):
                message = str(err["message"])
        raise AdMobApiError(response.status_code, message)

    def list_accounts(self) -> list[dict[str, Any]]:
        url = f"{BASE}/accounts"
        response = httpx.get(url, headers=self._headers, timeout=self._timeout)
        try:
            payload = response.json()
        except Exception:
            payload = None
        self._raise_for_status(response, payload)
        if not isinstance(payload, dict):
            raise AdMobApiError(response.status_code, "Unexpected non-JSON from accounts.list")
        accounts = payload.get("account") or []
        return [a for a in accounts if isinstance(a, dict)]

    def list_apps(self, account_resource: str) -> list[dict[str, Any]]:
        url = f"{BASE}/{account_resource}/apps"
        response = httpx.get(url, headers=self._headers, timeout=self._timeout)
        try:
            payload = response.json()
        except Exception:
            payload = None
        self._raise_for_status(response, payload)
        if not isinstance(payload, dict):
            raise AdMobApiError(response.status_code, "Unexpected non-JSON from apps.list")
        apps = payload.get("apps") or []
        return [a for a in apps if isinstance(a, dict)]

    def generate_network_report(
        self,
        account_resource: str,
        report_spec: dict[str, Any],
    ) -> list[dict[str, Any]]:
        url = f"{BASE}/{account_resource}/networkReport:generate"
        response = httpx.post(
            url,
            headers=self._headers,
            json={"reportSpec": report_spec},
            timeout=self._timeout,
        )
        text = response.text
        if response.status_code >= 400:
            try:
                payload = response.json()
            except Exception:
                payload = None
            self._raise_for_status(response, payload)
        return list(each_admob_stream_message(text))
