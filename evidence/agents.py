"""Analyst and Critic as Strands Agents. Each call starts a fresh conversation.

A fresh Agent per call keeps the Critic independent: it never shares context
with the Analyst, and sees only the prompt built from claims and actions.
"""

from __future__ import annotations

from strands import Agent

from llm import build_model

from .prompts import ANALYST_SYSTEM, CRITIC_SYSTEM, STRUCTURED_OUTPUT_PROMPT
from .schema import AnalystOutput, CriticReport, SqlCall
from .sql_tool import make_sql_tool
from .store import EvidenceStore

DEFAULT_MAX_QUERIES = 8


class StrandsAnalyst:
    def __init__(self, store: EvidenceStore, *, max_queries: int = DEFAULT_MAX_QUERIES) -> None:
        self._store = store
        self._max_queries = max_queries

    def __call__(self, prompt: str) -> tuple[AnalystOutput, list[SqlCall]]:
        log: list[SqlCall] = []
        agent = Agent(
            model=build_model(),
            system_prompt=ANALYST_SYSTEM,
            tools=[make_sql_tool(self._store, role="analyst", log=log, max_calls=self._max_queries)],
            callback_handler=None,
        )
        result = agent(
            prompt,
            structured_output_model=AnalystOutput,
            structured_output_prompt=STRUCTURED_OUTPUT_PROMPT,
        )
        if result.structured_output is None:
            raise RuntimeError("Analyst returned no structured output")
        return result.structured_output, log


class StrandsCritic:
    def __init__(self, store: EvidenceStore, *, max_queries: int = DEFAULT_MAX_QUERIES) -> None:
        self._store = store
        self._max_queries = max_queries

    def __call__(self, prompt: str) -> tuple[CriticReport, list[SqlCall]]:
        log: list[SqlCall] = []
        agent = Agent(
            model=build_model(),
            system_prompt=CRITIC_SYSTEM,
            tools=[make_sql_tool(self._store, role="critic", log=log, max_calls=self._max_queries)],
            callback_handler=None,
        )
        result = agent(
            prompt,
            structured_output_model=CriticReport,
            structured_output_prompt=STRUCTURED_OUTPUT_PROMPT,
        )
        if result.structured_output is None:
            raise RuntimeError("Critic returned no structured output")
        return result.structured_output, log
