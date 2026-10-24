"""Keep a finished Live Sample run as a Recorded Demo in samples/recorded/.

Run: python scripts/record_sample_demo.py sample-competitor-variant-20261025-101500

Refused unless the trace is a Live Sample run (sample- id with its .sample.json), on the
sample CSVs as they are now, finished (converged or max_rounds) with a recorded model and
at least one Critic review. Real-data traces can never be recorded this way.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sample_mode import RUNS_DIR, SampleError, record_demo  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_id")
    args = parser.parse_args()
    trace = RUNS_DIR / f"{args.run_id.removesuffix('.json')}.json"
    if not trace.is_file():
        print(f"error: {trace} not found", file=sys.stderr)
        raise SystemExit(1)
    try:
        target = record_demo(trace)
    except SampleError as exc:
        print(f"error: not recorded: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    print(f"recorded: {target.relative_to(ROOT)} (commit it with its .sample.json)")


if __name__ == "__main__":
    main()
