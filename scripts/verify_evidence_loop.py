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

from evidence import (  # noqa: E402
    AnalystOutput,
    CriticReport,
    DecisionRecord,
    SQLiteEvidenceStore,
    SqlCall,
)
from evidence.critic import (  # noqa: E402
    FindingIds,
    apply_critic_report,
    critic_payload,
    dedupe,
    is_composite,
    recheck_cited_sql,
    structural_findings,
    values_equal,
    values_match,
)
from evidence.loop import comparison_periods, run_evidence_loop  # noqa: E402
from evidence.prompts import (  # noqa: E402
    ANALYST_SYSTEM,
    CRITIC_SYSTEM,
    past_decisions_text,
    version_json,
)
from evidence.schema import DecisionOutcome  # noqa: E402
from evidence.sources import (  # noqa: E402
    ASC_DAILY,
    COMPETITOR_LISTING,
    EXTERNAL_TABLE_NAMES,
    INTERNAL_TABLE_NAMES,
    KNOWN_EVENTS,
)
from evidence.sql_tool import LAST_QUERY_NOTE, make_sql_tool  # noqa: E402

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


RATIO_SQL = "SELECT SUM(product_page_views) * 1.0 / SUM(impressions) FROM asc_daily"
PERCENT_SQL = "SELECT SUM(product_page_views) * 100.0 / SUM(impressions) FROM asc_daily"


def check_values_match() -> None:
    assert values_match(2258, 2258) and not values_match(2258, 2259)
    assert values_match("2,258", "2258")
    assert values_match(36, 35.63) and not values_match(35.6, 35.7)
    assert not values_match("n/a", 1) and not values_match(1, None)
    print("OK values_match: exact counts, claim precision, strings from stores")

    # Counts, ratings, and amounts never match at 100x / 0.01x.
    assert not values_match("410", 4.1, sql="SELECT rating_avg FROM competitor_listing")
    assert not values_match(4.1, 410, sql="SELECT rating_count FROM competitor_listing")
    assert not values_match(1, 100, sql="SELECT COUNT(*) FROM competitor_listing")
    assert not values_match(2258, 22.58) and not values_match(22.58, 2258)
    assert not values_match("0.0", 5.0, sql="SELECT COUNT(*) FROM competitor_listing WHERE price = 0")
    print("OK values_match: no 100x / 0.01x match for counts, ratings, or amounts")

    # Zero never matches a non-zero value, even when it rounds to the claim's precision.
    assert not values_match(0, 0.3) and not values_match("0.0", 0.04) and not values_match(0.3, 0)
    assert not values_match("0%", 0.004, sql=RATIO_SQL)
    assert values_match(0, 0) and values_match("0.0", 0.0) and values_match("0%", 0, sql=RATIO_SQL)
    print("OK values_match: zero and non-zero never match")

    # A rate converts only when both units are visible.
    assert values_match("35.63%", 0.356321, sql=RATIO_SQL)
    assert values_match(0.3563, 35.6321, sql=PERCENT_SQL) and values_match(35.63, 35.6321, sql=PERCENT_SQL)
    assert values_match(0.3563, 0.356321, sql=RATIO_SQL)
    assert not values_match(35.63, 0.356321, sql=RATIO_SQL), "plain 35.63 has no stated unit"
    assert not values_match(35.63, 0.356321) and not values_match(0.3563, 35.6321)
    assert not values_match("35.63%", 0.356321), "no SQL: the ratio's meaning is not visible"
    assert not values_match("35.63%", 0.356321, sql=PERCENT_SQL), "SQL already returns a percent"
    assert not values_match("35.63%", 0.356321, sql="SELECT '1/2' AS x, rate FROM t")
    print("OK values_match: percent / ratio only with a % claim or a SQL that computes the rate")

    assert is_composite("impressions=2248, page_views=76") and is_composite("previous=15, current=11")
    assert not is_composite("Games") and not is_composite("2026-10-11") and not is_composite(2258)
    assert values_equal("Games", "games ") and not values_equal("Games", "Utilities")
    assert values_equal("35.63%", 0.35632, sql=RATIO_SQL) and not values_equal("35.63%", 0.35632)
    assert values_equal("NULL", None) and values_equal(None, None)
    assert not values_equal("NULL", 0) and not values_equal("Games", None)
    listing = "◉ 不要に!!!\n◉ 把握 できる\n\n機能一覧"
    assert values_equal("◉ 不要に!!!◉ 把握 できる 機能一覧", listing)
    assert values_equal("◉不要に!!!◉把握できる機能一覧", listing)
    assert not values_equal("◉ 不要に!!!!!!◉ 把握 できる 機能一覧", listing)
    assert not values_equal("◉ 不要に!!!◉ 把握 できた 機能一覧", listing)
    print("OK text values ignore only whitespace / line breaks; changed characters still mismatch")
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

    two_periods = AnalystOutput.model_validate(
        {
            "most_important_finding": "f",
            "claims": [
                {
                    "id": "p1",
                    "text": "downloads 28 vs 35",
                    "kind": "fact",
                    "evidence": [
                        {"table": "asc_daily", "sql": DOWNLOADS_SQL, "value": 28, "as_of": "2026-10-22", "source": "s"},
                        {"table": "asc_daily", "sql": "SELECT 35", "value": 35, "as_of": "2026-10-15", "source": "s"},
                    ],
                }
            ],
            "actions": [],
        }
    )
    previous_sql = (
        "SELECT SUM(first_time_downloads) FROM asc_daily "
        "WHERE date BETWEEN '2026-10-09' AND '2026-10-15'"
    )
    report = CriticReport.model_validate(
        {
            "summary": "s",
            "checks": [
                {"claim_id": "p1", "sql": previous_sql},
                {"claim_id": "p1", "sql": "SELECT 99", "evidence_index": 1},
            ],
        }
    )
    found, outcomes = apply_critic_report(report, two_periods, store=store, ids=FindingIds("r1"), log=[])
    assert [(o.matched, o.evidence_index) for o in outcomes] == [(True, 1), (False, 1)], outcomes
    assert [(f.kind, f.claimed_value, f.critic_value) for f in found] == [("value_mismatch", 35, 99)]
    print("OK without evidence_index a check matches whichever evidence item it reproduces")

    ratings = AnalystOutput.model_validate(
        {
            "most_important_finding": "f",
            "claims": [
                {
                    "id": "r1",
                    "text": "fictional-104: 410 ratings, average 4.1",
                    "kind": "observation",
                    "evidence": [
                        {"table": "competitor_listing", "sql": "SELECT 410", "value": "410", "as_of": "2026-10-22", "source": "s"},
                        {"table": "competitor_listing", "sql": "SELECT 4.1", "value": "4.1", "as_of": "2026-10-22", "source": "s"},
                    ],
                },
                _claim("r2", "observation", "0.0", "SELECT 0.0", table="competitor_listing"),
            ],
            "actions": [],
        }
    )
    report = CriticReport.model_validate(
        {
            "summary": "s",
            "checks": [
                {"claim_id": "r1", "sql": "SELECT 4.1", "evidence_index": 1},
                {"claim_id": "r1", "sql": "SELECT 4.1", "evidence_index": 0},
                {"claim_id": "r1", "sql": "SELECT 4.1"},
                {"claim_id": "r1", "sql": "SELECT 41", "evidence_index": 0},
                {"claim_id": "r1", "sql": "SELECT 4.1", "evidence_index": 7},
                {"claim_id": "r2", "sql": "SELECT COUNT(*) FROM competitor_listing WHERE is_self = 0"},
            ],
        }
    )
    found, outcomes = apply_critic_report(report, ratings, store=store, ids=FindingIds("r1"), log=[])
    assert [(o.matched, o.evidence_index) for o in outcomes] == [
        (True, 1), (False, 0), (True, 1), (False, 0), (True, 1), (False, 0),
    ], outcomes
    assert outcomes[1].error and "item 1" in outcomes[1].error, outcomes[1]
    assert outcomes[3].error is None and outcomes[5].error is None
    assert [(f.claim_id, f.claimed_value, f.critic_value) for f in found] == [
        ("r1", "410", 41), ("r2", "0.0", 1),
    ], found
    print("OK evidence_index: a check is compared with the item it names; equal to another item "
          "is not compared (no match, no finding); a count never matches a price of 0.0")

    two_wrong = AnalystOutput.model_validate(
        {
            "most_important_finding": "f",
            "claims": [
                {
                    "id": "w1",
                    "text": "rates",
                    "kind": "fact",
                    "evidence": [
                        {"table": "asc_daily", "sql": "SELECT 6.0", "value": 16.67, "as_of": "2026-10-15", "source": "s"},
                        {"table": "asc_daily", "sql": "SELECT 20.0", "value": 5.0, "as_of": "2026-10-15", "source": "s"},
                    ],
                }
            ],
            "actions": [],
        }
    )
    recheck = recheck_cited_sql(two_wrong, store=store, ids=FindingIds("r1"), log=[])
    report = CriticReport.model_validate(
        {
            "summary": "s",
            "checks": [
                {"claim_id": "w1", "sql": "SELECT 6.0", "evidence_index": 0},
                {"claim_id": "w1", "sql": "SELECT 20.0", "evidence_index": 1},
            ],
        }
    )
    checked, _ = apply_critic_report(report, two_wrong, store=store, ids=FindingIds("r1"), log=[])
    kept = dedupe([*recheck, *checked, *recheck])
    assert [(f.origin, f.claimed_value) for f in kept] == [
        ("code", 16.67), ("code", 5.0), ("code", 16.67), ("code", 5.0),
    ], kept
    assert len({f.message for f in kept}) == 2 and len(kept) == len(recheck) + len(checked)
    print("OK dedupe keeps each mismatch of one claim (same message, different SQL or value) "
          "and drops exact repeats")

    payload = critic_payload(V2)
    assert "SELECT" not in payload and "初心者向け" in payload
    print("OK Critic payload has claims and actions but none of the Analyst's SQL")


SHOTS = "スクリーンショット1〜3枚目を新しいデザインに差し替えた。"
SHOTS_SQL = "SELECT description FROM known_events WHERE date = '2026-10-16'"


def check_source_text() -> None:
    store = SQLiteEvidenceStore()
    try:
        store.replace_table(
            KNOWN_EVENTS,
            [
                {"date": "2026-10-15", "type": "store", "product": "mahjong", "description": "キーワードを変更した。"},
                {"date": "2026-10-16", "type": "store", "product": "mahjong", "description": SHOTS},
            ],
        )
        store.replace_table(
            COMPETITOR_LISTING,
            [{"fetched_on": "2026-10-22", "country": "jp", "app_id": "2", "is_self": 0, "rating_count": 2860}],
        )
        output = AnalystOutput.model_validate(
            {
                "most_important_finding": "f",
                "claims": [
                    _claim("q1", "observation", SHOTS, SHOTS_SQL, table="known_events"),
                    _claim("q2", "observation", SHOTS.replace("3", "4"), SHOTS_SQL, table="known_events"),
                    _claim("q3", "observation", "2026-10-15 store; 2026-10-16 store",
                           "SELECT date FROM known_events", table="known_events"),
                    _claim("q4", "observation", "Games: 2860, 1180, 960",
                           "SELECT rating_count FROM competitor_listing", table="competitor_listing"),
                    _claim("q5", "observation", "impressions=2248, downloads=37",
                           "SELECT 'impressions=2248, downloads=37' AS description FROM known_events",
                           table="known_events"),
                    _claim("q6", "observation", SHOTS,
                           "SELECT description FROM known_events WHERE date = '2026-10-15'",
                           table="known_events"),
                ],
                "actions": [],
            }
        )

        def flagged(found) -> set[str]:
            return {f.claim_id for f in found if f.kind == "unverifiable" and "packs" in f.message}

        tables = ["known_events", "competitor_listing"]
        found = structural_findings(output, table_names=tables, external_tables=EXTERNAL_TABLE_NAMES,
                                    ids=FindingIds("r1"), store=store)
        assert flagged(found) == {"q2", "q3", "q4", "q5"}, flagged(found)
        without_store = structural_findings(output, table_names=tables,
                                            external_tables=EXTERNAL_TABLE_NAMES, ids=FindingIds("r1"))
        assert flagged(without_store) == {"q1", "q2", "q3", "q4", "q5", "q6"}
        print("OK text quoted verbatim from a text column passes; packed or altered values are still flagged")

        recheck = recheck_cited_sql(output, store=store, ids=FindingIds("r1"), log=[])
        assert [(f.claim_id, f.kind) for f in recheck] == [("q6", "value_mismatch")], recheck
        report = CriticReport.model_validate(
            {
                "summary": "s",
                "checks": [{"claim_id": "q1", "sql": SHOTS_SQL}],
                "issues": [{"claim_id": "q1", "kind": "infeasible_action",
                            "message": "PPO ではサブタイトルを A/B テストできない"}],
            }
        )
        found, outcomes = apply_critic_report(report, output, store=store, ids=FindingIds("r1"), log=[])
        assert [o.matched for o in outcomes] == [True], outcomes
        assert [(f.claim_id, f.kind, f.origin) for f in found] == [("q1", "infeasible_action", "critic")]
        print("OK quoted text is still compared with what its SQL returns; Critic can flag infeasible actions")
    finally:
        store.close()

    for system in (ANALYST_SYSTEM, CRITIC_SYSTEM):
        assert "cannot be A/B tested" in system and "Apple Search Ads" in system
        assert "earlier metadata" in system and "every\n  competitor row" in system
    assert "infeasible_action" in CRITIC_SYSTEM
    print("OK Analyst and Critic prompts state the App Store constraints")

    infeasible = CRITIC_SYSTEM.split("- infeasible_action:", 1)[1].split("\n  Do not raise", 1)[0]
    assert "PPO A/B test of the subtitle or keywords" in infeasible
    assert "Search Ads feature used\n    for organic search" in infeasible
    assert "Not infeasible" in infeasible and "dated before/after comparison" in infeasible
    assert "overlap in time" in infeasible and "confounded or weak test design" in infeasible
    assert "not causal_leap when the action only checks an effect" in infeasible
    print("OK infeasible_action: App Store limits only; a feasible before/after with overlapping "
          "changes or an unasserted effect is not flagged")


class StubAnalyst:
    """Each item is an AnalystOutput (answered after one successful query) or (output, queries)."""

    def __init__(self, versions):
        self.versions = list(versions)
        self.prompts: list[str] = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        item = self.versions.pop(0)
        if isinstance(item, tuple):
            return item
        return item, [SqlCall(role="analyst", sql="SELECT 1", ok=True, row_count=1)]


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
    assert "Start with" in analyst.prompts[0] and "run_sql" in analyst.prompts[0]
    rejected = "is rejected and discarded"
    assert rejected in analyst.prompts[0] and rejected in analyst.prompts[1]
    assert rejected not in analyst.prompts[2] and rejected not in ANALYST_SYSTEM
    print("OK the 'rejected without SQL' rule is stated in v1 / v2 only, where the guard applies")

    revision = analyst.prompts[2]
    assert "Reuse evidence that code confirmed" in revision and "critic_value" in revision
    assert "has\na sql and a single value" in revision
    assert "No finding alone does not make evidence verified" in revision
    assert "Never describe unchecked evidence as verified" in revision
    assert "passed, so keep" not in revision, "no finding must not read as verified"
    assert "does not use the query budget" in revision
    assert "Spend run_sql on the findings first" in revision
    assert "Never remove a claim only because the query budget ran out" in revision
    assert "must not stay as it is either" in revision and "downgrade it to a hypothesis" in revision
    assert "update every action that cites it" in revision
    assert "use only numbers and competitor facts stated in the\n  claims it cites" in ANALYST_SYSTEM
    print("OK v3 reuses verified evidence, spends queries on findings, never drops a claim only "
          "for the budget, and keeps actions consistent with changed claims")

    summary_rule = CRITIC_SYSTEM.split("- summary:", 1)[1].split("\n\n", 1)[0]
    assert "Never say that numbers are verified" in summary_rule
    assert "code compares your checks after you answer" in summary_rule
    print("OK the Critic summary must not claim numbers are verified; code decides matches")

    def embedded_version(prompt: str, header: str) -> AnalystOutput:
        start = prompt.index(header) + len(header)
        data, _ = json.JSONDecoder().raw_decode(prompt, start)
        return AnalystOutput.model_validate(data)

    assert embedded_version(analyst.prompts[1], "Previous version (v1):\n") == V1
    assert embedded_version(analyst.prompts[2], "Your last version:\n") == V2
    assert version_json(V2) in analyst.prompts[2] and V2.model_dump_json(indent=2) not in analyst.prompts[2]
    assert len(version_json(V2)) < len(V2.model_dump_json(indent=2))
    print("OK v2 / v3 get the previous version as compact JSON that parses back to the same version")
    assert json.loads(saved[-1])["status"] == "converged" and len(saved) >= 6
    assert run.rejected_attempts == [] and len(analyst.prompts) == 3
    assert all(s.attempts == 1 for s in run.steps) and "RETRY" not in "".join(analyst.prompts)
    print("OK loop converges: v1 -> v2 -> Critic -> v3 -> Critic, findings resolved / downgraded")
    print("OK grounded answers are accepted on the first attempt (no extra retry)")

    def loop(analyst_stub, critic_stub, run_id):
        return run_evidence_loop(
            run_id=run_id,
            product_id="mahjong",
            product_name="麻雀",
            store=store,
            analyst=analyst_stub,
            critic=critic_stub,
            internal_tables=INTERNAL_TABLE_NAMES,
            external_tables=EXTERNAL_TABLE_NAMES,
        )

    failed_query = [SqlCall(role="analyst", sql="SELECT nope", ok=False, error="no such column")]
    retried = StubAnalyst([(V1, failed_query), V1, (V2, []), V2, V3])
    run_r = loop(retried, StubCritic([ROUND1, CLEAN]), "t-retry")
    assert run_r.status == "converged", (run_r.status, run_r.error)
    assert [s.version for s in run_r.steps] == ["v1", "v2", "v3"]
    assert [s.attempts for s in run_r.steps] == [2, 2, 1]
    assert [(r.version, r.attempt) for r in run_r.rejected_attempts] == [("v1", 1), ("v2", 1)]
    assert "c1" in run_r.rejected_attempts[0].reason
    assert run_r.rejected_attempts[0].queries[0].ok is False
    assert run_r.rejected_attempts[1].output == V2
    assert "RETRY" not in retried.prompts[0] and "RETRY" in retried.prompts[1]
    assert "sqlite" in retried.prompts[1] and "RETRY" in retried.prompts[3]
    print("OK v1 / v2 with numeric facts but no successful SQL are rejected, kept in the trace, "
          "and retried once; the retry that runs SQL continues normally")

    gave_up_critic = StubCritic([])
    gave_up = loop(StubAnalyst([(V1, []), (V1, [])]), gave_up_critic, "t-gave-up")
    assert gave_up.status == "error" and gave_up.error.startswith("AnalystGroundingError")
    assert gave_up.steps == [] and len(gave_up.rejected_attempts) == 2
    assert gave_up_critic.prompts == [] and gave_up.finished_at
    print("OK two ungrounded attempts stop the run with a clear error; no step, no Critic call")

    no_numbers = AnalystOutput.model_validate(
        {
            "most_important_finding": "f",
            "claims": [_claim("h1", "hypothesis", test_plan=TEST_PLAN)],
            "actions": [],
        }
    )
    lenient = loop(StubAnalyst([(no_numbers, []), V2, (V3, [])]), StubCritic([ROUND1, CLEAN]), "t-ok")
    assert lenient.rejected_attempts == [] and lenient.status == "converged", lenient.error
    print("OK no retry when there are no numeric facts, or in revision stages (v3)")

    def v3_with(**fields):
        return AnalystOutput.model_validate({**V3.model_dump(), **fields})

    v3_empty = v3_with(actions=[])
    v3_withdrawn = v3_with(
        actions=[],
        action_changes=[
            {"previous_rank": 1, "decision": "removed", "reason": "根拠の c3 が仮説に格下げされたため"}
        ],
    )
    v3_blank_reason = v3_with(
        actions=[],
        action_changes=[{"previous_rank": 1, "decision": "removed", "reason": " "}],
    )

    refilled = StubAnalyst([V1, V2, v3_empty, V3])
    run_e = loop(refilled, StubCritic([ROUND1, CLEAN]), "t-empty-retry")
    assert run_e.status == "converged", (run_e.status, run_e.error)
    assert [(r.version, r.attempt) for r in run_e.rejected_attempts] == [("v3", 1)]
    assert "previous action(s) 1" in run_e.rejected_attempts[0].reason
    assert run_e.rejected_attempts[0].output.actions == []
    assert run_e.steps[-1].attempts == 2 and run_e.steps[-1].output.actions
    assert "RETRY" in refilled.prompts[3] and "action_changes" in refilled.prompts[3]
    assert "RETRY" not in refilled.prompts[2]
    print("OK a revision that drops every action without a reason is rejected and retried once")

    explained = loop(StubAnalyst([V1, V2, v3_withdrawn]), StubCritic([ROUND1, CLEAN]), "t-withdrawn")
    assert explained.status == "converged" and explained.rejected_attempts == []
    assert explained.steps[-1].output.actions == [] and explained.steps[-1].attempts == 1
    print("OK withdrawing every action is accepted when each has a stated reason")

    empty_critic = StubCritic([ROUND1])
    empty_twice = loop(StubAnalyst([V1, V2, v3_empty, v3_blank_reason]), empty_critic, "t-empty-x2")
    assert empty_twice.status == "error", empty_twice.status
    assert empty_twice.error.startswith("AnalystRevisionError")
    assert [s.version for s in empty_twice.steps] == ["v1", "v2"]
    assert [(r.version, r.attempt) for r in empty_twice.rejected_attempts] == [("v3", 1), ("v3", 2)]
    assert len(empty_critic.prompts) == 1
    print("OK two unexplained empty revisions stop with an error; no empty final step is stored")

    decision = DecisionRecord(
        id="d-2026-10-01",
        product_id="mahjong",
        origin="manual",
        action_title="スクショ1枚目を差し替えた",
        baseline=[
            {"metric": "page_view_to_download", "value": 0.4868, "period_start": "2026-09-24", "period_end": "2026-09-30"}
        ],
        method="before/after",
        success_criterion="CVR +10%",
        evaluation_date="2026-10-29",
        created_at="2026-10-01T10:00:00+09:00",
    )
    assert "outcome" not in past_decisions_text([decision])
    evaluated = decision.model_copy(
        update={
            "id": "d-2026-09-10",
            "action_title": "キーワードから三麻を外した",
            "outcome": DecisionOutcome(
                evaluated_on="2026-09-30",
                verdict="inconclusive",
                note="母数が小さい",
                implemented_on="2026-09-15",
                measured_after=[
                    {"metric": "impressions", "value": 5198, "period_start": "2026-09-16", "period_end": "2026-09-29"}
                ],
            ),
        }
    )
    analyst_m = StubAnalyst([V1, V3])
    critic_m = StubCritic([CLEAN])
    with_memory = run_evidence_loop(
        run_id="t-mem",
        product_id="mahjong",
        product_name="麻雀",
        store=store,
        analyst=analyst_m,
        critic=critic_m,
        internal_tables=INTERNAL_TABLE_NAMES,
        external_tables=EXTERNAL_TABLE_NAMES,
        past_decisions=[decision, evaluated],
    )
    assert with_memory.status == "converged"
    assert with_memory.past_decision_ids == ["d-2026-10-01", "d-2026-09-10"]
    assert all("d-2026-10-01" in p and "NOT evidence" in p for p in analyst_m.prompts)
    assert all(
        "outcome: developer's verdict = inconclusive (2026-09-30, implemented 2026-09-15)" in p
        and "developer's note: 母数が小さい" in p
        and "measured after the change, at evaluation time: impressions=5198.0" in p
        and "never state it as a fact" in p
        for p in analyst_m.prompts
    )
    for p in critic_m.prompts:
        for leaked in (
            "d-2026-10-01", "スクショ1枚目を差し替えた", "d-2026-09-10", "developer's verdict",
            "母数が小さい",
        ):
            assert leaked not in p, leaked
    assert run.past_decision_ids == [] and "Past decisions" not in analyst.prompts[0]
    print("OK past decisions reach the Analyst as context only, never the Critic, ids kept in the run")
    print("OK an evaluated decision adds its outcome: the developer's verdict apart from measured numbers")

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
    assert ok == {"columns": ["n"], "rows": [[14]], "truncated": False, "queries_left": 1}, ok
    denied = json.loads(run_sql(sql="DELETE FROM asc_daily"))
    assert "error" in denied and denied["queries_left"] == 0
    assert denied["note"] == LAST_QUERY_NOTE
    budget = json.loads(run_sql(sql="SELECT 1"))
    assert "budget" in budget["error"]
    assert [c.ok for c in log] == [True, False] and log[0].role == "critic"
    assert [c.model_dump(by_alias=True).keys() for c in log] == [
        SqlCall(role="critic", sql="", ok=True).model_dump(by_alias=True).keys()
    ] * 2, "trace SqlCall shape unchanged"
    print("OK run_sql tool: JSON rows, write rejected and logged, query budget enforced")

    last = json.loads(make_sql_tool(store, role="analyst", log=[], max_calls=1)(sql="SELECT 1 AS x"))
    assert last["rows"] == [[1]] and last["queries_left"] == 0 and last["note"] == LAST_QUERY_NOTE
    for system in (ANALYST_SYSTEM, CRITIC_SYSTEM):
        assert "queries_left" in system and "do not call run_sql again" in system
    print("OK every result shows queries_left; the last allowed query says to answer now, "
          "so the model need not spend a round trip on a refused call")


def main() -> None:
    check_values_match()
    store = _store()
    try:
        check_code_rules(store)
        check_source_text()
        check_loop(store)
        check_sql_tool(store)
    finally:
        store.close()
    print("\nAll evidence loop checks passed.")


if __name__ == "__main__":
    main()
