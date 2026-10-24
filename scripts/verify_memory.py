"""Verify decision memory backends (no model, network, or sponsor services).

Run: python scripts/verify_memory.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence.schema import BaselineMetric, DecisionRecord  # noqa: E402
from memory import (  # noqa: E402
    DecisionMemoryError,
    LocalMemory,
    MemoryEntry,
    NullMemory,
    build_memory,
    entry_from_decision,
    format_recalled,
)

DECISION = DecisionRecord(
    id="dr_001",
    product_id="mahjong",
    origin="ai_adopted",
    run_id="run_001",
    action_title="スクリーンショット1枚目を点数計算の結果画面に差し替える",
    change_description="1枚目を入力画面から結果画面へ",
    baseline=[
        BaselineMetric(
            metric="pv_to_download_rate", value=35.63,
            period_start="2026-10-16", period_end="2026-10-22",
        ),
        BaselineMetric(
            metric="ページビュー", value=87, period_start="2026-10-16", period_end="2026-10-22",
        ),
    ],
    method="変更前後の7日間比較",
    success_criterion="ページビュー→ダウンロード率が40%以上",
    evaluation_date="2026-11-05",
    created_at="2026-10-24T16:00:00+09:00",
)


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 24, 7, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def main() -> None:
    entry = entry_from_decision(DECISION)
    assert entry.source == "decision:dr_001" and entry.ref_id == "dr_001"
    assert entry.tags == ("decision", "origin:ai_adopted", "metric:pv_to_download_rate"), entry.tags
    assert "35.63" in entry.content and "2026-11-05" in entry.content
    print("OK decision → memory entry: provenance, ASCII tags (Japanese metric names skipped)")

    for bad in (
        dict(content="x", source="", product_id="mahjong", kind="decision"),
        dict(content="x", source="s", product_id="", kind="decision"),
        dict(content="x", source="s", product_id="p", kind="decision", tags=("指標",)),
        dict(content="x", source="s", product_id="p", kind="decision", confidence=1.5),
    ):
        try:
            MemoryEntry(**bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"must be rejected: {bad}")
    print("OK entries without source / product, with non-ASCII tags, or bad confidence are rejected")

    null = NullMemory()
    assert null.remember(entry).startswith("mem_")
    assert null.recall("スクリーンショット", product_id="mahjong") == []
    assert null.audit() == []
    print("OK NullMemory remembers and recalls nothing")

    with tempfile.TemporaryDirectory() as tmp:
        clock = Clock()
        memory = LocalMemory(tmp, clock=clock)
        decision_id = memory.remember(entry)
        other_id = memory.remember(
            MemoryEntry(
                content="キーワード欄から「三麻」を外した", source="manual:kw",
                product_id="mahjong", kind="decision", tags=("decision", "lever:keywords"),
            )
        )
        memory.remember(
            MemoryEntry(
                content="スクリーンショットを差し替えた", source="decision:other_app",
                product_id="nextuta", kind="decision",
            )
        )

        clock.now += timedelta(days=3)
        recalled = memory.recall(
            "スクリーンショットを差し替えて転換率を上げる",
            product_id="mahjong", tags=("metric:pv_to_download_rate",),
        )
        assert [m.memory_id for m in recalled] == [decision_id], recalled
        assert recalled[0].score > 0 and recalled[0].created_at.startswith("2026-10-24")
        by_tag = memory.recall("unrelated words", product_id="mahjong", tags=("lever:keywords",))
        assert [m.memory_id for m in by_tag] == [other_id], by_tag
        assert memory.recall("スクリーンショット", product_id="shopping") == []
        print("OK recall is scoped per product and matches Japanese text or ASCII tags")

        before = recalled[0].score
        memory.feedback(decision_id, "wrong")
        again = memory.recall(
            "スクリーンショットを差し替えて転換率を上げる",
            product_id="mahjong", tags=("metric:pv_to_download_rate",),
        )
        assert again and again[0].score < before, (before, again)
        assert "review" in again[0].tags
        try:
            memory.feedback("mem_missing", "helpful")
        except DecisionMemoryError:
            pass
        else:
            raise AssertionError("feedback on an unknown memory must fail")
        print("OK feedback 'wrong' lowers confidence by 0.20 and adds the review tag")

        history = [e.action for e in memory.audit(decision_id)]
        assert history == ["create", "read", "feedback", "read"], history
        feedback = memory.audit(decision_id)[2]
        assert feedback.details["previousState"]["confidence"] == 0.9
        assert feedback.details["newState"]["confidence"] == 0.7
        print("OK every create / read / feedback leaves an audit entry with previous and new state")

        ledger = Path(tmp) / "ledger.jsonl"
        lines_before = ledger.read_text(encoding="utf-8").splitlines()
        reopened = LocalMemory(tmp, clock=clock)
        assert [e.id for e in reopened.audit()] == [e.id for e in memory.audit()]
        assert reopened.recall("スクリーンショット 転換率", product_id="mahjong")[0].memory_id == (
            decision_id
        )
        lines_after = ledger.read_text(encoding="utf-8").splitlines()
        assert lines_after[: len(lines_before)] == lines_before, "ledger must be append-only"
        assert all(json.loads(line)["id"] for line in lines_after)
        print("OK state is rebuilt from the append-only ledger after reopen")

        block = format_recalled(again)
        assert "NOT evidence" in block and "source=decision:dr_001" in block, block
        assert format_recalled([]) == ""
        print("OK prompt block labels memory as context, not evidence, with its source")

    original = os.environ.get("MEMORY_BACKEND")
    try:
        os.environ["MEMORY_BACKEND"] = ""
        assert isinstance(build_memory(), NullMemory)
        os.environ["MEMORY_BACKEND"] = "no-such-memory"
        try:
            build_memory()
        except ValueError:
            pass
        else:
            raise AssertionError("unknown MEMORY_BACKEND must raise")
    finally:
        if original is None:
            os.environ.pop("MEMORY_BACKEND", None)
        else:
            os.environ["MEMORY_BACKEND"] = original
    print("OK MEMORY_BACKEND defaults to none; unknown values raise")

    print("\nAll decision memory checks passed.")


if __name__ == "__main__":
    main()
