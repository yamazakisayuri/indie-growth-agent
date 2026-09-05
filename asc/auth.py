"""JWT creation for App Store Connect API."""

from __future__ import annotations

import time

import jwt

from config import AppStoreConnectCredentials


def create_jwt(credentials: AppStoreConnectCredentials, *, lifetime_seconds: int = 20 * 60) -> str:
    now = int(time.time())
    payload = {
        "iss": credentials.issuer_id,
        "iat": now,
        "exp": now + lifetime_seconds,
        "aud": "appstoreconnect-v1",
    }
    headers = {"alg": "ES256", "kid": credentials.key_id, "typ": "JWT"}
    return jwt.encode(
        payload,
        credentials.private_key_pem(),
        algorithm="ES256",
        headers=headers,
    )
