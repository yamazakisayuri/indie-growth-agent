"""Verify evidence tables built from ASC daily data, Known Events, and listings. No network.

Run: python scripts/verify_evidence_sources.py
"""

from __future__ import annotations

import csv
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from asc.tsv import DailyMetrics  # noqa: E402
from evidence import SQLiteEvidenceStore  # noqa: E402
from evidence.sources import (  # noqa: E402
    ALL_TABLES,
    ASC_DAILY,
    ASC_DAILY_BY_SOURCE,
    COMPETITOR_LISTING,
    KNOWN_EVENTS,
    asc_daily_by_source_rows,
    asc_daily_rows,
    competitor_listing_rows,
    fetch_itunes_lookup,
    known_event_rows,
    write_csv,
)
from known_events import KnownEvent  # noqa: E402
from product_config import load_product_by_id  # noqa: E402

DAYS = [
    DailyMetrics(
        date="2026-10-17",
        impressions=310,
        product_page_views=12,
        first_time_downloads=4,
        impressions_by_source={"search": 250, "browse": 60},
        downloads_by_source={"search": 4},
    ),
    DailyMetrics(
        date="2026-10-16",
        impressions=300,
        product_page_views=13,
        first_time_downloads=5,
        impressions_by_source={"search": 240},
        downloads_by_source={"search": 3, "referrer": 2},
    ),
]
EVENTS = [
    KnownEvent(date=date(2026, 10, 11), type="release", product="mahjong", description="v2.4"),
    KnownEvent(date=date(2026, 9, 1), type="store", product="nextuta", description="other app"),
]
LOOKUP = {
    "resultCount": 3,
    "results": [
        {
            "wrapperType": "software",
            "trackId": 6740174129,
            "trackName": "麻雀点数計算｜三麻・四麻対応",
            "sellerName": "MAKOSOYO",
            "primaryGenreName": "Utilities",
            "averageUserRating": 0,
            "userRatingCount": 0,
            "version": "2.4",
            "currentVersionReleaseDate": "2026-10-11T23:38:25Z",
            "releaseDate": "2025-01-20T08:00:00Z",
            "price": 0.0,
            "screenshotUrls": ["a", "b", "c"],
            "description": "x" * 500,
            "trackViewUrl": "https://apps.apple.com/jp/app/id6740174129",
        },
        {
            "wrapperType": "software",
            "trackId": 1672476966,
            "trackName": "麻雀 点数計算マスター",
            "averageUserRating": 4.76593,
            "userRatingCount": 2824,
            "primaryGenreName": "Games",
            "currentVersionReleaseDate": "2026-09-22T13:15:04Z",
        },
        {"wrapperType": "artist", "artistId": 1},
    ],
}


def main() -> None:
    by_name = {spec.name: spec for spec in ALL_TABLES}
    assert set(by_name) == {"asc_daily", "asc_daily_by_source", "known_events", "competitor_listing"}
    assert ASC_DAILY.column_names == (
        "date",
        "app_id",
        "territory",
        "impressions",
        "product_page_views",
        "first_time_downloads",
        "source",
    ), "asc_daily must keep the column order of the Zetaris CSV"

    store = SQLiteEvidenceStore()
    daily = asc_daily_rows(DAYS, app_id="6740174129", territory="ALL")
    by_source = asc_daily_by_source_rows(DAYS, app_id="6740174129", territory="ALL")
    assert store.replace_table(ASC_DAILY, daily) == 2
    assert store.replace_table(ASC_DAILY_BY_SOURCE, by_source) == 4
    assert store.query("SELECT MIN(date) FROM asc_daily").scalar() == "2026-10-16"
    assert store.query(
        "SELECT SUM(first_time_downloads) * 1.0 / SUM(product_page_views) FROM asc_daily"
    ).scalar() == 9 / 25
    assert store.query(
        "SELECT SUM(first_time_downloads) FROM asc_daily_by_source WHERE source_bucket = 'referrer'"
    ).scalar() == 2
    assert store.query(
        "SELECT impressions FROM asc_daily_by_source "
        "WHERE date = '2026-10-16' AND source_bucket = 'referrer'"
    ).scalar() == 0
    print("OK ASC daily totals and per-source rows load and aggregate")

    assert store.replace_table(KNOWN_EVENTS, known_event_rows(EVENTS, product_id="mahjong")) == 1
    assert store.query("SELECT end_date FROM known_events").scalar() is None
    print("OK Known Events are filtered to the product; missing end_date stays NULL")

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=LOOKUP)
        if request.url.params["country"] == "jp"
        and request.url.params["id"] == "6740174129,1672476966"
        else httpx.Response(400)
    )
    with httpx.Client(transport=transport) as client:
        results = fetch_itunes_lookup(["6740174129", "1672476966"], country="jp", client=client)
    assert [r["trackId"] for r in results] == [6740174129, 1672476966]
    rows = competitor_listing_rows(
        results, self_app_id="6740174129", fetched_on=date(2026, 10, 24), country="jp"
    )
    assert store.replace_table(COMPETITOR_LISTING, rows) == 2
    own = store.query(
        "SELECT is_self, rating_avg, rating_count, screenshot_count, LENGTH(description_head), "
        "current_version_released_on FROM competitor_listing WHERE app_id = '6740174129'"
    ).rows[0]
    assert own == (1, None, 0, 3, 300, "2026-10-11"), own
    other = store.query(
        "SELECT is_self, rating_avg, version, description_head FROM competitor_listing "
        "WHERE app_id = '1672476966'"
    ).rows[0]
    assert other == (0, 4.76593, None, None), other
    print("OK listings: zero ratings give NULL average, missing fields stay NULL, non-apps dropped")
    store.close()

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "csv" / "asc_daily.csv"
        assert write_csv(ASC_DAILY, daily, path) == 2
        with path.open(encoding="utf-8") as handle:
            lines = list(csv.reader(handle))
        assert lines[0] == list(ASC_DAILY.column_names)
        assert lines[1] == ["2026-10-16", "6740174129", "ALL", "300", "13", "5", "asc_analytics"]
        known_path = Path(tmp) / "known_events.csv"
        write_csv(KNOWN_EVENTS, known_event_rows(EVENTS, product_id="mahjong"), known_path)
        assert known_path.read_text(encoding="utf-8").splitlines()[1] == "2026-10-11,,release,mahjong,v2.4"
    print("OK CSV export: header in column order, dates as ISO, NULL as empty field")

    mahjong = load_product_by_id("mahjong")
    assert mahjong.competitors.country == "jp"
    assert len(mahjong.competitors.app_ids) == 5
    assert load_product_by_id("nextuta").competitors.app_ids == ()
    print("OK product config: mahjong has 5 competitors, other products default to none")

    print("\nAll evidence source checks passed.")


if __name__ == "__main__":
    main()
