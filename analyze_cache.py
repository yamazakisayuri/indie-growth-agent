"""In-process Analyze success cache + single-flight (FastAPI process memory).

Key: productId × language × Asia/Tokyo calendar date.
Failures are never stored. Safe for sync uvicorn (threaded) handlers.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import Future
from datetime import datetime
from typing import Callable, TypeVar
from zoneinfo import ZoneInfo

from analysis_schema import AnalyzeResponse

logger = logging.getLogger("indie_growth_api.cache")

_TOKYO = ZoneInfo("Asia/Tokyo")

_lock = threading.Lock()
_success: dict[str, AnalyzeResponse] = {}
_inflight: dict[str, Future[AnalyzeResponse]] = {}

T = TypeVar("T")


def tokyo_analysis_date() -> str:
    """Calendar day in Asia/Tokyo used as the cache date component."""
    return datetime.now(_TOKYO).date().isoformat()


def normalize_product_id(product_id: str | None) -> str:
    """Stable product key; blank → catalog default (no external API)."""
    raw = (product_id or "").strip()
    if raw:
        return raw
    from product_config import get_default_product_id

    return get_default_product_id()


def analyze_cache_key(product_id: str | None, language: str) -> str:
    product = normalize_product_id(product_id)
    lang = (language or "en").strip().lower() or "en"
    if lang not in ("ja", "en"):
        lang = "en"
    return f"{product}|{lang}|{tokyo_analysis_date()}"


def get_or_run_analyze(
    key: str,
    runner: Callable[[], AnalyzeResponse],
) -> tuple[AnalyzeResponse, bool]:
    """Return (response, from_cache).

    Concurrent callers with the same key share one in-flight run (single-flight).
    Only successful results are retained.
    """
    with _lock:
        cached = _success.get(key)
        if cached is not None:
            logger.info("Analyze cache hit key=%s", key)
            return cached.model_copy(deep=True), True

        existing = _inflight.get(key)
        if existing is not None:
            fut = existing
            is_leader = False
        else:
            fut = Future()
            _inflight[key] = fut
            is_leader = True

    if not is_leader:
        logger.info("Analyze single-flight wait key=%s", key)
        result = fut.result()
        return result.model_copy(deep=True), False

    logger.info("Analyze cache miss key=%s (running)", key)
    try:
        report = runner()
    except Exception as exc:
        with _lock:
            _inflight.pop(key, None)
        fut.set_exception(exc)
        raise

    with _lock:
        _success[key] = report
        _inflight.pop(key, None)
    fut.set_result(report)
    logger.info(
        "Analyze cached key=%s analysisRunId=%s",
        key,
        report.analysis_run_id,
    )
    return report.model_copy(deep=True), False


def clear_analyze_cache() -> None:
    """Test / ops helper: drop success entries (does not cancel in-flight)."""
    with _lock:
        _success.clear()
