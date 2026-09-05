"""Local HTTP API for the Indie Growth Agent Web UI.

Secrets stay on this Python process. The browser never receives credentials.
"""

from __future__ import annotations

import logging
import traceback
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent import run_analysis
from analysis_schema import AnalyzeResponse

logger = logging.getLogger("indie_growth_api")

app = FastAPI(title="Indie Growth Agent API", version="0.1.0")

# Local Next.js only. Do not widen this for production without an auth layer.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
    ],
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class AnalyzeRequest(BaseModel):
    language: Literal["ja", "en"] = Field(default="en")


class ErrorBody(BaseModel):
    error: str
    code: str = "analyze_failed"


def _public_error_message(language: str) -> str:
    if language == "ja":
        return "分析を完了できませんでした。データ接続を確認してください。"
    return "Could not complete the analysis. Please check your data connections."


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


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    logger.info("Analyze requested language=%s", body.language)
    try:
        report = run_analysis(language=body.language)
        logger.info(
            "Analyze completed language=%s app=%s actions=%s",
            body.language,
            report.app.get("name"),
            len(report.analysis.get("actions") or []),
        )
        return report
    except Exception as exc:  # noqa: BLE001 — map all failures to a safe client message
        _log_failure(exc)
        raise HTTPException(
            status_code=502,
            detail=ErrorBody(
                error=_public_error_message(body.language),
                code="analyze_failed",
            ).model_dump(),
        ) from None


def main() -> None:
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # Bind localhost only — never expose this process publicly without auth.
    uvicorn.run(
        "api_server:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
