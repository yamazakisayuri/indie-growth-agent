"""MEMORY_BACKEND=local: an append-only JSONL audit log on disk is the whole store.

State is rebuilt by replaying the log, so nothing is ever rewritten or pruned.
Recall is lexical (ASCII words plus character bigrams for Japanese), tag overlap,
and recency, multiplied by confidence. No model or network is involved.
"""

from __future__ import annotations

import json
import math
import re
import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .base import (
    DEFAULT_RECALL_LIMIT,
    AuditEntry,
    FeedbackKind,
    MemoryEntry,
    DecisionMemoryError,
    RecalledMemory,
)

LEDGER_FILE = "ledger.jsonl"
RECENCY_DAYS = 14.0
MIN_SCORE = 0.05
FEEDBACK_DELTA = {"helpful": 0.05, "not_helpful": -0.03, "wrong": -0.20}
_ASCII_WORD = re.compile(r"[a-z0-9_]{2,}")
_NON_ASCII_RUN = re.compile(r"[^\x00-\x7f]+")


def _tokens(text: str) -> set[str]:
    lowered = text.lower()
    tokens = set(_ASCII_WORD.findall(lowered))
    for run in _NON_ASCII_RUN.findall(lowered):
        run = re.sub(r"[\s、。・「」（）()]+", "", run)
        tokens.update(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class LocalMemory:
    name = "local"

    def __init__(
        self,
        directory: str | Path,
        *,
        actor: str = "indie-growth-agent",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / LEDGER_FILE
        self._actor = actor
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()
        self._entries: dict[str, MemoryEntry] = {}
        self._created: dict[str, str] = {}
        self._ledger: list[AuditEntry] = []
        self._replay()

    def _replay(self) -> None:
        if not self._path.is_file():
            return
        for line_no, line in enumerate(self._path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
                entry = AuditEntry(**raw)
            except (ValueError, TypeError) as exc:
                raise DecisionMemoryError(
                    f"{self._path}:{line_no} is not a ledger entry: {exc}"
                ) from exc
            self._apply(entry)
            self._ledger.append(entry)

    def _apply(self, entry: AuditEntry) -> None:
        state = entry.details.get("newState") or {}
        if entry.action == "create":
            memory = dict(state)
            memory["tags"] = tuple(memory.get("tags", ()))
            self._entries[entry.memory_id] = MemoryEntry(**memory)
            self._created[entry.memory_id] = entry.timestamp
        elif entry.action == "feedback" and entry.memory_id in self._entries:
            current = self._entries[entry.memory_id]
            self._entries[entry.memory_id] = replace(
                current,
                confidence=state.get("confidence", current.confidence),
                tags=tuple(state.get("tags", current.tags)),
            )

    def _log(self, memory_id: str, action: str, details: dict[str, Any]) -> AuditEntry:
        entry = AuditEntry(
            id=f"led_{uuid.uuid4().hex[:12]}",
            memory_id=memory_id,
            action=action,
            actor=self._actor,
            timestamp=self._clock().isoformat(),
            details=details,
        )
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        self._apply(entry)
        self._ledger.append(entry)
        return entry

    def remember(self, entry: MemoryEntry) -> str:
        memory_id = f"mem_{uuid.uuid4().hex[:12]}"
        state = asdict(entry)
        state["tags"] = list(entry.tags)
        with self._lock:
            self._log(memory_id, "create", {"newState": state})
        return memory_id

    def recall(
        self, query: str, *, product_id: str, tags: tuple[str, ...] = (),
        limit: int = DEFAULT_RECALL_LIMIT,
    ) -> list[RecalledMemory]:
        query_tokens = _tokens(query)
        query_tags = set(tags)
        now = self._clock()
        with self._lock:
            scored: list[RecalledMemory] = []
            for memory_id, entry in self._entries.items():
                if entry.product_id != product_id:
                    continue
                lexical = _jaccard(query_tokens, _tokens(entry.content))
                tag = _jaccard(query_tags, set(entry.tags))
                if lexical == 0 and tag == 0:
                    continue
                created = datetime.fromisoformat(self._created[memory_id])
                age_days = max(0.0, (now - created).total_seconds() / 86400)
                recency = math.exp(-age_days / RECENCY_DAYS)
                score = _clamp01(0.55 * lexical + 0.30 * tag + 0.15 * recency) * entry.confidence
                if score < MIN_SCORE:
                    continue
                scored.append(
                    RecalledMemory(
                        memory_id=memory_id,
                        content=entry.content,
                        source=entry.source,
                        kind=entry.kind,
                        score=round(score, 4),
                        created_at=self._created[memory_id],
                        tags=entry.tags,
                        ref_id=entry.ref_id,
                    )
                )
            scored.sort(key=lambda m: (-m.score, m.created_at))
            top = scored[:limit]
            for memory in top:
                self._log(memory.memory_id, "read", {"query": query, "score": memory.score})
        return top

    def feedback(self, memory_id: str, kind: FeedbackKind) -> None:
        if kind not in FEEDBACK_DELTA:
            raise ValueError(f"Unknown feedback {kind!r}")
        with self._lock:
            current = self._entries.get(memory_id)
            if current is None:
                raise DecisionMemoryError(f"Unknown memory {memory_id}")
            tags = list(current.tags)
            if kind == "wrong" and "review" not in tags:
                tags.append("review")
            confidence = round(_clamp01(current.confidence + FEEDBACK_DELTA[kind]), 4)
            self._log(
                memory_id,
                "feedback",
                {
                    "kind": kind,
                    "previousState": {"confidence": current.confidence, "tags": list(current.tags)},
                    "newState": {"confidence": confidence, "tags": tags},
                },
            )

    def audit(self, memory_id: str | None = None) -> list[AuditEntry]:
        with self._lock:
            if memory_id is None:
                return list(self._ledger)
            return [e for e in self._ledger if e.memory_id == memory_id]

    def close(self) -> None:
        pass
