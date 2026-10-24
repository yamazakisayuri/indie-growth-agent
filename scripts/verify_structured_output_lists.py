"""Verify LLM output models accept list fields sent as JSON strings (no model calls).

Run: python scripts/verify_structured_output_lists.py
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

from analysis_schema import (  # noqa: E402
    DraftGeneratorOutput,
    PlannerStructuredOutput,
    StructuredAnalysis,
)

FACTS = ["インプレッション 2,258 → 2,248", "ページビュー→ダウンロード率 48.68% → 35.63%"]
ACTIONS = [
    {"rank": 1, "title": "製品ページを見直す", "reason": "転換率が低下", "basis": "ASC"},
    {"rank": 2, "title": "キーワードを調整する", "reason": "検索が主経路"},
]


def _expect_invalid(model, payload: dict, label: str) -> None:
    try:
        model.model_validate(payload)
    except ValidationError:
        print(f"OK {label} → still rejected")
    else:
        raise AssertionError(f"{label} must stay invalid")


def main() -> None:
    # Shape Nemotron returned via Nightshift when tool_choice was auto.
    stringified = StructuredAnalysis.model_validate(
        {
            "most_important_finding": "転換率が低下",
            "facts": json.dumps(FACTS, ensure_ascii=False),
            "speculation": "[]",
            "actions": json.dumps(ACTIONS, ensure_ascii=False),
        }
    )
    native = StructuredAnalysis.model_validate(
        {"most_important_finding": "転換率が低下", "facts": FACTS, "actions": ACTIONS}
    )
    assert stringified == native, (stringified, native)
    assert [a.rank for a in stringified.actions] == [1, 2]
    print("OK StructuredAnalysis: JSON-string lists decode to the same result as arrays")

    _expect_invalid(
        StructuredAnalysis,
        {"most_important_finding": "x", "facts": "not a list"},
        "plain string in a list field",
    )
    _expect_invalid(
        StructuredAnalysis,
        {"most_important_finding": "x", "actions": '{"rank": 1}'},
        "JSON object string in a list field",
    )
    _expect_invalid(
        StructuredAnalysis,
        {"most_important_finding": "x", "actions": '[{"rank": 9, "title": "t", "reason": "r"}]'},
        "decoded list with an out-of-range rank",
    )

    planner = PlannerStructuredOutput.model_validate(
        {
            "summary": "s",
            "playbooksConsulted": '["aso-basics"]',
            "knownEventsUsed": '["2026-10-11 release"]',
            "experiments": "[]",
        }
    )
    assert planner.playbooks_consulted == ["aso-basics"]
    assert planner.known_events_used == ["2026-10-11 release"]
    print("OK PlannerStructuredOutput: aliased JSON-string lists decode")

    draft = DraftGeneratorOutput.model_validate(
        {
            "draft": {
                "experimentTitle": "t",
                "draftType": "screenshot_copy",
                "objective": "o",
                "rationale": "r",
                "screenshots": '[{"position": 1, "copyDraft": "c"}]',
                "missingInputs": '["current screenshots"]',
                "playbooksUsed": "[]",
            }
        }
    )
    assert draft.draft.screenshots[0].copy_draft == "c"
    assert draft.draft.missing_inputs == ["current screenshots"]
    print("OK ActionDraft: nested JSON-string lists decode")

    props = convert_pydantic_to_tool_spec(StructuredAnalysis)["inputSchema"]["json"]["properties"]
    for name in ("facts", "speculation", "actions"):
        assert "array" in props[name]["type"], (name, props[name])
    print("OK tool spec sent to the model still declares the list fields as arrays")

    print("\nAll structured-output list checks passed.")


if __name__ == "__main__":
    main()
