"""Verify the API serves Recorded Demos with no model settings, and Analyze says why it fails.

Run: python scripts/verify_api_without_model.py

Each provider runs in a child process whose environment blanks that provider's settings
(the shell wins over .env). No model, network, or data source is called: Analyze builds
the model before fetching any source, so it fails first.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RECORDED_RUN = "sample-base-20261025-110333"
UNSET_PROVIDERS = {
    "meterless": {"LLM_PROVIDER": "meterless", "METERLESS_RUNTIME_TOKEN": ""},
    "openai_compatible": {
        "LLM_PROVIDER": "openai_compatible",
        "OPENAI_COMPATIBLE_BASE_URL": "",
        "OPENAI_COMPATIBLE_API_KEY": "",
        "OPENAI_COMPATIBLE_MODEL": "",
    },
    "bedrock": {"LLM_PROVIDER": "bedrock", "AWS_PROFILE": "indie-growth-no-such-profile"},
}


def child(provider: str) -> None:
    from fastapi.testclient import TestClient

    import api_server

    client = TestClient(api_server.app)
    assert client.get("/health").json() == {"status": "ok"}
    runs = client.get("/api/evidence/runs", params={"limit": 100}).json()["runs"]
    recorded = {r["runId"] for r in runs if r["recorded"]}
    assert RECORDED_RUN in recorded and len(recorded) >= 3, recorded
    run = client.get(f"/api/evidence/runs/{RECORDED_RUN}")
    assert run.status_code == 200 and run.json()["recorded"] is True, run.text

    analyze = client.post("/api/analyze", json={"language": "en", "productId": "mahjong"})
    assert analyze.status_code == 502, analyze.text
    detail = analyze.json()["detail"]
    assert detail["code"] == "model_unavailable" and f"({provider})" in detail["error"], detail
    print(f"OK {provider} without settings: API starts, Recorded Demos load, "
          "Analyze answers model_unavailable")


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        child(sys.argv[2])
        return
    for provider, unset in UNSET_PROVIDERS.items():
        proc = subprocess.run(
            [sys.executable, __file__, "--child", provider],
            cwd=ROOT,
            env={**os.environ, **unset},
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print((proc.stdout + proc.stderr)[-3000:])
            raise SystemExit(f"FAIL {provider}")
        print(proc.stdout.strip().splitlines()[-1])
    print("\nAll API-without-model checks passed.")


if __name__ == "__main__":
    main()
