"""Interventions: a change a person chose to make, its lifecycle, and how it turned out.

Three kinds of content never mix:
- prediction: the AI proposal copied from an evidence run when it was adopted. Never edited.
- decision / evaluation: what a person decided and how they judged the result.
- baseline / after: numbers computed by code with SQL on the evidence store. Never typed in.

Only the lifecycle needed for measurement is stored (planned -> implemented -> evaluated,
or dropped). Task planning (todo, due dates, priority) belongs to MakosoyoOffice.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from analysis_schema import decode_json_list
from evidence.schema import (
    ISO_DATE,
    BaselineMetric,
    Claim,
    DecisionOutcome,
    DecisionRecord,
    EvidenceModel,
    TestPlan,
)

InterventionStatus = Literal["planned", "implemented", "evaluated", "dropped"]
Verdict = Literal["improved", "no_change", "worse", "inconclusive"]
VERDICTS: tuple[Verdict, ...] = ("improved", "no_change", "worse", "inconclusive")


class AiPrediction(EvidenceModel):
    """The AI proposal as it was when a person adopted it."""

    run_id: str
    version: str = Field(pattern=r"^v\d+$")
    model: str = ""
    action_rank: int = Field(ge=1, le=3)
    action_title: str
    action_reason: str
    claims: list[Claim] = Field(default_factory=list)
    test_plan: TestPlan | None = None

    _decode_lists = field_validator("claims", mode="before")(decode_json_list)


class Measurement(EvidenceModel):
    """Numbers for one window, computed by code from the evidence store."""

    measured_at: str
    store: str
    period_start: str = Field(pattern=ISO_DATE)
    period_end: str = Field(pattern=ISO_DATE)
    metrics: list[BaselineMetric] = Field(default_factory=list)
    skipped: list[str] = Field(
        default_factory=list, description="Metrics not measured, with the reason."
    )


class HumanEvaluation(EvidenceModel):
    """A person's judgment of the outcome. inconclusive is a valid, honest answer."""

    evaluated_on: str = Field(pattern=ISO_DATE)
    verdict: Verdict
    note: str = ""


class Intervention(EvidenceModel):
    id: str
    status: InterventionStatus = "planned"
    target_metric: str = Field(description="The metric the person will judge the change by.")
    duration_days: int = Field(ge=1, description="Days after implementation until evaluation.")
    window_days: int = Field(ge=1, description="Length of the before and after windows.")
    decision: DecisionRecord
    prediction: AiPrediction | None = None
    implemented_on: str | None = Field(default=None, pattern=ISO_DATE)
    baseline: Measurement | None = None
    after: Measurement | None = None
    evaluation: HumanEvaluation | None = None
    drop_reason: str = ""
    memory_ids: dict[str, str] = Field(
        default_factory=dict, description="'<backend>:<decision|outcome>' -> memory id"
    )
    updated_at: str

    @model_validator(mode="after")
    def _origin_matches_prediction(self) -> Intervention:
        if self.decision.id != self.id:
            raise ValueError("decision.id must equal the intervention id")
        if self.decision.origin == "ai_adopted" and self.prediction is None:
            raise ValueError("an AI-adopted intervention needs the AI prediction it came from")
        if self.decision.origin == "manual" and self.prediction is not None:
            raise ValueError("a manual intervention has no AI prediction")
        return self

    @property
    def product_id(self) -> str:
        return self.decision.product_id

    @property
    def title(self) -> str:
        return self.decision.action_title

    def decision_with_outcome(self) -> DecisionRecord:
        """The decision for Analyst context, with the verdict and after numbers once evaluated."""
        if self.evaluation is None:
            return self.decision
        return self.decision.model_copy(
            update={
                "outcome": DecisionOutcome(
                    evaluated_on=self.evaluation.evaluated_on,
                    verdict=self.evaluation.verdict,
                    note=self.evaluation.note,
                    implemented_on=self.implemented_on,
                    measured_after=list(self.after.metrics) if self.after else [],
                )
            }
        )
