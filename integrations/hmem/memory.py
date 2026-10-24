"""MEMORY_BACKEND=hmem: the Meterless H-MEM reference, run by Node, behind DecisionMemory."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import ROOT_DIR, load_env
from memory.base import (
    DEFAULT_RECALL_LIMIT,
    AuditEntry,
    DecisionMemoryError,
    FeedbackKind,
    MemoryEntry,
    RecalledMemory,
)

SIDECAR = Path(__file__).resolve().parent / "sidecar.ts"
DEFAULT_DIR = "tmp/hmem"
NODE_FLAGS = ("--experimental-transform-types", "--no-warnings")
# Spec default is 0.35 (AGENTS.md section 13, "tune per domain"). Japanese content only
# matches through its ASCII keywords: related entries score ~0.33-0.37, unrelated <= ~0.19.
DEFAULT_RECALL_THRESHOLD = 0.25
# H-MEM tokenizes ASCII only, so tag words are appended to the stored content.
KEYWORDS_MARKER = "\nkeywords: "
_TYPE = {"decision": "preference", "outcome": "factual", "lesson": "general"}
_ORIGIN = {"decision": "manual", "outcome": "plan_completion", "lesson": "model_response"}
_KIND_TAG = re.compile(r"^kind:(decision|outcome|lesson)$")


@dataclass(frozen=True)
class HmemSettings:
    directory: Path
    node: str = "node"
    recall_threshold: float = DEFAULT_RECALL_THRESHOLD


def get_hmem_settings() -> HmemSettings:
    load_env()
    raw_dir = os.getenv("HMEM_DIR", "").strip() or DEFAULT_DIR
    directory = Path(raw_dir).expanduser()
    if not directory.is_absolute():
        directory = ROOT_DIR / directory
    threshold_raw = os.getenv("HMEM_RECALL_THRESHOLD", "").strip()
    try:
        threshold = float(threshold_raw) if threshold_raw else DEFAULT_RECALL_THRESHOLD
    except ValueError as exc:
        raise ValueError("HMEM_RECALL_THRESHOLD must be a number") from exc
    return HmemSettings(
        directory=directory,
        node=os.getenv("HMEM_NODE", "").strip() or "node",
        recall_threshold=threshold,
    )


def _tag_words(tags: tuple[str, ...] | list[str]) -> str:
    return " ".join(re.sub(r"[:_.\-]+", " ", t) for t in tags).strip()


def _iso(ms: int | float) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat()


class HmemMemory:
    name = "hmem"

    def __init__(self, settings: HmemSettings | None = None) -> None:
        self._settings = settings or get_hmem_settings()
        node = shutil.which(self._settings.node)
        if node is None:
            raise DecisionMemoryError(
                f"MEMORY_BACKEND=hmem needs Node.js 22.7+ ({self._settings.node!r} not found)"
            )
        self._settings.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._next_id = 0
        self._proc = subprocess.Popen(
            [node, *NODE_FLAGS, str(SIDECAR), str(self._settings.directory)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._call("ping")

    def _call(self, op: str, **payload: Any) -> Any:
        with self._lock:
            self._next_id += 1
            request = {"id": self._next_id, "op": op, **payload}
            try:
                assert self._proc.stdin and self._proc.stdout
                self._proc.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
                self._proc.stdin.flush()
                line = self._proc.stdout.readline()
            except (BrokenPipeError, OSError) as exc:
                raise DecisionMemoryError(f"H-MEM sidecar is not running: {exc}") from exc
            if not line:
                stderr = self._proc.stderr.read() if self._proc.stderr else ""
                raise DecisionMemoryError(
                    f"H-MEM sidecar exited (code {self._proc.poll()}): {stderr.strip()[-500:]}"
                )
        response = json.loads(line)
        if response.get("id") != request["id"]:
            raise DecisionMemoryError("H-MEM sidecar answered out of order")
        if not response.get("ok"):
            raise DecisionMemoryError(f"H-MEM: {response.get('error')}")
        return response["result"]

    def remember(self, entry: MemoryEntry) -> str:
        tags = [*entry.tags, f"kind:{entry.kind}"]
        content = entry.content + KEYWORDS_MARKER + _tag_words(tags)
        record = self._call(
            "add",
            input={
                "content": content,
                "type": _TYPE[entry.kind],
                "layer": "long_term",
                "tags": tags,
                "confidence": entry.confidence,
                "source": entry.source,
                "provenance": {
                    "origin": _ORIGIN[entry.kind],
                    "learnedAt": int(datetime.now(UTC).timestamp() * 1000),
                    "label": f"Indie Growth Agent {entry.kind} ({entry.source})",
                    "refs": [entry.ref_id] if entry.ref_id else [],
                },
                "chatId": f"product:{entry.product_id}",
                "missionId": entry.product_id,
            },
        )
        return record["id"]

    def recall(
        self, query: str, *, product_id: str, tags: tuple[str, ...] = (),
        limit: int = DEFAULT_RECALL_LIMIT,
    ) -> list[RecalledMemory]:
        payload: dict[str, Any] = {
            "query": f"{query} {_tag_words(tags)}".strip(),
            "topN": limit,
            "chatId": f"product:{product_id}",
            "threshold": self._settings.recall_threshold,
        }
        result = self._call("query", **payload)
        recalled = []
        for item in result["memories"]:
            record = item["memory"]
            if record.get("missionId") != product_id:
                continue
            record_tags = [t for t in record.get("tags", []) if not _KIND_TAG.match(t)]
            kind = next(
                (m.group(1) for t in record.get("tags", []) if (m := _KIND_TAG.match(t))),
                "decision",
            )
            refs = (record.get("provenance") or {}).get("refs") or []
            recalled.append(
                RecalledMemory(
                    memory_id=record["id"],
                    content=record["content"].split(KEYWORDS_MARKER, 1)[0],
                    source=record["source"],
                    kind=kind,
                    score=round(float(item["relevance"]), 4),
                    created_at=_iso(record["timestamp"]),
                    tags=tuple(record_tags),
                    ref_id=refs[0] if refs else None,
                )
            )
        return recalled

    def feedback(self, memory_id: str, kind: FeedbackKind) -> None:
        self._call("feedback", memoryId=memory_id, kind=kind)

    def audit(self, memory_id: str | None = None) -> list[AuditEntry]:
        payload = {"memoryId": memory_id} if memory_id is not None else {}
        entries = self._call("ledger", **payload)
        return [
            AuditEntry(
                id=f"hmem-ledger-{e['index']}",
                memory_id=e["memoryId"],
                action=e["action"],
                actor=e["actor"],
                timestamp=_iso(e["timestamp"]),
                details={
                    k: e[k] for k in ("previousState", "newState", "details") if k in e
                },
            )
            for e in entries
        ]

    def close(self) -> None:
        if self._proc.poll() is not None:
            return
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()
        finally:
            for stream in (self._proc.stdout, self._proc.stderr):
                if stream:
                    stream.close()
