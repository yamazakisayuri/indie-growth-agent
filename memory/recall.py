"""Recall past decisions for a run: memory finds them, the record owner supplies the records.

Read-only. Nothing here writes to memory; decisions are remembered only when a person
adopts or registers one, by the code that owns those records.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence

from evidence.schema import DecisionRecord

from .base import DEFAULT_RECALL_LIMIT, DecisionMemory, RecalledMemory

logger = logging.getLogger(__name__)

RECALL_TAGS = ("decision", "outcome")


def recall_tags(metrics: Iterable[str] = ()) -> tuple[str, ...]:
    """Tags that match decision and outcome entries, plus metric:<name> for each metric."""
    tags = list(RECALL_TAGS)
    for name in metrics:
        tag = f"metric:{name.strip().lower()}"
        if tag not in tags:
            tags.append(tag)
    return tuple(tags)


def recall_past_decisions(
    memory: DecisionMemory,
    *,
    product_id: str,
    query: str,
    lookup: Callable[[str], DecisionRecord | None],
    tag_sets: Sequence[tuple[str, ...]] = (RECALL_TAGS,),
    limit: int = DEFAULT_RECALL_LIMIT,
) -> list[DecisionRecord]:
    """Decisions whose decision or outcome memory matches, best first, one per decision.

    Each tag set is a separate recall, merged by best score: engines that read only the
    first few query words (H-MEM uses 8) miss entries when every tag goes in one query.
    lookup maps a memory's ref_id to the current DecisionRecord, or None when it no
    longer applies (e.g. dropped). A failing backend yields no decisions, not an error:
    memory is optional context and must never stop an analysis.
    """
    best: dict[str, RecalledMemory] = {}
    try:
        for tags in tag_sets:
            for item in memory.recall(query, product_id=product_id, tags=tags, limit=limit * 2):
                if item.ref_id and (
                    item.ref_id not in best or item.score > best[item.ref_id].score
                ):
                    best[item.ref_id] = item
    except Exception as exc:  # noqa: BLE001
        logger.warning("Decision memory recall failed (%s: %s); continuing without it",
                       type(exc).__name__, exc)
        return []
    recalled = sorted(best.values(), key=lambda m: (-m.score, m.created_at))
    decisions: list[DecisionRecord] = []
    seen: set[str] = set()
    for item in recalled:
        if item.ref_id in seen:
            continue
        record = lookup(item.ref_id)
        if record is None or record.product_id != product_id:
            continue
        seen.add(item.ref_id)
        decisions.append(record)
        if len(decisions) >= limit:
            break
    return decisions
