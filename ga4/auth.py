"""Authenticate for Google Analytics Data API."""

from __future__ import annotations

import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials

ANALYTICS_READONLY = "https://www.googleapis.com/auth/analytics.readonly"
TOKEN_URI = "https://oauth2.googleapis.com/token"


def access_token_from_service_account(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"GA4 service account file not found: {path}")
    creds = service_account.Credentials.from_service_account_file(
        str(path),
        scopes=[ANALYTICS_READONLY],
    )
    creds.refresh(Request())
    if not creds.token:
        raise RuntimeError("Failed to obtain access token from GA4 service account")
    return creds.token


def access_token_from_refresh_token(
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> str:
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=[ANALYTICS_READONLY],
    )
    creds.refresh(Request())
    if not creds.token:
        raise RuntimeError("Failed to obtain access token from GA4 refresh token")
    return creds.token


def service_account_email(path: Path) -> str | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    email = data.get("client_email")
    return str(email) if email else None
