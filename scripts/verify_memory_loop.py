"""Integration: interventions write memory on adoption, the evidence run only recalls it.

Run: python scripts/verify_memory_loop.py
Offline (stub Analyst / Critic, SQLite store). Runs MEMORY_BACKEND=local, and hmem
when Node.js is available.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from evidence.loop import run_evidence_loop  # noqa: E402
from evidence.sources import EXTERNAL_TABLE_NAMES, INTERNAL_TABLE_NAMES  # noqa: E402
from interventions import InterventionLedger, add_manual, evaluate, implement, sync_memory  # noqa: E402
from memory import DecisionMemory, LocalMemory, NullMemory  # noqa: E402
from product_config import load_product_by_id  # noqa: E402
from run_evidence import recall_decisions  # noqa: E402
from verify_evidence_loop import CLEAN, V1, V3, StubAnalyst, StubCritic, _store  # noqa: E402


def _register(ledger: InterventionLedger, memory: DecisionMemory, **fields):
    """The write path scripts/interventions.py uses: create, then sync once."""
    item, _created = add_manual(ledger, **fields)
    return sync_memory(ledger, memory, item)


def _creates(memory: DecisionMemory) -> int:
    return sum(1 for e in memory.audit() if e.action == "create")


class BrokenMemory(NullMemory):
    name = "broken"

    def recall(self, *args, **kwargs):
        raise RuntimeError("backend down")


def check_backend(label: str, memory: DecisionMemory, tmp: Path) -> None:
    product = load_product_by_id("mahjong")
    ledger = InterventionLedger(tmp / "interventions.jsonl")
    common = dict(method="変更前後の比較", success_criterion="転換率 +10%", duration_days=14)

    screenshot = _register(
        ledger, memory, product_id="mahjong", title="スクリーンショット1枚目を結果画面に差し替える",
        target_metric="page_view_to_download_pct", **common,
    )
    keyword = _register(
        ledger, memory, product_id="mahjong", title="キーワード欄から三麻を外す",
        target_metric="impressions", **common,
    )
    dropped = _register(
        ledger, memory, product_id="mahjong", title="アイコンの色を変える",
        target_metric="page_view_to_download_pct", **common,
    )
    ledger.drop(dropped.id, reason="やめた")
    other = _register(
        ledger, memory, product_id="nextuta", title="スクリーンショットを差し替える",
        target_metric="page_view_to_download_pct", **common,
    )
    implement(ledger, keyword.id, implemented_on="2026-10-01", store=None, app_id=None)
    evaluated, _ = evaluate(
        ledger, keyword.id, verdict="no_change", note="変化なし", evaluated_on="2026-10-20",
        store=None, app_id=None, early=True,
    )
    evaluated = sync_memory(ledger, memory, evaluated)

    creates_after_adoption = _creates(memory)
    assert creates_after_adoption == 5, creates_after_adoption  # 4 decisions + 1 outcome
    for item in ledger.list_interventions():
        sync_memory(ledger, memory, item)
    assert _creates(memory) == creates_after_adoption, "re-sync must not write duplicates"
    print(f"OK [{label}] memory is written on adoption / evaluation only, once per intervention")

    past = recall_decisions(product, memory=memory, ledger=ledger)
    ids = [d.id for d in past]
    assert set(ids) == {screenshot.id, keyword.id}, ids
    assert dropped.id not in ids and other.id not in ids
    assert all(d.product_id == "mahjong" for d in past)
    assert len(ids) == len(set(ids)), "decision + outcome of one intervention must collapse"
    print(f"OK [{label}] recall returns this product's live decisions from the ledger: {ids}")

    analyst = StubAnalyst([V1, V3])
    critic = StubCritic([CLEAN])
    store = _store()
    try:
        run = run_evidence_loop(
            run_id=f"t-{label}",
            product_id="mahjong",
            product_name=product.name,
            store=store,
            analyst=analyst,
            critic=critic,
            internal_tables=INTERNAL_TABLE_NAMES,
            external_tables=EXTERNAL_TABLE_NAMES,
            past_decisions=past,
        )
    finally:
        store.close()
    assert run.status == "converged", (run.status, run.error)
    assert sorted(run.past_decision_ids) == sorted(ids)
    titles = [d.action_title for d in past]
    assert all(all(t in p for t in titles) for p in analyst.prompts)
    assert all(not any(t in p for t in titles) for p in critic.prompts)
    assert _creates(memory) == creates_after_adoption, "an analysis run must not write memory"
    assert all(
        e.action in ("create", "read", "feedback") for e in memory.audit()
    ), {e.action for e in memory.audit()}
    print(f"OK [{label}] Analyst gets them, Critic does not, and the run writes no memory")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        memory = LocalMemory(Path(tmp) / "memory")
        try:
            check_backend("local", memory, Path(tmp))
        finally:
            memory.close()

    if shutil.which("node"):
        from integrations.hmem import HmemMemory, HmemSettings

        with tempfile.TemporaryDirectory() as tmp:
            memory = HmemMemory(HmemSettings(directory=Path(tmp) / "hmem"))
            try:
                check_backend("hmem", memory, Path(tmp))
            finally:
                memory.close()
    else:
        print("SKIP [hmem] Node.js not found")

    product = load_product_by_id("mahjong")
    with tempfile.TemporaryDirectory() as tmp:
        ledger = InterventionLedger(Path(tmp) / "interventions.jsonl")
        assert recall_decisions(product, memory=NullMemory(), ledger=ledger) == []
        assert recall_decisions(product, memory=BrokenMemory(), ledger=ledger) == []
    print("OK MEMORY_BACKEND=none and a failing backend both give no past decisions, no error")

    print("\nAll memory / loop integration checks passed.")


if __name__ == "__main__":
    main()
