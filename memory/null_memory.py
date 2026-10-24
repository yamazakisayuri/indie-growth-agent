"""MEMORY_BACKEND=none: remembers nothing, recalls nothing. The default."""

from __future__ import annotations

import uuid

from .base import DEFAULT_RECALL_LIMIT, AuditEntry, FeedbackKind, MemoryEntry, RecalledMemory


class NullMemory:
    name = "none"

    def remember(self, entry: MemoryEntry) -> str:
        return f"mem_{uuid.uuid4().hex[:12]}"

    def recall(
        self, query: str, *, product_id: str, tags: tuple[str, ...] = (),
        limit: int = DEFAULT_RECALL_LIMIT,
    ) -> list[RecalledMemory]:
        return []

    def feedback(self, memory_id: str, kind: FeedbackKind) -> None:
        pass

    def audit(self, memory_id: str | None = None) -> list[AuditEntry]:
        return []

    def close(self) -> None:
        pass
