"""Verify the Critic's code rules and the revision loop with stub models. No network.

Run: python scripts/verify_evidence_loop.py

Covers the three test claims: one correct, one with a wrong number, one causal leap.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence import AnalystOutput, CriticReport, SQLiteEvidenceStore, SqlCall  # noqa: E402
from evidence.critic import (  # noqa: E402
    FindingIds,
    apply_critic_report,
    critic_payload,
    is_composite,
    recheck_cited_sql,
    structural_findings,
    values_equal,
    values_match,
)
from evidence.loop import comparison_periods, run_evidence_loop  # noqa: E402
from evidence.sources import (  # noqa: E402
    ASC_DAILY,
    COMPETITOR_LISTING,
    EXTERNAL_TABLE_NAMES,
    INTERNAL_TABLE_NAMES,
)
from evidence.sql_tool import make_sql_tool  # noqa: E402

DOWNLOADS_SQL = (
    "SELECT SUM(first_time_downloads) FROM asc_daily "
    "WHERE date BETWEEN '2026-10-16' AND '2026-10-22'"
)
RATING_SQL = "SELECT MAX(rating_count) FROM competitor_listing WHERE is_self = 0"


def _store() -> SQLiteEvidenceStore:
    store = SQLiteEvidenceStore()
    daily = []
    for day in range(9, 23):
        daily.append(
            {
                "date": f"2026-10-{day:02d}",
                "app_id": "1",
                "territory": "ALL",
                "impressions": 300,
                "product_page_views": 12,
                "first_time_downloads": 4 if day >= 16 else 5,
                "source": "asc_analytics",
            }
        )
    store.replace_table(ASC_DAILY, daily)
    store.replace_table(
        COMPETITOR_LISTING,
        [
            {"fetched_on": "2026-10-24", "country": "jp", "app_id": "1", "is_self": 1, "rating_count": 0},
            {"fetched_on": "2026-10-24", "country": "jp", "app_id": "2", "is_self": 0, "rating_count": 2824},
        ],
    )
    return store


def _claim(cid, kind, value=None, sql="", table="asc_daily", text="t", test_plan=None):
    evidence = []
    if value is not None:
        evidence.append(
            {"table": table, "sql": sql, "value": value, "as_of": "2026-10-22", "source": "s"}
        )
    return {"id": cid, "text": text, "kind": kind, "evidence": evidence, "test_plan": test_plan}


TEST_PLAN = {
    "metric": "conversion",
    "method": "product page optimization A/B test",
    "duration_days": 28,
    "success_criterion": "treatment wins",
}
# v2 contains the three test claims: c1 correct, c2 wrong number, c3 causal leap.
V2 = AnalystOutput.model_validate(
    {
        "most_important_finding": "f",
        "claims": [
            _claim("c1", "fact", 28, DOWNLOADS_SQL),
            _claim("c2", "observation", 2900, RATING_SQL, table="competitor_listing"),
            _claim("c3", "fact", text="初心者向けの訴求にすれば転換率が上がる"),
        ],
        "actions": [{"rank": 1, "title": "a", "reason": "r", "claim_ids": ["c1", "c3"]}],
    }
)
V3 = AnalystOutput.model_validate(
    {
        "most_important_finding": "f",
        "claims": [
            _claim("c1", "fact", 28, DOWNLOADS_SQL),
            _claim("c2", "observation", 2824, RATING_SQL, table="competitor_listing"),
            _claim("c3", "hypothesis", text="初心者向けの訴求が効くかもしれない", test_plan=TEST_PLAN),
        ],
        "actions": [{"rank": 1, "title": "a", "reason": "r", "claim_ids": ["c1", "c3"]}],
        "finding_responses": [{"finding_id": "r1-f1", "response": "fixed"}],
    }
)
V1 = AnalystOutput.model_validate(
    {"most_important_finding": "f", "claims": [_claim("c1", "fact", 28, DOWNLOADS_SQL)], "actions": []}
)


def check_values_match() -> None:
    assert values_match(2258, 2258) and not values_match(2258, 2259)
    assert values_match(35.63, 0.356321) and values_match(0.3563, 0.356321)
    assert values_match("35.63%", "0.356321") and values_match("2,258", "2258")
    assert values_match(36, 35.63) and not values_match(35.6, 35.7)
    assert not values_match("n/a", 1) and not values_match(1, None)
    print("OK values_match: exact counts, claim precision, percent/ratio forms, strings from stores")

    assert is_composite("impressions=2248, page_views=76") and is_composite("previous=15, current=11")
    assert not is_composite("Games") and not is_composite("2026-10-11") and not is_composite(2258)
    assert values_equal("Games", "games ") and not values_equal("Games", "Utilities")
    assert values_equal("35.63%", 0.35632)
    print("OK packed values like 'a=1, b=2' are detected; single texts compare as text")


def check_code_rules(store: SQLiteEvidenceStore) -> None:
    ids = FindingIds("r1")
    findings = structural_findings(
        V2, table_names=["asc_daily", "competitor_listing"], external_tables=EXTERNAL_TABLE_NAMES, ids=ids
    )
    kinds = {(f.claim_id, f.kind) for f in findings}
    assert ("c3", "unverifiable") in kinds, kinds  # a fact with no evidence
    assert all(f.origin == "code" for f in findings)

    bad = AnalystOutput.model_validate(
        {
            "most_important_finding": "f",
            "claims": [
                _claim("x1", "fact", 2824, RATING_SQL, table="competitor_listing"),
                _claim("x2", "hypothesis"),
                _claim("x3", "observation", 1, "SELECT 1", table="nope"),
                _claim("x4", "fact", "impressions=2248, downloads=37", "SELECT 1"),
            ],
            "actions": [
                {"rank": 1, "title": "a", "reason": "r", "claim_ids": ["x3"]},
                {"rank": 2, "title": "b", "reason": "r", "claim_ids": ["missing"]},
            ],
        }
    )
    kinds = {
        (f.claim_id, f.kind)
        for f in structural_findings(
            bad,
            table_names=["asc_daily", "competitor_listing"],
            external_tables=EXTERNAL_TABLE_NAMES,
            ids=FindingIds("r1"),
        )
    }
    assert ("x1", "kind_mislabel") in kinds, kinds
    assert ("x2", "causal_leap") in kinds, kinds
    assert ("x3", "unverifiable") in kinds, kinds
    assert ("x3", "causal_leap") in kinds, kinds
    assert ("missing", "unverifiable") in kinds, kinds
    assert ("x4", "unverifiable") in kinds, kinds
    print("OK code rules: external data as fact, hypothesis without test, unknown table, "
          "observation-only action, missing claim id, packed evidence values")

    log: list[SqlCall] = []
    recheck = recheck_cited_sql(V2, store=store, ids=FindingIds("r1"), log=log)
    assert [(f.claim_id, f.kind) for f in recheck] == [("c2", "value_mismatch")], recheck
    assert recheck[0].critic_value == 2824 and recheck[0].claimed_value == 2900
    assert all(call.role == "code" for call in log) and len(log) == 2
    print("OK re-running cited SQL: correct claim passes, wrong number is a value_mismatch")

    report = CriticReport.model_validate(
        {
            "summary": "s",
            "checks": [
                {"claim_id": "c1", "sql": "SELECT SUM(first_time_downloads) FROM asc_daily WHERE date >= '2026-10-16'"},
                {"claim_id": "c2", "sql": "SELECT rating_count FROM competitor_listing WHERE app_id = '2'"},
                {"claim_id": "c1", "sql": "SELECT * FROM asc_daily"},
                {"claim_id": "zz", "sql": "SELECT 1"},
            ],
            "issues": [
                {"claim_id": "c3", "kind": "causal_leap", "message": "因果は未確認"},
                {"claim_id": "zz", "kind": "scope_mismatch", "message": "unknown claim is ignored"},
            ],
        }
    )
    found, outcomes = apply_critic_report(report, V2, store=store, ids=FindingIds("r1"), log=[])
    assert [o.matched for o in outcomes] == [True, False, False]
    assert outcomes[2].error and "one row" in outcomes[2].error
    assert {(f.claim_id, f.kind, f.origin) for f in found} == {
        ("c2", "value_mismatch", "code"),
        ("c3", "causal_leap", "critic"),
    }
    print("OK Critic checks: code runs the Critic's SQL and decides matches; issues kept per claim")

    payload = critic_payload(V2)
    assert "SELECT" not in payload and "初心者向け" in payload
    print("OK Critic payload has claims and actions but none of the Analyst's SQL")


class StubAnalyst:
    def __init__(self, versions):
        self.versions = list(versions)
        self.prompts: list[str] = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        return self.versions.pop(0), [SqlCall(role="analyst", sql="SELECT 1", ok=True, row_count=1)]


class StubCritic:
    def __init__(self, reports):
        self.reports = list(reports)
        self.prompts: list[str] = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        return self.reports.pop(0), []


ROUND1 = CriticReport.model_validate(
    {
        "summary": "差し戻し",
        "checks": [{"claim_id": "c2", "sql": "SELECT MAX(rating_count) FROM competitor_listing"}],
        "issues": [{"claim_id": "c3", "kind": "causal_leap", "message": "因果は未確認"}],
    }
)
CLEAN = CriticReport(summary="問題なし")


def check_loop(store: SQLiteEvidenceStore) -> None:
    assert comparison_periods(store) == (("2026-10-16", "2026-10-22"), ("2026-10-09", "2026-10-15"))

    saved: list[str] = []
    analyst = StubAnalyst([V1, V2, V3])
    critic = StubCritic([ROUND1, CLEAN])
    run = run_evidence_loop(
        run_id="t1",
        product_id="mahjong",
        product_name="麻雀",
        store=store,
        analyst=analyst,
        critic=critic,
        internal_tables=INTERNAL_TABLE_NAMES,
        external_tables=EXTERNAL_TABLE_NAMES,
        context_note="- Our app_id = '1'",
        on_update=lambda r: saved.append(r.model_dump_json(by_alias=True)),
    )
    assert all("Our app_id = '1'" in p for p in [*analyst.prompts, *critic.prompts])
    assert run.status == "converged", (run.status, run.error)
    assert [s.version for s in run.steps] == ["v1", "v2", "v3"]
    assert [s.stage for s in run.steps] == ["internal", "competitive", "critic_revision"]
    assert run.steps[0].critic is None
    round1 = run.steps[1].critic
    by_key = {(f.claim_id, f.kind): f for f in round1.findings}
    assert by_key[("c2", "value_mismatch")].resolution == "resolved"
    assert by_key[("c3", "causal_leap")].resolution == "downgraded"
    assert by_key[("c3", "unverifiable")].resolution == "resolved"
    assert run.steps[2].critic.findings == []
    assert "competitor_listing" not in analyst.prompts[0], "v1 must see internal tables only"
    assert "competitor_listing" in analyst.prompts[1]
    assert "r1-f" in analyst.prompts[2] and "因果は未確認" in analyst.prompts[2]
    assert all(DOWNLOADS_SQL not in p for p in critic.prompts), "Critic must not see Analyst SQL"
    assert json.loads(saved[-1])["status"] == "converged" and len(saved) >= 6
    print("OK loop converges: v1 -> v2 -> Critic -> v3 -> Critic, findings resolved / downgraded")

    stuck = run_evidence_loop(
        run_id="t2",
        product_id="mahjong",
        product_name="麻雀",
        store=store,
        analyst=StubAnalyst([V1, V2, V2]),
        critic=StubCritic([ROUND1, ROUND1]),
        internal_tables=INTERNAL_TABLE_NAMES,
        external_tables=EXTERNAL_TABLE_NAMES,
        max_critic_rounds=2,
    )
    assert stuck.status == "max_rounds"
    assert {f.resolution for f in stuck.steps[-1].critic.findings} == {"unresolved"}
    assert {f.resolution for f in stuck.steps[1].critic.findings} == {"open"}
    print("OK loop stops at max_critic_rounds and marks remaining findings unresolved")

    def broken(_prompt):
        raise TimeoutError("model timed out")

    logging.getLogger("evidence.loop").disabled = True
    failed = run_evidence_loop(
        run_id="t3",
        product_id="mahjong",
        product_name="麻雀",
        store=store,
        analyst=broken,
        critic=StubCritic([]),
        internal_tables=INTERNAL_TABLE_NAMES,
        external_tables=EXTERNAL_TABLE_NAMES,
    )
    assert failed.status == "error" and "model timed out" in failed.error and failed.finished_at
    print("OK a model failure ends the run with status error and keeps the trace")


def check_sql_tool(store: SQLiteEvidenceStore) -> None:
    log: list[SqlCall] = []
    run_sql = make_sql_tool(store, role="critic", log=log, max_calls=2)
    ok = json.loads(run_sql(sql="SELECT COUNT(*) AS n FROM asc_daily"))
    assert ok == {"columns": ["n"], "rows": [[14]], "truncated": False}, ok
    denied = json.loads(run_sql(sql="DELETE FROM asc_daily"))
    assert "error" in denied
    budget = json.loads(run_sql(sql="SELECT 1"))
    assert "budget" in budget["error"]
    assert [c.ok for c in log] == [True, False] and log[0].role == "critic"
    print("OK run_sql tool: JSON rows, write rejected and logged, query budget enforced")


def main() -> None:
    check_values_match()
    store = _store()
    try:
        check_code_rules(store)
        check_loop(store)
        check_sql_tool(store)
    finally:
        store.close()
    print("\nAll evidence loop checks passed.")


if __name__ == "__main__":
    main()
