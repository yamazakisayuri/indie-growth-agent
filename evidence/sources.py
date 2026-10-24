"""Turn fetched data into evidence tables (ASC daily, Known Events, competitor listings).

Each table keeps its population in columns (territory, country, source) so a
query can never silently mix App Store Connect totals with public listing data.
Missing values stay NULL; they are never filled with 0.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from asc.tsv import DailyMetrics
from known_events import KnownEvent

from .store import Column, TableSpec

ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"
DESCRIPTION_HEAD_CHARS = 300

ASC_DAILY = TableSpec(
    name="asc_daily",
    description=(
        "App Store Connect Analytics daily totals for our own app. "
        "A day with no report row is absent (not zero). impressions / page views can be 0 "
        "on a day that only appears in the downloads report."
    ),
    columns=(
        Column("date", "date"),
        Column("app_id", "text"),
        Column("territory", "text", "ALL = every territory"),
        Column("impressions", "integer"),
        Column("product_page_views", "integer"),
        Column("first_time_downloads", "integer"),
        Column("source", "text", "asc_analytics"),
    ),
)

ASC_DAILY_BY_SOURCE = TableSpec(
    name="asc_daily_by_source",
    description=(
        "App Store Connect daily impressions and first-time downloads split by how users "
        "found the app. Page views have no source split. Sources outside these buckets are "
        "not listed, so buckets may not add up to asc_daily."
    ),
    columns=(
        Column("date", "date"),
        Column("app_id", "text"),
        Column("territory", "text"),
        Column("source_bucket", "text", "search | browse | referrer"),
        Column("impressions", "integer"),
        Column("first_time_downloads", "integer"),
        Column("source", "text", "asc_analytics"),
    ),
)

KNOWN_EVENTS = TableSpec(
    name="known_events",
    description=(
        "Developer-written context (releases, store changes, unusual usage). "
        "Context only: an event near a change does not prove it caused the change."
    ),
    columns=(
        Column("date", "date"),
        Column("end_date", "date", "NULL for a single-day event"),
        Column("type", "text"),
        Column("product", "text"),
        Column("description", "text"),
    ),
)

COMPETITOR_LISTING = TableSpec(
    name="competitor_listing",
    description=(
        "Public App Store listing data (iTunes Lookup API) for our app and a fixed list of "
        "competitors, one row per app per fetch date. External observation: a different "
        "source and population from asc_daily."
    ),
    columns=(
        Column("fetched_on", "date"),
        Column("country", "text", "App Store storefront, e.g. jp"),
        Column("app_id", "text"),
        Column("is_self", "integer", "1 = our app, 0 = competitor"),
        Column("name", "text"),
        Column("seller", "text"),
        Column("primary_genre", "text"),
        Column("rating_avg", "real", "NULL when there are no ratings"),
        Column("rating_count", "integer"),
        Column("version", "text"),
        Column("current_version_released_on", "date"),
        Column("first_released_on", "date"),
        Column("price", "real"),
        Column("screenshot_count", "integer", "iPhone screenshots on the listing"),
        Column("description_head", "text", f"First {DESCRIPTION_HEAD_CHARS} characters"),
        Column("url", "text"),
        Column("source", "text", "itunes_lookup"),
    ),
)

ALL_TABLES = (ASC_DAILY, ASC_DAILY_BY_SOURCE, KNOWN_EVENTS, COMPETITOR_LISTING)
INTERNAL_TABLE_NAMES = frozenset({ASC_DAILY.name, ASC_DAILY_BY_SOURCE.name, KNOWN_EVENTS.name})
# Public data about other apps: claims citing these are observations, never facts.
EXTERNAL_TABLE_NAMES = frozenset({COMPETITOR_LISTING.name})


def asc_daily_rows(
    days: Iterable[DailyMetrics], *, app_id: str, territory: str
) -> list[dict[str, Any]]:
    return [
        {
            "date": day.date,
            "app_id": app_id,
            "territory": territory,
            "impressions": day.impressions,
            "product_page_views": day.product_page_views,
            "first_time_downloads": day.first_time_downloads,
            "source": "asc_analytics",
        }
        for day in sorted(days, key=lambda d: d.date)
    ]


def asc_daily_by_source_rows(
    days: Iterable[DailyMetrics], *, app_id: str, territory: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for day in sorted(days, key=lambda d: d.date):
        buckets = sorted(set(day.impressions_by_source) | set(day.downloads_by_source))
        for bucket in buckets:
            rows.append(
                {
                    "date": day.date,
                    "app_id": app_id,
                    "territory": territory,
                    "source_bucket": bucket,
                    "impressions": day.impressions_by_source.get(bucket, 0),
                    "first_time_downloads": day.downloads_by_source.get(bucket, 0),
                    "source": "asc_analytics",
                }
            )
    return rows


def known_event_rows(events: Iterable[KnownEvent], *, product_id: str) -> list[dict[str, Any]]:
    return [
        {
            "date": event.date,
            "end_date": event.end_date,
            "type": event.type,
            "product": event.product,
            "description": event.description,
        }
        for event in sorted(events, key=lambda e: e.date)
        if event.product == product_id
    ]


def fetch_itunes_lookup(
    app_ids: Sequence[str],
    *,
    country: str,
    client: httpx.Client | None = None,
    timeout: float = 20.0,
) -> list[dict[str, Any]]:
    """Public listing JSON for these app ids (no API key). Apps not found are omitted."""
    if not app_ids:
        return []
    params = {"id": ",".join(app_ids), "country": country}
    if client is None:
        with httpx.Client(timeout=timeout) as owned:
            response = owned.get(ITUNES_LOOKUP_URL, params=params)
    else:
        response = client.get(ITUNES_LOOKUP_URL, params=params)
    response.raise_for_status()
    results = response.json().get("results", [])
    return [r for r in results if isinstance(r, Mapping) and r.get("wrapperType") == "software"]


def _date_part(value: Any) -> str | None:
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else None


def competitor_listing_rows(
    results: Iterable[Mapping[str, Any]],
    *,
    self_app_id: str | None,
    fetched_on: date,
    country: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in results:
        app_id = str(item.get("trackId", "")).strip()
        if not app_id:
            continue
        rating_count = item.get("userRatingCount")
        rating_avg = item.get("averageUserRating")
        description = str(item.get("description") or "")
        rows.append(
            {
                "fetched_on": fetched_on,
                "country": country,
                "app_id": app_id,
                "is_self": int(app_id == (self_app_id or "")),
                "name": item.get("trackName"),
                "seller": item.get("sellerName"),
                "primary_genre": item.get("primaryGenreName"),
                "rating_avg": rating_avg if rating_count else None,
                "rating_count": rating_count,
                "version": item.get("version"),
                "current_version_released_on": _date_part(item.get("currentVersionReleaseDate")),
                "first_released_on": _date_part(item.get("releaseDate")),
                "price": item.get("price"),
                "screenshot_count": len(item.get("screenshotUrls") or []),
                "description_head": description[:DESCRIPTION_HEAD_CHARS] or None,
                "url": item.get("trackViewUrl"),
                "source": "itunes_lookup",
            }
        )
    return rows


def write_csv(spec: TableSpec, rows: Iterable[Mapping[str, Any]], path: Path) -> int:
    """Write rows with a header in spec column order. NULL becomes an empty field."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(spec.column_names)
        for row in rows:
            values = []
            for name in spec.column_names:
                value = row.get(name)
                if value is None:
                    value = ""
                elif hasattr(value, "isoformat"):
                    value = value.isoformat()
                values.append(value)
            writer.writerow(values)
            count += 1
    return count
