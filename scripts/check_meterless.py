"""Check the Meterless Runtime (Nightshift) this app is configured for.

Run:
  python scripts/check_meterless.py           # status only: GET /v1/models (no model request)
  python scripts/check_meterless.py --detect  # also try the contract's ports and hosts
  python scripts/check_meterless.py --chat    # plus one short text request on METERLESS_MODEL;
                                              # it spends provider credits through Nightshift

Reads METERLESS_* from .env. The runtime token is never printed.
Exit code: 0 online (and, with --chat, a text reply), 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integrations.meterless import (  # noqa: E402
    detect,
    get_meterless_settings,
    probe,
    text_request,
)

CHAT_PROMPT = "Reply with the single word OK."


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--detect", action="store_true", help="Auto Detect the runtime port")
    parser.add_argument("--chat", action="store_true", help="Send one short text request")
    args = parser.parse_args()

    try:
        settings = get_meterless_settings()
    except ValueError as exc:
        print(f"config: {exc}")
        raise SystemExit(1) from None
    print(f"config: {settings!r}")

    status = probe(settings.base_url, settings.token, app=settings.app)
    print(f"status: {status.state} at {status.base_url}" + (f" ({status.detail})" if status.detail else ""))
    if status.model_ids:
        pinned = "listed" if settings.model_id in status.model_ids else "not listed"
        print(f"models: {', '.join(status.model_ids)}")
        print(f"METERLESS_MODEL {settings.model_id}: {pinned} by the runtime")
        if pinned == "not listed" and not settings.model_id.startswith("meterless/"):
            print(
                "note: a provider model can be missing from /v1/models (for example, when the "
                "runtime has no key for that provider); --chat shows whether it answers"
            )
    if status.state == "unauthorized":
        print("hint: METERLESS_RUNTIME_TOKEN does not match <stateDir>/proxy-token")

    if args.detect:
        found = detect(settings.token, app=settings.app)
        if found is None:
            print("detect: no runtime answered on ports 8088, 8090, 8787, 11434")
        else:
            print(f"detect: {found.state} at {found.base_url}")

    ok = status.state == "online"
    if args.chat and ok:
        reply = text_request(settings, CHAT_PROMPT)
        print(f"chat: HTTP {reply.status_code} in {reply.seconds}s")
        if reply.routing:
            print(f"routing: {json.dumps(reply.routing, ensure_ascii=False)[:600]}")
        if reply.error is not None:
            print(f"error: {json.dumps(reply.error, ensure_ascii=False, default=str)[:600]}")
            if isinstance(reply.error, dict) and reply.error.get("meterless_detail") == "nvidia_key_missing":
                print("hint: Nightshift has no NVIDIA API key loaded; set the key again in Nightshift")
            ok = False
        else:
            print(f"reply: {reply.text[:200]!r}")
            ok = bool(reply.text.strip())
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
