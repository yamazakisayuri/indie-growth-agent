"""Reject any SQL that is not a single read-only SELECT (or WITH ... SELECT).

Analyst and Critic write their own SQL, so every query passes through here
before any store runs it. Stores should add their own read-only enforcement
as well (e.g. a SQLite authorizer); this check is dialect-neutral text only.
"""

from __future__ import annotations

import re


class ReadOnlyQueryError(ValueError):
    """The SQL is not a single read-only query."""


_ALLOWED_FIRST_KEYWORDS = ("SELECT", "WITH")
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|UPSERT|DROP|CREATE|ALTER|TRUNCATE|RENAME|"
    r"ATTACH|DETACH|PRAGMA|VACUUM|REINDEX|ANALYZE|GRANT|REVOKE|CALL|EXEC|EXECUTE|"
    r"COPY|LOAD|INTO|SET|BEGIN|COMMIT|ROLLBACK|SAVEPOINT|RELEASE|REFRESH|CACHE|"
    r"UNCACHE|REGISTER)\b"
)
# REPLACE is also a string function; only REPLACE INTO / OR REPLACE are writes.
_REPLACE_WRITE = re.compile(r"\bREPLACE\b(?!\s*\()")


def _mask(sql: str) -> str:
    """Blank out string literals, quoted identifiers, and comments, keeping length."""
    out: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch in ("'", '"', "`"):
            j = i + 1
            while j < n:
                if sql[j] == ch:
                    if j + 1 < n and sql[j + 1] == ch:
                        j += 2
                        continue
                    break
                j += 1
            if j >= n:
                raise ReadOnlyQueryError("Unterminated quoted string or identifier.")
            out.append(ch + " " * (j - i - 1) + ch)
            i = j + 1
        elif sql.startswith("--", i):
            j = sql.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            if j == -1:
                raise ReadOnlyQueryError("Unterminated block comment.")
            out.append(" " * (j + 2 - i))
            i = j + 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def ensure_read_only(sql: str) -> str:
    """Return the query without trailing semicolons, or raise ReadOnlyQueryError."""
    text = sql.strip()
    while text.endswith(";"):
        text = text[:-1].rstrip()
    if not text:
        raise ReadOnlyQueryError("Empty query.")

    masked = _mask(text).upper()
    if ";" in masked:
        raise ReadOnlyQueryError("Only one statement is allowed.")
    words = masked.split()
    if not words or words[0] not in _ALLOWED_FIRST_KEYWORDS:
        raise ReadOnlyQueryError("Only SELECT (or WITH ... SELECT) queries are allowed.")
    forbidden = _FORBIDDEN.search(masked) or _REPLACE_WRITE.search(masked)
    if forbidden:
        raise ReadOnlyQueryError(
            f"Keyword {forbidden.group(0)} is not allowed in a read-only query."
        )
    return text
