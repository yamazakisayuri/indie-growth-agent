"""Verify the evidence schema (claims, Critic findings, runs, decisions). No model calls.

Run: python scripts/verify_evidence_schema.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import ValidationError  # noqa: E402
from strands.tools.structured_output.structured_output_utils import (  # noqa: E402
    convert_pydantic_to_tool_spec,
)

from evidence import (  # noqa: E402
    AnalystOutput,
    CriticReport,
    DecisionRecord,
    EvidenceRun,
    RevisionStep,
)

FACT = {
    "id": "c1",
    "text": "ページビュー→ダウンロード率は 48.68% → 35.63%",
    "kind": "fact",
    "evidence": [
        {
            "table": "asc_daily",
            "sql": "SELECT SUM(first_time_downloads) * 1.0 / SUM(product_page_views) FROM asc_daily",
            "value": 0.3563,
            "as_of": "2026-10-22",
            "source": "asc_analytics",
            "scope": "JP App Store, all sources",
        }
    ],
}
OBSERVATION = {
    "id": "c2",
    "text": "上位競合5件の評価数の中央値は 1,095 件",
    "kind": "observation",
    "evidence": [
        {
            "table": "competitor_listing",
            "value": 1095,
            "as_of": "2026-10-24",
            "source": "itunes_lookup",
            "url": "https://apps.apple.com/jp/app/id1329138513",
        }
    ],
}
HYPOTHESIS = {
    "id": "c3",
    "text": "初心者向けの訴求にすると転換率が上がる",
    "kind": "hypothesis",
    "testPlan": {
        "metric": "conversion rate",
        "method": "product page optimization A/B test",
        "durationDays": 28,
        "successCriterion": "treatment beats baseline at 90% confidence",
    },
}
ANALYST = {
    "most_important_finding": "転換率が低下",
    "claims": [FACT, OBSERVATION, HYPOTHESIS],
    "actions": [
        {"rank": 1, "title": "スクショ1枚目を差し替えて A/B テスト", "reason": "r", "claim_ids": ["c1", "c3"]}
    ],
}


def _expect_invalid(model, payload: dict, label: str) -> None:
    try:
        model.model_validate(payload)
    except ValidationError:
        print(f"OK {label} → rejected")
    else:
        raise AssertionError(f"{label} must be invalid")


def main() -> None:
    v2 = AnalystOutput.model_validate(ANALYST)
    assert [c.kind for c in v2.claims] == ["fact", "observation", "hypothesis"]
    assert v2.claims[2].test_plan and v2.claims[2].test_plan.duration_days == 28
    assert v2.actions[0].claim_ids == ["c1", "c3"]
    print("OK AnalystOutput accepts snake_case and camelCase keys")

    stringified = AnalystOutput.model_validate(
        {
            **ANALYST,
            "claims": json.dumps(ANALYST["claims"], ensure_ascii=False),
            "actions": json.dumps(ANALYST["actions"], ensure_ascii=False),
        }
    )
    assert stringified == v2
    print("OK JSON-string lists decode to the same AnalystOutput")

    _expect_invalid(
        AnalystOutput,
        {**ANALYST, "claims": [{**FACT, "kind": "guess"}]},
        "unknown claim kind",
    )
    _expect_invalid(
        AnalystOutput,
        {**ANALYST, "claims": [{**OBSERVATION, "evidence": [{**OBSERVATION["evidence"][0], "as_of": "10/24"}]}]},
        "evidence date not in YYYY-MM-DD",
    )

    critic = CriticReport.model_validate(
        {
            "summary": "1件差し戻し",
            "findings": '[{"id": "f1", "claim_id": "c3", "kind": "causal_leap", '
            '"message": "競合の訴求から効果は断定できない"}]',
        }
    )
    assert critic.findings[0].resolution == "open"
    print("OK CriticReport decodes findings and defaults resolution to open")

    run = EvidenceRun(
        run_id="run-1",
        product_id="mahjong",
        started_at="2026-10-24T16:00:00+09:00",
        status="converged",
        steps=[
            RevisionStep(version="v2", stage="competitive", output=v2, critic=critic),
            RevisionStep(version="v3", stage="critic_revision", output=v2),
        ],
        decision=DecisionRecord(
            id="d1",
            product_id="mahjong",
            origin="ai_adopted",
            run_id="run-1",
            action_title="スクショ1枚目を差し替えて A/B テスト",
            baseline=[
                {
                    "metric": "page_view_to_download",
                    "value": 0.3563,
                    "period_start": "2026-10-16",
                    "period_end": "2026-10-22",
                }
            ],
            method="product page optimization A/B test",
            success_criterion="treatment beats baseline",
            evaluation_date="2026-11-21",
            created_at="2026-10-24T16:05:00+09:00",
        ),
    )
    dumped = run.model_dump(by_alias=True)
    assert "runId" in dumped and "findingResponses" in dumped["steps"][0]["output"]
    assert EvidenceRun.model_validate_json(run.model_dump_json(by_alias=True)) == run
    assert run.final is not None and run.final.version == "v3"
    print("OK EvidenceRun round-trips as camelCase JSON for the Web UI")

    _expect_invalid(
        RevisionStep,
        {"version": "final", "stage": "internal", "output": ANALYST},
        "version label not like v1",
    )

    for model in (AnalystOutput, CriticReport):
        props = convert_pydantic_to_tool_spec(model)["inputSchema"]["json"]["properties"]
        list_field = "claims" if model is AnalystOutput else "findings"
        assert "array" in json.dumps(props[list_field]), (model.__name__, props[list_field])
    print("OK tool specs for AnalystOutput and CriticReport declare list fields as arrays")

    print("\nAll evidence schema checks passed.")


if __name__ == "__main__":
    main()
