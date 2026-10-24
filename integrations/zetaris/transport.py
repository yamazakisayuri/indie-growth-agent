"""How SQL reaches Zetaris. The store only depends on this protocol, so JDBC and REST are swappable."""

from __future__ import annotations

import re
from typing import Protocol

from evidence.store import EvidenceStoreError, QueryResult

_LIGHTNING_MESSAGE = re.compile(r"<<<(.*?)>>>", re.S)


class ZetarisTransport(Protocol):
    def execute(self, sql: str, *, max_rows: int) -> QueryResult:
        """Run one statement (query or DDL). Raises EvidenceStoreError on failure."""
        ...

    def close(self) -> None: ...


def zetaris_error(exc: BaseException) -> EvidenceStoreError:
    """Short, model-safe message: the Lightning text when present, else the first line."""
    text = str(exc)
    match = _LIGHTNING_MESSAGE.search(text)
    if match:
        message = match.group(1).strip()
    else:
        message = text.strip().splitlines()[0] if text.strip() else type(exc).__name__
        message = re.sub(r"^(?:[\w.]+(?:Exception|Error):\s*)+", "", message)
    return EvidenceStoreError(f"Zetaris: {message[:500]}")
