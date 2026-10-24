"""Lifecycle operations shared by the CLI and tests: adopt, add, implement, evaluate."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from evidence.schema import DecisionRecord, EvidenceRun
from evidence.store import EvidenceStore

from .ledger import InterventionError, InterventionLedger
from .measure import after_window, before_window, measure_window
from .schema import AiPrediction, HumanEvaluation, Intervention, Measurement, Verdict


def _plus_days(day: str, days: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=days)).isoformat()


def load_run(path: str | Path) -> EvidenceRun:
    return EvidenceRun.model_validate_json(Path(path).read_text(encoding="utf-8"))


def prediction_from_run(run: EvidenceRun, *, rank: int, version: str | None = None) -> AiPrediction:
    """Copy one proposed action and the claims it cites, as the AI wrote them."""
    steps = [s for s in run.steps if version is None or s.version == version]
    if not steps:
        raise InterventionError(
            f"Run {run.run_id} has no {'steps' if version is None else version}",
            code="not_found",
        )
    step = steps[-1]
    action = next((a for a in step.output.actions if a.rank == rank), None)
    if action is None:
        raise InterventionError(
            f"Run {run.run_id} {step.version} has no action ranked {rank}", code="not_found"
        )
    by_id = {c.id: c for c in step.output.claims}
    claims = [by_id[cid] for cid in action.claim_ids if cid in by_id]
    test_plan = next((c.test_plan for c in claims if c.test_plan is not None), None)
    return AiPrediction(
        run_id=run.run_id,
        version=step.version,
        model=run.model,
        action_rank=rank,
        action_title=action.title,
        action_reason=action.reason,
        claims=claims,
        test_plan=test_plan,
    )


def adopt(
    ledger: InterventionLedger,
    prediction: AiPrediction,
    *,
    product_id: str,
    title: str | None = None,
    change_description: str = "",
    target_metric: str | None = None,
    method: str | None = None,
    success_criterion: str | None = None,
    duration_days: int | None = None,
    window_days: int | None = None,
) -> tuple[Intervention, bool]:
    """Adopt an AI action. Missing plan fields fall back to the AI's test plan."""
    plan = prediction.test_plan
    target_metric = target_metric or (plan.metric if plan else None)
    method = method or (plan.method if plan else None)
    success_criterion = success_criterion or (plan.success_criterion if plan else None)
    duration_days = duration_days or (plan.duration_days if plan else None)
    missing = [
        name
        for name, value in (
            ("metric", target_metric),
            ("method", method),
            ("criterion", success_criterion),
            ("days", duration_days),
        )
        if not value
    ]
    if missing:
        raise InterventionError(
            "The adopted action has no test plan for: " + ", ".join(missing)
            + ". Pass them explicitly.",
            code="missing_plan",
        )
    return _create(
        ledger,
        product_id=product_id,
        origin="ai_adopted",
        prediction=prediction,
        title=title or prediction.action_title,
        change_description=change_description,
        target_metric=target_metric,
        method=method,
        success_criterion=success_criterion,
        duration_days=duration_days,
        window_days=window_days,
    )


def add_manual(
    ledger: InterventionLedger,
    *,
    product_id: str,
    title: str,
    target_metric: str,
    method: str,
    success_criterion: str,
    duration_days: int,
    change_description: str = "",
    window_days: int | None = None,
) -> tuple[Intervention, bool]:
    return _create(
        ledger,
        product_id=product_id,
        origin="manual",
        prediction=None,
        title=title,
        change_description=change_description,
        target_metric=target_metric,
        method=method,
        success_criterion=success_criterion,
        duration_days=duration_days,
        window_days=window_days,
    )


def _create(
    ledger: InterventionLedger,
    *,
    product_id: str,
    origin: str,
    prediction: AiPrediction | None,
    title: str,
    change_description: str,
    target_metric: str,
    method: str,
    success_criterion: str,
    duration_days: int,
    window_days: int | None,
) -> tuple[Intervention, bool]:
    intervention_id = ledger.new_id()
    now = ledger.now_iso()
    candidate = Intervention(
        id=intervention_id,
        target_metric=target_metric,
        duration_days=duration_days,
        window_days=window_days or duration_days,
        decision=DecisionRecord(
            id=intervention_id,
            product_id=product_id,
            origin=origin,
            run_id=prediction.run_id if prediction else None,
            action_title=title,
            change_description=change_description,
            method=method,
            success_criterion=success_criterion,
            evaluation_date=_plus_days(ledger.today(), duration_days),
            created_at=now,
        ),
        prediction=prediction,
        updated_at=now,
    )
    return ledger.create(candidate)


def _measure(
    store: EvidenceStore | None, app_id: str | None, window: tuple[str, str], measured_at: str
) -> Measurement | None:
    if store is None:
        return None
    if not app_id:
        return Measurement(
            measured_at=measured_at,
            store=getattr(store, "dialect", ""),
            period_start=window[0],
            period_end=window[1],
            skipped=["all metrics: the product has no App Store app_id"],
        )
    return measure_window(
        store, app_id=app_id, start=window[0], end=window[1], measured_at=measured_at
    )


def implement(
    ledger: InterventionLedger,
    intervention_id: str,
    *,
    implemented_on: str,
    store: EvidenceStore | None,
    app_id: str | None,
    evaluation_date: str | None = None,
) -> tuple[Intervention, bool]:
    """Record the change date and measure the window before it."""
    item = ledger.get(intervention_id)
    if item.status != "planned":
        return ledger.implement(
            intervention_id,
            implemented_on=implemented_on,
            evaluation_date=item.decision.evaluation_date,
            baseline=None,
        )
    evaluation_date = evaluation_date or _plus_days(implemented_on, item.duration_days)
    window_end = after_window(implemented_on, item.window_days)[1]
    if evaluation_date < window_end:
        raise InterventionError(
            f"The {item.window_days}-day after window ends on {window_end}, after the "
            f"evaluation date {evaluation_date}; pick a later date or a shorter --window-days",
            code="invalid_dates",
        )
    baseline = _measure(
        store, app_id, before_window(implemented_on, item.window_days), ledger.now_iso()
    )
    return ledger.implement(
        intervention_id,
        implemented_on=implemented_on,
        evaluation_date=evaluation_date,
        baseline=baseline,
    )


def evaluate(
    ledger: InterventionLedger,
    intervention_id: str,
    *,
    verdict: Verdict,
    note: str,
    evaluated_on: str,
    store: EvidenceStore | None,
    app_id: str | None,
    early: bool = False,
) -> tuple[Intervention, bool]:
    """Record the person's verdict and measure the window after the change."""
    item = ledger.get(intervention_id)
    evaluation = HumanEvaluation(evaluated_on=evaluated_on, verdict=verdict, note=note)
    if item.status != "implemented":
        return ledger.evaluate(intervention_id, evaluation=evaluation, after=None)
    if evaluated_on < item.decision.evaluation_date and not early:
        raise InterventionError(
            f"{intervention_id} is due for evaluation on {item.decision.evaluation_date}; "
            "use --early to judge it sooner",
            code="not_due",
        )
    after = _measure(
        store,
        app_id,
        after_window(item.implemented_on or evaluated_on, item.window_days),
        ledger.now_iso(),
    )
    return ledger.evaluate(intervention_id, evaluation=evaluation, after=after)


def remeasure(
    ledger: InterventionLedger,
    intervention_id: str,
    *,
    store: EvidenceStore,
    app_id: str | None,
) -> tuple[Intervention, bool]:
    """Measure the same windows again, e.g. after the store was down or ASC data arrived late."""
    item = ledger.get(intervention_id)
    if item.implemented_on is None:
        raise InterventionError(f"{intervention_id} is {item.status}; nothing to measure")
    now = ledger.now_iso()
    baseline = _measure(store, app_id, before_window(item.implemented_on, item.window_days), now)
    after = (
        _measure(store, app_id, after_window(item.implemented_on, item.window_days), now)
        if item.status == "evaluated"
        else None
    )
    return ledger.remeasure(intervention_id, baseline=baseline, after=after)
