"""Revision loop: v1 (internal) -> v2 (competitive) -> Critic -> v3 -> Critic ...

Each Critic round runs code rules, re-runs the Analyst's cited SQL, asks the
Critic model for its own checks and judgment, and lets code decide value
matches. The loop stops when a version has no findings or after
max_critic_rounds reviews; findings still open then become "unresolved".
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta, timezone

from .critic import (
    FindingIds,
    apply_critic_report,
    critic_payload,
    dedupe,
    recheck_cited_sql,
    resolve_previous,
    structural_findings,
)
from .prompts import (
    analyst_competitive_prompt,
    analyst_initial_prompt,
    analyst_revision_prompt,
    critic_prompt,
)
from .schema import AnalystOutput, CriticReport, CriticReview, EvidenceRun, RevisionStep, SqlCall
from .store import EvidenceStore, describe_tables

logger = logging.getLogger(__name__)

AnalystFn = Callable[[str], tuple[AnalystOutput, list[SqlCall]]]
CriticFn = Callable[[str], tuple[CriticReport, list[SqlCall]]]
DEFAULT_MAX_CRITIC_ROUNDS = 2


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def comparison_periods(
    store: EvidenceStore, *, daily_table: str = "asc_daily", lookback_days: int = 7
) -> tuple[tuple[str, str], tuple[str, str]]:
    """Latest N days with data vs the N days before, anchored on the newest daily row."""
    latest = store.query(f"SELECT MAX(date) FROM {daily_table}").scalar()
    if not latest:
        raise RuntimeError(f"{daily_table} has no rows; load evidence tables first")
    end = date.fromisoformat(str(latest)[:10])
    start = end - timedelta(days=lookback_days - 1)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=lookback_days - 1)
    return (start.isoformat(), end.isoformat()), (prev_start.isoformat(), prev_end.isoformat())


def run_evidence_loop(
    *,
    run_id: str,
    product_id: str,
    product_name: str,
    store: EvidenceStore,
    analyst: AnalystFn,
    critic: CriticFn,
    internal_tables: Iterable[str],
    external_tables: Iterable[str],
    language: str = "ja",
    max_critic_rounds: int = DEFAULT_MAX_CRITIC_ROUNDS,
    model: str = "",
    on_update: Callable[[EvidenceRun], None] | None = None,
) -> EvidenceRun:
    internal = list(internal_tables)
    external = list(external_tables)
    current, previous = comparison_periods(store)
    run = EvidenceRun(
        run_id=run_id,
        product_id=product_id,
        started_at=_now(),
        model=model,
        language="ja" if language == "ja" else "en",
        current_period=current,
        previous_period=previous,
        max_critic_rounds=max_critic_rounds,
    )
    all_schema = describe_tables(store, only=[*internal, *external])
    table_names = [t.name for t in store.tables()]

    def save() -> None:
        if on_update is not None:
            on_update(run)

    def analyst_step(version: str, stage: str, prompt: str) -> RevisionStep:
        logger.info("Analyst %s (%s) started", version, stage)
        started = time.monotonic()
        output, queries = analyst(prompt)
        step = RevisionStep(
            version=version,
            stage=stage,
            output=output,
            queries=queries,
            duration_seconds=round(time.monotonic() - started, 1),
        )
        run.steps.append(step)
        save()
        logger.info("Analyst %s done in %.1fs", version, step.duration_seconds)
        return step

    def review(step: RevisionStep, round_no: int) -> CriticReview:
        logger.info("Critic round %d on %s started", round_no, step.version)
        started = time.monotonic()
        ids = FindingIds(f"r{round_no}")
        code_log: list[SqlCall] = []
        findings = structural_findings(
            step.output, table_names=table_names, external_tables=external, ids=ids
        )
        findings += recheck_cited_sql(step.output, store=store, ids=ids, log=code_log)
        report, critic_log = critic(
            critic_prompt(
                payload=critic_payload(step.output),
                schema_text=all_schema,
                current=current,
                previous=previous,
                language=run.language,
            )
        )
        check_log: list[SqlCall] = []
        critic_findings, outcomes = apply_critic_report(
            report, step.output, store=store, ids=ids, log=check_log
        )
        result = CriticReview(
            summary=report.summary,
            findings=dedupe([*findings, *critic_findings]),
            checks=outcomes,
            queries=[*critic_log, *code_log, *check_log],
            duration_seconds=round(time.monotonic() - started, 1),
        )
        step.critic = result
        save()
        logger.info(
            "Critic round %d: %d findings, %d/%d checks matched, %.1fs",
            round_no,
            len(result.findings),
            sum(o.matched for o in outcomes),
            len(outcomes),
            result.duration_seconds,
        )
        return result

    try:
        v1 = analyst_step(
            "v1",
            "internal",
            analyst_initial_prompt(
                product_name=product_name,
                schema_text=describe_tables(store, only=internal),
                current=current,
                previous=previous,
                language=run.language,
            ),
        )
        step = analyst_step(
            "v2",
            "competitive",
            analyst_competitive_prompt(
                product_name=product_name,
                schema_text=all_schema,
                current=current,
                previous=previous,
                previous_version=v1.output,
                language=run.language,
            ),
        )
        previous_findings = None
        round_no = 1
        while True:
            result = review(step, round_no)
            if previous_findings is not None:
                resolve_previous(previous_findings, step.output, result.findings)
            if not result.findings:
                run.status = "converged"
                break
            if round_no >= max_critic_rounds:
                for finding in result.findings:
                    finding.resolution = "unresolved"
                run.status = "max_rounds"
                break
            step = analyst_step(
                f"v{len(run.steps) + 1}",
                "critic_revision",
                analyst_revision_prompt(
                    product_name=product_name,
                    schema_text=all_schema,
                    current=current,
                    previous=previous,
                    previous_version=step.output,
                    findings=result.findings,
                    language=run.language,
                ),
            )
            previous_findings = result.findings
            round_no += 1
    except Exception as exc:
        logger.exception("Evidence run %s failed", run_id)
        run.status = "error"
        run.error = f"{type(exc).__name__}: {exc}"
    run.finished_at = _now()
    save()
    return run
