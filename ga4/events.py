"""List GA4 eventName + eventCount for current vs previous lookback windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from config import Ga4Settings, get_ga4_settings

from .auth import (
    access_token_from_refresh_token,
    access_token_from_service_account,
)
from .client import Ga4Client


@dataclass(frozen=True)
class Ga4EventCountRow:
    event_name: str
    current_count: int
    previous_count: int

    @property
    def change_pct(self) -> float | None:
        if self.previous_count <= 0:
            return None
        return (self.current_count - self.previous_count) / self.previous_count * 100.0


@dataclass(frozen=True)
class Ga4EventInventory:
    property_resource: str
    lookback_days: int
    current_start: str
    current_end: str
    previous_start: str
    previous_end: str
    rows: tuple[Ga4EventCountRow, ...]


def _access_token(settings: Ga4Settings) -> str:
    if settings.service_account_path is not None:
        return access_token_from_service_account(settings.service_account_path)
    assert settings.oauth_client_id and settings.oauth_client_secret and settings.refresh_token
    return access_token_from_refresh_token(
        client_id=settings.oauth_client_id,
        client_secret=settings.oauth_client_secret,
        refresh_token=settings.refresh_token,
    )


def _metric_int(row: dict, index: int = 0) -> int:
    values = row.get("metricValues") or []
    if index >= len(values):
        return 0
    raw = values[index].get("value") if isinstance(values[index], dict) else None
    try:
        n = float(raw) if raw is not None else 0.0
    except (TypeError, ValueError):
        return 0
    return int(n) if n > 0 else 0


def _fetch_event_counts(
    client: Ga4Client,
    property_resource: str,
    start: str,
    end: str,
) -> dict[str, int]:
    payload = client.run_report(
        property_resource,
        {
            "dateRanges": [{"startDate": start, "endDate": end}],
            "dimensions": [{"name": "eventName"}],
            "metrics": [{"name": "eventCount"}],
            "orderBys": [
                {
                    "desc": True,
                    "metric": {"metricName": "eventCount"},
                }
            ],
            "limit": 200,
        },
    )
    counts: dict[str, int] = {}
    for row in payload.get("rows") or []:
        if not isinstance(row, dict):
            continue
        dims = row.get("dimensionValues") or []
        name = dims[0].get("value") if dims and isinstance(dims[0], dict) else None
        if not name:
            continue
        counts[str(name)] = _metric_int(row, 0)
    return counts


def fetch_event_inventory(
    settings: Ga4Settings | None = None,
    *,
    as_of: date | None = None,
) -> Ga4EventInventory:
    settings = settings or get_ga4_settings()
    if settings is None:
        raise RuntimeError("GA4 is not configured")

    client = Ga4Client(_access_token(settings))
    end = as_of or (date.today() - timedelta(days=1))
    lookback = settings.lookback_days
    current_start = end - timedelta(days=lookback - 1)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=lookback - 1)

    current = _fetch_event_counts(
        client,
        settings.property_resource,
        current_start.isoformat(),
        end.isoformat(),
    )
    previous = _fetch_event_counts(
        client,
        settings.property_resource,
        previous_start.isoformat(),
        previous_end.isoformat(),
    )

    names = sorted(set(current) | set(previous), key=lambda n: (-(current.get(n, 0)), n))
    rows = tuple(
        Ga4EventCountRow(
            event_name=name,
            current_count=current.get(name, 0),
            previous_count=previous.get(name, 0),
        )
        for name in names
    )
    return Ga4EventInventory(
        property_resource=settings.property_resource,
        lookback_days=lookback,
        current_start=current_start.isoformat(),
        current_end=end.isoformat(),
        previous_start=previous_start.isoformat(),
        previous_end=previous_end.isoformat(),
        rows=rows,
    )


def format_event_inventory(inventory: Ga4EventInventory) -> str:
    def pct(row: Ga4EventCountRow) -> str:
        if row.change_pct is None:
            return "n/a"
        sign = "+" if row.change_pct >= 0 else ""
        return f"{sign}{row.change_pct:.1f}%"

    lines = [
        f"property: {inventory.property_resource}",
        f"current:  {inventory.current_start} → {inventory.current_end}",
        f"previous: {inventory.previous_start} → {inventory.previous_end}",
        f"events:   {len(inventory.rows)}",
        "",
        f"{'eventName':<40} {'current':>10} {'previous':>10} {'wow':>10}",
        "-" * 74,
    ]
    for row in inventory.rows:
        lines.append(
            f"{row.event_name:<40} {row.current_count:>10,} {row.previous_count:>10,} {pct(row):>10}"
        )
    return "\n".join(lines)
