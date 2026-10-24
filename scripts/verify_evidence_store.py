"""Verify the read-only SQL guard and the SQLite evidence store. No network.

Run: python scripts/verify_evidence_store.py
"""

from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence import (  # noqa: E402
    Column,
    EvidenceStoreError,
    ReadOnlyQueryError,
    SQLiteEvidenceStore,
    TableSpec,
    build_store,
    describe_tables,
    ensure_read_only,
)

ASC_DAILY = TableSpec(
    name="asc_daily",
    description="App Store Connect daily totals, JP store",
    columns=(
        Column("date", "date"),
        Column("impressions", "integer"),
        Column("product_page_views", "integer"),
        Column("first_time_downloads", "integer", "first-time downloads only"),
    ),
)
ROWS = [
    {"date": dt.date(2026, 10, 16), "impressions": 300, "product_page_views": 12, "first_time_downloads": 5},
    {"date": dt.date(2026, 10, 17), "impressions": 320, "product_page_views": 13, "first_time_downloads": 4},
    {"date": "2026-10-18", "impressions": 310, "product_page_views": None, "first_time_downloads": 3},
]

ALLOWED = (
    "SELECT 1",
    "select count(*) from asc_daily;",
    "WITH t AS (SELECT impressions FROM asc_daily) SELECT SUM(impressions) FROM t",
    "SELECT REPLACE(date, '-', '') FROM asc_daily",
    "SELECT 'drop table x; delete' AS note",
    'SELECT "date" FROM asc_daily -- update later',
)
REJECTED = (
    "",
    "DELETE FROM asc_daily",
    "SELECT 1; DROP TABLE asc_daily",
    "WITH d AS (DELETE FROM asc_daily RETURNING *) SELECT * FROM d",
    "INSERT INTO asc_daily SELECT * FROM asc_daily",
    "REPLACE INTO asc_daily VALUES ('2026-10-01', 1, 1, 1)",
    "SELECT * INTO backup FROM asc_daily",
    "PRAGMA table_info(asc_daily)",
    "ATTACH DATABASE 'x.db' AS x",
    "SELECT 'unterminated",
    "SELECT 1 /* open comment",
)


def check_guard() -> None:
    for sql in ALLOWED:
        ensure_read_only(sql)
    for sql in REJECTED:
        try:
            ensure_read_only(sql)
        except ReadOnlyQueryError:
            continue
        raise AssertionError(f"guard must reject: {sql!r}")
    assert ensure_read_only("SELECT 1 ;; ") == "SELECT 1"
    print(f"OK guard: {len(ALLOWED)} read-only queries allowed, {len(REJECTED)} rejected")


def check_store(store: SQLiteEvidenceStore) -> None:
    assert store.replace_table(ASC_DAILY, ROWS) == 3
    result = store.query(
        "SELECT SUM(impressions) AS impressions, SUM(first_time_downloads) AS downloads FROM asc_daily"
    )
    assert result.columns == ("impressions", "downloads")
    assert result.rows == ((930, 12),)
    assert store.query("SELECT COUNT(product_page_views) FROM asc_daily").scalar() == 2
    assert store.query("SELECT MIN(date) FROM asc_daily").scalar() == "2026-10-16"
    print("OK store: load, aggregate, NULL kept as missing (not zero), dates as ISO text")

    limited = store.query("SELECT * FROM asc_daily ORDER BY date", max_rows=2)
    assert len(limited.rows) == 2 and limited.truncated
    print("OK store: max_rows truncates and reports it")

    assert store.replace_table(ASC_DAILY, ROWS[:1]) == 1
    assert store.query("SELECT COUNT(*) FROM asc_daily").scalar() == 1
    print("OK store: replace_table fully replaces previous rows")

    for sql in ("SELECT * FROM missing_table", "SELECT nope FROM asc_daily"):
        try:
            store.query(sql)
        except EvidenceStoreError as exc:
            assert "Query failed" in str(exc)
        else:
            raise AssertionError(f"must fail: {sql}")
    try:
        store.replace_table(ASC_DAILY, [{"date": "2026-10-01", "bogus": 1}])
    except EvidenceStoreError:
        pass
    else:
        raise AssertionError("unknown column must be rejected")
    try:
        TableSpec(name="asc daily", columns=(Column("x", "text"),))
    except ValueError:
        pass
    else:
        raise AssertionError("invalid identifier must be rejected")
    print("OK store: SQL errors, unknown columns, and bad identifiers raise clear errors")

    # Defense in depth: even if the text guard missed something, SQLite denies writes.
    from evidence import sqlite_store

    original = sqlite_store.ensure_read_only
    sqlite_store.ensure_read_only = lambda sql: sql
    try:
        try:
            store.query("DELETE FROM asc_daily")
        except EvidenceStoreError as exc:
            assert "not authorized" in str(exc), exc
        else:
            raise AssertionError("authorizer must deny writes")
    finally:
        sqlite_store.ensure_read_only = original
    assert store.query("SELECT COUNT(*) FROM asc_daily").scalar() == 1
    print("OK store: SQLite authorizer blocks writes the text guard did not see")

    slow = SQLiteEvidenceStore(query_timeout_seconds=0.05)
    try:
        slow.query(
            "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n) "
            "SELECT COUNT(*) FROM n"
        )
    except EvidenceStoreError as exc:
        assert "timed out" in str(exc), exc
    else:
        raise AssertionError("runaway query must time out")
    finally:
        slow.close()
    print("OK store: runaway query stops at the timeout")

    text = describe_tables(store)
    assert "asc_daily: App Store Connect daily totals" in text
    assert "first_time_downloads integer -- first-time downloads only" in text
    print("OK describe_tables lists tables and columns for prompts")


def check_factory(tmp: Path) -> None:
    os.environ["EVIDENCE_STORE"] = "sqlite"
    os.environ["EVIDENCE_SQLITE_PATH"] = str(tmp / "nested" / "evidence.sqlite")
    store = build_store()
    store.replace_table(ASC_DAILY, ROWS)
    store.close()
    reopened = build_store()
    assert [t.name for t in reopened.tables()] == ["asc_daily"]
    assert reopened.tables()[0].columns[3].description == "first-time downloads only"
    reopened.close()
    print("OK build_store: file-backed SQLite keeps tables and descriptions across reopen")

    os.environ["EVIDENCE_STORE"] = "nope"
    try:
        build_store()
    except ValueError as exc:
        assert "sqlite" in str(exc)
    else:
        raise AssertionError("unknown EVIDENCE_STORE must fail")
    print("OK build_store rejects an unknown EVIDENCE_STORE")


def main() -> None:
    check_guard()
    store = SQLiteEvidenceStore()
    try:
        check_store(store)
    finally:
        store.close()
    with tempfile.TemporaryDirectory() as tmp:
        check_factory(Path(tmp))
    print("\nAll evidence store checks passed.")


if __name__ == "__main__":
    main()
