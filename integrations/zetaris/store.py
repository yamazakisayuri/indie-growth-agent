"""Evidence store on Zetaris: tables are CSV pointer tables, queries go through a transport."""

from __future__ import annotations

import csv
import io
import json
import re
import threading
from collections.abc import Iterable, Mapping
from typing import Any

from evidence.sql_guard import _mask, ensure_read_only
from evidence.store import (
    DEFAULT_MAX_ROWS,
    Column,
    EvidenceStoreError,
    QueryResult,
    TableSpec,
    normalize_rows,
)

from .staging import FileStager
from .transport import ZetarisTransport

META_TABLE = "evidence_tables"
_META_SPEC = TableSpec(
    name=META_TABLE,
    columns=(Column("name", "text"), Column("description", "text"), Column("columns", "text")),
)
_CSV_OPTIONS = 'header "true", inferSchema "true", multiLine "true", escape "\\""'
_NOT_FOUND = "TABLE_OR_VIEW_NOT_FOUND"
_IDENTIFIER_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _csv_bytes(spec: TableSpec, values: list[tuple[Any, ...]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(spec.column_names)
    for row in values:
        writer.writerow(["" if v is None else v for v in row])
    return buffer.getvalue().encode("utf-8")


class ZetarisEvidenceStore:
    dialect = "zetaris (Spark SQL)"

    def __init__(self, transport: ZetarisTransport, stager: FileStager, *, database: str) -> None:
        self._transport = transport
        self._stager = stager
        self._database = database
        self._lock = threading.RLock()
        self._specs: dict[str, TableSpec] | None = None
        self._ensure_database()

    def _ddl(self, sql: str) -> None:
        self._transport.execute(sql, max_rows=1)

    def _ensure_database(self) -> None:
        try:
            self._ddl(
                f'CREATE LIGHTNING DATABASE {self._database} '
                f'DESCRIBE BY "Indie Growth Agent evidence store" OPTIONS ()'
            )
        except EvidenceStoreError as exc:
            if "already exists" not in str(exc):
                raise

    def _registered_columns(self, name: str) -> tuple[str, ...] | None:
        try:
            result = self._transport.execute(
                f"SELECT * FROM {self._database}.{name} LIMIT 0", max_rows=0
            )
        except EvidenceStoreError as exc:
            if _NOT_FOUND in str(exc) or "cannot be found" in str(exc):
                return None
            raise
        return result.columns

    def _stage_and_register(self, spec: TableSpec, values: list[tuple[Any, ...]]) -> None:
        registered = self._registered_columns(spec.name)
        if registered is not None and (
            [c.lower() for c in registered] != [c.lower() for c in spec.column_names]
        ):
            raise EvidenceStoreError(
                f"{self._database}.{spec.name} is registered with columns {list(registered)}, "
                f"not {list(spec.column_names)}. Zetaris cannot change a registered table's "
                "columns; load it under a new table name."
            )
        uri = self._stager.put(spec.name, _csv_bytes(spec, values))
        if registered is None:
            self._ddl(
                f"CREATE LIGHTNING FILESTORE TABLE {spec.name} FROM {self._database} "
                f'FORMAT csv OPTIONS (path "{uri}", {_CSV_OPTIONS})'
            )

    def _load_specs(self) -> dict[str, TableSpec]:
        if self._specs is not None:
            return self._specs
        specs: dict[str, TableSpec] = {}
        if self._registered_columns(META_TABLE) is not None:
            result = self._transport.execute(
                f"SELECT name, description, columns FROM {self._database}.{META_TABLE}",
                max_rows=10_000,
            )
            for name, description, columns in result.rows:
                specs[str(name).lower()] = TableSpec(
                    name=str(name),
                    description=description or "",
                    columns=tuple(Column(**c) for c in json.loads(columns)),
                )
        self._specs = specs
        return specs

    def replace_table(self, spec: TableSpec, rows: Iterable[Mapping[str, Any]]) -> int:
        if spec.name.lower() == META_TABLE:
            raise EvidenceStoreError(f"{META_TABLE} is reserved")
        values = normalize_rows(spec, rows)
        with self._lock:
            self._stage_and_register(spec, values)
            specs = dict(self._load_specs())
            specs[spec.name.lower()] = spec
            meta_rows = [
                (
                    s.name,
                    s.description,
                    json.dumps(
                        [{"name": c.name, "type": c.type, "description": c.description}
                         for c in s.columns],
                        ensure_ascii=False,
                    ),
                )
                for s in sorted(specs.values(), key=lambda s: s.name.lower())
            ]
            self._stage_and_register(_META_SPEC, meta_rows)
            self._specs = specs
        return len(values)

    def _qualify(self, sql: str) -> str:
        """Prefix bare references to loaded tables with the database, so ANSI SQL stays portable."""
        known = set(self._load_specs())
        masked = _mask(sql)
        out: list[str] = []
        last = 0
        for match in _IDENTIFIER_TOKEN.finditer(masked):
            start, end = match.span()
            if match.group(0).lower() not in known:
                continue
            before = masked[:start].rstrip()
            after = masked[end:].lstrip()
            if (
                before.endswith(".")
                or before.upper().endswith(" AS")
                or after.startswith((".", "("))
            ):
                continue
            out.append(sql[last:start])
            out.append(f"{self._database}.{sql[start:end]}")
            last = end
        out.append(sql[last:])
        return "".join(out)

    def query(self, sql: str, *, max_rows: int = DEFAULT_MAX_ROWS) -> QueryResult:
        text = ensure_read_only(sql)
        with self._lock:
            result = self._transport.execute(self._qualify(text), max_rows=max_rows)
        return QueryResult(
            columns=result.columns, rows=result.rows, truncated=result.truncated, sql=text
        )

    def tables(self) -> list[TableSpec]:
        with self._lock:
            return sorted(self._load_specs().values(), key=lambda s: s.name.lower())

    def close(self) -> None:
        self._transport.close()
