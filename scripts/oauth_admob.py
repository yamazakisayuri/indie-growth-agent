"""Obtain an AdMob-only OAuth refresh token (admob.readonly).

Uses the same GOOGLE_OAUTH_CLIENT_ID / SECRET as GA4, but writes a separate
token file so the GA4 analytics.readonly token is left untouched.

Prerequisites:
1. Enable "AdMob API" on the GCP project that owns the OAuth client.
2. If the client is type "Web application", add this redirect URI in Google Cloud
   Console → Credentials → the OAuth client:
     http://127.0.0.1:8765/
3. Run from the repo root:
     .venv/bin/python scripts/oauth_admob.py

The browser opens; sign in with the Google account that owns the AdMob publisher.
On success, secrets/admob_refresh_token.txt is written (gitignored).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import ROOT_DIR, load_env  # noqa: E402
import os  # noqa: E402

from admob.auth import ADMOB_READONLY  # noqa: E402

DEFAULT_PORT = 8765
DEFAULT_OUT = ROOT_DIR / "secrets" / "admob_refresh_token.txt"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Local redirect port (default {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Refresh token output path (default {DEFAULT_OUT})",
    )
    args = parser.parse_args()

    load_env()
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise SystemExit(
            "Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in .env"
        )

    # Web clients need a registered http://127.0.0.1:<port>/ redirect URI.
    # Installed ("Desktop") clients accept the same local-server flow.
    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [f"http://127.0.0.1:{args.port}/"],
        }
    }

    print("AdMob OAuth (scope: admob.readonly only)")
    print(f"- redirect: http://127.0.0.1:{args.port}/")
    print(f"- output:   {args.out}")
    print()
    print(
        "If the browser shows redirect_uri_mismatch, add the redirect above "
        "to this OAuth client's Authorized redirect URIs in Google Cloud Console."
    )
    print()

    flow = InstalledAppFlow.from_client_config(
        client_config,
        scopes=[ADMOB_READONLY],
    )
    creds = flow.run_local_server(
        host="127.0.0.1",
        port=args.port,
        open_browser=True,
        access_type="offline",
        prompt="consent",
        authorization_prompt_message="Open this URL if the browser does not open:\n{url}",
        success_message="AdMob authorization complete. You can close this tab.",
    )
    if not creds.refresh_token:
        raise SystemExit(
            "No refresh_token returned. Revoke prior access at "
            "https://myaccount.google.com/permissions and re-run with prompt=consent, "
            "or ensure access_type=offline (InstalledAppFlow sets this by default)."
        )

    out_path: Path = args.out
    if not out_path.is_absolute():
        out_path = ROOT_DIR / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(creds.refresh_token.strip() + "\n", encoding="utf-8")
    out_path.chmod(0o600)

    print()
    print(f"OK: wrote refresh token to {out_path}")
    print("Next:")
    print("  1. Set ADMOB_ACCOUNT_ID=pub-… in .env (list accounts after verify)")
    print("  2. Optionally set ADMOB_APP_ID=ca-app-pub-…~…")
    print("  3. Run: .venv/bin/python scripts/verify_admob.py --list-accounts")


if __name__ == "__main__":
    main()
