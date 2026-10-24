"""Verify the Zetaris evidence store against a fake engine (no Docker, JVM, or network).

Run: python scripts/verify_zetaris_store.py
"""

from __future__ import annotations

import csv
import io
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence import Column, EvidenceStoreError, ReadOnlyQueryError, TableSpec  # noqa: E402
from evidence.store import QueryResult  # noqa: E402
from integrations.zetaris import ZetarisEvidenceStore  # noqa: E402

DB = "INDIE_GROWTH"
CREATE_TABLE = re.compile(
    r'CREATE LIGHTNING FILESTORE TABLE (\w+) FROM (\w+) FORMAT csv OPTIONS \(path "([^"]+)"'
)


class FakeStager:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.puts: list[str] = []

    def put(self, table: str, data: bytes) -> str:
        uri = f"file:///fake/{table}"
        self.files[uri] = data
        self.puts.append(table)
        return uri


class FakeEngine:
    """Answers the statements the store sends, reading staged CSV like a pointer table."""

    def __init__(self, stager: FakeStager) -> None:
        self.stager = stager
        self.databases: set[str] = set()
        self.tables: dict[str, str] = {}
        self.statements: list[str] = []

    def _sqlite(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        for name, uri in self.tables.items():
            rows = list(csv.reader(io.StringIO(self.stager.files[uri].decode("utf-8"))))
            header, body = rows[0], rows[1:]
            conn.execute(f'CREATE TABLE "{name}" ({", ".join(header)})')
            conn.executemany(
                f'INSERT INTO "{name}" VALUES ({", ".join("?" for _ in header)})',
                [[None if v == "" else (int(v) if v.isdigit() else v) for v in r] for r in body],
            )
        return conn

    def execute(self, sql: str, *, max_rows: int) -> QueryResult:
        self.statements.append(sql)
        if sql.startswith("CREATE LIGHTNING DATABASE"):
            name = sql.split()[3]
            if name in self.databases:
                raise EvidenceStoreError(f'Zetaris: A database named "{name}" already exists.')
            self.databases.add(name)
            return QueryResult(columns=("Result",), rows=())
        match = CREATE_TABLE.match(sql)
        if match:
            name, database, uri = match.groups()
            assert database == DB, sql
            if name in self.tables:
                raise EvidenceStoreError(f'Zetaris: A table named "{name}" already exists.')
            self.tables[name] = uri
            return QueryResult(columns=("Result",), rows=())
        assert sql.lstrip().upper().startswith(("SELECT", "WITH")), sql
        local = sql.replace(f"{DB}.", "")
        for name in re.findall(r"\b(?:FROM|JOIN)\s+(\w+)", local, re.I):
            if name not in self.tables and f"{DB}." in sql:
                raise EvidenceStoreError(
                    f"Zetaris: [TABLE_OR_VIEW_NOT_FOUND] The table or view `{DB}`.`{name}` "
                    "cannot be found."
                )
        conn = self._sqlite()
        try:
            cursor = conn.execute(local)
        except sqlite3.OperationalError as exc:
            raise EvidenceStoreError(f"Zetaris: {exc}") from exc
        rows = cursor.fetchmany(max_rows + 1)
        return QueryResult(
            columns=tuple(d[0] for d in cursor.description or ()),
            rows=tuple(tuple(r) for r in rows[:max_rows]),
            truncated=len(rows) > max_rows,
            sql=sql,
        )

    def close(self) -> None:
        pass


ASC = TableSpec(
    name="asc_daily",
    description="ASC daily totals",
    columns=(
        Column("date", "date"),
        Column("impressions", "integer"),
        Column("note", "text", "free text"),
    ),
)


def main() -> None:
    stager = FakeStager()
    engine = FakeEngine(stager)
    store = ZetarisEvidenceStore(engine, stager, database=DB)
    assert store.tables() == []
    assert ZetarisEvidenceStore(engine, stager, database=DB).tables() == []
    print("OK database is created once; an existing database is reused")

    rows = [
        {"date": "2026-10-16", "impressions": 300, "note": '麻雀, "点数"\n2行目'},
        {"date": "2026-10-17", "impressions": 200, "note": None},
    ]
    assert store.replace_table(ASC, rows) == 2
    staged = stager.files["file:///fake/asc_daily"].decode("utf-8")
    parsed = list(csv.reader(io.StringIO(staged)))
    assert parsed[0] == ["date", "impressions", "note"], parsed
    assert parsed[1][2] == '麻雀, "点数"\n2行目' and parsed[2][2] == "", parsed
    print("OK replace_table stages RFC 4180 CSV (commas, quotes, newlines, NULL as empty)")

    result = store.query("SELECT SUM(impressions) AS total FROM asc_daily")
    assert result.scalar() == 500, result
    assert result.sql == "SELECT SUM(impressions) AS total FROM asc_daily"
    assert f"FROM {DB}.asc_daily" in engine.statements[-1], engine.statements[-1]
    print("OK bare table names are qualified with the database; result.sql stays as written")

    for sql, expected in (
        (
            "SELECT 'asc_daily' AS s, a.impressions AS asc_daily FROM asc_daily a",
            f"SELECT 'asc_daily' AS s, a.impressions AS asc_daily FROM {DB}.asc_daily a",
        ),
        (
            f"SELECT asc_daily.date FROM {DB}.asc_daily",
            f"SELECT asc_daily.date FROM {DB}.asc_daily",
        ),
    ):
        store.query(sql)
        assert engine.statements[-1] == expected, engine.statements[-1]
    print("OK literals, aliases, column qualifiers and qualified names are left alone")

    creates_before = sum(s.startswith("CREATE LIGHTNING FILESTORE") for s in engine.statements)
    store.replace_table(ASC, [{"date": "2026-10-18", "impressions": 7, "note": "x"}])
    creates_after = sum(s.startswith("CREATE LIGHTNING FILESTORE") for s in engine.statements)
    assert creates_after == creates_before, "a registered table must not be registered again"
    assert store.query("SELECT COUNT(*) FROM asc_daily").scalar() == 1
    print("OK replacing a table overwrites its file without registering it again")

    reopened = ZetarisEvidenceStore(engine, stager, database=DB)
    assert [t.name for t in reopened.tables()] == ["asc_daily"]
    assert reopened.tables()[0] == ASC
    assert reopened.query("SELECT impressions FROM asc_daily").scalar() == 7
    print("OK table specs survive reopen through the evidence_tables metadata table")

    changed = TableSpec(name="asc_daily", columns=(Column("date", "date"),))
    try:
        store.replace_table(changed, [{"date": "2026-10-18"}])
    except EvidenceStoreError as exc:
        assert "new table name" in str(exc), exc
    else:
        raise AssertionError("changing a registered table's columns must fail")
    assert store.query("SELECT impressions FROM asc_daily").scalar() == 7
    print("OK changing a registered table's columns fails before its data is overwritten")

    for bad in ("DELETE FROM asc_daily", "SELECT 1; SELECT 2"):
        try:
            store.query(bad)
        except ReadOnlyQueryError:
            pass
        else:
            raise AssertionError(f"{bad!r} must be rejected")
    try:
        store.replace_table(TableSpec(name="evidence_tables", columns=(Column("x", "text"),)), [])
    except EvidenceStoreError:
        pass
    else:
        raise AssertionError("evidence_tables must be reserved")
    print("OK write SQL is rejected before reaching Zetaris; the metadata table is reserved")

    print("\nAll Zetaris store checks passed.")


if __name__ == "__main__":
    main()
