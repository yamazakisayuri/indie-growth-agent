"""Known Events / Human Context for Planner (not Analyzer).

Standing constraints live in GROWTH.md. Temporary dated context lives here.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from config import ROOT_DIR, _resolve_path, load_env

logger = logging.getLogger(__name__)

DEFAULT_KNOWN_EVENTS_FILENAME = "known_events.json"

# Days before the Analyzer period start still included for Planner context
# (e.g. a store change shortly before the window). Overridable via env.
DEFAULT_KNOWN_EVENTS_LOOKBACK_DAYS = 21

# Legacy bundleId → product id (compat only; prefer product.json / selection).
_BUNDLE_TO_PRODUCT: dict[str, str] = {
    "net.makosoyo.MahjongScoreCalculator": "mahjong",
    "net.makosoyo.shopping-memo": "shopping-memo",
}


@dataclass(frozen=True)
class KnownEvent:
    """One human-provided temporary context item. Extra JSON keys are preserved."""

    date: date
    type: str
    product: str
    description: str
    end_date: date | None = None
    extra: tuple[tuple[str, Any], ...] = ()

    def overlaps(self, window_start: date, window_end: date) -> bool:
        start = self.date
        end = self.end_date or self.date
        return start <= window_end and end >= window_start

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "date": self.date.isoformat(),
            "type": self.type,
            "product": self.product,
            "description": self.description,
        }
        if self.end_date is not None:
            data["end_date"] = self.end_date.isoformat()
        for key, value in self.extra:
            data[key] = value
        return data

    def prompt_line(self) -> str:
        if self.end_date and self.end_date != self.date:
            when = f"{self.date.isoformat()}–{self.end_date.isoformat()}"
        else:
            when = self.date.isoformat()
        return (
            f"- date={when}; type={self.type}; product={self.product}; "
            f"description={self.description}"
        )


def get_known_events_lookback_days() -> int:
    load_env()
    raw = os.getenv("KNOWN_EVENTS_LOOKBACK_DAYS", "").strip()
    if not raw:
        return DEFAULT_KNOWN_EVENTS_LOOKBACK_DAYS
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("KNOWN_EVENTS_LOOKBACK_DAYS must be an integer") from exc
    if value < 0:
        raise ValueError("KNOWN_EVENTS_LOOKBACK_DAYS must be >= 0")
    return value


def _known_events_path() -> Path | None:
    load_env()
    path_raw = os.getenv("KNOWN_EVENTS_PATH", "").strip()
    if path_raw:
        path = _resolve_path(path_raw)
        if not path.is_file():
            raise FileNotFoundError(f"KNOWN_EVENTS_PATH file not found: {path}")
        return path
    default = ROOT_DIR / DEFAULT_KNOWN_EVENTS_FILENAME
    return default if default.is_file() else None


def resolve_known_events_product(
    *,
    bundle_id: str | None = None,
) -> str | None:
    """Product id for filtering.

    Priority: env override → active/selected product.id → legacy bundle map.
    """
    load_env()
    override = os.getenv("KNOWN_EVENTS_PRODUCT", "").strip()
    if override:
        return override
    try:
        from product_config import load_product_config

        product = load_product_config()
    except Exception:
        product = None
    if product is not None and product.id:
        return product.id
    if bundle_id and bundle_id in _BUNDLE_TO_PRODUCT:
        return _BUNDLE_TO_PRODUCT[bundle_id]
    return None


def _parse_iso_date(raw: Any, *, field: str) -> date:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"Known event missing {field}")
    return date.fromisoformat(raw.strip())


def _parse_event(raw: dict[str, Any]) -> KnownEvent:
    known_keys = {"date", "end_date", "type", "product", "description"}
    start = _parse_iso_date(raw.get("date"), field="date")
    end_raw = raw.get("end_date")
    end = _parse_iso_date(end_raw, field="end_date") if end_raw else None
    if end is not None and end < start:
        raise ValueError(f"Known event end_date {end} is before date {start}")

    event_type = str(raw.get("type") or "").strip()
    product = str(raw.get("product") or "").strip()
    description = str(raw.get("description") or "").strip()
    if not event_type or not product or not description:
        raise ValueError("Known event requires type, product, and description")

    extra = tuple(
        (key, value) for key, value in raw.items() if key not in known_keys
    )
    return KnownEvent(
        date=start,
        end_date=end,
        type=event_type,
        product=product,
        description=description,
        extra=extra,
    )


def load_all_known_events() -> list[KnownEvent]:
    """Load all events from JSON. Missing file → empty list."""
    path = _known_events_path()
    if path is None:
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in known events file: {path}") from exc

    if not isinstance(raw, list):
        raise ValueError(f"Known events file must be a JSON array: {path}")

    events: list[KnownEvent] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Known events[{index}] must be an object")
        events.append(_parse_event(item))
    return events


def filter_known_events_for_planner(
    events: list[KnownEvent],
    *,
    period_start: date,
    period_end: date,
    product: str | None,
    lookback_days: int | None = None,
) -> list[KnownEvent]:
    """Keep events for the product that overlap [period_start - lookback, period_end]."""
    lookback = (
        get_known_events_lookback_days() if lookback_days is None else lookback_days
    )
    window_start = period_start - timedelta(days=lookback)
    window_end = period_end

    selected: list[KnownEvent] = []
    for event in events:
        if product is not None and event.product != product:
            continue
        if event.overlaps(window_start, window_end):
            selected.append(event)

    selected.sort(key=lambda e: (e.date, e.end_date or e.date, e.type))
    return selected


def get_known_events_for_report(
    *,
    period_start: str | None,
    period_end: str | None,
    bundle_id: str | None = None,
) -> list[KnownEvent]:
    """Convenience: load + filter for an Analyzer report period."""
    if not period_start or not period_end:
        logger.info("Known events skipped: Analyzer period missing")
        return []

    try:
        start = date.fromisoformat(period_start)
        end = date.fromisoformat(period_end)
    except ValueError:
        logger.warning(
            "Known events skipped: invalid period %s→%s", period_start, period_end
        )
        return []

    product = resolve_known_events_product(bundle_id=bundle_id)
    events = load_all_known_events()
    filtered = filter_known_events_for_planner(
        events,
        period_start=start,
        period_end=end,
        product=product,
    )
    logger.info(
        "Known events loaded=%s filtered=%s product=%s window=%s→%s lookback=%s",
        len(events),
        len(filtered),
        product or "(all)",
        start - timedelta(days=get_known_events_lookback_days()),
        end,
        get_known_events_lookback_days(),
    )
    return filtered
