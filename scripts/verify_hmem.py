"""Verify MEMORY_BACKEND=hmem: the vendored H-MEM conformance suite, then the adapter.

Run: python scripts/verify_hmem.py
Needs Node.js 22.7+ (no npm packages, no network). Skips when Node is missing.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence.schema import BaselineMetric, DecisionRecord  # noqa: E402
from integrations.hmem import HmemMemory, HmemSettings  # noqa: E402
from integrations.hmem.memory import NODE_FLAGS  # noqa: E402
from memory import MemoryEntry, entry_from_decision, format_recalled  # noqa: E402

VENDOR = ROOT / "integrations" / "hmem" / "vendor"

DECISION = DecisionRecord(
    id="dr_001",
    product_id="mahjong",
    origin="ai_adopted",
    run_id="run_001",
    action_title="スクリーンショット1枚目を点数計算の結果画面に差し替える",
    baseline=[
        BaselineMetric(
            metric="pv_to_download_rate", value=35.63,
            period_start="2026-10-16", period_end="2026-10-22",
        )
    ],
    method="変更前後の7日間比較",
    success_criterion="ページビュー→ダウンロード率が40%以上",
    evaluation_date="2026-11-05",
    created_at="2026-10-24T16:00:00+09:00",
)
RECALL_TAGS = ("decision", "metric:pv_to_download_rate")


def main() -> None:
    node = shutil.which("node")
    if node is None:
        print("SKIP Node.js not found; MEMORY_BACKEND=hmem is unavailable here")
        return

    proc = subprocess.run(
        [node, *NODE_FLAGS, "../conformance/runner.ts"],
        cwd=VENDOR / "reference",
        capture_output=True,
        text=True,
        timeout=120,
    )
    summary = (proc.stdout.strip().splitlines() or ["(no output)"])[-1].strip()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    print(f"OK vendored H-MEM reference passes the official conformance suite: {summary}")

    with tempfile.TemporaryDirectory() as tmp:
        memory = HmemMemory(HmemSettings(directory=Path(tmp)))
        try:
            decision_id = memory.remember(entry_from_decision(DECISION))
            memory.remember(
                MemoryEntry(
                    content="スクリーンショットを差し替えた", source="decision:other",
                    product_id="nextuta", kind="decision", tags=RECALL_TAGS,
                )
            )
            recalled = memory.recall(
                "スクリーンショットを差し替える", product_id="mahjong", tags=RECALL_TAGS
            )
            assert [m.memory_id for m in recalled] == [decision_id], recalled
            first = recalled[0]
            assert first.content == entry_from_decision(DECISION).content, first.content
            assert first.source == "decision:dr_001" and first.ref_id == "dr_001"
            assert first.kind == "decision" and "kind:decision" not in first.tags
            assert memory.recall("x", product_id="shopping", tags=RECALL_TAGS) == []
            assert memory.recall("広告", product_id="mahjong", tags=("lever:paid_ads",)) == []
            print(
                f"OK Japanese decision recalled through ASCII tags (score {first.score}), "
                "scoped to its product, content and provenance intact"
            )

            memory.feedback(decision_id, "wrong")
            after = memory.recall("x", product_id="mahjong", tags=RECALL_TAGS)
            assert not after or after[0].score < first.score, (first, after)
            history = memory.audit(decision_id)
            assert [e.action for e in history] == ["create", "read", "feedback"] + (
                ["read"] if after else []
            ), [e.action for e in history]
            feedback = history[2].details
            assert feedback["previousState"]["confidence"] == 0.9
            assert abs(feedback["newState"]["confidence"] - 0.7) < 1e-9
            assert "review" in feedback["newState"]["tags"]
            print("OK feedback 'wrong' is H-MEM's exact -0.20 with review tag, in the trust ledger")

            block = format_recalled(recalled)
            assert "NOT evidence" in block and "keywords:" not in block
        finally:
            memory.close()

        reopened = HmemMemory(HmemSettings(directory=Path(tmp)))
        try:
            assert len(reopened.audit()) >= 4
            assert reopened.audit(decision_id)[0].action == "create"
        finally:
            reopened.close()
        assert (Path(tmp) / "ledger.jsonl").is_file() and (Path(tmp) / "state.json").is_file()
        print("OK state and the append-only ledger persist across sidecar restarts")

    print("\nAll H-MEM checks passed.")


if __name__ == "__main__":
    main()
