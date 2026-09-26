"""HTTP API for the Indie Growth Agent Web UI.

Secrets stay on this Python process. The browser never receives credentials.
"""

from __future__ import annotations

import logging
import os
import traceback
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent import run_analysis
from analysis_schema import AnalyzeResponse
from analyze_cache import analyze_cache_key, get_or_run_analyze
from draft_generator import run_draft_generator

logger = logging.getLogger("indie_growth_api")

# Local Next.js defaults. Add production Amplify origins via CORS_ALLOWED_ORIGINS.
_DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
)


def _cors_allowed_origins() -> list[str]:
    origins: list[str] = list(_DEFAULT_CORS_ORIGINS)
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    if raw:
        for part in raw.split(","):
            origin = part.strip().rstrip("/")
            if origin and origin not in origins:
                origins.append(origin)
    return origins


app = FastAPI(title="Indie Growth Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allowed_origins(),
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class AnalyzeRequest(BaseModel):
    language: Literal["ja", "en"] = Field(default="en")
    product_id: str | None = Field(default=None, alias="productId")

    model_config = {"populate_by_name": True}


class DraftExperimentBody(BaseModel):
    title: str
    hypothesis: str = ""
    why: str = ""
    action: str = ""
    targetMetric: str = ""
    expectedSignal: str = ""
    suggestedDuration: str = ""
    evidence: str = ""
    playbookReference: str = ""
    analysisRunId: str | None = None


class UserScreenshotInput(BaseModel):
    """Ephemeral App Store screenshot for Screenshot Drafts (request only).

    Not persisted to disk, Known Events, or the repository.
    """

    position: int | None = None
    fileName: str | None = None
    mimeType: str | None = None
    description: str | None = None
    dataBase64: str | None = None


class DraftPeriodBody(BaseModel):
    start: str | None = None
    end: str | None = None
    lookbackDays: int | None = None
    label: str | None = None
    comparisonLabel: str | None = None
    latestProcessingDate: str | None = None


class DraftRequest(BaseModel):
    """Human-selected experiment only — never auto-draft all experiments."""

    language: Literal["ja", "en"] = Field(default="en")
    product_id: str | None = Field(default=None, alias="productId")
    experiment: DraftExperimentBody
    mostImportantFinding: str = ""
    facts: list[str] = Field(default_factory=list)
    playbooksConsulted: list[str] = Field(default_factory=list)
    app: dict = Field(default_factory=dict)
    userScreenshots: list[UserScreenshotInput] = Field(default_factory=list)
    period: DraftPeriodBody | None = None
    metrics: dict = Field(default_factory=dict)
    analysisRunId: str | None = None
    dataSource: Literal["live", "mock"] | None = None

    model_config = {"populate_by_name": True}


class ErrorBody(BaseModel):
    error: str
    code: str = "analyze_failed"


def _public_error_message(language: str) -> str:
    if language == "ja":
        return "分析を完了できませんでした。データ接続を確認してください。"
    return "Could not complete the analysis. Please check your data connections."


def _public_draft_error_message(language: str) -> str:
    if language == "ja":
        return "草案を生成できませんでした。しばらくしてから再度お試しください。"
    return "Could not generate the draft. Please try again later."


def _assert_draft_analysis_context(body: DraftRequest) -> None:
    """Fail fast when Experiment and report Analysis Context disagree."""
    report_run = (body.analysisRunId or "").strip() or None
    exp_run = (body.experiment.analysisRunId or "").strip() or None
    data_source = body.dataSource

    if report_run and exp_run and report_run != exp_run:
        raise HTTPException(
            status_code=409,
            detail=ErrorBody(
                error="Analysis context mismatch",
                code="analysis_context_mismatch",
            ).model_dump(),
        )

    if data_source == "live":
        if not report_run or not exp_run:
            raise HTTPException(
                status_code=409,
                detail=ErrorBody(
                    error="Analysis context mismatch",
                    code="analysis_context_mismatch",
                ).model_dump(),
            )

    if data_source == "mock" and exp_run and report_run and not exp_run.startswith("mock"):
        # Live experiment must never be drafted against mock Facts.
        raise HTTPException(
            status_code=409,
            detail=ErrorBody(
                error="Analysis context mismatch",
                code="analysis_context_mismatch",
            ).model_dump(),
        )


def _log_failure(exc: BaseException) -> None:
    """Log debug context without credential / token / key material."""
    logger.error(
        "Analyze failed: %s: %s",
        type(exc).__name__,
        str(exc)[:500],
    )
    logger.debug("Traceback:\n%s", traceback.format_exc())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/products")
def list_products() -> dict:
    """Public product catalog for the UI selector (no secrets)."""
    from product_config import get_default_product_id, list_product_summaries

    return {
        "defaultProductId": get_default_product_id(),
        "products": list_product_summaries(),
    }


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    cache_key = analyze_cache_key(body.product_id, body.language)
    logger.info(
        "Analyze requested language=%s productId=%s cacheKey=%s",
        body.language,
        body.product_id or "(default)",
        cache_key,
    )
    try:
        report, from_cache = get_or_run_analyze(
            cache_key,
            lambda: run_analysis(
                language=body.language,
                product_id=body.product_id,
            ),
        )
        logger.info(
            "Analyze completed cached=%s language=%s product=%s app=%s actions=%s "
            "experiments=%s planner=%s analysisRunId=%s period=%s→%s",
            from_cache,
            body.language,
            (report.product or {}).get("id") if report.product else None,
            report.app.get("name"),
            len(report.analysis.get("actions") or []),
            len(report.growth_experiments or []),
            (report.planner_status or "")[:120],
            report.analysis_run_id,
            (report.period or {}).get("start"),
            (report.period or {}).get("end"),
        )
        return report
    except ValueError as exc:
        # Unknown product id etc. — not cached.
        logger.warning("Analyze rejected: %s", str(exc)[:300])
        raise HTTPException(
            status_code=400,
            detail=ErrorBody(
                error=str(exc)[:200],
                code="invalid_product",
            ).model_dump(),
        ) from None
    except Exception as exc:  # noqa: BLE001 — map all failures to a safe client message
        _log_failure(exc)
        raise HTTPException(
            status_code=502,
            detail=ErrorBody(
                error=_public_error_message(body.language),
                code="analyze_failed",
            ).model_dump(),
        ) from None


@app.post("/api/draft")
def create_draft(body: DraftRequest) -> dict:
    """Generate a production draft for one explicitly selected Growth Experiment."""
    _assert_draft_analysis_context(body)
    period = body.period.model_dump() if body.period is not None else {}
    logger.info(
        "Draft requested language=%s productId=%s experiment=%s user_screenshots=%s "
        "analysisRunId=%s dataSource=%s period=%s→%s",
        body.language,
        body.product_id or "(default)",
        body.experiment.title[:120],
        len(body.userScreenshots or []),
        body.analysisRunId,
        body.dataSource,
        period.get("start"),
        period.get("end"),
    )
    try:
        from product_config import use_product

        with use_product(body.product_id):
            result = run_draft_generator(
                experiment=body.experiment.model_dump(),
                most_important_finding=body.mostImportantFinding,
                facts=body.facts,
                playbooks_consulted=body.playbooksConsulted,
                app=body.app,
                user_screenshots=[s.model_dump() for s in body.userScreenshots],
                language=body.language,
                period=period,
                metrics=body.metrics or {},
                analysis_run_id=body.analysisRunId,
                data_source=body.dataSource,
            )
        draft = result.get("draft") or {}
        logger.info(
            "Draft completed type=%s screenshots=%s missing=%s analysisRunId=%s",
            draft.get("draftType"),
            len(draft.get("screenshots") or []),
            len(draft.get("missingInputs") or []),
            result.get("analysisRunId"),
        )
        return result
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Draft failed: %s: %s",
            type(exc).__name__,
            str(exc)[:500],
        )
        logger.debug("Traceback:\n%s", traceback.format_exc())
        raise HTTPException(
            status_code=502,
            detail=ErrorBody(
                error=_public_draft_error_message(body.language),
                code="draft_failed",
            ).model_dump(),
        ) from None


def main() -> None:
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    host = os.getenv("HOST", "0.0.0.0").strip() or "0.0.0.0"
    port_raw = os.getenv("PORT", "8000").strip() or "8000"
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise ValueError(f"PORT must be an integer, got {port_raw!r}") from exc

    uvicorn.run(
        "api_server:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
