"""Load configuration from environment variables. Never hardcode secrets."""

from __future__ import annotations

import json
import os
import shlex
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_EVENT_DEFINITIONS_FILENAME = "event_definitions.json"


@dataclass(frozen=True)
class AppStoreConnectCredentials:
    issuer_id: str
    key_id: str
    private_key_path: Path | None = None
    private_key_pem_inline: str | None = None

    def private_key_pem(self) -> str:
        if self.private_key_pem_inline:
            return self.private_key_pem_inline
        if self.private_key_path is None:
            raise ValueError(
                "App Store Connect private key missing: set "
                "APP_STORE_CONNECT_PRIVATE_KEY or APP_STORE_CONNECT_PRIVATE_KEY_PATH"
            )
        if not self.private_key_path.is_file():
            raise FileNotFoundError(
                f"App Store Connect private key not found: {self.private_key_path}"
            )
        return self.private_key_path.read_text(encoding="utf-8")


def _normalize_pem(raw: str) -> str:
    """Accept PEM with real newlines or escaped \\n (common in Secrets Manager)."""
    text = raw.strip()
    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n")
    return text.strip()


@dataclass(frozen=True)
class AppStoreConnectSettings:
    credentials: AppStoreConnectCredentials
    app_id: str | None
    bundle_id: str | None
    territory: str
    lookback_days: int
    analytics_request_id: str | None
    # App SKU for Sales Parent Identifier / Apple Identifier filtering.
    app_sku: str | None = None


@dataclass(frozen=True)
class Ga4EventDefinition:
    """Developer-declared meaning of a GA4 event, supplied by config, not guessed."""

    name: str
    definition: str
    source: str


@dataclass(frozen=True)
class Ga4FeaturePathSettings:
    """Path-scoped Web GA4 metrics (feature page views + reference events).

    Separate from site-wide users/sessions/page views. A declared Product
    capability is NOT the same as these measured path metrics.
    """

    id: str
    page_path: str
    include_page_views: bool = True
    # GA4 eventNames counted only with pagePath EXACT filter (e.g. form_submit).
    reference_event_names: tuple[str, ...] = ()
    # Optional: reference event → future replacement event (e.g. form_submit → score_calculated).
    reference_replaceable_by: tuple[tuple[str, str], ...] = ()


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
    # Optional dimension filters (Web channel). Exact match only — no subdomain bleed.
    hostname_exact: str | None = None
    platform_exact: str | None = None
    # When set, key eventCounts are further restricted to this pagePath (EXACT).
    key_event_page_path: str | None = None
    feature_paths: tuple[Ga4FeaturePathSettings, ...] = ()


@dataclass(frozen=True)
class AdMobSettings:
    """AdMob Network report settings. OAuth client is shared with GA4; refresh token is separate."""

    account_resource: str
    app_ids: tuple[str, ...]
    lookback_days: int
    currency_code: str
    oauth_client_id: str
    oauth_client_secret: str
    refresh_token: str


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
    key_pem_raw = os.getenv("APP_STORE_CONNECT_PRIVATE_KEY", "").strip()
    key_path_raw = os.getenv("APP_STORE_CONNECT_PRIVATE_KEY_PATH", "").strip()

    missing = [
        name
        for name, value in (
            ("APP_STORE_CONNECT_ISSUER_ID", issuer_id),
            ("APP_STORE_CONNECT_KEY_ID", key_id),
        )
        if not value
    ]
    if missing:
        raise ValueError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill in your credentials."
        )

    if key_pem_raw:
        return AppStoreConnectCredentials(
            issuer_id=issuer_id,
            key_id=key_id,
            private_key_pem_inline=_normalize_pem(key_pem_raw),
        )

    if not key_path_raw:
        raise ValueError(
            "Missing App Store Connect private key: set "
            "APP_STORE_CONNECT_PRIVATE_KEY (PEM body, for containers) or "
            "APP_STORE_CONNECT_PRIVATE_KEY_PATH (local file). "
            "Copy .env.example to .env and fill in your credentials."
        )

    return AppStoreConnectCredentials(
        issuer_id=issuer_id,
        key_id=key_id,
        private_key_path=_resolve_path(key_path_raw),
    )


def get_asc_vendor_number() -> str | None:
    """Vendor Number for Sales / Finance reports. Account-level secret-adjacent config."""
    load_env()
    value = os.getenv("ASC_VENDOR_NUMBER", "").strip()
    return value or None


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
    app_sku: str | None = None

    # Product channel identity overlays env. Non-default products never borrow
    # another product's env IDs when their own identity is incomplete.
    try:
        from product_config import allow_env_identity_fallback, load_product_config

        product = load_product_config()
    except Exception:
        product = None
    if product is not None and product.app_store.enabled:
        channel = product.app_store
        env_ok = allow_env_identity_fallback(product)
        if channel.app_id:
            app_id = channel.app_id
        elif not env_ok:
            app_id = None
        if channel.bundle_id:
            bundle_id = channel.bundle_id
        elif not env_ok:
            bundle_id = None
        if channel.territory:
            territory = channel.territory.strip().upper() or territory
        if channel.sku:
            app_sku = channel.sku
        elif not env_ok:
            app_sku = None
        # Clear preferred analytics request when switching away from env default —
        # request IDs are app-specific.
        if not env_ok:
            analytics_request_id = None

    return AppStoreConnectSettings(
        credentials=credentials,
        app_id=app_id,
        bundle_id=bundle_id,
        territory=territory,
        lookback_days=lookback_days,
        analytics_request_id=analytics_request_id,
        app_sku=app_sku,
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


def _ga4_auth_from_env() -> tuple[
    Path | None,
    str | None,
    str | None,
    str | None,
]:
    """Shared OAuth / service-account credentials for App and Web GA4."""
    sa_raw = os.getenv("GA4_SERVICE_ACCOUNT_PATH", "").strip()
    service_account_path = _resolve_path(sa_raw) if sa_raw else None
    if service_account_path is not None and not service_account_path.is_file():
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
    return service_account_path, client_id, client_secret, refresh_token


def _definition_names_for_settings(
    *,
    key_event_names: tuple[str, ...],
    feature_paths: tuple[Ga4FeaturePathSettings, ...],
) -> tuple[str, ...]:
    """Event / metric ids that may appear in the definitions file for this channel."""
    names: list[str] = list(key_event_names)
    for path in feature_paths:
        if path.include_page_views:
            names.append(f"{path.id}_page_views")
        for event_name in path.reference_event_names:
            names.append(event_name)
            names.append(f"{path.id}_{event_name}")
    # Preserve order, drop duplicates.
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return tuple(ordered)


def _build_ga4_settings(
    *,
    property_raw: str,
    key_event_names: tuple[str, ...],
    definitions_path: Path,
    lookback_days: int,
    auth_label: str,
    hostname_exact: str | None = None,
    platform_exact: str | None = None,
    key_event_page_path: str | None = None,
    feature_paths: tuple[Ga4FeaturePathSettings, ...] = (),
) -> Ga4Settings:
    property_id, property_resource = _normalize_property_id(property_raw)
    definition_names = _definition_names_for_settings(
        key_event_names=key_event_names,
        feature_paths=feature_paths,
    )
    event_definitions = (
        _load_event_definitions(definitions_path, definition_names)
        if definitions_path.is_file()
        else ()
    )
    service_account_path, client_id, client_secret, refresh_token = _ga4_auth_from_env()
    has_sa = service_account_path is not None
    has_oauth = bool(client_id and client_secret and refresh_token)
    if not has_sa and not has_oauth:
        raise ValueError(
            f"{auth_label} property is set, but auth is incomplete. Provide OAuth "
            "(GOOGLE_OAUTH_CLIENT_ID + GOOGLE_OAUTH_CLIENT_SECRET + "
            "GA4_REFRESH_TOKEN or GA4_REFRESH_TOKEN_PATH) "
            "or GA4_SERVICE_ACCOUNT_PATH."
        )
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
        hostname_exact=hostname_exact,
        platform_exact=platform_exact,
        key_event_page_path=key_event_page_path,
        feature_paths=feature_paths,
    )


def get_ga4_settings() -> Ga4Settings | None:
    """Return App GA4 settings when configured; otherwise None (not connected)."""
    load_env()

    property_raw = os.getenv("GA4_PROPERTY_ID", "").strip()
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

    # Product App GA4 identity. Env property is fallback for default product only.
    try:
        from product_config import allow_env_identity_fallback, load_product_config

        product = load_product_config()
    except Exception:
        product = None
    if product is not None:
        if not product.ga4_app.enabled:
            return None
        channel = product.ga4_app
        env_ok = allow_env_identity_fallback(product)
        if channel.property_id:
            property_raw = channel.property_id
        elif not env_ok:
            # Non-default product without propertyId → not_configured.
            return None
        if channel.key_events:
            key_event_names = channel.key_events
        elif not env_ok:
            key_event_names = ()
        if channel.event_definitions_path:
            definitions_path = _resolve_path(channel.event_definitions_path)
            if not definitions_path.is_file():
                raise FileNotFoundError(
                    f"GA4 event definitions file not found: {definitions_path}"
                )

    if not property_raw:
        return None

    lookback_raw = os.getenv("GA4_LOOKBACK_DAYS", "").strip()
    if not lookback_raw:
        lookback_raw = os.getenv("APP_STORE_CONNECT_LOOKBACK_DAYS", "7").strip() or "7"
    try:
        lookback_days = int(lookback_raw)
    except ValueError as exc:
        raise ValueError("GA4_LOOKBACK_DAYS must be an integer") from exc
    if lookback_days < 1:
        raise ValueError("GA4_LOOKBACK_DAYS must be >= 1")

    return _build_ga4_settings(
        property_raw=property_raw,
        key_event_names=key_event_names,
        definitions_path=definitions_path,
        lookback_days=lookback_days,
        auth_label="GA4",
    )


def get_ga4_web_settings() -> Ga4Settings | None:
    """Return Web GA4 settings from the product config when configured; else None.

    Preferred: a separate GA4 property from the App channel. When hostname /
    platform are set on the Web channel, exact-match dimension filters are applied
    (hostName EXACT — subdomains like tech.example.com do not match example.com).
    Auth reuses the same .env GA4 credentials as App GA4.
    """
    load_env()
    try:
        from product_config import load_product_config

        product = load_product_config()
    except Exception:
        product = None
    if product is None:
        return None
    channel = product.ga4_web
    if not channel.enabled or not channel.property_id:
        return None

    definitions_path = ROOT_DIR / DEFAULT_EVENT_DEFINITIONS_FILENAME
    if channel.event_definitions_path:
        definitions_path = _resolve_path(channel.event_definitions_path)
        if not definitions_path.is_file():
            raise FileNotFoundError(
                f"Web GA4 event definitions file not found: {definitions_path}"
            )

    lookback_raw = os.getenv("GA4_WEB_LOOKBACK_DAYS", "").strip()
    if not lookback_raw:
        lookback_raw = os.getenv("GA4_LOOKBACK_DAYS", "").strip()
    if not lookback_raw:
        lookback_raw = os.getenv("APP_STORE_CONNECT_LOOKBACK_DAYS", "7").strip() or "7"
    try:
        lookback_days = int(lookback_raw)
    except ValueError as exc:
        raise ValueError("GA4_WEB_LOOKBACK_DAYS must be an integer") from exc
    if lookback_days < 1:
        raise ValueError("GA4_WEB_LOOKBACK_DAYS must be >= 1")

    return _build_ga4_settings(
        property_raw=channel.property_id,
        key_event_names=channel.key_events,
        definitions_path=definitions_path,
        lookback_days=lookback_days,
        auth_label="Web GA4",
        hostname_exact=channel.hostname,
        platform_exact=channel.platform,
        key_event_page_path=channel.key_event_page_path,
        feature_paths=channel.feature_paths,
    )


def _normalize_admob_account(raw: str) -> str:
    value = raw.strip()
    if value.startswith("accounts/"):
        return value
    if value.startswith("pub-"):
        return f"accounts/{value}"
    raise ValueError(
        "ADMOB_ACCOUNT_ID must be pub-… or accounts/pub-… "
        f"(got {raw!r})"
    )


@dataclass(frozen=True)
class GrowthMcpSettings:
    """Stdio launch config for Growth Agent MCP (knowledge provider for Planner).

    Paths / commands come from env so the MCP stays outside this repo and can
    later switch from a local ``node dist/index.js`` build to ``npx growth-agent-mcp``.
    """

    command: str
    args: tuple[str, ...]
    cwd: str | None = None


def _parse_growth_mcp_args(raw: str) -> tuple[str, ...]:
    """Accept a JSON string array or a shell-style argument string."""
    text = raw.strip()
    if not text:
        return ()
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "GROWTH_MCP_ARGS must be a JSON array or a shell-style string"
            ) from exc
        if not isinstance(parsed, list) or not all(isinstance(x, str) for x in parsed):
            raise ValueError("GROWTH_MCP_ARGS JSON must be an array of strings")
        return tuple(parsed)
    return tuple(shlex.split(text))


def get_growth_mcp_settings() -> GrowthMcpSettings | None:
    """Return Growth MCP launch settings when configured; otherwise None (Planner skips MCP)."""
    load_env()

    command = os.getenv("GROWTH_MCP_COMMAND", "").strip()
    if not command:
        return None

    args = _parse_growth_mcp_args(os.getenv("GROWTH_MCP_ARGS", ""))
    cwd_raw = os.getenv("GROWTH_MCP_CWD", "").strip()
    cwd = str(_resolve_path(cwd_raw)) if cwd_raw else None

    return GrowthMcpSettings(command=command, args=args, cwd=cwd)


DEFAULT_LLM_PROVIDER = "bedrock"


def get_llm_provider() -> str:
    """Return the model provider for every Strands Agent (LLM_PROVIDER, default bedrock)."""
    load_env()
    return os.getenv("LLM_PROVIDER", "").strip().lower() or DEFAULT_LLM_PROVIDER


# Local runtimes can take minutes to load a model on the first request.
DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_SECONDS = 180.0


@dataclass(frozen=True)
class OpenAICompatibleSettings:
    """Any server that speaks the OpenAI Chat Completions API."""

    base_url: str
    api_key: str
    model_id: str
    headers: tuple[tuple[str, str], ...] = ()
    timeout_seconds: float = DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_SECONDS


def _parse_headers_json(name: str, raw: str) -> tuple[tuple[str, str], ...]:
    text = raw.strip()
    if not text:
        return ()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must be a JSON object of header names to values") from exc
    if not isinstance(parsed, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in parsed.items()
    ):
        raise ValueError(f"{name} must be a JSON object of string header names to string values")
    return tuple(parsed.items())


def get_openai_compatible_settings() -> OpenAICompatibleSettings:
    """Settings for LLM_PROVIDER=openai_compatible. Raises ValueError when incomplete."""
    load_env()

    required = (
        "OPENAI_COMPATIBLE_BASE_URL",
        "OPENAI_COMPATIBLE_API_KEY",
        "OPENAI_COMPATIBLE_MODEL",
    )
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        raise ValueError("LLM_PROVIDER=openai_compatible needs " + ", ".join(missing))

    timeout_raw = os.getenv("OPENAI_COMPATIBLE_TIMEOUT_SECONDS", "").strip()
    try:
        timeout = float(timeout_raw) if timeout_raw else DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_SECONDS
    except ValueError as exc:
        raise ValueError("OPENAI_COMPATIBLE_TIMEOUT_SECONDS must be a number") from exc
    if timeout <= 0:
        raise ValueError("OPENAI_COMPATIBLE_TIMEOUT_SECONDS must be > 0")

    return OpenAICompatibleSettings(
        base_url=os.getenv("OPENAI_COMPATIBLE_BASE_URL", "").strip().rstrip("/"),
        api_key=os.getenv("OPENAI_COMPATIBLE_API_KEY", "").strip(),
        model_id=os.getenv("OPENAI_COMPATIBLE_MODEL", "").strip(),
        headers=_parse_headers_json(
            "OPENAI_COMPATIBLE_HEADERS", os.getenv("OPENAI_COMPATIBLE_HEADERS", "")
        ),
        timeout_seconds=timeout,
    )


DEFAULT_EVIDENCE_STORE = "sqlite"
DEFAULT_EVIDENCE_SQLITE_PATH = "tmp/evidence.sqlite"


def get_evidence_store_kind() -> str:
    """Return the evidence store backend (EVIDENCE_STORE, default sqlite)."""
    load_env()
    return os.getenv("EVIDENCE_STORE", "").strip().lower() or DEFAULT_EVIDENCE_STORE


def get_evidence_sqlite_path() -> Path:
    """SQLite file for EVIDENCE_STORE=sqlite (EVIDENCE_SQLITE_PATH, relative to the repo)."""
    load_env()
    raw = os.getenv("EVIDENCE_SQLITE_PATH", "").strip() or DEFAULT_EVIDENCE_SQLITE_PATH
    return _resolve_path(raw)


DEFAULT_GROWTH_MD_FILENAME = "GROWTH.md"


def get_growth_md_text() -> str | None:
    """Load optional GROWTH.md (constraints / available resources for Planner).

    Resolution order:
    1. GROWTH_MD_PATH if set
    2. Repository-root GROWTH.md if present
    Missing file → None (Planner runs without constraints, as before).
    """
    load_env()

    path_raw = os.getenv("GROWTH_MD_PATH", "").strip()
    if path_raw:
        path = _resolve_path(path_raw)
        if not path.is_file():
            raise FileNotFoundError(f"GROWTH_MD_PATH file not found: {path}")
        text = path.read_text(encoding="utf-8").strip()
        return text or None

    default_path = ROOT_DIR / DEFAULT_GROWTH_MD_FILENAME
    if not default_path.is_file():
        return None
    text = default_path.read_text(encoding="utf-8").strip()
    return text or None


def get_admob_settings() -> AdMobSettings | None:
    """Return AdMob settings when configured; otherwise None (treated as not connected)."""
    load_env()

    account_raw = os.getenv("ADMOB_ACCOUNT_ID", "").strip()
    refresh_token = os.getenv("ADMOB_REFRESH_TOKEN", "").strip() or None
    refresh_token_path_raw = os.getenv("ADMOB_REFRESH_TOKEN_PATH", "").strip()
    if not refresh_token and refresh_token_path_raw:
        refresh_token_path = _resolve_path(refresh_token_path_raw)
        if refresh_token_path.is_file():
            refresh_token = refresh_token_path.read_text(encoding="utf-8").strip() or None

    # Not connected until both account and refresh token exist.
    if not account_raw and not refresh_token:
        return None
    if not account_raw or not refresh_token:
        # Partial config (e.g. token obtained, account not chosen yet) → not connected.
        return None

    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise ValueError(
            "AdMob needs GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET "
            "(same OAuth client as GA4)."
        )

    lookback_raw = os.getenv("ADMOB_LOOKBACK_DAYS", "").strip()
    if not lookback_raw:
        lookback_raw = os.getenv("APP_STORE_CONNECT_LOOKBACK_DAYS", "7").strip() or "7"
    try:
        lookback_days = int(lookback_raw)
    except ValueError as exc:
        raise ValueError("ADMOB_LOOKBACK_DAYS must be an integer") from exc
    if lookback_days < 1:
        raise ValueError("ADMOB_LOOKBACK_DAYS must be >= 1")

    app_ids_raw = os.getenv("ADMOB_APP_IDS", "").strip()
    if not app_ids_raw:
        app_ids_raw = os.getenv("ADMOB_APP_ID", "").strip()
    app_ids = tuple(part.strip() for part in app_ids_raw.split(",") if part.strip())

    try:
        from product_config import allow_env_identity_fallback, load_product_config

        product = load_product_config()
    except Exception:
        product = None
    if product is not None:
        if not product.admob.enabled:
            return None
        env_ok = allow_env_identity_fallback(product)
        if product.admob.app_ids:
            app_ids = product.admob.app_ids
        elif not env_ok:
            # Non-default without appIds → do not use another product's env filter
            # (would mix revenue). Treat as not configured.
            return None

    currency = os.getenv("ADMOB_CURRENCY_CODE", "JPY").strip().upper() or "JPY"

    return AdMobSettings(
        account_resource=_normalize_admob_account(account_raw),
        app_ids=app_ids,
        lookback_days=lookback_days,
        currency_code=currency,
        oauth_client_id=client_id,
        oauth_client_secret=client_secret,
        refresh_token=refresh_token,
    )
