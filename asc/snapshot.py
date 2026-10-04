"""High-level ASC growth snapshot for the agent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from config import AppStoreConnectSettings, get_app_store_connect_settings

from .analytics import (
    list_daily_instances,
    list_report_requests,
    list_reports,
    load_instance_texts,
    pick_discovery_report,
    pick_downloads_report,
    pick_report_request,
)
from .apps import AscApp, resolve_app
from .auth import create_jwt
from .client import AscClient
from .tsv import (
    DailyMetrics,
    aggregate_discovery,
    aggregate_downloads,
    merge_daily,
    pct_change,
    sum_metrics,
)

# The instances endpoint returns oldest-first, so a low limit silently drops the
# newest reports. Request the API maximum and let the client-side sort pick the top.
MAX_INSTANCES = 200


@dataclass(frozen=True)
class PeriodTotals:
    start: str
    end: str
    days_with_data: int
    impressions: int
    product_page_views: int
    first_time_downloads: int
    impressions_by_source: dict[str, int]
    downloads_by_source: dict[str, int]

    @property
    def impression_to_page_view_rate(self) -> float | None:
        if self.impressions <= 0:
            return None
        return self.product_page_views / self.impressions

    @property
    def page_view_to_download_rate(self) -> float | None:
        if self.product_page_views <= 0:
            return None
        return self.first_time_downloads / self.product_page_views

    @property
    def impression_to_download_rate(self) -> float | None:
        if self.impressions <= 0:
            return None
        return self.first_time_downloads / self.impressions


@dataclass(frozen=True)
class AscGrowthSnapshot:
    app: AscApp
    territory: str
    lookback_days: int
    current: PeriodTotals
    previous: PeriodTotals
    daily: list[DailyMetrics]
    report_request_id: str
    latest_processing_date: str

    def change_impressions_pct(self) -> float | None:
        return pct_change(self.current.impressions, self.previous.impressions)

    def change_page_views_pct(self) -> float | None:
        return pct_change(self.current.product_page_views, self.previous.product_page_views)

    def change_downloads_pct(self) -> float | None:
        return pct_change(self.current.first_time_downloads, self.previous.first_time_downloads)


def _to_period(days: list[DailyMetrics], start: str, end: str) -> PeriodTotals:
    total = sum_metrics(days)
    return PeriodTotals(
        start=start,
        end=end,
        days_with_data=len(days),
        impressions=total.impressions,
        product_page_views=total.product_page_views,
        first_time_downloads=total.first_time_downloads,
        impressions_by_source=dict(sorted(total.impressions_by_source.items())),
        downloads_by_source=dict(sorted(total.downloads_by_source.items())),
    )


def _collect_report_days(
    client: AscClient,
    report_id: str,
    territory: str,
    kind: str,
) -> dict[str, DailyMetrics]:
    # Consecutive daily instances re-deliver the same date, so each date is taken
    # from the newest instance only (instances are newest-first) instead of summed.
    by_date: dict[str, DailyMetrics] = {}
    instances = list_daily_instances(client, report_id, limit=MAX_INSTANCES)
    for instance in instances:
        instance_days: dict[str, DailyMetrics] = {}
        for text in load_instance_texts(client, instance.id):
            if kind == "discovery":
                chunk = aggregate_discovery(text, territory)
            else:
                chunk = aggregate_downloads(text, territory)
            merge_daily(instance_days, chunk)
        for day, metrics in instance_days.items():
            by_date.setdefault(day, metrics)
    return by_date


def fetch_growth_snapshot(
    settings: AppStoreConnectSettings | None = None,
) -> AscGrowthSnapshot:
    settings = settings or get_app_store_connect_settings()
    token = create_jwt(settings.credentials)
    client = AscClient(token)

    app = resolve_app(
        client,
        app_id=settings.app_id,
        bundle_id=settings.bundle_id,
    )

    requests = list_report_requests(client, app.id)
    request = pick_report_request(requests, preferred_id=settings.analytics_request_id)
    reports = list_reports(client, request.id)
    discovery = pick_discovery_report(reports)
    downloads = pick_downloads_report(reports)

    discovery_days = _collect_report_days(client, discovery.id, settings.territory, "discovery")
    download_days = _collect_report_days(client, downloads.id, settings.territory, "downloads")

    merged: dict[str, DailyMetrics] = {}
    merge_daily(merged, discovery_days)
    merge_daily(merged, download_days)

    if not merged:
        raise RuntimeError(
            "No App Store analytics daily rows found. "
            "Reports may still be processing, or the territory filter excluded all rows."
        )

    ordered = sorted(merged.values(), key=lambda d: d.date)
    latest = ordered[-1].date
    lookback = settings.lookback_days

    current_end = date.fromisoformat(latest)
    current_start = current_end - timedelta(days=lookback - 1)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=lookback - 1)

    current_days = [
        d
        for d in ordered
        if current_start.isoformat() <= d.date <= current_end.isoformat()
    ]
    previous_days = [
        d
        for d in ordered
        if previous_start.isoformat() <= d.date <= previous_end.isoformat()
    ]

    return AscGrowthSnapshot(
        app=app,
        territory=settings.territory,
        lookback_days=lookback,
        current=_to_period(current_days, current_start.isoformat(), current_end.isoformat()),
        previous=_to_period(previous_days, previous_start.isoformat(), previous_end.isoformat()),
        daily=ordered,
        report_request_id=request.id,
        latest_processing_date=latest,
    )
