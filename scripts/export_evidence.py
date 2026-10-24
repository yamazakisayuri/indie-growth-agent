"""Load a product's evidence tables into the evidence store (and optionally CSV).

Run:
  python scripts/export_evidence.py --product-id mahjong
  python scripts/export_evidence.py --product-id mahjong --csv-dir tmp/evidence_csv

Fetches App Store Connect daily data (needs ASC credentials), Known Events, and
public competitor listings (iTunes Lookup, no key). The store is EVIDENCE_STORE.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from asc import fetch_growth_snapshot  # noqa: E402
from evidence import build_store  # noqa: E402
from evidence.sources import (  # noqa: E402
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
from known_events import load_all_known_events  # noqa: E402
from product_config import use_product  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--product-id", default=None, help="Defaults to products/index.json")
    parser.add_argument("--csv-dir", type=Path, default=None, help="Also write one CSV per table")
    parser.add_argument("--skip-asc", action="store_true", help="Skip ASC (no credentials needed)")
    parser.add_argument("--skip-competitors", action="store_true", help="Skip iTunes Lookup")
    args = parser.parse_args()

    tables = []
    with use_product(args.product_id) as product:
        self_app_id = product.app_store.app_id
        if not args.skip_asc:
            snapshot = fetch_growth_snapshot()
            app_id = snapshot.app.id
            self_app_id = self_app_id or app_id
            tables.append(
                (ASC_DAILY, asc_daily_rows(snapshot.daily, app_id=app_id, territory=snapshot.territory))
            )
            tables.append(
                (
                    ASC_DAILY_BY_SOURCE,
                    asc_daily_by_source_rows(
                        snapshot.daily, app_id=app_id, territory=snapshot.territory
                    ),
                )
            )
        tables.append((KNOWN_EVENTS, known_event_rows(load_all_known_events(), product_id=product.id)))
        if not args.skip_competitors:
            competitors = product.competitors
            ids = [i for i in (self_app_id, *competitors.app_ids) if i]
            results = fetch_itunes_lookup(ids, country=competitors.country)
            missing = sorted(set(ids) - {str(r.get("trackId")) for r in results})
            if missing:
                print(f"warning: not found in the {competitors.country} store: {', '.join(missing)}")
            tables.append(
                (
                    COMPETITOR_LISTING,
                    competitor_listing_rows(
                        results,
                        self_app_id=self_app_id,
                        fetched_on=date.today(),
                        country=competitors.country,
                    ),
                )
            )

    store = build_store()
    try:
        for spec, rows in tables:
            count = store.replace_table(spec, rows)
            line = f"{spec.name}: {count} rows → {store.dialect}"
            if args.csv_dir is not None:
                path = args.csv_dir / f"{spec.name}.csv"
                write_csv(spec, rows, path)
                line += f", {path}"
            print(line)
    finally:
        store.close()


if __name__ == "__main__":
    main()
