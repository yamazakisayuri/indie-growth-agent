"""Verify AdMob OAuth and print per-app 7-day vs prior-7-day Network metrics."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import get_admob_settings, load_env  # noqa: E402
from admob.auth import access_token_from_refresh_token  # noqa: E402
from admob.client import AdMobClient  # noqa: E402
from admob.snapshot import fetch_admob_snapshot, format_period_comparison  # noqa: E402


def _client_from_env() -> AdMobClient:
    load_env()
    import os

    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    refresh = os.getenv("ADMOB_REFRESH_TOKEN", "").strip() or None
    path_raw = os.getenv("ADMOB_REFRESH_TOKEN_PATH", "secrets/admob_refresh_token.txt").strip()
    if not refresh and path_raw:
        path = Path(path_raw)
        if not path.is_absolute():
            path = ROOT / path
        if path.is_file():
            refresh = path.read_text(encoding="utf-8").strip() or None
    if not client_id or not client_secret or not refresh:
        raise SystemExit(
            "Need GOOGLE_OAUTH_CLIENT_* and AdMob refresh token "
            "(run scripts/oauth_admob.py first)."
        )
    token = access_token_from_refresh_token(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh,
    )
    return AdMobClient(token)


def list_accounts() -> None:
    client = _client_from_env()
    accounts = client.list_accounts()
    if not accounts:
        print("No AdMob accounts visible for this token.")
        return
    print("AdMob accounts:")
    for acc in accounts:
        name = acc.get("name")
        pub = acc.get("publisherId")
        currency = acc.get("currencyCode")
        tz = acc.get("reportingTimeZone")
        print(f"- {name}  publisherId={pub}  currency={currency}  tz={tz}")


def list_apps(account: str) -> None:
    client = _client_from_env()
    resource = account if account.startswith("accounts/") else f"accounts/{account}"
    apps = client.list_apps(resource)
    if not apps:
        print(f"No apps under {resource}")
        return
    print(f"Apps under {resource}:")
    for app in apps:
        app_id = app.get("appId")
        linked = app.get("linkedAppInfo") if isinstance(app.get("linkedAppInfo"), dict) else {}
        manual = app.get("manualAppInfo") if isinstance(app.get("manualAppInfo"), dict) else {}
        label = linked.get("displayName") or manual.get("displayName") or ""
        platform = linked.get("platform") or ""
        print(f"- {app_id}  {label}  {platform}".rstrip())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list-accounts",
        action="store_true",
        help="List AdMob publisher accounts for the refresh token and exit",
    )
    parser.add_argument(
        "--list-apps",
        metavar="ACCOUNT",
        help="List apps for accounts/pub-… (or pub-…) and exit",
    )
    parser.add_argument(
        "--as-of",
        metavar="YYYY-MM-DD",
        help="Anchor end date (default: yesterday). Use ASC latest date to align windows.",
    )
    args = parser.parse_args()

    if args.list_accounts:
        list_accounts()
        return
    if args.list_apps:
        list_apps(args.list_apps)
        return

    settings = get_admob_settings()
    if settings is None:
        raise SystemExit(
            "AdMob is not configured. Run scripts/oauth_admob.py, then set "
            "ADMOB_ACCOUNT_ID and ADMOB_REFRESH_TOKEN_PATH in .env"
        )

    as_of = date.fromisoformat(args.as_of) if args.as_of else None

    print("AdMob connection check")
    print(f"- account: {settings.account_resource}")
    print(f"- lookback_days: {settings.lookback_days}")
    print(f"- currency: {settings.currency_code}")
    print(f"- app filter: {', '.join(settings.app_ids) if settings.app_ids else '(all apps)'}")
    print(f"- as_of: {as_of.isoformat() if as_of else 'yesterday (default)'}")
    print("- auth: oauth_refresh_token (admob.readonly)")
    print()

    snap = fetch_admob_snapshot(settings, as_of=as_of)
    print("OK: connected and network reports fetched")
    print(f"- auth_mode: {snap.auth_mode}")
    print(f"- currency (response): {snap.currency_code}")
    for note in snap.notes:
        print(f"- note: {note}")
    print()
    print(format_period_comparison(snap))


if __name__ == "__main__":
    main()
