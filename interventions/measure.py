"""Before / after numbers for an intervention, computed by SQL on the evidence store.

A window is measured only when every day in it has a row in asc_daily. A partial
window is reported as skipped instead of summing fewer days.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from evidence.schema import BaselineMetric
from evidence.store import EvidenceStore, EvidenceStoreError

from .schema import Measurement

DAILY_TABLE = "asc_daily"
TERRITORY = "ALL"
METRICS: dict[str, str] = {
    "impressions": "SUM(impressions)",
    "product_page_views": "SUM(product_page_views)",
    "first_time_downloads": "SUM(first_time_downloads)",
    "impression_to_page_view_pct": (
        "100.0 * SUM(product_page_views) / NULLIF(SUM(impressions), 0)"
    ),
    "page_view_to_download_pct": (
        "100.0 * SUM(first_time_downloads) / NULLIF(SUM(product_page_views), 0)"
    ),
}
_APP_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def before_window(implemented_on: str, window_days: int) -> tuple[str, str]:
    """The window_days days ending the day before the change."""
    day = date.fromisoformat(implemented_on)
    return (
        (day - timedelta(days=window_days)).isoformat(),
        (day - timedelta(days=1)).isoformat(),
    )


def after_window(implemented_on: str, window_days: int) -> tuple[str, str]:
    """The window_days days starting the day after the change."""
    day = date.fromisoformat(implemented_on)
    return (
        (day + timedelta(days=1)).isoformat(),
        (day + timedelta(days=window_days)).isoformat(),
    )


def measure_window(
    store: EvidenceStore,
    *,
    app_id: str,
    start: str,
    end: str,
    measured_at: str,
) -> Measurement:
    if not _APP_ID.match(app_id):
        raise ValueError(f"Unexpected app_id {app_id!r}")
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if last < first:
        raise ValueError(f"Window end {end} is before start {start}")
    expected_days = (last - first).days + 1
    where = (
        f"FROM {DAILY_TABLE} WHERE app_id = '{app_id}' AND territory = '{TERRITORY}' "
        f"AND date BETWEEN '{first.isoformat()}' AND '{last.isoformat()}'"
    )
    measurement = Measurement(
        measured_at=measured_at,
        store=getattr(store, "dialect", ""),
        period_start=first.isoformat(),
        period_end=last.isoformat(),
    )
    try:
        days = int(store.query(f"SELECT COUNT(DISTINCT date) {where}").scalar() or 0)
    except EvidenceStoreError as exc:
        measurement.skipped.append(f"all metrics: {DAILY_TABLE} could not be read ({exc})")
        return measurement
    if days < expected_days:
        measurement.skipped.append(
            f"all metrics: {days}/{expected_days} days have data in {DAILY_TABLE}"
        )
        return measurement
    for name, expression in METRICS.items():
        sql = f"SELECT {expression} {where}"
        try:
            value = store.query(sql).scalar()
        except EvidenceStoreError as exc:
            measurement.skipped.append(f"{name}: query failed ({exc})")
            continue
        if value is None:
            measurement.skipped.append(f"{name}: undefined (denominator is 0)")
            continue
        measurement.metrics.append(
            BaselineMetric(
                metric=name,
                value=round(float(value), 4),
                period_start=first.isoformat(),
                period_end=last.isoformat(),
                sql=sql,
            )
        )
    return measurement
