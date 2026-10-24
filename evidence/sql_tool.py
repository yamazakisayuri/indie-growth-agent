"""The run_sql tool given to the Analyst and the Critic, with a per-call query budget."""

from __future__ import annotations

import json
from typing import Any

from strands import tool

from .critic import run_logged
from .schema import SqlCall
from .store import EvidenceStore, EvidenceStoreError

TOOL_MAX_ROWS = 50


def _jsonable(value: Any) -> Any:
    return value if isinstance(value, (str, int, float, bool)) or value is None else str(value)


def make_sql_tool(store: EvidenceStore, *, role: str, log: list[SqlCall], max_calls: int):
    """A fresh run_sql tool. Every call (and refusal) is appended to log."""
    calls = 0

    @tool(name="run_sql")
    def run_sql(sql: str) -> str:
        """Run one read-only SQL query against the evidence store and return JSON.

        Args:
            sql: A single SELECT (or WITH ... SELECT) statement in ANSI SQL.
        """
        nonlocal calls
        if calls >= max_calls:
            return json.dumps(
                {"error": f"Query budget of {max_calls} used up. Give your final answer now."}
            )
        calls += 1
        try:
            result = run_logged(store, sql, role, log)
        except (EvidenceStoreError, ValueError) as exc:
            return json.dumps({"error": str(exc)}, ensure_ascii=False)
        rows = [[_jsonable(v) for v in row] for row in result.rows[:TOOL_MAX_ROWS]]
        return json.dumps(
            {
                "columns": list(result.columns),
                "rows": rows,
                "truncated": result.truncated or len(result.rows) > TOOL_MAX_ROWS,
            },
            ensure_ascii=False,
        )

    return run_sql
