"""Decision memory interface: remember past decisions and outcomes, recall them for a run.

Memory is context, not evidence. A recalled decision may explain what was tried
before, but every number in a claim still has to come from the evidence store.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

MemoryKind = Literal["decision", "outcome", "lesson"]
FeedbackKind = Literal["helpful", "not_helpful", "wrong"]
DEFAULT_RECALL_LIMIT = 5
# Tags are ASCII so engines with ASCII-only tokenizers can still match Japanese entries.
_TAG = re.compile(r"^[a-z0-9_]+(:[a-z0-9_.-]+)?$")


class DecisionMemoryError(RuntimeError):
    """The memory backend could not store or recall."""


@dataclass(frozen=True)
class MemoryEntry:
    content: str
    source: str
    product_id: str
    kind: MemoryKind
    tags: tuple[str, ...] = ()
    confidence: float = 0.8
    ref_id: str | None = None

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("MemoryEntry.content is empty")
        if not self.source.strip():
            raise ValueError("MemoryEntry.source is required")
        if not self.product_id.strip():
            raise ValueError("MemoryEntry.product_id is required (recall is scoped per product)")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("MemoryEntry.confidence must be within 0..1")
        bad = [t for t in self.tags if not _TAG.match(t)]
        if bad:
            raise ValueError(f"Tags must be lower-case ASCII like metric:cvr, got {bad}")


@dataclass(frozen=True)
class RecalledMemory:
    memory_id: str
    content: str
    source: str
    kind: MemoryKind
    score: float
    created_at: str
    tags: tuple[str, ...] = ()
    ref_id: str | None = None


@dataclass(frozen=True)
class AuditEntry:
    id: str
    memory_id: str
    action: str
    actor: str
    timestamp: str
    details: Mapping[str, Any] = field(default_factory=dict)


class DecisionMemory(Protocol):
    """Backend-neutral decision memory. Every mutation must leave an audit entry."""

    name: str

    def remember(self, entry: MemoryEntry) -> str:
        """Store one entry. Returns its memory id."""
        ...

    def recall(
        self, query: str, *, product_id: str, tags: tuple[str, ...] = (),
        limit: int = DEFAULT_RECALL_LIMIT,
    ) -> list[RecalledMemory]:
        """Best matches for this product only, highest score first."""
        ...

    def feedback(self, memory_id: str, kind: FeedbackKind) -> None: ...

    def audit(self, memory_id: str | None = None) -> list[AuditEntry]:
        """Audit trail, oldest first; one memory's history when memory_id is given."""
        ...

    def close(self) -> None: ...
