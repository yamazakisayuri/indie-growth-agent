"""Verify GA4 OAuth connection and period-scoped 7-day vs prior-7-day metrics."""

from __future__ import annotations

from config import get_ga4_settings
from ga4.snapshot import fetch_ga4_snapshot, format_period_comparison


def main() -> None:
    settings = get_ga4_settings()
    if settings is None:
        raise SystemExit("GA4 is not configured")

    print("GA4 connection check")
    print(f"- property: {settings.property_resource}")
    print(f"- lookback_days: {settings.lookback_days}")
    print("- auth: oauth_refresh_token")
    print("- activeUsers mode: period-scoped (no date dimension)")
    print()

    snap = fetch_ga4_snapshot(settings)
    print("OK: connected and period reports fetched")
    print(f"- auth_mode: {snap.auth_mode}")
    for note in snap.notes:
        print(f"- note: {note}")
    print()
    print(format_period_comparison(snap))


if __name__ == "__main__":
    main()
