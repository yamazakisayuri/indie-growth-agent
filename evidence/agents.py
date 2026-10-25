"""Analyst and Critic as Strands Agents. Each call starts a fresh conversation.

A fresh Agent per call keeps the Critic independent: it never shares context
with the Analyst, and sees only the prompt built from claims and actions.

A model request that fails for a reason a retry can fix (lost connection, timeout,
5xx, an error streamed mid-answer) is retried once with a fresh Agent; the failure
is logged with the provider's error details. Errors that are not about the
provider are raised unchanged. The openai client's own retries are off, so that
one retry is the only one: a silent SDK retry after a timeout would add a full
timeout each time, unlogged.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from pydantic import BaseModel
from strands import Agent

from llm import build_model, describe_model_error, find_api_error, is_retryable

from .prompts import ANALYST_SYSTEM, CRITIC_SYSTEM, STRUCTURED_OUTPUT_PROMPT
from .schema import AnalystOutput, CriticReport, SqlCall
from .sql_tool import make_sql_tool
from .store import EvidenceStore

DEFAULT_MAX_QUERIES = 8
MODEL_ATTEMPTS = 2
SDK_RETRIES = 0
logger = logging.getLogger(__name__)


class ModelCallError(RuntimeError):
    """A model request failed; the message carries the provider's error details."""


def _structured_call(
    role: str,
    make_agent: Callable[[list[SqlCall]], Agent],
    prompt: str,
    output_model: type[BaseModel],
) -> tuple[BaseModel | None, list[SqlCall]]:
    for attempt in range(1, MODEL_ATTEMPTS + 1):
        log: list[SqlCall] = []
        started = time.monotonic()
        try:
            result = make_agent(log)(
                prompt,
                structured_output_model=output_model,
                structured_output_prompt=STRUCTURED_OUTPUT_PROMPT,
            )
            return result.structured_output, log
        except Exception as exc:
            if find_api_error(exc) is None:
                raise
            seconds = time.monotonic() - started
            detail = describe_model_error(exc)
            if attempt < MODEL_ATTEMPTS and is_retryable(exc):
                logger.warning(
                    "%s model request failed after %.0fs (attempt %d, %d SQL calls); "
                    "retrying once: %s",
                    role, seconds, attempt, len(log), detail,
                )
                continue
            raise ModelCallError(
                f"{role} model request failed after {seconds:.0f}s "
                f"(attempt {attempt} of {MODEL_ATTEMPTS}): {detail}"
            ) from exc
    raise AssertionError("unreachable")


class StrandsAnalyst:
    def __init__(self, store: EvidenceStore, *, max_queries: int = DEFAULT_MAX_QUERIES) -> None:
        self._store = store
        self._max_queries = max_queries

    def __call__(self, prompt: str) -> tuple[AnalystOutput, list[SqlCall]]:
        def make_agent(log: list[SqlCall]) -> Agent:
            return Agent(
                model=build_model(sdk_retries=SDK_RETRIES),
                system_prompt=ANALYST_SYSTEM,
                tools=[
                    make_sql_tool(self._store, role="analyst", log=log, max_calls=self._max_queries)
                ],
                callback_handler=None,
            )

        output, log = _structured_call("Analyst", make_agent, prompt, AnalystOutput)
        if output is None:
            raise RuntimeError("Analyst returned no structured output")
        return output, log


class StrandsCritic:
    def __init__(self, store: EvidenceStore, *, max_queries: int = DEFAULT_MAX_QUERIES) -> None:
        self._store = store
        self._max_queries = max_queries

    def __call__(self, prompt: str) -> tuple[CriticReport, list[SqlCall]]:
        def make_agent(log: list[SqlCall]) -> Agent:
            return Agent(
                model=build_model(sdk_retries=SDK_RETRIES),
                system_prompt=CRITIC_SYSTEM,
                tools=[
                    make_sql_tool(self._store, role="critic", log=log, max_calls=self._max_queries)
                ],
                callback_handler=None,
            )

        output, log = _structured_call("Critic", make_agent, prompt, CriticReport)
        if output is None:
            raise RuntimeError("Critic returned no structured output")
        return output, log
