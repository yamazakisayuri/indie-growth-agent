"""Turn decision records into memory entries, and recalled memories into prompt context."""

from __future__ import annotations

import re
from collections.abc import Sequence

from evidence.schema import DecisionRecord

from .base import MemoryEntry, RecalledMemory

_SLUG = re.compile(r"[^a-z0-9_.-]+")
_ORIGIN_LABEL = {"ai_adopted": "AI の提案を採用", "manual": "手動で登録"}


def _slug(text: str) -> str:
    return _SLUG.sub("_", text.strip().lower()).strip("_")


def decision_tags(record: DecisionRecord) -> tuple[str, ...]:
    tags = ["decision", f"origin:{record.origin}"]
    for metric in record.baseline:
        slug = _slug(metric.metric)
        if slug and f"metric:{slug}" not in tags:
            tags.append(f"metric:{slug}")
    return tuple(tags)


def entry_from_decision(record: DecisionRecord, *, confidence: float = 0.9) -> MemoryEntry:
    """One memory per decision. The decision is the person's; the numbers are baselines only."""
    parts = [
        f"{record.created_at[:10]}: 「{record.action_title}」を実施すると決めた"
        f"（{_ORIGIN_LABEL[record.origin]}）。"
    ]
    if record.change_description:
        parts.append(f"変更内容: {record.change_description}。")
    if record.baseline:
        baseline = "、".join(
            f"{b.metric}={b.value:g}（{b.period_start}〜{b.period_end}）" for b in record.baseline
        )
        parts.append(f"ベースライン: {baseline}。")
    parts.append(
        f"判定方法: {record.method}。成功基準: {record.success_criterion}。"
        f"評価日: {record.evaluation_date}。"
    )
    return MemoryEntry(
        content="".join(parts),
        source=f"decision:{record.id}",
        product_id=record.product_id,
        kind="decision",
        tags=decision_tags(record),
        confidence=confidence,
        ref_id=record.id,
    )


def format_recalled(memories: Sequence[RecalledMemory]) -> str:
    """Prompt block for recalled memories. Empty string when there is nothing to add."""
    if not memories:
        return ""
    lines = [
        "PAST DECISIONS (from decision memory; context only, NOT evidence).",
        "Use them to avoid repeating a change that is still being evaluated or that did not",
        "work. Never cite them as a fact: every number in a claim must come from SQL.",
    ]
    for memory in memories:
        lines.append(
            f"- [{memory.created_at[:10]} {memory.kind}, source={memory.source}, "
            f"relevance={memory.score:.2f}] {memory.content}"
        )
    return "\n".join(lines)
