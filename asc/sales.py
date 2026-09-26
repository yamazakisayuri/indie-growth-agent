"""App Store Connect Sales Reports (Sales and Trends) for Product revenue.

Phase 2 primary path:
  reportType=SALES, reportSubType=SUMMARY, frequency=DAILY
  amount = sum(Units × Developer Proceeds) per currency (worldwide)

This is Trends Developer Proceeds — not Financial Partner Share.
"""

from __future__ import annotations

import gzip
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

from .auth import create_jwt
from .client import AscApiError
from .tsv import parse_tsv, tsv_field

logger = logging.getLogger(__name__)

SalesStatus = Literal[
    "ok",
    "no_data",
    "not_configured",
    "permission_denied",
    "unavailable",
    "error",
]

SALES_REPORT_VERSION = "1_0"


@dataclass(frozen=True)
class CurrencyProceeds:
    currency: str
    amount: float
    units: int  # paid / proceeds-bearing units only


@dataclass(frozen=True)
class PeriodProceeds:
    start: str
    end: str
    by_currency: tuple[CurrencyProceeds, ...] = ()

    @property
    def total_paid_units(self) -> int:
        return sum(c.units for c in self.by_currency)

    def amount_for(self, currency: str) -> float:
        key = currency.strip().upper()
        for row in self.by_currency:
            if row.currency == key:
                return row.amount
        return 0.0


@dataclass(frozen=True)
class AscSalesRevenueSnapshot:
    """Product-scoped App Store Sales proceeds for Analyzer windows."""

    app_id: str
    app_sku: str
    status: SalesStatus
    status_message: str | None
    vendor_configured: bool
    lookback_days: int
    current: PeriodProceeds
    previous: PeriodProceeds
    notes: tuple[str, ...] = ()
    # Days where Apple returned a report (including empty-after-filter) vs 404 no-sales.
    days_fetched: int = 0
    days_no_sales_account: int = 0
    days_error: int = 0

    def change_percent_for(self, currency: str) -> float | None:
        """Period-over-period % for one currency. None when previous is 0."""
        prev = self.previous.amount_for(currency)
        if prev == 0:
            return None
        cur = self.current.amount_for(currency)
        return (cur - prev) / prev * 100.0


def row_belongs_to_product(
    row: dict[str, str],
    *,
    app_id: str,
    app_sku: str,
) -> bool:
    """Product ownership for Sales SUMMARY rows (apps + IAP).

    IAP rows use the IAP Apple Identifier, not the app id. Match either:
    - Apple Identifier == appId, or
    - Parent Identifier == app SKU
    """
    apple_id = tsv_field(row, "Apple Identifier").strip()
    parent = tsv_field(row, "Parent Identifier").strip()
    app_id_s = (app_id or "").strip()
    sku_s = (app_sku or "").strip()
    if app_id_s and apple_id == app_id_s:
        return True
    if sku_s and parent == sku_s:
        return True
    return False


def _parse_decimal(raw: str) -> float:
    text = (raw or "").strip().replace(",", "")
    if not text or text in (".", "-"):
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _parse_units(raw: str) -> int:
    text = (raw or "").strip().replace(",", "")
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def is_proceeds_bearing_row(row: dict[str, str]) -> bool:
    """True when the row contributes paid / refunded proceeds (not free DL)."""
    proceeds = _parse_decimal(tsv_field(row, "Developer Proceeds"))
    price = _parse_decimal(tsv_field(row, "Customer Price"))
    return proceeds != 0.0 or price != 0.0


def aggregate_product_proceeds(
    rows: list[dict[str, str]],
    *,
    app_id: str,
    app_sku: str,
) -> dict[str, CurrencyProceeds]:
    """Sum Units × Developer Proceeds by Currency of Proceeds for one product."""
    amounts: dict[str, float] = {}
    units: dict[str, int] = {}
    for row in rows:
        if not row_belongs_to_product(row, app_id=app_id, app_sku=app_sku):
            continue
        unit_n = _parse_units(tsv_field(row, "Units"))
        proceeds_per = _parse_decimal(tsv_field(row, "Developer Proceeds"))
        line = unit_n * proceeds_per
        currency = tsv_field(row, "Currency of Proceeds").strip().upper()
        if not currency:
            # Free rows often leave Currency of Proceeds blank; skip empty currency
            # unless there is a non-zero proceeds contribution (unexpected).
            if line == 0.0 and not is_proceeds_bearing_row(row):
                continue
            currency = tsv_field(row, "Customer Currency").strip().upper() or "UNK"
        amounts[currency] = amounts.get(currency, 0.0) + line
        if is_proceeds_bearing_row(row):
            units[currency] = units.get(currency, 0) + unit_n
    return {
        cur: CurrencyProceeds(
            currency=cur,
            amount=round(amounts[cur], 4),
            units=units.get(cur, 0),
        )
        for cur in sorted(amounts.keys())
        if amounts[cur] != 0.0 or units.get(cur, 0) != 0
    }


def _merge_currency_maps(
    into: dict[str, list[float | int]],
    chunk: dict[str, CurrencyProceeds],
) -> None:
    for cur, row in chunk.items():
        bucket = into.setdefault(cur, [0.0, 0])
        bucket[0] = float(bucket[0]) + row.amount
        bucket[1] = int(bucket[1]) + row.units


def _freeze_currency_map(raw: dict[str, list[float | int]]) -> tuple[CurrencyProceeds, ...]:
    out: list[CurrencyProceeds] = []
    for cur in sorted(raw.keys()):
        amount, units = raw[cur]
        out.append(
            CurrencyProceeds(
                currency=cur,
                amount=round(float(amount), 4),
                units=int(units),
            )
        )
    return tuple(out)


def download_daily_sales_report(
    *,
    bearer_jwt: str,
    vendor_number: str,
    report_date: str,
    timeout: float = 120.0,
) -> tuple[list[dict[str, str]] | None, str]:
    """Return (rows, status_token).

    status_token:
      - ok: report downloaded (may be empty after parse)
      - no_sales: Apple 404 — no sales for the date (normal)
      - permission_denied / error: failures
    """
    import httpx

    params: dict[str, Any] = {
        "filter[vendorNumber]": vendor_number,
        "filter[reportType]": "SALES",
        "filter[reportSubType]": "SUMMARY",
        "filter[frequency]": "DAILY",
        "filter[reportDate]": report_date,
        "filter[version]": SALES_REPORT_VERSION,
    }
    try:
        # Sales endpoint returns gzip bytes, not JSON.
        response = httpx.get(
            "https://api.appstoreconnect.apple.com/v1/salesReports",
            headers={
                "Authorization": f"Bearer {bearer_jwt}",
                "Accept": "application/a-gzip",
            },
            params=params,
            timeout=timeout,
            follow_redirects=True,
        )
    except Exception as exc:
        logger.warning("ASC sales download failed for %s: %s", report_date, exc)
        return None, "error"

    if response.status_code == 404:
        return None, "no_sales"
    if response.status_code == 403:
        return None, "permission_denied"
    if response.status_code >= 400:
        detail = ""
        try:
            payload = response.json()
            errors = payload.get("errors") or []
            if errors:
                detail = errors[0].get("detail") or errors[0].get("title") or ""
        except Exception:
            detail = response.text[:200]
        logger.warning(
            "ASC sales HTTP %s for %s: %s",
            response.status_code,
            report_date,
            detail,
        )
        return None, "error"

    raw = response.content
    try:
        text = gzip.decompress(raw).decode("utf-8")
    except OSError:
        text = raw.decode("utf-8")
    return parse_tsv(text), "ok"


def _daterange(start: date, end: date) -> list[date]:
    days: list[date] = []
    cur = start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)
    return days


def _aggregate_period(
    *,
    bearer_jwt: str,
    vendor_number: str,
    app_id: str,
    app_sku: str,
    start: date,
    end: date,
) -> tuple[PeriodProceeds, int, int, int, SalesStatus | None, str | None]:
    """Fetch each day and aggregate. Returns period + day counters + hard fail status."""
    amounts: dict[str, list[float | int]] = {}
    fetched = 0
    no_sales = 0
    errors = 0
    hard_status: SalesStatus | None = None
    hard_message: str | None = None

    for day in _daterange(start, end):
        rows, token = download_daily_sales_report(
            bearer_jwt=bearer_jwt,
            vendor_number=vendor_number,
            report_date=day.isoformat(),
        )
        if token == "no_sales":
            no_sales += 1
            continue
        if token == "permission_denied":
            hard_status = "permission_denied"
            hard_message = "ASC Sales Reports forbidden (API key lacks Sales access)"
            break
        if token != "ok" or rows is None:
            errors += 1
            continue
        fetched += 1
        chunk = aggregate_product_proceeds(rows, app_id=app_id, app_sku=app_sku)
        _merge_currency_maps(amounts, chunk)

    period = PeriodProceeds(
        start=start.isoformat(),
        end=end.isoformat(),
        by_currency=_freeze_currency_map(amounts),
    )
    return period, fetched, no_sales, errors, hard_status, hard_message


def fetch_sales_revenue_snapshot(
    *,
    app_id: str,
    app_sku: str,
    current_start: str,
    current_end: str,
    previous_start: str,
    previous_end: str,
    lookback_days: int,
    vendor_number: str | None = None,
) -> AscSalesRevenueSnapshot:
    """Fetch WW Sales Developer Proceeds for one product across Analyzer windows."""
    from config import get_asc_vendor_number, get_app_store_connect_credentials

    vendor = (vendor_number if vendor_number is not None else get_asc_vendor_number()) or ""
    vendor = vendor.strip()
    notes = [
        "App Store revenue uses Sales Reports Developer Proceeds (Trends), worldwide.",
        "Not Financial Reports Partner Share (final settled proceeds).",
        "Scope is WW — independent of ASC Analytics territory (e.g. JP).",
        "Free download Units are not counted as revenue units.",
        "Currencies are kept separate; no FX conversion or cross-currency sum.",
    ]

    empty_current = PeriodProceeds(start=current_start, end=current_end)
    empty_previous = PeriodProceeds(start=previous_start, end=previous_end)

    if not vendor:
        return AscSalesRevenueSnapshot(
            app_id=app_id,
            app_sku=app_sku,
            status="not_configured",
            status_message="ASC_VENDOR_NUMBER is not set",
            vendor_configured=False,
            lookback_days=lookback_days,
            current=empty_current,
            previous=empty_previous,
            notes=tuple(notes),
        )

    if not (app_id or "").strip() or not (app_sku or "").strip():
        return AscSalesRevenueSnapshot(
            app_id=app_id or "",
            app_sku=app_sku or "",
            status="not_configured",
            status_message="App Store appId and sku are required for Sales revenue",
            vendor_configured=True,
            lookback_days=lookback_days,
            current=empty_current,
            previous=empty_previous,
            notes=tuple(notes),
        )

    try:
        creds = get_app_store_connect_credentials()
        bearer = create_jwt(creds)
    except Exception as exc:
        logger.warning("ASC sales auth failed: %s", exc)
        return AscSalesRevenueSnapshot(
            app_id=app_id,
            app_sku=app_sku,
            status="error",
            status_message=str(exc),
            vendor_configured=True,
            lookback_days=lookback_days,
            current=empty_current,
            previous=empty_previous,
            notes=tuple(notes),
        )

    try:
        cur_start = date.fromisoformat(current_start)
        cur_end = date.fromisoformat(current_end)
        prev_start = date.fromisoformat(previous_start)
        prev_end = date.fromisoformat(previous_end)
    except ValueError as exc:
        return AscSalesRevenueSnapshot(
            app_id=app_id,
            app_sku=app_sku,
            status="error",
            status_message=f"Invalid period dates: {exc}",
            vendor_configured=True,
            lookback_days=lookback_days,
            current=empty_current,
            previous=empty_previous,
            notes=tuple(notes),
        )

    current, f1, n1, e1, hard, hard_msg = _aggregate_period(
        bearer_jwt=bearer,
        vendor_number=vendor,
        app_id=app_id,
        app_sku=app_sku,
        start=cur_start,
        end=cur_end,
    )
    if hard is not None:
        return AscSalesRevenueSnapshot(
            app_id=app_id,
            app_sku=app_sku,
            status=hard,
            status_message=hard_msg,
            vendor_configured=True,
            lookback_days=lookback_days,
            current=empty_current,
            previous=empty_previous,
            notes=tuple(notes),
            days_fetched=f1,
            days_no_sales_account=n1,
            days_error=e1,
        )

    previous, f2, n2, e2, hard2, hard_msg2 = _aggregate_period(
        bearer_jwt=bearer,
        vendor_number=vendor,
        app_id=app_id,
        app_sku=app_sku,
        start=prev_start,
        end=prev_end,
    )
    if hard2 is not None:
        return AscSalesRevenueSnapshot(
            app_id=app_id,
            app_sku=app_sku,
            status=hard2,
            status_message=hard_msg2,
            vendor_configured=True,
            lookback_days=lookback_days,
            current=empty_current,
            previous=empty_previous,
            notes=tuple(notes),
            days_fetched=f1 + f2,
            days_no_sales_account=n1 + n2,
            days_error=e1 + e2,
        )

    fetched = f1 + f2
    no_sales = n1 + n2
    errors = e1 + e2
    total_days = (cur_end - cur_start).days + 1 + (prev_end - prev_start).days + 1

    if errors > 0 and fetched == 0 and no_sales == 0:
        status: SalesStatus = "error"
        message = "ASC Sales Reports failed for all days in the Analyzer windows"
    elif errors > 0 and fetched == 0:
        # Only 404s + errors with no successful downloads — treat as unavailable
        status = "unavailable"
        message = "ASC Sales Reports unavailable for Analyzer windows"
    else:
        # Successful path: zero paid proceeds is ok (e.g. Mahjong).
        status = "ok"
        message = None
        if errors:
            notes = notes + (
                f"Some daily Sales downloads failed ({errors}/{total_days} days); "
                "aggregates use successfully fetched days plus no-sales days as zero.",
            )

    return AscSalesRevenueSnapshot(
        app_id=app_id,
        app_sku=app_sku,
        status=status,
        status_message=message,
        vendor_configured=True,
        lookback_days=lookback_days,
        current=current,
        previous=previous,
        notes=tuple(notes),
        days_fetched=fetched,
        days_no_sales_account=no_sales,
        days_error=errors,
    )


def try_fetch_sales_revenue_snapshot(
    *,
    app_id: str | None,
    app_sku: str | None,
    current_start: str,
    current_end: str,
    previous_start: str,
    previous_end: str,
    lookback_days: int,
) -> AscSalesRevenueSnapshot:
    """Never raises — soft-fail into status fields for Analyze continuity."""
    try:
        return fetch_sales_revenue_snapshot(
            app_id=app_id or "",
            app_sku=app_sku or "",
            current_start=current_start,
            current_end=current_end,
            previous_start=previous_start,
            previous_end=previous_end,
            lookback_days=lookback_days,
        )
    except AscApiError as exc:
        status: SalesStatus = (
            "permission_denied" if exc.status == 403 else "error"
        )
        return AscSalesRevenueSnapshot(
            app_id=app_id or "",
            app_sku=app_sku or "",
            status=status,
            status_message=exc.message,
            vendor_configured=True,
            lookback_days=lookback_days,
            current=PeriodProceeds(start=current_start, end=current_end),
            previous=PeriodProceeds(start=previous_start, end=previous_end),
            notes=("ASC Sales fetch raised AscApiError.",),
        )
    except Exception as exc:
        logger.exception("ASC Sales revenue fetch failed")
        return AscSalesRevenueSnapshot(
            app_id=app_id or "",
            app_sku=app_sku or "",
            status="error",
            status_message=str(exc),
            vendor_configured=True,
            lookback_days=lookback_days,
            current=PeriodProceeds(start=current_start, end=current_end),
            previous=PeriodProceeds(start=previous_start, end=previous_end),
            notes=("ASC Sales fetch raised an unexpected error.",),
        )
