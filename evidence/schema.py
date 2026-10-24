"""Claims with sources, Critic findings, revision runs, and decision records.

LLM output models (AnalystOutput, CriticReport) are sent to the model as
structured-output tools. Stored models (RevisionStep, EvidenceRun,
DecisionRecord) are written by code and returned to the Web UI.

Decision records hold the content of a change (baseline, evaluation date,
method). Task status (todo / done) is intentionally not stored here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from analysis_schema import decode_json_list

ClaimKind = Literal["fact", "observation", "hypothesis"]
FindingKind = Literal[
    "value_mismatch",
    "unverifiable",
    "kind_mislabel",
    "scope_mismatch",
    "causal_leap",
]
FindingResolution = Literal["open", "resolved", "downgraded", "unresolved"]
RevisionStage = Literal["internal", "competitive", "critic_revision"]
ISO_DATE = r"^\d{4}-\d{2}-\d{2}$"


class EvidenceModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Evidence(EvidenceModel):
    """Where one number or observation in a claim came from."""

    table: str
    sql: str = Field(
        default="",
        description="Read-only SELECT that reproduces value. Empty only when no store query applies.",
    )
    value: float | str | None = None
    as_of: str = Field(pattern=ISO_DATE, description="Date of the data or fetch (YYYY-MM-DD).")
    source: str = Field(description="Origin, e.g. asc_analytics, itunes_lookup, web_scrape.")
    scope: str = Field(default="", description="Population, e.g. 'JP App Store, all sources'.")
    url: str | None = None


class TestPlan(EvidenceModel):
    """How a hypothesis would be tested before it is treated as true."""

    metric: str
    method: str = Field(description="e.g. product page optimization A/B test, before/after.")
    duration_days: int = Field(ge=1)
    success_criterion: str


class Claim(EvidenceModel):
    """One statement the Analyst relies on.

    fact: first-party data reproducible by SQL. observation: external public
    information with source and fetch date. hypothesis: causal or speculative,
    needs a test plan.
    """

    id: str
    text: str
    kind: ClaimKind
    evidence: list[Evidence] = Field(default_factory=list)
    test_plan: TestPlan | None = None

    _decode_lists = field_validator("evidence", mode="before")(decode_json_list)


class ProposedAction(EvidenceModel):
    rank: int = Field(ge=1, le=3)
    title: str
    reason: str
    claim_ids: list[str] = Field(default_factory=list)

    _decode_lists = field_validator("claim_ids", mode="before")(decode_json_list)


class FindingResponse(EvidenceModel):
    """Analyst's answer to one Critic finding when producing the next version."""

    finding_id: str
    response: Literal["fixed", "downgraded", "removed", "disputed"]
    note: str = ""


class AnalystOutput(EvidenceModel):
    """Structured Analyst output for one version (v1, v2, v3, ...)."""

    most_important_finding: str
    claims: list[Claim] = Field(default_factory=list)
    actions: list[ProposedAction] = Field(default_factory=list)
    finding_responses: list[FindingResponse] = Field(default_factory=list)

    _decode_lists = field_validator(
        "claims", "actions", "finding_responses", mode="before"
    )(decode_json_list)


class CriticFinding(EvidenceModel):
    """One problem the Critic found in a claim, checked with its own SQL."""

    id: str
    claim_id: str
    kind: FindingKind
    message: str
    critic_sql: str = ""
    critic_value: float | str | None = None
    claimed_value: float | str | None = None
    resolution: FindingResolution = "open"


class CriticReport(EvidenceModel):
    """Structured Critic output. An empty findings list means the version passed."""

    summary: str
    findings: list[CriticFinding] = Field(default_factory=list)

    _decode_lists = field_validator("findings", mode="before")(decode_json_list)


class RevisionStep(EvidenceModel):
    version: str = Field(pattern=r"^v\d+$")
    stage: RevisionStage
    output: AnalystOutput
    critic: CriticReport | None = None


class BaselineMetric(EvidenceModel):
    metric: str
    value: float
    period_start: str = Field(pattern=ISO_DATE)
    period_end: str = Field(pattern=ISO_DATE)
    sql: str = ""


class DecisionRecord(EvidenceModel):
    """A change a person chose to make, with what to measure and when."""

    id: str
    product_id: str
    origin: Literal["ai_adopted", "manual"]
    run_id: str | None = Field(default=None, description="Evidence run when origin is ai_adopted.")
    action_title: str
    change_description: str = ""
    baseline: list[BaselineMetric] = Field(default_factory=list)
    method: str
    success_criterion: str
    evaluation_date: str = Field(pattern=ISO_DATE)
    created_at: str


class EvidenceRun(EvidenceModel):
    """One v1 → v2 → Critic → v3 run, stored as the revision history."""

    run_id: str
    product_id: str
    started_at: str
    finished_at: str | None = None
    status: Literal["running", "converged", "max_rounds", "error"] = "running"
    steps: list[RevisionStep] = Field(default_factory=list)
    error: str | None = None
    decision: DecisionRecord | None = None

    @property
    def final(self) -> RevisionStep | None:
        return self.steps[-1] if self.steps else None
