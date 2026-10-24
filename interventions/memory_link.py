"""Copy interventions into decision memory so later runs can recall them.

The ledger stays the record; memory only gets a readable copy. With MEMORY_BACKEND=none
nothing is linked, so switching to a real backend later and syncing adds every entry once.
"""

from __future__ import annotations

from memory import DecisionMemory, MemoryEntry, decision_tags, entry_from_decision

from .ledger import InterventionLedger
from .schema import Intervention, Measurement

_ORIGIN_LABEL = {"ai_adopted": "AI の提案を採用", "manual": "手動で登録"}
_VERDICT_LABEL = {
    "improved": "改善した",
    "no_change": "変化なし",
    "worse": "悪化した",
    "inconclusive": "判定不能",
}


def _metric_lines(baseline: Measurement | None, after: Measurement | None) -> list[str]:
    before = {m.metric: m for m in (baseline.metrics if baseline else [])}
    later = {m.metric: m for m in (after.metrics if after else [])}
    lines = []
    for name in [*before, *(n for n in later if n not in before)]:
        b, a = before.get(name), later.get(name)
        left = f"{b.value:g}（{b.period_start}〜{b.period_end}）" if b else "未計測"
        right = f"{a.value:g}（{a.period_start}〜{a.period_end}）" if a else "未計測"
        lines.append(f"{name} 変更前 {left} → 変更後 {right}")
    return lines


def outcome_entry(item: Intervention, *, confidence: float = 0.9) -> MemoryEntry:
    """One memory per evaluated intervention: the person's verdict and the measured numbers."""
    if item.evaluation is None:
        raise ValueError(f"{item.id} has no evaluation yet")
    evaluation = item.evaluation
    parts = [
        f"{evaluation.evaluated_on}: 「{item.title}」の結果を評価した"
        f"（{_ORIGIN_LABEL[item.decision.origin]}、実施日 {item.implemented_on or '不明'}）。",
        f"評価指標: {item.target_metric}。",
        f"人の判定: {_VERDICT_LABEL[evaluation.verdict]}。",
    ]
    if evaluation.note:
        parts.append(f"メモ: {evaluation.note}。")
    lines = _metric_lines(item.baseline, item.after)
    if lines:
        parts.append(f"計測値（SQL）: {'、'.join(lines)}。")
    else:
        parts.append("計測値なし。")
    if item.prediction and item.prediction.test_plan:
        parts.append(f"AI の成功基準: {item.prediction.test_plan.success_criterion}。")
    tags = ["outcome", f"verdict:{evaluation.verdict}"]
    tags += [t for t in decision_tags(item.decision) if t != "decision"]
    return MemoryEntry(
        content="".join(parts),
        source=f"outcome:{item.id}",
        product_id=item.product_id,
        kind="outcome",
        tags=tuple(tags),
        confidence=confidence,
        ref_id=item.id,
    )


def sync_memory(
    ledger: InterventionLedger, memory: DecisionMemory, item: Intervention
) -> Intervention:
    """Remember the decision, and the outcome once evaluated, unless already linked."""
    if memory.name == "none":
        return item
    if item.status == "dropped":
        return item
    decision_key = f"{memory.name}:decision"
    if decision_key not in item.memory_ids:
        memory_id = memory.remember(entry_from_decision(item.decision))
        item = ledger.link_memory(item.id, key=decision_key, memory_id=memory_id)
    outcome_key = f"{memory.name}:outcome"
    if item.evaluation is not None and outcome_key not in item.memory_ids:
        memory_id = memory.remember(outcome_entry(item))
        item = ledger.link_memory(item.id, key=outcome_key, memory_id=memory_id)
    return item
