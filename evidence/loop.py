"""Revision loop: v1 (internal) -> v2 (competitive) -> Critic -> v3 -> Critic ...

Each Critic round runs code rules, re-runs the Analyst's cited SQL, asks the
Critic model for its own checks and judgment, and lets code decide value
matches. The loop stops when a version has no findings or after
max_critic_rounds reviews; findings still open then become "unresolved".

A v1 or v2 answer that states numeric facts without any successful SQL in that
answer is rejected before review and retried once; a second rejection stops
the run, so invented numbers never reach the Critic or the stored steps. A
revision that drops every action without a stated reason is handled the same way.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable, Iterable, Sequence
from datetime import date, datetime, timedelta, timezone

from .critic import (
    FindingIds,
    apply_critic_report,
    critic_payload,
    dedupe,
    is_composite,
    recheck_cited_sql,
    resolve_previous,
    structural_findings,
    to_number,
)
from .prompts import (
    analyst_competitive_prompt,
    analyst_initial_prompt,
    analyst_revision_prompt,
    critic_prompt,
    grounding_retry_text,
    past_decisions_text,
    revision_retry_text,
)
from .schema import (
    AnalystOutput,
    CriticReport,
    CriticReview,
    DecisionRecord,
    EvidenceRun,
    RejectedAttempt,
    RevisionStep,
    SqlCall,
)
from .store import EvidenceStore, describe_tables

logger = logging.getLogger(__name__)

AnalystFn = Callable[[str], tuple[AnalystOutput, list[SqlCall]]]
CriticFn = Callable[[str], tuple[CriticReport, list[SqlCall]]]
DEFAULT_MAX_CRITIC_ROUNDS = 2
# Stages whose numbers must come from the Analyst's own queries in that same answer.
GROUNDED_STAGES = ("internal", "competitive")
_DIGIT = re.compile(r"\d")


class AnalystGroundingError(RuntimeError):
    """The Analyst kept stating numeric facts without running any SQL."""


class AnalystRevisionError(RuntimeError):
    """A revision kept dropping every action without saying why."""


def unexplained_drop_reason(output: AnalystOutput, previous: AnalystOutput) -> str | None:
    """Why a revision must be rejected: all previous actions gone without a stated reason.

    Withdrawing actions is allowed when action_changes marks every previous action
    as removed with a non-empty reason.
    """
    if output.actions or not previous.actions:
        return None
    explained = {
        change.previous_rank
        for change in output.action_changes
        if change.decision == "removed" and change.reason.strip()
    }
    missing = [a.rank for a in previous.actions if a.rank not in explained]
    if not missing:
        return None
    ranks = ", ".join(str(rank) for rank in missing)
    return (
        "the revision has no actions, and action_changes gives no removal reason "
        f"for previous action(s) {ranks}."
    )


def ungrounded_reason(output: AnalystOutput, queries: Sequence[SqlCall]) -> str | None:
    """Why an answer must be rejected: numeric fact claims but no successful Analyst query."""
    if any(q.ok for q in queries if q.role == "analyst"):
        return None
    numeric_facts = [
        claim.id
        for claim in output.claims
        if claim.kind == "fact"
        and (
            any(to_number(e.value) is not None or is_composite(e.value) for e in claim.evidence)
            or _DIGIT.search(claim.text)
        )
    ]
    if not numeric_facts:
        return None
    return (
        f"fact claims {', '.join(numeric_facts)} state numbers, "
        "but no SQL query succeeded in this answer."
    )


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
    context_note: str = "",
    past_decisions: Sequence[DecisionRecord] | None = None,
    on_update: Callable[[EvidenceRun], None] | None = None,
) -> EvidenceRun:
    """Run the loop and return the stored run.

    context_note: identifiers the models need (e.g. our app_id), appended to the schema.
    past_decisions: earlier DecisionRecords for this product, shown to the Analyst as
    context only (not evidence). The Critic never receives them. Retrieval and storage
    are the caller's job.
    """
    decisions = list(past_decisions or ())
    decisions_text = past_decisions_text(decisions)
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
        past_decision_ids=[d.id for d in decisions],
    )

    def schema(only: list[str]) -> str:
        text = describe_tables(store, only=only)
        return f"{text}\n\nIdentifiers:\n{context_note}" if context_note else text

    all_schema = schema([*internal, *external])
    table_names = [t.name for t in store.tables()]

    def save() -> None:
        if on_update is not None:
            on_update(run)

    def analyst_step(
        version: str, stage: str, prompt: str, prior_output: AnalystOutput | None = None
    ) -> RevisionStep:
        base_prompt = f"{prompt}\n{decisions_text}\n" if decisions_text else prompt
        attempt_prompt = base_prompt
        if stage in GROUNDED_STAGES:

            def check(output: AnalystOutput, queries: list[SqlCall]) -> str | None:
                return ungrounded_reason(output, queries)

            retry_text = lambda reason: grounding_retry_text(reason, store.dialect)  # noqa: E731
            failure = AnalystGroundingError(
                f"Analyst {version} stated numeric facts without running SQL in 2 attempts; "
                "stopped without using those numbers."
            )
        elif prior_output is not None:

            def check(output: AnalystOutput, queries: list[SqlCall]) -> str | None:
                return unexplained_drop_reason(output, prior_output)

            retry_text = revision_retry_text
            failure = AnalystRevisionError(
                f"Analyst {version} dropped every action without a reason in 2 attempts; "
                "an empty final proposal is not accepted."
            )
        else:
            check = None
        max_attempts = 1 if check is None else 2
        for attempt in range(1, max_attempts + 1):
            logger.info("Analyst %s (%s) attempt %d started", version, stage, attempt)
            started = time.monotonic()
            output, queries = analyst(attempt_prompt)
            duration = round(time.monotonic() - started, 1)
            reason = None if check is None else check(output, queries)
            if reason is None:
                step = RevisionStep(
                    version=version,
                    stage=stage,
                    output=output,
                    queries=queries,
                    duration_seconds=duration,
                    attempts=attempt,
                )
                run.steps.append(step)
                save()
                logger.info("Analyst %s done in %.1fs", version, duration)
                return step
            run.rejected_attempts.append(
                RejectedAttempt(
                    version=version,
                    stage=stage,
                    attempt=attempt,
                    reason=reason,
                    output=output,
                    queries=queries,
                    duration_seconds=duration,
                )
            )
            save()
            logger.warning("Analyst %s attempt %d rejected: %s", version, attempt, reason)
            attempt_prompt = base_prompt + retry_text(reason)
        raise failure

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
                schema_text=schema(internal),
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
                prior_output=step.output,
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
