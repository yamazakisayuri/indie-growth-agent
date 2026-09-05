"""Authenticate for AdMob API (OAuth refresh token, separate from GA4)."""

from __future__ import annotations

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

ADMOB_READONLY = "https://www.googleapis.com/auth/admob.readonly"
TOKEN_URI = "https://oauth2.googleapis.com/token"


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
        scopes=[ADMOB_READONLY],
    )
    creds.refresh(Request())
    if not creds.token:
        raise RuntimeError("Failed to obtain access token from AdMob refresh token")
    return creds.token
