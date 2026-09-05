"""Fetch AdMob Network report snapshot (period vs prior period, per app).

Metric / dimension names come from the official AdMob API docs:
https://developers.google.com/admob/api/v1/report-metrics-dimensions

- ESTIMATED_EARNINGS (micros)
- IMPRESSIONS (integer)
- IMPRESSION_RPM (micros; UI eCPM equivalent)
- CLICKS (integer)
- APP dimension for per-app rows

These are AdMob Network figures, not GA4 ad_impression / event counts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from config import AdMobSettings, get_admob_settings

from .auth import access_token_from_refresh_token
from .client import AdMobClient

# Official Network report metric enums (do not invent aliases).
METRIC_ESTIMATED_EARNINGS = "ESTIMATED_EARNINGS"
METRIC_IMPRESSIONS = "IMPRESSIONS"
METRIC_IMPRESSION_RPM = "IMPRESSION_RPM"
METRIC_CLICKS = "CLICKS"
DIMENSION_APP = "APP"


@dataclass(frozen=True)
class AdMobAppPeriodTotals:
    app_id: str
    app_label: str | None
    start: str
    end: str
    # False when AdMob returned no row for this app/period. The metric fields are
    # then placeholders and must never be read as measured zeros.
    has_data: bool
    estimated_earnings: float
    impressions: int
    impression_rpm: float
    clicks: int


@dataclass(frozen=True)
class AdMobAppComparison:
    app_id: str
    app_label: str | None
    current: AdMobAppPeriodTotals
    previous: AdMobAppPeriodTotals

    @property
    def both_periods_have_data(self) -> bool:
        return self.current.has_data and self.previous.has_data

    def _change(self, attr: str) -> float | None:
        if not self.both_periods_have_data:
            return None
        return _pct_change(
            float(getattr(self.current, attr)),
            float(getattr(self.previous, attr)),
        )

    def change_estimated_earnings_pct(self) -> float | None:
        return self._change("estimated_earnings")

    def change_impressions_pct(self) -> float | None:
        return self._change("impressions")

    def change_impression_rpm_pct(self) -> float | None:
        return self._change("impression_rpm")

    def change_clicks_pct(self) -> float | None:
        return self._change("clicks")


@dataclass(frozen=True)
class AdMobGrowthSnapshot:
    account_resource: str
    lookback_days: int
    currency_code: str
    auth_mode: str
    current_start: str
    current_end: str
    previous_start: str
    previous_end: str
    apps: tuple[AdMobAppComparison, ...]
    notes: tuple[str, ...]


def _pct_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return (current - previous) / previous * 100.0


def _fmt_pct(change: float | None) -> str:
    if change is None:
        return "n/a (no prior-period baseline)"
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.1f}%"


def _fmt_money(value: float, currency: str) -> str:
    return f"{value:,.2f} {currency}"


def _micros_to_major(raw: Any) -> float:
    try:
        return float(raw) / 1_000_000.0
    except (TypeError, ValueError):
        return 0.0


def _metric_integer(metric_values: dict[str, Any], key: str) -> int:
    entry = metric_values.get(key)
    if not isinstance(entry, dict):
        return 0
    raw = entry.get("integerValue")
    if raw is not None:
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            return 0
    # microsValue carries 1e6 per unit; converting without dividing would inflate
    # counts by a million.
    return int(_micros_to_major(entry.get("microsValue")))


def _metric_micros_major(metric_values: dict[str, Any], key: str) -> float:
    """ESTIMATED_EARNINGS-style values: API returns microsValue."""
    entry = metric_values.get(key)
    if not isinstance(entry, dict):
        return 0.0
    return _micros_to_major(entry.get("microsValue"))


def _metric_impression_rpm_major(metric_values: dict[str, Any]) -> float:
    """IMPRESSION_RPM (UI eCPM).

    Docs describe micros, but live Network report responses return doubleValue
    already in major currency units (confirmed against API response). Prefer
    doubleValue; fall back to microsValue / 1e6 if present.
    """
    entry = metric_values.get(METRIC_IMPRESSION_RPM)
    if not isinstance(entry, dict):
        return 0.0
    if entry.get("doubleValue") is not None:
        try:
            return float(entry["doubleValue"])
        except (TypeError, ValueError):
            return 0.0
    if entry.get("microsValue") is not None:
        return _micros_to_major(entry.get("microsValue"))
    return 0.0


def _date_parts(d: date) -> dict[str, int]:
    return {"year": d.year, "month": d.month, "day": d.day}


def _period_windows(
    *,
    lookback_days: int,
    as_of: date | None,
) -> tuple[date, date, date, date]:
    end = as_of or (date.today() - timedelta(days=1))
    current_start = end - timedelta(days=lookback_days - 1)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=lookback_days - 1)
    return current_start, end, previous_start, previous_end


def _app_display_map(client: AdMobClient, account_resource: str) -> dict[str, str]:
    """Map AdMob appId (ca-app-pub-…~…) → display name when available."""
    out: dict[str, str] = {}
    for app in client.list_apps(account_resource):
        app_id = str(app.get("appId") or "").strip()
        if not app_id:
            continue
        linked = app.get("linkedAppInfo") if isinstance(app.get("linkedAppInfo"), dict) else {}
        manual = app.get("manualAppInfo") if isinstance(app.get("manualAppInfo"), dict) else {}
        label = (
            str(linked.get("displayName") or "").strip()
            or str(manual.get("displayName") or "").strip()
            or None
        )
        if label:
            out[app_id] = label
    return out


def _parse_app_rows(
    messages: list[dict[str, Any]],
    *,
    start: str,
    end: str,
    labels: dict[str, str],
) -> tuple[dict[str, AdMobAppPeriodTotals], str | None]:
    rows: dict[str, AdMobAppPeriodTotals] = {}
    currency: str | None = None

    for msg in messages:
        header = msg.get("header")
        if isinstance(header, dict):
            loc = header.get("localizationSettings")
            if isinstance(loc, dict) and loc.get("currencyCode"):
                currency = str(loc["currencyCode"])

        row = msg.get("row")
        if not isinstance(row, dict):
            continue
        dim_values = row.get("dimensionValues") or {}
        if not isinstance(dim_values, dict):
            continue
        app_dim = dim_values.get(DIMENSION_APP)
        app_id = None
        app_label = None
        if isinstance(app_dim, dict):
            app_id = str(app_dim.get("value") or "").strip() or None
            display = app_dim.get("displayLabel")
            if isinstance(display, str) and display.strip():
                app_label = display.strip()
        if not app_id:
            continue

        metric_values = row.get("metricValues") or {}
        if not isinstance(metric_values, dict):
            metric_values = {}

        if app_label is None:
            app_label = labels.get(app_id)

        rows[app_id] = AdMobAppPeriodTotals(
            app_id=app_id,
            app_label=app_label,
            start=start,
            end=end,
            has_data=True,
            estimated_earnings=_metric_micros_major(
                metric_values, METRIC_ESTIMATED_EARNINGS
            ),
            impressions=_metric_integer(metric_values, METRIC_IMPRESSIONS),
            impression_rpm=_metric_impression_rpm_major(metric_values),
            clicks=_metric_integer(metric_values, METRIC_CLICKS),
        )

    return rows, currency


def _no_data_period(app_id: str, label: str | None, start: str, end: str) -> AdMobAppPeriodTotals:
    """AdMob returned no row for this app/period. Not a measured zero."""
    return AdMobAppPeriodTotals(
        app_id=app_id,
        app_label=label,
        start=start,
        end=end,
        has_data=False,
        estimated_earnings=0.0,
        impressions=0,
        impression_rpm=0.0,
        clicks=0,
    )


def _fetch_period_by_app(
    client: AdMobClient,
    settings: AdMobSettings,
    *,
    start: date,
    end: date,
    labels: dict[str, str],
) -> tuple[dict[str, AdMobAppPeriodTotals], str | None]:
    report_spec: dict[str, Any] = {
        "dateRange": {
            "startDate": _date_parts(start),
            "endDate": _date_parts(end),
        },
        "dimensions": [DIMENSION_APP],
        "metrics": [
            METRIC_ESTIMATED_EARNINGS,
            METRIC_IMPRESSIONS,
            METRIC_IMPRESSION_RPM,
            METRIC_CLICKS,
        ],
        "localizationSettings": {
            "currencyCode": settings.currency_code,
            "languageCode": "ja-JP",
        },
    }
    if settings.app_ids:
        report_spec["dimensionFilters"] = [
            {
                "dimension": DIMENSION_APP,
                "matchesAny": {"values": list(settings.app_ids)},
            }
        ]

    messages = client.generate_network_report(settings.account_resource, report_spec)
    return _parse_app_rows(
        messages,
        start=start.isoformat(),
        end=end.isoformat(),
        labels=labels,
    )


def fetch_admob_snapshot(
    settings: AdMobSettings | None = None,
    *,
    as_of: date | None = None,
) -> AdMobGrowthSnapshot:
    settings = settings or get_admob_settings()
    if settings is None:
        raise RuntimeError("AdMob is not configured")

    token = access_token_from_refresh_token(
        client_id=settings.oauth_client_id,
        client_secret=settings.oauth_client_secret,
        refresh_token=settings.refresh_token,
    )
    client = AdMobClient(token)
    labels = _app_display_map(client, settings.account_resource)

    current_start, current_end, previous_start, previous_end = _period_windows(
        lookback_days=settings.lookback_days,
        as_of=as_of,
    )

    current_rows, currency_cur = _fetch_period_by_app(
        client,
        settings,
        start=current_start,
        end=current_end,
        labels=labels,
    )
    previous_rows, currency_prev = _fetch_period_by_app(
        client,
        settings,
        start=previous_start,
        end=previous_end,
        labels=labels,
    )

    currency = currency_cur or currency_prev or settings.currency_code
    app_ids = settings.app_ids or tuple(
        sorted(set(current_rows) | set(previous_rows), key=lambda x: labels.get(x, x))
    )
    if settings.app_ids:
        # Keep configured order; include configured apps even if a period has no rows.
        app_ids = settings.app_ids

    comparisons: list[AdMobAppComparison] = []
    for app_id in app_ids:
        label = labels.get(app_id)
        cur = current_rows.get(app_id) or _no_data_period(
            app_id, label, current_start.isoformat(), current_end.isoformat()
        )
        prev = previous_rows.get(app_id) or _no_data_period(
            app_id, label, previous_start.isoformat(), previous_end.isoformat()
        )
        # Prefer label from either period row.
        row_label = cur.app_label or prev.app_label or label
        if row_label and (cur.app_label != row_label or prev.app_label != row_label):
            cur = AdMobAppPeriodTotals(**{**cur.__dict__, "app_label": row_label})
            prev = AdMobAppPeriodTotals(**{**prev.__dict__, "app_label": row_label})
        comparisons.append(
            AdMobAppComparison(
                app_id=app_id,
                app_label=row_label,
                current=cur,
                previous=prev,
            )
        )

    notes = [
        "Metrics from AdMob Network report "
        f"({METRIC_ESTIMATED_EARNINGS}, {METRIC_IMPRESSIONS}, "
        f"{METRIC_IMPRESSION_RPM}, {METRIC_CLICKS}) with dimension {DIMENSION_APP}.",
        f"{METRIC_IMPRESSION_RPM} is the API name for UI eCPM "
        "(response uses doubleValue in major currency units; microsValue fallback supported).",
        "AdMob IMPRESSIONS is not GA4 ad_impression; do not treat them as the same series.",
        "Period windows match ASC/GA4 style: lookback N days ending on as_of (default yesterday).",
        "Authenticated via OAuth refresh token (admob.readonly), separate from the GA4 token.",
    ]
    if settings.app_ids:
        notes.append("Filtered to configured ADMOB_APP_ID(S): " + ", ".join(settings.app_ids) + ".")
    else:
        notes.append("No ADMOB_APP_ID filter; rows are every app returned for the account.")

    missing: list[str] = []
    for comparison in comparisons:
        name = comparison.app_label or comparison.app_id
        if not comparison.current.has_data:
            missing.append(
                f"{name} current period ({comparison.current.start} → {comparison.current.end})"
            )
        if not comparison.previous.has_data:
            missing.append(
                f"{name} previous period ({comparison.previous.start} → {comparison.previous.end})"
            )
    if missing:
        notes.append(
            "AdMob returned NO rows for: "
            + "; ".join(missing)
            + ". Those metrics are UNAVAILABLE, not zero. Do not read them as 0, do "
            "not infer that earnings/impressions stopped, and treat the "
            "period-over-period change for that app as n/a."
        )

    return AdMobGrowthSnapshot(
        account_resource=settings.account_resource,
        lookback_days=settings.lookback_days,
        currency_code=currency,
        auth_mode="oauth_refresh_token",
        current_start=current_start.isoformat(),
        current_end=current_end.isoformat(),
        previous_start=previous_start.isoformat(),
        previous_end=previous_end.isoformat(),
        apps=tuple(comparisons),
        notes=tuple(notes),
    )


def try_fetch_admob_snapshot(
    *,
    as_of: date | None = None,
) -> tuple[AdMobGrowthSnapshot | None, str | None]:
    """Return (snapshot, skip_or_error_message). None message means connected OK."""
    settings = get_admob_settings()
    if settings is None:
        return None, "AdMob: not connected (missing configuration)."
    try:
        return fetch_admob_snapshot(settings, as_of=as_of), None
    except Exception as exc:
        return None, f"AdMob: fetch failed ({exc})."


def format_period_comparison(snapshot: AdMobGrowthSnapshot) -> str:
    """Human-readable per-app period comparison for verification scripts."""
    lines = [
        f"Account: {snapshot.account_resource}",
        f"Currency: {snapshot.currency_code}",
        f"Current: {snapshot.current_start} → {snapshot.current_end}",
        f"Previous: {snapshot.previous_start} → {snapshot.previous_end}",
        "",
    ]
    if not snapshot.apps:
        lines.append("No app rows returned.")
        return "\n".join(lines)

    for app in snapshot.apps:
        title = app.app_label or app.app_id
        lines.append(f"## {title}")
        lines.append(f"- app_id: {app.app_id}")
        for label, period in (("Current", app.current), ("Previous", app.previous)):
            lines.append(f"{label}:")
            if not period.has_data:
                lines.append("  - no AdMob rows returned for this period (data unavailable, not 0)")
                continue
            lines.append(
                f"  - estimated earnings ({METRIC_ESTIMATED_EARNINGS}): "
                f"{_fmt_money(period.estimated_earnings, snapshot.currency_code)}"
            )
            lines.append(f"  - impressions ({METRIC_IMPRESSIONS}): {period.impressions:,}")
            lines.append(
                f"  - eCPM / IMPRESSION_RPM: "
                f"{_fmt_money(period.impression_rpm, snapshot.currency_code)}"
            )
            lines.append(f"  - clicks ({METRIC_CLICKS}): {period.clicks:,}")
        lines.append("Period-over-period:")
        lines.append(f"  - estimated earnings: {_fmt_pct(app.change_estimated_earnings_pct())}")
        lines.append(f"  - impressions: {_fmt_pct(app.change_impressions_pct())}")
        lines.append(f"  - eCPM / IMPRESSION_RPM: {_fmt_pct(app.change_impression_rpm_pct())}")
        lines.append(f"  - clicks: {_fmt_pct(app.change_clicks_pct())}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
