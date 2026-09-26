"""Load Product / Channel identity (non-secret).

Secrets stay in .env. Product selection is request-scoped via ContextVar so
CLI / API runs for different products do not cross-contaminate.

Resolution rules for channel identity:
1. Selected product channel fields
2. Default product only: optional env fallback (migration compatibility)
3. Non-default product missing identity → channel not_configured (never borrow
   another product\'s env IDs)
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from config import ROOT_DIR, Ga4FeaturePathSettings, _resolve_path, load_env

DEFAULT_PRODUCT_FILENAME = "product.json"
PRODUCTS_DIRNAME = "products"
PRODUCTS_INDEX_FILENAME = "index.json"
DEFAULT_PRODUCT_ID = "mahjong"

_active_product: ContextVar["ProductConfig | None"] = ContextVar(
    "active_product", default=None
)
_active_product_id: ContextVar[str | None] = ContextVar(
    "active_product_id", default=None
)


@dataclass(frozen=True)
class AppStoreChannelConfig:
    enabled: bool = True
    app_id: str | None = None
    bundle_id: str | None = None
    territory: str | None = None
    # App SKU from App Store Connect (Sales Parent Identifier / product filter).
    sku: str | None = None


@dataclass(frozen=True)
class Ga4ChannelConfig:
    """GA4 connection for app or web. Filters are reserved for future use."""

    enabled: bool = True
    property_id: str | None = None
    key_events: tuple[str, ...] = ()
    event_definitions_path: str | None = None
    hostname: str | None = None
    platform: str | None = None
    filters: dict[str, str | None] = field(default_factory=dict)
    key_event_page_path: str | None = None
    feature_paths: tuple[Ga4FeaturePathSettings, ...] = ()
    note: str | None = None


@dataclass(frozen=True)
class WebSiteChannelConfig:
    enabled: bool = False
    domain: str | None = None
    note: str | None = None
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
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProductIndexEntry:
    id: str
    name: str
    path: str


@dataclass(frozen=True)
class ProductIndex:
    default_product_id: str
    products: tuple[ProductIndexEntry, ...]


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
        sku=_as_str(data.get("sku")),
    )


def _parse_feature_paths(raw: Any) -> tuple[Ga4FeaturePathSettings, ...]:
    if not isinstance(raw, list):
        return ()
    paths: list[Ga4FeaturePathSettings] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"ga4 featurePaths[{index}] must be an object")
        path_id = _as_str(item.get("id"))
        page_path = _as_str(item.get("pagePath") or item.get("page_path"))
        if not path_id or not page_path:
            raise ValueError(
                f"ga4 featurePaths[{index}] requires id and pagePath"
            )
        if not page_path.startswith("/"):
            raise ValueError(
                f"ga4 featurePaths[{index}].pagePath must start with /"
            )
        include_page_views = _as_bool(
            item.get("pageViews", item.get("includePageViews", True)),
            True,
        )
        ref_raw = item.get("referenceEvents") or item.get("reference_events") or []
        ref_names: list[str] = []
        replaceable: list[tuple[str, str]] = []
        if isinstance(ref_raw, list):
            for ref_index, ref in enumerate(ref_raw):
                if isinstance(ref, str):
                    name = ref.strip()
                    if name:
                        ref_names.append(name)
                    continue
                if not isinstance(ref, dict):
                    raise ValueError(
                        f"ga4 featurePaths[{index}].referenceEvents[{ref_index}] "
                        "must be a string or object"
                    )
                name = _as_str(ref.get("eventName") or ref.get("event_name"))
                if not name:
                    raise ValueError(
                        f"ga4 featurePaths[{index}].referenceEvents[{ref_index}] "
                        "requires eventName"
                    )
                ref_names.append(name)
                replacement = _as_str(
                    ref.get("replaceableBy") or ref.get("replaceable_by")
                )
                if replacement:
                    replaceable.append((name, replacement))
        paths.append(
            Ga4FeaturePathSettings(
                id=path_id,
                page_path=page_path,
                include_page_views=include_page_views,
                reference_event_names=tuple(ref_names),
                reference_replaceable_by=tuple(replaceable),
            )
        )
    return tuple(paths)


def _parse_ga4(raw: Any, *, default_enabled: bool) -> Ga4ChannelConfig:
    data = raw if isinstance(raw, dict) else {}
    filters = _parse_filters(data.get("filters"))
    hostname = _as_str(data.get("hostname")) or filters.get("hostname")
    platform = _as_str(data.get("platform")) or filters.get("platform")
    key_event_page_path = _as_str(
        data.get("keyEventPagePath") or data.get("key_event_page_path")
    )
    if key_event_page_path and not key_event_page_path.startswith("/"):
        raise ValueError("ga4 keyEventPagePath must start with /")
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
        key_event_page_path=key_event_page_path,
        feature_paths=_parse_feature_paths(
            data.get("featurePaths") or data.get("feature_paths")
        ),
        note=_as_str(data.get("note")),
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


def products_dir() -> Path:
    return ROOT_DIR / PRODUCTS_DIRNAME


def products_index_path() -> Path:
    return products_dir() / PRODUCTS_INDEX_FILENAME


def load_product_index() -> ProductIndex:
    """Load products/index.json, or synthesize a default mahjong entry."""
    path = products_index_path()
    if not path.is_file():
        return ProductIndex(
            default_product_id=DEFAULT_PRODUCT_ID,
            products=(
                ProductIndexEntry(
                    id=DEFAULT_PRODUCT_ID,
                    name="Mahjong Score Calculator / 麻雀点数計算",
                    path="mahjong.json",
                ),
            ),
        )

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in products index: {path}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"products index must be a JSON object: {path}")

    default_id = _as_str(raw.get("defaultProductId") or raw.get("default_product_id"))
    default_id = default_id or DEFAULT_PRODUCT_ID

    entries_raw = raw.get("products")
    if not isinstance(entries_raw, list) or not entries_raw:
        raise ValueError(f"products index requires a non-empty products array: {path}")

    entries: list[ProductIndexEntry] = []
    for index, item in enumerate(entries_raw):
        if not isinstance(item, dict):
            raise ValueError(f"products[{index}] must be an object")
        product_id = _as_str(item.get("id"))
        name = _as_str(item.get("name"))
        rel_path = _as_str(item.get("path"))
        if not product_id or not name or not rel_path:
            raise ValueError(
                f"products[{index}] requires id, name, and path"
            )
        entries.append(
            ProductIndexEntry(id=product_id, name=name, path=rel_path)
        )

    return ProductIndex(
        default_product_id=default_id,
        products=tuple(entries),
    )


def get_default_product_id() -> str:
    return load_product_index().default_product_id or DEFAULT_PRODUCT_ID


def list_product_summaries() -> list[dict[str, str]]:
    """Public product list for GET /api/products (no secrets)."""
    index = load_product_index()
    summaries: list[dict[str, str]] = []
    for entry in index.products:
        try:
            product = load_product_by_id(entry.id)
        except Exception:
            summaries.append(
                {
                    "id": entry.id,
                    "name": entry.name,
                    "type": "unknown",
                }
            )
            continue
        summaries.append(
            {
                "id": product.id,
                "name": product.name,
                "type": product.type,
            }
        )
    return summaries


def _legacy_product_json_path() -> Path | None:
    """Root product.json / PRODUCT_JSON_PATH (migration compatibility)."""
    load_env()
    path_raw = os.getenv("PRODUCT_JSON_PATH", "").strip()
    if path_raw:
        path = _resolve_path(path_raw)
        return path if path.is_file() else None
    default = ROOT_DIR / DEFAULT_PRODUCT_FILENAME
    return default if default.is_file() else None


def product_json_path() -> Path | None:
    """Path used by env-only / legacy loaders. Prefer products/ when present."""
    index = load_product_index()
    default_id = index.default_product_id
    for entry in index.products:
        if entry.id == default_id:
            path = products_dir() / entry.path
            if path.is_file():
                return path
    return _legacy_product_json_path()


def _parse_product_dict(raw: dict[str, Any], *, path: Path) -> ProductConfig:
    product_id = _as_str(raw.get("id"))
    name = _as_str(raw.get("name"))
    product_type = _as_str(raw.get("type")) or "hybrid"
    if not product_id or not name:
        raise ValueError(f"product config requires id and name: {path}")

    channels = raw.get("channels") if isinstance(raw.get("channels"), dict) else {}
    top_capabilities = _as_str_tuple(raw.get("capabilities"))
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
        capabilities=top_capabilities,
    )


def _load_product_file(path: Path) -> ProductConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in product config: {path}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"product config must be a JSON object: {path}")
    return _parse_product_dict(raw, path=path)


def load_product_by_id(product_id: str | None = None) -> ProductConfig:
    """Load a product by id. None / blank → defaultProductId."""
    index = load_product_index()
    requested = (product_id or "").strip() or index.default_product_id

    for entry in index.products:
        if entry.id != requested:
            continue
        path = products_dir() / entry.path
        if not path.is_file():
            raise FileNotFoundError(f"Product config not found: {path}")
        product = _load_product_file(path)
        if product.id != entry.id:
            raise ValueError(
                f"Product id mismatch: index={entry.id} file={product.id} ({path})"
            )
        return product

    # Migration: explicit default / omitted id may fall back to root product.json.
    if requested == index.default_product_id:
        legacy = _legacy_product_json_path()
        if legacy is not None:
            return _load_product_file(legacy)

    known = ", ".join(entry.id for entry in index.products) or "(none)"
    raise ValueError(f"Unknown product id: {requested}. Known: {known}")


def load_product_config() -> ProductConfig | None:
    """Return the active product, or default product when catalog exists.

    Prefer ``use_product`` / ``load_product_by_id`` for explicit selection.
    Returns None only when no products catalog and no legacy product.json exist
    (env-only mode).
    """
    active = _active_product.get()
    if active is not None:
        return active

    active_id = _active_product_id.get()
    if active_id is not None:
        return load_product_by_id(active_id)

    index_path = products_index_path()
    if index_path.is_file() or (products_dir() / "mahjong.json").is_file():
        return load_product_by_id(None)

    legacy = _legacy_product_json_path()
    if legacy is None:
        return None
    return _load_product_file(legacy)


def is_default_product(product: ProductConfig | None = None) -> bool:
    resolved = product if product is not None else load_product_config()
    if resolved is None:
        return True
    return resolved.id == get_default_product_id()


def allow_env_identity_fallback(product: ProductConfig | None = None) -> bool:
    """Env channel IDs may fill gaps only for the default product."""
    return is_default_product(product)


@contextmanager
def use_product(product_id: str | None = None) -> Iterator[ProductConfig]:
    """Bind product for the current context (CLI run / API request)."""
    product = load_product_by_id(product_id)
    token = _active_product.set(product)
    id_token = _active_product_id.set(product.id)
    try:
        yield product
    finally:
        _active_product.reset(token)
        _active_product_id.reset(id_token)


def ga4_web_is_configured(product: ProductConfig | None = None) -> bool:
    """True when Web GA4 should be fetched (enabled + propertyId)."""
    product = product if product is not None else load_product_config()
    if product is None:
        return False
    channel = product.ga4_web
    return bool(channel.enabled and channel.property_id)


def ga4_app_is_configured(product: ProductConfig | None = None) -> bool:
    """True when App GA4 has an explicit propertyId on the product."""
    product = product if product is not None else load_product_config()
    if product is None:
        return False
    channel = product.ga4_app
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
    ga4_app = product.ga4_app
    web_status = "ok" if (web.enabled and web.domain) else "not_configured"
    if ga4_web.enabled and ga4_web.property_id:
        ga4_web_status = "ok" if ga4_web_connected else "unavailable"
    else:
        ga4_web_status = "not_configured"

    if not ga4_app.enabled:
        ga4_app_status = "not_configured"
    elif ga4_app.property_id:
        ga4_app_status = "ok" if ga4_app_connected else "unavailable"
    elif allow_env_identity_fallback(product) and ga4_app_connected:
        ga4_app_status = "ok"
    elif allow_env_identity_fallback(product):
        ga4_app_status = "not_connected"
    else:
        ga4_app_status = "not_configured"

    admob = product.admob
    if not admob.enabled:
        admob_status = "not_configured"
    elif admob.app_ids:
        admob_status = "ok" if admob_connected else "unavailable"
    elif allow_env_identity_fallback(product) and admob_connected:
        admob_status = "ok"
    elif allow_env_identity_fallback(product):
        admob_status = "not_connected"
    else:
        admob_status = "not_configured"

    return [
        {
            "id": "app_store",
            "kind": "store",
            "connected": asc_connected and product.app_store.enabled,
            "status": (
                "ok"
                if asc_connected and product.app_store.enabled
                else "not_connected"
            ),
            "bundleId": product.app_store.bundle_id,
            "appId": product.app_store.app_id,
            "sku": product.app_store.sku,
            "territory": product.app_store.territory,
        },
        {
            "id": "ga4_app",
            "kind": "analytics",
            "connected": (
                ga4_app_connected and ga4_app.enabled and ga4_app_status == "ok"
            ),
            "status": ga4_app_status,
            "propertyId": ga4_app.property_id,
            "note": (
                ga4_app.note if ga4_app_status == "not_configured" else None
            ),
        },
        {
            "id": "web",
            "kind": "site",
            "connected": bool(web.enabled and web.domain),
            "status": web_status,
            "domain": web.domain,
            "note": web.note
            or ("not configured" if web_status == "not_configured" else None),
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
                ga4_web.note
                or (
                    "not configured"
                    if ga4_web_status == "not_configured"
                    else None
                )
            ),
        },
        {
            "id": "admob",
            "kind": "monetization",
            "connected": (
                admob_connected and admob.enabled and admob_status == "ok"
            ),
            "status": admob_status,
            "appIds": list(admob.app_ids) or None,
        },
    ]
