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
