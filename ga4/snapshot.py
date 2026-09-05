"""Fetch GA4 growth snapshot for the agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from config import Ga4EventDefinition, Ga4Settings, get_ga4_settings

from .auth import (
    access_token_from_refresh_token,
    access_token_from_service_account,
    service_account_email,
)
from .client import Ga4Client


@dataclass(frozen=True)
class Ga4PeriodTotals:
    start: str
    end: str
    # Period-scoped metrics from a single GA4 dateRange (no date dimension).
    active_users: int
    sessions: int
    screen_page_views: int
    key_event_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Ga4GrowthSnapshot:
    property_id: str
    property_resource: str
    lookback_days: int
    key_event_names: tuple[str, ...]
    event_definitions: tuple[Ga4EventDefinition, ...]
    auth_mode: str
    current: Ga4PeriodTotals
    previous: Ga4PeriodTotals
    notes: tuple[str, ...]

    @property
    def undefined_event_names(self) -> tuple[str, ...]:
        """Configured key events with no declared definition; meaning stays off-limits."""
        defined = {d.name for d in self.event_definitions}
        return tuple(n for n in self.key_event_names if n not in defined)

    def change_active_users_pct(self) -> float | None:
        return _pct_change(self.current.active_users, self.previous.active_users)

    def change_sessions_pct(self) -> float | None:
        return _pct_change(self.current.sessions, self.previous.sessions)

    def change_screen_page_views_pct(self) -> float | None:
        return _pct_change(self.current.screen_page_views, self.previous.screen_page_views)


def _pct_change(current: int, previous: int) -> float | None:
    if previous <= 0:
        return None
    return (current - previous) / previous * 100.0


def _fmt_pct(change: float | None) -> str:
    if change is None:
        return "n/a (no prior-period baseline)"
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.1f}%"


def _metric_int(row: dict, index: int) -> int:
    values = row.get("metricValues") or []
    if index >= len(values):
        return 0
    raw = values[index].get("value") if isinstance(values[index], dict) else None
    try:
        n = float(raw) if raw is not None else 0.0
    except (TypeError, ValueError):
        return 0
    return int(n) if n > 0 else 0


def _fetch_period_totals(
    client: Ga4Client,
    property_resource: str,
    start: str,
    end: str,
) -> tuple[int, int, int]:
    """Return period-scoped (activeUsers, sessions, screenPageViews)."""
    payload = client.run_report(
        property_resource,
        {
            "dateRanges": [{"startDate": start, "endDate": end}],
            "metrics": [
                {"name": "activeUsers"},
                {"name": "sessions"},
                {"name": "screenPageViews"},
            ],
        },
    )
    rows = payload.get("rows") or []
    if not rows or not isinstance(rows[0], dict):
        return 0, 0, 0
    row = rows[0]
    return _metric_int(row, 0), _metric_int(row, 1), _metric_int(row, 2)


def _fetch_key_events(
    client: Ga4Client,
    property_resource: str,
    start: str,
    end: str,
    event_names: tuple[str, ...],
) -> dict[str, int]:
    if not event_names:
        return {}
    payload = client.run_report(
        property_resource,
        {
            "dateRanges": [{"startDate": start, "endDate": end}],
            "dimensions": [{"name": "eventName"}],
            "dimensionFilter": {
                "filter": {
                    "fieldName": "eventName",
                    "inListFilter": {"values": list(event_names)},
                }
            },
            "metrics": [{"name": "eventCount"}],
        },
    )
    counts = {name: 0 for name in event_names}
    for row in payload.get("rows") or []:
        if not isinstance(row, dict):
            continue
        dims = row.get("dimensionValues") or []
        name = dims[0].get("value") if dims and isinstance(dims[0], dict) else None
        if not name:
            continue
        counts[str(name)] = _metric_int(row, 0)
    return counts


def _access_token(settings: Ga4Settings) -> tuple[str, str]:
    if settings.service_account_path is not None:
        return access_token_from_service_account(settings.service_account_path), "service_account"
    assert settings.oauth_client_id and settings.oauth_client_secret and settings.refresh_token
    return (
        access_token_from_refresh_token(
            client_id=settings.oauth_client_id,
            client_secret=settings.oauth_client_secret,
            refresh_token=settings.refresh_token,
        ),
        "oauth_refresh_token",
    )


def fetch_ga4_snapshot(
    settings: Ga4Settings | None = None,
    *,
    as_of: date | None = None,
) -> Ga4GrowthSnapshot:
    settings = settings or get_ga4_settings()
    if settings is None:
        raise RuntimeError("GA4 is not configured")

    token, auth_mode = _access_token(settings)
    client = Ga4Client(token)

    end = as_of or (date.today() - timedelta(days=1))
    lookback = settings.lookback_days
    current_start = end - timedelta(days=lookback - 1)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=lookback - 1)

    cur_users, cur_sessions, cur_views = _fetch_period_totals(
        client,
        settings.property_resource,
        current_start.isoformat(),
        end.isoformat(),
    )
    prev_users, prev_sessions, prev_views = _fetch_period_totals(
        client,
        settings.property_resource,
        previous_start.isoformat(),
        previous_end.isoformat(),
    )

    current_events = _fetch_key_events(
        client,
        settings.property_resource,
        current_start.isoformat(),
        end.isoformat(),
        settings.key_event_names,
    )
    previous_events = _fetch_key_events(
        client,
        settings.property_resource,
        previous_start.isoformat(),
        previous_end.isoformat(),
        settings.key_event_names,
    )

    current = Ga4PeriodTotals(
        start=current_start.isoformat(),
        end=end.isoformat(),
        active_users=cur_users,
        sessions=cur_sessions,
        screen_page_views=cur_views,
        key_event_counts=current_events,
    )
    previous = Ga4PeriodTotals(
        start=previous_start.isoformat(),
        end=previous_end.isoformat(),
        active_users=prev_users,
        sessions=prev_sessions,
        screen_page_views=prev_views,
        key_event_counts=previous_events,
    )

    notes = [
        "activeUsers / sessions / screenPageViews are period-scoped totals "
        "(single GA4 dateRange, no date dimension). activeUsers is not a sum of daily activeUsers.",
    ]
    if settings.key_event_names:
        defined = {d.name for d in settings.event_definitions}
        undefined = [n for n in settings.key_event_names if n not in defined]
        note = "Key eventCounts included only for: " + ", ".join(settings.key_event_names) + "."
        if undefined:
            note += " No declared definition for: " + ", ".join(undefined) + "."
        notes.append(note)
    if settings.service_account_path is not None:
        email = service_account_email(settings.service_account_path)
        if email:
            notes.append(f"Authenticated via service account ({email}).")
    else:
        notes.append("Authenticated via OAuth refresh token.")

    return Ga4GrowthSnapshot(
        property_id=settings.property_id,
        property_resource=settings.property_resource,
        lookback_days=lookback,
        key_event_names=settings.key_event_names,
        event_definitions=settings.event_definitions,
        auth_mode=auth_mode,
        current=current,
        previous=previous,
        notes=tuple(notes),
    )


def try_fetch_ga4_snapshot(
    *,
    as_of: date | None = None,
) -> tuple[Ga4GrowthSnapshot | None, str | None]:
    """Return (snapshot, skip_or_error_message). None message means connected OK."""
    settings = get_ga4_settings()
    if settings is None:
        return None, "GA4: not connected (missing configuration)."
    try:
        return fetch_ga4_snapshot(settings, as_of=as_of), None
    except Exception as exc:
        return None, f"GA4: fetch failed ({exc})."


def format_period_comparison(snapshot: Ga4GrowthSnapshot) -> str:
    """Human-readable period comparison for verification scripts."""
    lines = [
        f"Current ({snapshot.current.start} → {snapshot.current.end}):",
        f"- activeUsers (period): {snapshot.current.active_users}",
        f"- sessions (period): {snapshot.current.sessions}",
        f"- screenPageViews (period): {snapshot.current.screen_page_views}",
        "",
        f"Previous ({snapshot.previous.start} → {snapshot.previous.end}):",
        f"- activeUsers (period): {snapshot.previous.active_users}",
        f"- sessions (period): {snapshot.previous.sessions}",
        f"- screenPageViews (period): {snapshot.previous.screen_page_views}",
        "",
        "Period-over-period change:",
        f"- activeUsers: {_fmt_pct(snapshot.change_active_users_pct())}",
        f"- sessions: {_fmt_pct(snapshot.change_sessions_pct())}",
        f"- screenPageViews: {_fmt_pct(snapshot.change_screen_page_views_pct())}",
    ]
    return "\n".join(lines)
