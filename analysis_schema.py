"""Pydantic models for structured Agent analysis and the Web API response."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalysisAction(BaseModel):
    """One prioritized action from the Agent."""

    rank: int = Field(ge=1, le=3)
    title: str
    reason: str
    basis: str = ""


class StructuredAnalysis(BaseModel):
    """
    Structured Agent output. Same grounding as the text system prompt:
    facts stay observable; speculation stays labeled separately; actions stay grounded.
    """

    most_important_finding: str
    facts: list[str] = Field(default_factory=list)
    speculation: list[str] = Field(default_factory=list)
    actions: list[AnalysisAction] = Field(default_factory=list)


class GrowthExperiment(BaseModel):
    """One Planner-proposed growth / measurement experiment (not Analyzer actions)."""

    model_config = ConfigDict(populate_by_name=True)

    title: str
    hypothesis: str
    why: str
    action: str
    target_metric: str = Field(alias="targetMetric")
    expected_signal: str = Field(alias="expectedSignal")
    suggested_duration: str = Field(alias="suggestedDuration")
    evidence: str
    playbook_reference: str = Field(alias="playbookReference")
    # Stamped by the server after Planner runs — not invented by the LLM.
    analysis_run_id: str | None = Field(default=None, alias="analysisRunId")


class PlannerStructuredOutput(BaseModel):
    """Structured Planner Agent output (0–3 experiments)."""

    model_config = ConfigDict(populate_by_name=True)

    summary: str
    playbooks_consulted: list[str] = Field(
        default_factory=list,
        alias="playbooksConsulted",
    )
    known_events_used: list[str] = Field(
        default_factory=list,
        alias="knownEventsUsed",
        description="Short labels of Known Events that influenced this plan (date + type).",
    )
    experiments: list[GrowthExperiment] = Field(default_factory=list)


class ScreenshotDraftItem(BaseModel):
    """One screenshot slot in a production draft (text plan only — no images stored)."""

    model_config = ConfigDict(populate_by_name=True)

    position: int = Field(ge=1)
    # When user images are present, prefer currentMessage / keep / change.
    message_goal: str = Field(default="", alias="messageGoal")
    current_message: str = Field(default="", alias="currentMessage")
    keep: str = ""
    change: str = ""
    copy_draft: str = Field(default="", alias="copyDraft")
    recommended_screen: str = Field(default="", alias="recommendedScreen")
    why: str = ""


class ActionDraft(BaseModel):
    """Human-usable production draft for a selected Growth Experiment."""

    model_config = ConfigDict(populate_by_name=True)

    experiment_title: str = Field(alias="experimentTitle")
    draft_type: str = Field(
        alias="draftType",
        description=(
            "Extensible type label, e.g. screenshot_copy, metadata, "
            "measurement_plan, social_post, video_script, seo_article."
        ),
    )
    objective: str
    rationale: str
    screenshots: list[ScreenshotDraftItem] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list, alias="missingInputs")
    notes: str = ""
    playbooks_used: list[str] = Field(default_factory=list, alias="playbooksUsed")
    no_change_recommended: bool = Field(
        default=False,
        alias="noChangeRecommended",
        description=(
            "True when current creatives already meet the experiment objective; "
            "do not invent changes just because Planner suggested screenshots."
        ),
    )


class DraftGeneratorOutput(BaseModel):
    """Structured Draft Generator agent output."""

    model_config = ConfigDict(populate_by_name=True)

    draft: ActionDraft


class MetricItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    label: str
    change_percent: float | None = Field(default=None, alias="changePercent")
    value: str | None = None
    absolute: str | None = None
    note: str | None = None


class MetricGroup(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Literal["app_store", "usage", "revenue"]
    title: str
    source: str
    connected: bool = True
    status_message: str | None = Field(default=None, alias="statusMessage")
    metrics: list[MetricItem] = Field(default_factory=list)


class DataScopeItem(BaseModel):
    source: str
    scope: str


class RevenueSourceItem(BaseModel):
    """One revenue source row in RevenueSummary (extensible beyond AdMob)."""

    model_config = ConfigDict(populate_by_name=True)

    source: str = Field(
        description="Logical source id, e.g. admob, app_store, google_play, web.",
    )
    amount: float | None = None
    previous_amount: float | None = Field(default=None, alias="previousAmount")
    change_percent: float | None = Field(default=None, alias="changePercent")
    currency: str | None = None
    connected: bool = False
    status: Literal["ok", "unavailable", "not_connected"] = "not_connected"


class RevenueSummary(BaseModel):
    """Optional cross-source revenue view for Analyzer / Planner / UI.

    Phase 1 typically has a single admob source. ``total`` is intentionally
    omitted until multiple comparable same-currency sources exist.
    """

    model_config = ConfigDict(populate_by_name=True)

    currency: str | None = None
    note: str = ""
    sources: list[RevenueSourceItem] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    """JSON shape returned to the Web UI."""

    model_config = ConfigDict(populate_by_name=True)

    language: Literal["ja", "en"]
    app: dict[str, Any]
    period: dict[str, Any]
    metrics: dict[str, MetricGroup]
    analysis: dict[str, Any]
    data_scope: list[DataScopeItem] = Field(alias="dataScope")
    grounding_rules: list[str] = Field(alias="groundingRules")
    # Identifies one Analyzer→Planner run; Draft must reuse the same id.
    analysis_run_id: str = Field(alias="analysisRunId")
    data_source: Literal["live", "mock"] = Field(
        default="live",
        alias="dataSource",
    )
    revenue_summary: RevenueSummary | None = Field(
        default=None,
        alias="revenueSummary",
    )
    # Planner is additive; Analyzer succeeds even when these stay empty / error.
    growth_experiments: list[dict[str, Any]] = Field(
        default_factory=list,
        alias="growthExperiments",
    )
    planner_status: str | None = Field(default=None, alias="plannerStatus")
    planner_error: str | None = Field(default=None, alias="plannerError")
    playbooks_consulted: list[str] = Field(
        default_factory=list,
        alias="playbooksConsulted",
    )
    known_events_considered: list[dict[str, Any]] = Field(
        default_factory=list,
        alias="knownEventsConsidered",
    )
    known_events_used: list[str] = Field(
        default_factory=list,
        alias="knownEventsUsed",
    )
