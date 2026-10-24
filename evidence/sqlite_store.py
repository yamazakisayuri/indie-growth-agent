"""Evidence store on SQLite (standard library only). The default backend."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .sql_guard import ensure_read_only
from .store import (
    DEFAULT_MAX_ROWS,
    Column,
    EvidenceStoreError,
    QueryResult,
    TableSpec,
    normalize_rows,
)

_SQLITE_TYPES = {"text": "TEXT", "integer": "INTEGER", "real": "REAL", "date": "TEXT"}
_META_TABLE = "evidence_tables"
_READ_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    sqlite3.SQLITE_RECURSIVE,
}
DEFAULT_QUERY_TIMEOUT_SECONDS = 10.0


def _read_only_authorizer(action: int, *_args: Any) -> int:
    return sqlite3.SQLITE_OK if action in _READ_ACTIONS else sqlite3.SQLITE_DENY


class SQLiteEvidenceStore:
    dialect = "sqlite"

    def __init__(
        self,
        path: str | Path = ":memory:",
        *,
        query_timeout_seconds: float = DEFAULT_QUERY_TIMEOUT_SECONDS,
    ) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        self._query_timeout = query_timeout_seconds
        with self._conn:
            self._conn.execute(
                f"CREATE TABLE IF NOT EXISTS {_META_TABLE} "
                "(name TEXT PRIMARY KEY, description TEXT, columns TEXT)"
            )

    def replace_table(self, spec: TableSpec, rows: Iterable[Mapping[str, Any]]) -> int:
        if spec.name.lower() == _META_TABLE:
            raise EvidenceStoreError(f"{_META_TABLE} is reserved")
        values = normalize_rows(spec, rows)
        column_sql = ", ".join(f'"{c.name}" {_SQLITE_TYPES[c.type]}' for c in spec.columns)
        placeholders = ", ".join("?" for _ in spec.columns)
        columns_json = json.dumps(
            [{"name": c.name, "type": c.type, "description": c.description} for c in spec.columns],
            ensure_ascii=False,
        )
        with self._lock:
            try:
                with self._conn:
                    self._conn.execute(f'DROP TABLE IF EXISTS "{spec.name}"')
                    self._conn.execute(f'CREATE TABLE "{spec.name}" ({column_sql})')
                    self._conn.executemany(
                        f'INSERT INTO "{spec.name}" VALUES ({placeholders})', values
                    )
                    self._conn.execute(
                        f"INSERT OR REPLACE INTO {_META_TABLE} VALUES (?, ?, ?)",
                        (spec.name, spec.description, columns_json),
                    )
            except sqlite3.Error as exc:
                raise EvidenceStoreError(f"Could not load {spec.name}: {exc}") from exc
        return len(values)

    def query(self, sql: str, *, max_rows: int = DEFAULT_MAX_ROWS) -> QueryResult:
        text = ensure_read_only(sql)
        deadline = time.monotonic() + self._query_timeout
        with self._lock:
            self._conn.set_authorizer(_read_only_authorizer)
            self._conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            try:
                cursor = self._conn.execute(text)
                fetched = cursor.fetchmany(max_rows + 1)
                columns = tuple(d[0] for d in cursor.description or ())
            except sqlite3.Error as exc:
                if time.monotonic() > deadline:
                    raise EvidenceStoreError(
                        f"Query timed out after {self._query_timeout:g}s."
                    ) from exc
                raise EvidenceStoreError(f"Query failed: {exc}") from exc
            finally:
                self._conn.set_authorizer(None)
                self._conn.set_progress_handler(None, 0)
        return QueryResult(
            columns=columns,
            rows=tuple(tuple(r) for r in fetched[:max_rows]),
            truncated=len(fetched) > max_rows,
            sql=text,
        )

    def tables(self) -> list[TableSpec]:
        with self._lock:
            rows = self._conn.execute(
                f"SELECT name, description, columns FROM {_META_TABLE} ORDER BY name"
            ).fetchall()
        return [
            TableSpec(
                name=name,
                description=description or "",
                columns=tuple(Column(**c) for c in json.loads(columns)),
            )
            for name, description, columns in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
