"""Load optional product.json (non-secret Product / Channel identity).

Secrets stay in .env. When product.json is missing, callers keep using env-only
settings (full backward compatibility).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config import ROOT_DIR, _resolve_path, load_env

DEFAULT_PRODUCT_FILENAME = "product.json"


@dataclass(frozen=True)
class AppStoreChannelConfig:
    enabled: bool = True
    app_id: str | None = None
    bundle_id: str | None = None
    territory: str | None = None


@dataclass(frozen=True)
class Ga4ChannelConfig:
    """GA4 connection for app or web. Filters are reserved for future use."""

    enabled: bool = True
    property_id: str | None = None
    key_events: tuple[str, ...] = ()
    event_definitions_path: str | None = None
    # Preferred setup: separate property for web. Same-property + filter later.
    hostname: str | None = None
    platform: str | None = None
    filters: dict[str, str | None] = field(default_factory=dict)


@dataclass(frozen=True)
class WebSiteChannelConfig:
    enabled: bool = False
    domain: str | None = None
    note: str | None = None
    # Declared product capabilities on this channel (what users can do) —
    # NOT measured usage. Do not confuse with GA4 event definitions / metrics.
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdMobChannelConfig:
    enabled: bool = True
    app_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProductConfig:
    """Logical product that may own multiple channels (App Store, Web, GA4, AdMob)."""

    id: str
    name: str
    type: str  # mobile_app | web | hybrid
    path: Path
    app_store: AppStoreChannelConfig
    ga4_app: Ga4ChannelConfig
    web: WebSiteChannelConfig
    ga4_web: Ga4ChannelConfig
    admob: AdMobChannelConfig


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in ("0", "false", "no", "off")
    return bool(value)


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _parse_filters(raw: Any) -> dict[str, str | None]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str | None] = {}
    for key, value in raw.items():
        out[str(key)] = _as_str(value)
    return out


def _parse_app_store(raw: Any) -> AppStoreChannelConfig:
    data = raw if isinstance(raw, dict) else {}
    return AppStoreChannelConfig(
        enabled=_as_bool(data.get("enabled"), True),
        app_id=_as_str(data.get("appId") or data.get("app_id")),
        bundle_id=_as_str(data.get("bundleId") or data.get("bundle_id")),
        territory=_as_str(data.get("territory")),
    )


def _parse_ga4(raw: Any, *, default_enabled: bool) -> Ga4ChannelConfig:
    data = raw if isinstance(raw, dict) else {}
    filters = _parse_filters(data.get("filters"))
    hostname = _as_str(data.get("hostname")) or filters.get("hostname")
    platform = _as_str(data.get("platform")) or filters.get("platform")
    return Ga4ChannelConfig(
        enabled=_as_bool(data.get("enabled"), default_enabled),
        property_id=_as_str(data.get("propertyId") or data.get("property_id")),
        key_events=_as_str_tuple(data.get("keyEvents") or data.get("key_events")),
        event_definitions_path=_as_str(
            data.get("eventDefinitionsPath") or data.get("event_definitions_path")
        ),
        hostname=hostname,
        platform=platform,
        filters=filters,
    )


def _parse_web(raw: Any) -> WebSiteChannelConfig:
    data = raw if isinstance(raw, dict) else {}
    return WebSiteChannelConfig(
        enabled=_as_bool(data.get("enabled"), False),
        domain=_as_str(data.get("domain")),
        note=_as_str(data.get("note")),
        capabilities=_as_str_tuple(data.get("capabilities")),
    )


def _parse_admob(raw: Any) -> AdMobChannelConfig:
    data = raw if isinstance(raw, dict) else {}
    app_ids = _as_str_tuple(data.get("appIds") or data.get("app_ids"))
    return AdMobChannelConfig(
        enabled=_as_bool(data.get("enabled"), True),
        app_ids=app_ids,
    )


def product_json_path() -> Path | None:
    load_env()
    path_raw = os.getenv("PRODUCT_JSON_PATH", "").strip()
    if path_raw:
        path = _resolve_path(path_raw)
        return path if path.is_file() else None
    default = ROOT_DIR / DEFAULT_PRODUCT_FILENAME
    return default if default.is_file() else None


def load_product_config() -> ProductConfig | None:
    """Return ProductConfig when product.json exists; otherwise None (env-only mode)."""
    path = product_json_path()
    if path is None:
        return None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in product config: {path}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"product config must be a JSON object: {path}")

    product_id = _as_str(raw.get("id"))
    name = _as_str(raw.get("name"))
    product_type = _as_str(raw.get("type")) or "hybrid"
    if not product_id or not name:
        raise ValueError(f"product config requires id and name: {path}")

    channels = raw.get("channels") if isinstance(raw.get("channels"), dict) else {}
    return ProductConfig(
        id=product_id,
        name=name,
        type=product_type,
        path=path,
        app_store=_parse_app_store(channels.get("app_store")),
        ga4_app=_parse_ga4(channels.get("ga4_app"), default_enabled=True),
        web=_parse_web(channels.get("web")),
        ga4_web=_parse_ga4(channels.get("ga4_web"), default_enabled=False),
        admob=_parse_admob(channels.get("admob")),
    )


def ga4_web_is_configured(product: ProductConfig | None = None) -> bool:
    """True when Web GA4 should be fetched (enabled + propertyId)."""
    product = product if product is not None else load_product_config()
    if product is None:
        return False
    channel = product.ga4_web
    return bool(channel.enabled and channel.property_id)


def channel_status_rows(
    *,
    product: ProductConfig | None,
    ga4_app_connected: bool,
    ga4_web_connected: bool,
    admob_connected: bool,
    asc_connected: bool = True,
) -> list[dict[str, Any]]:
    """Compact channel inventory for AnalyzeResponse / Planner prompts."""
    if product is None:
        return [
            {
                "id": "app_store",
                "kind": "store",
                "connected": asc_connected,
                "status": "ok" if asc_connected else "not_connected",
            },
            {
                "id": "ga4_app",
                "kind": "analytics",
                "connected": ga4_app_connected,
                "status": "ok" if ga4_app_connected else "not_connected",
            },
            {
                "id": "admob",
                "kind": "monetization",
                "connected": admob_connected,
                "status": "ok" if admob_connected else "not_connected",
            },
        ]

    web = product.web
    ga4_web = product.ga4_web
    web_status = "ok" if (web.enabled and web.domain) else "not_configured"
    if ga4_web.enabled and ga4_web.property_id:
        ga4_web_status = "ok" if ga4_web_connected else "unavailable"
    else:
        ga4_web_status = "not_configured"

    return [
        {
            "id": "app_store",
            "kind": "store",
            "connected": asc_connected and product.app_store.enabled,
            "status": "ok" if asc_connected and product.app_store.enabled else "not_connected",
            "bundleId": product.app_store.bundle_id,
            "territory": product.app_store.territory,
        },
        {
            "id": "ga4_app",
            "kind": "analytics",
            "connected": ga4_app_connected and product.ga4_app.enabled,
            "status": (
                "ok"
                if ga4_app_connected and product.ga4_app.enabled
                else "not_connected"
            ),
            "propertyId": product.ga4_app.property_id,
        },
        {
            "id": "web",
            "kind": "site",
            "connected": bool(web.enabled and web.domain),
            "status": web_status,
            "domain": web.domain,
            "note": web.note or ("not configured" if web_status == "not_configured" else None),
            "capabilities": list(web.capabilities) if web.capabilities else [],
        },
        {
            "id": "ga4_web",
            "kind": "analytics",
            "connected": ga4_web_connected,
            "status": ga4_web_status,
            "propertyId": ga4_web.property_id,
            "hostname": ga4_web.hostname,
            "platform": ga4_web.platform,
            "filters": ga4_web.filters,
            "note": (
                "not configured"
                if ga4_web_status == "not_configured"
                else None
            ),
        },
        {
            "id": "admob",
            "kind": "monetization",
            "connected": admob_connected and product.admob.enabled,
            "status": (
                "ok"
                if admob_connected and product.admob.enabled
                else "not_connected"
            ),
            "appIds": list(product.admob.app_ids) or None,
        },
    ]
