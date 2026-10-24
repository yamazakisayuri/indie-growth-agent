"""Run every offline verification (no live ASC / GA4 / AdMob / Bedrock calls).

Run: python scripts/verify_offline.py

Each check runs in its own subprocess so module-level state and monkeypatches
cannot leak between checks. Add a script to OFFLINE_CHECKS only when it runs
without credentials or network access.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Entry modules for CLI analyze, Planner, Draft, and the Web API.
IMPORT_SMOKE_MODULES = ("agent", "planner", "draft_generator", "api_server")

OFFLINE_CHECKS = (
    "scripts/verify_analyze_cache.py",
    "scripts/verify_llm_provider.py",
    "scripts/verify_openai_compatible.py",
    "scripts/verify_structured_output_lists.py",
    "scripts/verify_evidence_schema.py",
    "scripts/verify_evidence_store.py",
    "scripts/verify_evidence_sources.py",
    "scripts/verify_zetaris_store.py",
    "scripts/verify_evidence_loop.py",
    "scripts/verify_evidence_api.py",
    "scripts/verify_memory.py",
    "scripts/verify_hmem.py",
    "scripts/verify_memory_loop.py",
)


def _run(label: str, args: list[str]) -> bool:
    proc = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        print(f"PASS  {label}")
        return True
    print(f"FAIL  {label} (exit {proc.returncode})")
    output = (proc.stdout + proc.stderr).strip()
    if output:
        print("\n".join(f"      {line}" for line in output.splitlines()[-20:]))
    return False


def main() -> None:
    results = [
        _run(
            "import " + ", ".join(IMPORT_SMOKE_MODULES),
            ["-c", "import " + ", ".join(IMPORT_SMOKE_MODULES)],
        )
    ]
    for script in OFFLINE_CHECKS:
        results.append(_run(script, [script]))

    failed = results.count(False)
    print()
    if failed:
        print(f"{failed} of {len(results)} offline checks failed.")
        raise SystemExit(1)
    print(f"All {len(results)} offline checks passed.")


if __name__ == "__main__":
    main()
