"""Verify interventions: ledger, lifecycle, SQL measurement, decision memory (offline).

Run: python scripts/verify_interventions.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence.schema import (  # noqa: E402
    AnalystOutput,
    Claim,
    DecisionRecord,
    Evidence,
    EvidenceRun,
    ProposedAction,
    RevisionStep,
    TestPlan,
)
from evidence.prompts import past_decisions_text  # noqa: E402
from evidence.sources import ASC_DAILY  # noqa: E402
from evidence.sqlite_store import SQLiteEvidenceStore  # noqa: E402
from interventions import (  # noqa: E402
    Intervention,
    InterventionError,
    InterventionLedger,
    add_manual,
    adopt,
    evaluate,
    implement,
    load_run,
    prediction_from_run,
    remeasure,
    sync_memory,
)
from memory import LocalMemory, NullMemory  # noqa: E402

JST = timezone(timedelta(hours=9))
APP_ID = "6740174129"


class Clock:
    def __init__(self, day: str) -> None:
        self.now = datetime.fromisoformat(f"{day}T10:00:00+09:00").astimezone(JST)

    def set(self, day: str) -> None:
        self.now = datetime.fromisoformat(f"{day}T10:00:00+09:00").astimezone(JST)

    def __call__(self) -> datetime:
        return self.now


def build_store(last_day: date = date(2026, 10, 24)) -> SQLiteEvidenceStore:
    """Daily rows from 2026-10-01. From 10-16 page views and downloads go up."""
    rows = []
    day = date(2026, 10, 1)
    while day <= last_day:
        later = day >= date(2026, 10, 16)
        rows.append(
            {
                "date": day,
                "app_id": APP_ID,
                "territory": "ALL",
                "impressions": 100,
                "product_page_views": 20 if later else 10,
                "first_time_downloads": 5 if later else 2,
                "source": "asc_analytics",
            }
        )
        day += timedelta(days=1)
    store = SQLiteEvidenceStore(":memory:")
    store.replace_table(ASC_DAILY, rows)
    return store


def build_run(path: Path) -> None:
    hypothesis = Claim(
        id="C2",
        text="結果画面を1枚目にすればページビュー→ダウンロード率が上がる",
        kind="hypothesis",
        test_plan=TestPlan(
            metric="page_view_to_download_pct",
            method="変更前後7日間の比較",
            duration_days=7,
            success_criterion="+5ポイント以上",
        ),
    )
    fact = Claim(
        id="C1",
        text="直近7日のページビューは70件",
        kind="fact",
        evidence=[
            Evidence(
                table="asc_daily", sql="SELECT 70", value=70, as_of="2026-10-14",
                source="asc_analytics",
            )
        ],
    )
    output = AnalystOutput(
        most_important_finding="ページビュー→ダウンロード率が低い",
        claims=[fact, hypothesis],
        actions=[
            ProposedAction(
                rank=1, title="スクショ1枚目を結果画面にする", reason="転換率が低い",
                claim_ids=["C1", "C2"],
            ),
            ProposedAction(rank=2, title="説明文の冒頭を変える", reason="", claim_ids=["C1"]),
        ],
    )
    run = EvidenceRun(
        run_id="mahjong-20261015-090000",
        product_id="mahjong",
        started_at="2026-10-15T09:00:00+09:00",
        model="fixture",
        steps=[
            RevisionStep(version="v1", stage="internal", output=output),
            RevisionStep(version="v3", stage="critic_revision", output=output),
        ],
    )
    path.write_text(run.model_dump_json(by_alias=True, indent=2), encoding="utf-8")


def lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def main() -> None:
    store = build_store()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        run_path = tmp_path / "run.json"
        build_run(run_path)
        ledger_path = tmp_path / "interventions" / "ledger.jsonl"
        clock = Clock("2026-10-15")
        ledger = InterventionLedger(ledger_path, clock=clock)

        prediction = prediction_from_run(load_run(run_path), rank=1)
        assert prediction.version == "v3" and [c.id for c in prediction.claims] == ["C1", "C2"]
        assert prediction.test_plan and prediction.test_plan.duration_days == 7
        ai, created = adopt(ledger, prediction, product_id="mahjong")
        assert created and ai.status == "planned" and ai.decision.origin == "ai_adopted"
        assert ai.target_metric == "page_view_to_download_pct" and ai.window_days == 7
        assert ai.decision.run_id == "mahjong-20261015-090000"
        assert ai.decision.evaluation_date == "2026-10-22" and ai.decision.baseline == []
        print("OK adopt copies the AI action, cited claims, and test plan into a planned intervention")

        try:
            adopt(ledger, prediction_from_run(load_run(run_path), rank=2), product_id="mahjong")
        except InterventionError as exc:
            assert "metric" in str(exc), exc
        else:
            raise AssertionError("an action without a test plan needs explicit plan fields")
        print("OK an action without a test plan must be given metric / method / criterion / days")

        before = lines(ledger_path)
        again, created = adopt(
            ledger, prediction_from_run(load_run(run_path), rank=1), product_id="mahjong"
        )
        assert not created and again.id == ai.id and lines(ledger_path) == before
        manual, created = add_manual(
            ledger, product_id="mahjong", title="キーワードから「三麻」を外す",
            target_metric="impressions", method="変更前後14日比較",
            success_criterion="検索インプレッションが減らない", duration_days=14,
        )
        assert created and manual.decision.origin == "manual" and manual.prediction is None
        same, created = add_manual(
            ledger, product_id="mahjong", title="  キーワードから「三麻」を外す ",
            target_metric="impressions", method="x", success_criterion="y", duration_days=14,
        )
        assert not created and same.id == manual.id
        assert len(ledger.list_interventions()) == 2
        print("OK adopting the same action or re-adding the same title does not duplicate")

        try:
            implement(
                ledger, ai.id, implemented_on="2026-10-15", evaluation_date="2026-10-20",
                store=store, app_id=APP_ID,
            )
        except InterventionError as exc:
            assert "2026-10-22" in str(exc), exc
        else:
            raise AssertionError("the evaluation date must cover the whole after window")
        ai, changed = implement(
            ledger, ai.id, implemented_on="2026-10-15", store=store, app_id=APP_ID
        )
        assert changed and ai.status == "implemented" and ai.implemented_on == "2026-10-15"
        assert ai.decision.evaluation_date == "2026-10-22"
        values = {m.metric: m.value for m in ai.baseline.metrics}
        assert values == {
            "impressions": 700.0,
            "product_page_views": 70.0,
            "first_time_downloads": 14.0,
            "impression_to_page_view_pct": 10.0,
            "page_view_to_download_pct": 20.0,
        }, values
        assert ai.baseline.period_start == "2026-10-08" and ai.baseline.period_end == "2026-10-14"
        assert all(m.sql.startswith("SELECT ") for m in ai.baseline.metrics)
        assert ai.decision.baseline == ai.baseline.metrics
        print("OK implement measures the 7 days before the change with SQL on asc_daily")

        before = lines(ledger_path)
        same, changed = implement(
            ledger, ai.id, implemented_on="2026-10-15", store=store, app_id=APP_ID
        )
        assert not changed and same == ai and lines(ledger_path) == before
        try:
            implement(ledger, ai.id, implemented_on="2026-10-16", store=store, app_id=APP_ID)
        except InterventionError:
            pass
        else:
            raise AssertionError("a different implementation date must be rejected")
        print("OK repeating implement is a no-op; a conflicting date is rejected")

        try:
            evaluate(
                ledger, ai.id, verdict="improved", note="", evaluated_on="2026-10-18",
                store=store, app_id=APP_ID,
            )
        except InterventionError as exc:
            assert "2026-10-22" in str(exc), exc
        else:
            raise AssertionError("evaluating before the evaluation date needs early=True")
        clock.set("2026-10-23")
        ai, changed = evaluate(
            ledger, ai.id, verdict="improved", note="転換率が上がった",
            evaluated_on="2026-10-23", store=store, app_id=APP_ID,
        )
        assert changed and ai.status == "evaluated" and ai.evaluation.verdict == "improved"
        after = {m.metric: m.value for m in ai.after.metrics}
        assert ai.after.period_start == "2026-10-16" and ai.after.period_end == "2026-10-22"
        assert after["page_view_to_download_pct"] == 25.0 and after["product_page_views"] == 140
        print("OK evaluate stores the person's verdict and measures the 7 days after")

        before = lines(ledger_path)
        same, changed = evaluate(
            ledger, ai.id, verdict="improved", note="転換率が上がった",
            evaluated_on="2026-10-23", store=store, app_id=APP_ID,
        )
        assert not changed and lines(ledger_path) == before
        try:
            evaluate(
                ledger, ai.id, verdict="worse", note="", evaluated_on="2026-10-23",
                store=store, app_id=APP_ID,
            )
        except InterventionError:
            pass
        else:
            raise AssertionError("a second, different verdict must be rejected")
        print("OK repeating the same evaluation is a no-op; a different verdict is rejected")

        manual, _ = implement(
            ledger, manual.id, implemented_on="2026-10-15", store=store, app_id=APP_ID
        )
        assert manual.baseline.metrics and manual.decision.evaluation_date == "2026-10-29"
        manual, _ = evaluate(
            ledger, manual.id, verdict="inconclusive", note="母数が小さい",
            evaluated_on="2026-10-24", store=store, app_id=APP_ID, early=True,
        )
        assert manual.evaluation.verdict == "inconclusive"
        assert manual.after.metrics == [] and "9/14 days" in manual.after.skipped[0], manual.after
        print("OK inconclusive is accepted; a window with missing days is skipped, not summed")

        later_store = build_store(last_day=date(2026, 10, 31))
        before = lines(ledger_path)
        manual, changed = remeasure(ledger, manual.id, store=later_store, app_id=APP_ID)
        assert changed and manual.after.skipped == [] and len(manual.after.metrics) == 5
        assert manual.evaluation.verdict == "inconclusive"
        event = json.loads(lines(ledger_path)[-1])
        assert len(lines(ledger_path)) == len(before) + 1 and event["action"] == "measure"
        assert event["data"]["baseline"] is None, "an unchanged baseline is not rewritten"
        assert remeasure(ledger, manual.id, store=later_store, app_id=APP_ID)[1] is False
        print("OK measure fills a window once late data arrives; the same numbers write nothing")

        dropped, _ = add_manual(
            ledger, product_id="mahjong", title="アイコンを変える", target_metric="impressions",
            method="前後比較", success_criterion="+10%", duration_days=14,
        )
        dropped, changed = ledger.drop(dropped.id, reason="今月はやらない")
        assert changed and dropped.status == "dropped"
        assert ledger.drop(dropped.id, reason="今月はやらない")[1] is False
        retry, created = add_manual(
            ledger, product_id="mahjong", title="アイコンを変える", target_metric="impressions",
            method="前後比較", success_criterion="+10%", duration_days=14,
        )
        assert created and retry.id != dropped.id
        retry, _ = implement(ledger, retry.id, implemented_on="2026-10-20", store=None, app_id=APP_ID)
        assert retry.status == "implemented" and retry.baseline is None
        retry, changed = remeasure(ledger, retry.id, store=store, app_id=APP_ID)
        assert changed and retry.baseline.metrics and retry.decision.baseline == retry.baseline.metrics
        assert retry.after is None
        try:
            remeasure(ledger, dropped.id, store=store, app_id=APP_ID)
        except InterventionError:
            pass
        else:
            raise AssertionError("a dropped intervention has nothing to measure")
        try:
            ledger.drop(ai.id, reason="x")
        except InterventionError:
            pass
        else:
            raise AssertionError("an evaluated intervention cannot be dropped")
        print("OK dropping is idempotent; a dropped title can be registered again")
        print("OK an implementation recorded while the store was down can be measured later")

        null = NullMemory()
        for item in ledger.list_interventions():
            assert sync_memory(ledger, null, item).memory_ids == {}
        reopened = InterventionLedger(ledger_path, clock=clock)
        assert [i.model_dump() for i in reopened.list_interventions()] == [
            i.model_dump() for i in ledger.list_interventions()
        ]
        assert len(reopened.list_interventions()) == 4
        print("OK with MEMORY_BACKEND=none the ledger alone keeps every intervention after reopen")

        memory = LocalMemory(tmp_path / "memory", clock=clock)
        for item in reopened.list_interventions():
            sync_memory(reopened, memory, item)
        ai = reopened.get(ai.id)
        assert set(ai.memory_ids) == {"local:decision", "local:outcome"}, ai.memory_ids
        assert set(reopened.get(manual.id).memory_ids) == {"local:decision", "local:outcome"}
        assert set(reopened.get(retry.id).memory_ids) == {"local:decision"}
        assert reopened.get(dropped.id).memory_ids == {}
        created_count = sum(1 for e in memory.audit() if e.action == "create")
        for item in reopened.list_interventions():
            sync_memory(reopened, memory, item)
        assert sum(1 for e in memory.audit() if e.action == "create") == created_count == 5
        print("OK sync-memory adds decisions and outcomes once; dropped ones are skipped")

        recalled = memory.recall(
            "結果を評価した 判定", product_id="mahjong",
            tags=("outcome", "verdict:inconclusive"), limit=10,
        )
        outcome = next(m for m in recalled if m.kind == "outcome" and m.ref_id == manual.id)
        assert "人の判定: 判定不能" in outcome.content and "計測値" in outcome.content
        assert "verdict:inconclusive" in outcome.tags
        ai_outcome = next(
            m
            for m in memory.recall(
                "スクショ1枚目を結果画面にする 結果", product_id="mahjong",
                tags=("verdict:improved",), limit=10,
            )
            if m.kind == "outcome"
        )
        assert ai_outcome.ref_id == ai.id and "AI の提案を採用" in ai_outcome.content
        assert "page_view_to_download_pct 変更前 20（2026-10-08〜2026-10-14）" in ai_outcome.content
        assert "変更後 25（2026-10-16〜2026-10-22）" in ai_outcome.content
        assert "AI の成功基準: +5ポイント以上" in ai_outcome.content
        print("OK outcomes are recalled with the human verdict and the SQL numbers kept apart")

        stored_ai = reopened.get(ai.id)
        assert stored_ai.decision.outcome is None, "the ledger keeps the outcome in evaluation"
        with_outcome = stored_ai.decision_with_outcome()
        assert with_outcome.id == ai.id and with_outcome.outcome is not None
        assert with_outcome.outcome.verdict == "improved"
        assert with_outcome.outcome.note == "転換率が上がった"
        assert with_outcome.outcome.implemented_on == "2026-10-15"
        assert with_outcome.outcome.measured_after == stored_ai.after.metrics
        assert all(m.sql for m in with_outcome.outcome.measured_after)
        assert reopened.get(retry.id).decision_with_outcome().outcome is None
        inconclusive = reopened.get(manual.id).decision_with_outcome().outcome
        assert inconclusive.verdict == "inconclusive" and inconclusive.measured_after
        text = past_decisions_text(
            [reopened.get(retry.id).decision_with_outcome(), with_outcome]
        )
        assert text.count("  outcome: ") == 1, text
        assert "outcome: developer's verdict = improved (2026-10-23, implemented 2026-10-15)" in text
        assert "page_view_to_download_pct=25.0 (2026-10-16..2026-10-22)" in text
        print("OK evaluated interventions give the Analyst the verdict and after numbers, apart")

        raw = json.loads(reopened.get(ai.id).model_dump_json(by_alias=True))
        assert set(raw["evaluation"]) == {"evaluatedOn", "verdict", "note"}
        assert raw["prediction"]["testPlan"]["successCriterion"] == "+5ポイント以上"
        assert all(m["sql"] for m in raw["baseline"]["metrics"] + raw["after"]["metrics"])
        events = [json.loads(line) for line in lines(ledger_path)]
        assert all(e["id"] and e["interventionId"] for e in events)
        assert [e["action"] for e in events if e["interventionId"] == ai.id][:3] == [
            "create", "implement", "evaluate",
        ]
        print("OK prediction, human evaluation, and measured values are separate fields")

        decision = reopened.get(manual.id).decision
        for bad in (
            dict(prediction=None, decision=ai.decision),
            dict(prediction=ai.prediction, decision=decision),
        ):
            try:
                Intervention(
                    id=bad["decision"].id, target_metric="x", duration_days=7, window_days=7,
                    updated_at="2026-10-15T10:00:00+09:00", **bad,
                )
            except ValidationError:
                pass
            else:
                raise AssertionError(f"origin and prediction must agree: {bad}")
        try:
            Intervention(
                id="iv_other", target_metric="x", duration_days=7, window_days=7,
                decision=DecisionRecord(**{**decision.model_dump(), "id": "iv_x"}),
                updated_at="2026-10-15T10:00:00+09:00",
            )
        except ValidationError:
            pass
        else:
            raise AssertionError("decision.id must equal the intervention id")
        print("OK AI-adopted needs its prediction; manual has none")

        bad_ledger = tmp_path / "bad.jsonl"
        bad_ledger.write_text("{not json}\n", encoding="utf-8")
        try:
            InterventionLedger(bad_ledger)
        except InterventionError:
            pass
        else:
            raise AssertionError("a corrupt ledger line must fail loudly")
        print("OK a corrupt ledger line fails loudly instead of being skipped")
        later_store.close()
    store.close()

    print("\nAll intervention checks passed.")


if __name__ == "__main__":
    main()
