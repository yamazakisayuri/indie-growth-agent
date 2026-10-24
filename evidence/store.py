"""Evidence store interface: load small tables, then answer read-only SQL.

Every number in a claim must be reproducible by a SELECT against one store.
Write SQL that stays within ANSI (no MEDIAN, no dialect-specific date math)
so the same query runs on every backend.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

ColumnType = Literal["text", "integer", "real", "date"]
DEFAULT_MAX_ROWS = 200
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class EvidenceStoreError(RuntimeError):
    """The store could not load or run a query. The message is safe to show to a model."""


@dataclass(frozen=True)
class Column:
    name: str
    type: ColumnType
    description: str = ""


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[Column, ...]
    description: str = ""

    def __post_init__(self) -> None:
        names = [self.name, *(c.name for c in self.columns)]
        bad = [n for n in names if not _IDENTIFIER.match(n)]
        if bad:
            raise ValueError(f"Invalid identifiers (letters, digits, underscore only): {bad}")
        if not self.columns:
            raise ValueError(f"Table {self.name} needs at least one column")
        column_names = [c.name.lower() for c in self.columns]
        if len(set(column_names)) != len(column_names):
            raise ValueError(f"Table {self.name} has duplicate column names")

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns)


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    truncated: bool = False
    sql: str = field(default="", compare=False)

    def scalar(self) -> Any:
        """The single value of a 1x1 result. Raises when the shape is different."""
        if len(self.columns) != 1 or len(self.rows) != 1:
            raise EvidenceStoreError(
                f"Expected one row with one column, got {len(self.rows)} rows x "
                f"{len(self.columns)} columns."
            )
        return self.rows[0][0]

    def as_dicts(self) -> list[dict[str, Any]]:
        return [dict(zip(self.columns, row)) for row in self.rows]


class EvidenceStore(Protocol):
    """Backend-neutral store. Implementations must reject non-SELECT SQL in query()."""

    dialect: str

    def replace_table(self, spec: TableSpec, rows: Iterable[Mapping[str, Any]]) -> int:
        """Create or fully replace a table with these rows. Returns the row count."""
        ...

    def query(self, sql: str, *, max_rows: int = DEFAULT_MAX_ROWS) -> QueryResult:
        """Run one read-only query."""
        ...

    def tables(self) -> list[TableSpec]:
        """Tables loaded through replace_table, for prompts and UI."""
        ...

    def close(self) -> None: ...


def normalize_rows(spec: TableSpec, rows: Iterable[Mapping[str, Any]]) -> list[tuple[Any, ...]]:
    """Order row values by spec columns; dates become ISO strings. Unknown keys are an error."""
    allowed = set(spec.column_names)
    out: list[tuple[Any, ...]] = []
    for index, row in enumerate(rows):
        extra = set(row) - allowed
        if extra:
            raise EvidenceStoreError(
                f"Row {index} for {spec.name} has unknown columns: {sorted(extra)}"
            )
        values = []
        for column in spec.columns:
            value = row.get(column.name)
            if value is not None and column.type == "date" and hasattr(value, "isoformat"):
                value = value.isoformat()
            values.append(value)
        out.append(tuple(values))
    return out


def describe_tables(store: EvidenceStore, only: Iterable[str] | None = None) -> str:
    """Plain-text schema for Analyst / Critic prompts, optionally limited to some tables."""
    allowed = None if only is None else {name.lower() for name in only}
    lines = [f"SQL dialect: {store.dialect} (write ANSI SQL; SELECT only)."]
    for spec in store.tables():
        if allowed is not None and spec.name.lower() not in allowed:
            continue
        header = f"- {spec.name}"
        if spec.description:
            header += f": {spec.description}"
        lines.append(header)
        for column in spec.columns:
            line = f"    {column.name} {column.type}"
            if column.description:
                line += f" -- {column.description}"
            lines.append(line)
    return "\n".join(lines)
