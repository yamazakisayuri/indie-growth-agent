"""Live check of EVIDENCE_STORE=zetaris against the running local Zetaris platform.

Run: EVIDENCE_STORE=zetaris python scripts/verify_zetaris_live.py
Needs ZETARIS_* in .env (see .env.example) and Docker running. Not part of verify_offline.py.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence import Column, TableSpec, build_store, describe_tables  # noqa: E402

PROBE = TableSpec(
    name="zetaris_live_check",
    description="Round-trip check written by scripts/verify_zetaris_live.py",
    columns=(Column("day", "date"), Column("label", "text"), Column("value", "integer")),
)


def main() -> None:
    os.environ.setdefault("EVIDENCE_STORE", "zetaris")
    started = time.monotonic()
    store = build_store()
    print(f"OK connected ({store.dialect}) in {time.monotonic() - started:.1f}s")
    try:
        store.replace_table(
            PROBE,
            [
                {"day": "2026-10-01", "label": "麻雀, \"点数\"", "value": 1},
                {"day": "2026-10-02", "label": None, "value": 2},
            ],
        )
        first = store.query("SELECT COUNT(*) AS n, SUM(value) AS s FROM zetaris_live_check")
        assert first.rows == ((2, 3),), first.rows
        label = store.query("SELECT label FROM zetaris_live_check WHERE value = 1").scalar()
        assert label == '麻雀, "点数"', label

        store.replace_table(PROBE, [{"day": "2026-10-03", "label": "x", "value": 40}])
        second = store.query("SELECT COUNT(*) AS n, SUM(value) AS s FROM zetaris_live_check")
        assert second.rows == ((1, 40),), second.rows
        print("OK replace_table round trip; a replaced table is re-read on the same connection")
    finally:
        store.close()

    reopened = build_store()
    try:
        names = [t.name for t in reopened.tables()]
        assert "zetaris_live_check" in names, names
        print("OK table specs survive reconnect:", ", ".join(names))
        print(describe_tables(reopened))
    finally:
        reopened.close()

    print("\nZetaris live check passed.")


if __name__ == "__main__":
    main()
