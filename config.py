"""Load configuration from environment variables. Never hardcode secrets."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_EVENT_DEFINITIONS_FILENAME = "event_definitions.json"


@dataclass(frozen=True)
class AppStoreConnectCredentials:
    issuer_id: str
    key_id: str
    private_key_path: Path

    def private_key_pem(self) -> str:
        if not self.private_key_path.is_file():
            raise FileNotFoundError(
                f"App Store Connect private key not found: {self.private_key_path}"
            )
        return self.private_key_path.read_text(encoding="utf-8")


@dataclass(frozen=True)
class AppStoreConnectSettings:
    credentials: AppStoreConnectCredentials
    app_id: str | None
    bundle_id: str | None
    territory: str
    lookback_days: int
    analytics_request_id: str | None


@dataclass(frozen=True)
class Ga4EventDefinition:
    """Developer-declared meaning of a GA4 event, supplied by config, not guessed."""

    name: str
    definition: str
    source: str


@dataclass(frozen=True)
class Ga4Settings:
    property_id: str
    property_resource: str
    lookback_days: int
    key_event_names: tuple[str, ...]
    event_definitions: tuple[Ga4EventDefinition, ...]
    service_account_path: Path | None
    oauth_client_id: str | None
    oauth_client_secret: str | None
    refresh_token: str | None


def load_env() -> None:
    load_dotenv(ROOT_DIR / ".env")


def _resolve_path(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def get_app_store_connect_credentials() -> AppStoreConnectCredentials:
    load_env()

    issuer_id = os.getenv("APP_STORE_CONNECT_ISSUER_ID", "").strip()
    key_id = os.getenv("APP_STORE_CONNECT_KEY_ID", "").strip()
    key_path_raw = os.getenv("APP_STORE_CONNECT_PRIVATE_KEY_PATH", "").strip()

    missing = [
        name
        for name, value in (
            ("APP_STORE_CONNECT_ISSUER_ID", issuer_id),
            ("APP_STORE_CONNECT_KEY_ID", key_id),
            ("APP_STORE_CONNECT_PRIVATE_KEY_PATH", key_path_raw),
        )
        if not value
    ]
    if missing:
        raise ValueError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill in your credentials."
        )

    return AppStoreConnectCredentials(
        issuer_id=issuer_id,
        key_id=key_id,
        private_key_path=_resolve_path(key_path_raw),
    )


def get_app_store_connect_settings() -> AppStoreConnectSettings:
    load_env()
    credentials = get_app_store_connect_credentials()

    lookback_raw = os.getenv("APP_STORE_CONNECT_LOOKBACK_DAYS", "7").strip() or "7"
    try:
        lookback_days = int(lookback_raw)
    except ValueError as exc:
        raise ValueError("APP_STORE_CONNECT_LOOKBACK_DAYS must be an integer") from exc
    if lookback_days < 1:
        raise ValueError("APP_STORE_CONNECT_LOOKBACK_DAYS must be >= 1")

    territory = os.getenv("APP_STORE_CONNECT_TERRITORY", "JP").strip().upper() or "JP"
    app_id = os.getenv("APP_STORE_CONNECT_APP_ID", "").strip() or None
    bundle_id = os.getenv("APP_STORE_CONNECT_BUNDLE_ID", "").strip() or None
    analytics_request_id = os.getenv("APP_STORE_CONNECT_ANALYTICS_REQUEST_ID", "").strip() or None

    return AppStoreConnectSettings(
        credentials=credentials,
        app_id=app_id,
        bundle_id=bundle_id,
        territory=territory,
        lookback_days=lookback_days,
        analytics_request_id=analytics_request_id,
    )


def _normalize_property_id(raw: str) -> tuple[str, str]:
    value = raw.strip()
    if value.startswith("properties/"):
        numeric = value.removeprefix("properties/").strip()
        if not numeric.isdigit():
            raise ValueError("GA4_PROPERTY_ID must be numeric or properties/<id>")
        return numeric, f"properties/{numeric}"
    if not value.isdigit():
        raise ValueError("GA4_PROPERTY_ID must be numeric or properties/<id>")
    return value, f"properties/{value}"


def _load_event_definitions(
    path: Path,
    names: tuple[str, ...],
) -> tuple[Ga4EventDefinition, ...]:
    """Load declared meanings for the configured key events. Unlisted events stay opaque."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in GA4 event definitions: {path}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"GA4 event definitions must be a JSON object: {path}")

    definitions: list[Ga4EventDefinition] = []
    for name in names:
        entry = raw.get(name)
        if not isinstance(entry, dict):
            continue
        definition = str(entry.get("definition") or "").strip()
        if not definition:
            continue
        definitions.append(
            Ga4EventDefinition(
                name=name,
                definition=definition,
                source=str(entry.get("source") or "developer-declared").strip(),
            )
        )
    return tuple(definitions)


def get_ga4_settings() -> Ga4Settings | None:
    """Return GA4 settings when configured; otherwise None (treated as not connected)."""
    load_env()

    property_raw = os.getenv("GA4_PROPERTY_ID", "").strip()
    if not property_raw:
        return None

    property_id, property_resource = _normalize_property_id(property_raw)

    lookback_raw = os.getenv("GA4_LOOKBACK_DAYS", "").strip()
    if not lookback_raw:
        lookback_raw = os.getenv("APP_STORE_CONNECT_LOOKBACK_DAYS", "7").strip() or "7"
    try:
        lookback_days = int(lookback_raw)
    except ValueError as exc:
        raise ValueError("GA4_LOOKBACK_DAYS must be an integer") from exc
    if lookback_days < 1:
        raise ValueError("GA4_LOOKBACK_DAYS must be >= 1")

    key_events_raw = os.getenv("GA4_KEY_EVENTS", "").strip()
    key_event_names = tuple(
        part.strip() for part in key_events_raw.split(",") if part.strip()
    )

    definitions_raw = os.getenv("GA4_EVENT_DEFINITIONS_PATH", "").strip()
    if definitions_raw:
        definitions_path = _resolve_path(definitions_raw)
        if not definitions_path.is_file():
            raise FileNotFoundError(
                f"GA4 event definitions file not found: {definitions_path}"
            )
    else:
        definitions_path = ROOT_DIR / DEFAULT_EVENT_DEFINITIONS_FILENAME
    event_definitions = (
        _load_event_definitions(definitions_path, key_event_names)
        if definitions_path.is_file()
        else ()
    )

    sa_raw = os.getenv("GA4_SERVICE_ACCOUNT_PATH", "").strip()
    service_account_path = _resolve_path(sa_raw) if sa_raw else None
    if service_account_path is not None and not service_account_path.is_file():
        # Path configured but file missing → ignore so OAuth can be used instead.
        service_account_path = None

    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip() or None
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip() or None
    refresh_token = os.getenv("GA4_REFRESH_TOKEN", "").strip() or None
    refresh_token_path_raw = os.getenv("GA4_REFRESH_TOKEN_PATH", "").strip()
    if not refresh_token and refresh_token_path_raw:
        refresh_token_path = _resolve_path(refresh_token_path_raw)
        if not refresh_token_path.is_file():
            raise FileNotFoundError(
                f"GA4 refresh token file not found: {refresh_token_path}"
            )
        refresh_token = refresh_token_path.read_text(encoding="utf-8").strip() or None

    has_sa = service_account_path is not None
    has_oauth = bool(client_id and client_secret and refresh_token)
    if not has_sa and not has_oauth:
        raise ValueError(
            "GA4_PROPERTY_ID is set, but auth is incomplete. Provide OAuth "
            "(GOOGLE_OAUTH_CLIENT_ID + GOOGLE_OAUTH_CLIENT_SECRET + "
            "GA4_REFRESH_TOKEN or GA4_REFRESH_TOKEN_PATH) "
            "or GA4_SERVICE_ACCOUNT_PATH."
        )

    # Prefer OAuth when both are available (hackathon / indie-growth reuse path).
    use_oauth = has_oauth
    use_sa = has_sa and not use_oauth

    return Ga4Settings(
        property_id=property_id,
        property_resource=property_resource,
        lookback_days=lookback_days,
        key_event_names=key_event_names,
        event_definitions=event_definitions,
        service_account_path=service_account_path if use_sa else None,
        oauth_client_id=client_id if use_oauth else None,
        oauth_client_secret=client_secret if use_oauth else None,
        refresh_token=refresh_token if use_oauth else None,
    )
