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
