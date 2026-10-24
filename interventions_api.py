"""/api/interventions: adopt an AI action or add one by hand, then implement and evaluate.

Same lifecycle and ledger as scripts/interventions.py. The ledger is re-read on every
request so changes made from the CLI show up, and writes are serialized here.
Measuring or syncing memory never blocks a change; problems come back as warnings.
"""

from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

import evidence_api
from evidence.schema import ISO_DATE
from evidence.store import EvidenceStore
from interventions import (
    Intervention,
    InterventionError,
    InterventionLedger,
    InterventionStatus,
    Verdict,
    add_manual,
    adopt,
    evaluate,
    get_interventions_path,
    implement,
    load_run,
    prediction_from_run,
    remeasure,
)
from interventions.runtime import open_store, product_app_id, sync_memory_safely

logger = logging.getLogger("indie_growth_api.interventions")
router = APIRouter(prefix="/api/interventions")
_lock = threading.Lock()

_STATUS_BY_CODE = {
    "not_found": 404,
    "missing_plan": 400,
    "invalid_dates": 400,
    "not_due": 409,
    "invalid_transition": 409,
    "corrupt_ledger": 500,
}


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class AdoptRequest(ApiModel):
    run_id: str
    rank: int = Field(ge=1, le=3)
    version: str | None = Field(default=None, pattern=r"^v\d+$")
    title: str | None = None
    change_description: str = ""
    target_metric: str | None = None
    method: str | None = None
    success_criterion: str | None = None
    duration_days: int | None = Field(default=None, ge=1, le=365)
    window_days: int | None = Field(default=None, ge=1, le=365)


class ManualRequest(ApiModel):
    product_id: str
    title: str = Field(min_length=1)
    change_description: str = ""
    target_metric: str = Field(min_length=1)
    method: str = Field(min_length=1)
    success_criterion: str = Field(min_length=1)
    duration_days: int = Field(ge=1, le=365)
    window_days: int | None = Field(default=None, ge=1, le=365)


class ImplementRequest(ApiModel):
    implemented_on: str = Field(pattern=ISO_DATE)
    evaluation_date: str | None = Field(default=None, pattern=ISO_DATE)
    measure: bool = True


class EvaluateRequest(ApiModel):
    verdict: Verdict
    note: str = ""
    evaluated_on: str = Field(pattern=ISO_DATE)
    early: bool = False
    measure: bool = True


class DropRequest(ApiModel):
    reason: str = Field(min_length=1)


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": message, "code": code})


def _from_intervention_error(exc: InterventionError) -> HTTPException:
    return _error(_STATUS_BY_CODE.get(exc.code, 409), exc.code, str(exc)[:300])


def _ledger() -> InterventionLedger:
    try:
        return InterventionLedger(get_interventions_path())
    except InterventionError as exc:
        logger.error("Intervention ledger unreadable: %s", exc)
        raise _from_intervention_error(exc) from None


def _app_id(product_id: str) -> str | None:
    try:
        return product_app_id(product_id)
    except (ValueError, FileNotFoundError):
        return None


def _payload(item: Intervention, *, changed: bool, warnings: list[str]) -> dict:
    return {
        "intervention": item.model_dump(by_alias=True, mode="json"),
        "changed": changed,
        "warnings": warnings,
    }


def _finish(
    ledger: InterventionLedger, item: Intervention, changed: bool, warnings: list[str]
) -> dict:
    item, warning = sync_memory_safely(ledger, item)
    if warning:
        warnings.append(warning)
    for message in warnings:
        logger.warning("Intervention %s: %s", item.id, message)
    return _payload(item, changed=changed, warnings=warnings)


def _store_for(needed: bool, warnings: list[str]) -> EvidenceStore | None:
    if not needed:
        return None
    store, warning = open_store()
    if warning:
        warnings.append(warning)
    return store


@router.get("")
def list_interventions(
    product_id: str | None = Query(default=None, alias="productId"),
    status: InterventionStatus | None = Query(default=None),
) -> dict:
    """Newest first, optionally for one product and status."""
    items = _ledger().list_interventions(product_id=product_id, status=status)
    items.sort(key=lambda i: i.decision.created_at, reverse=True)
    return {"interventions": [i.model_dump(by_alias=True, mode="json") for i in items]}


@router.get("/{intervention_id}")
def get_intervention(intervention_id: str) -> dict:
    try:
        item = _ledger().get(intervention_id)
    except InterventionError as exc:
        raise _from_intervention_error(exc) from None
    return item.model_dump(by_alias=True, mode="json")


@router.post("/adopt")
def adopt_action(body: AdoptRequest) -> dict:
    """Adopt one proposed action from a finished evidence run."""
    if not evidence_api.RUN_ID_PATTERN.match(body.run_id):
        raise _error(400, "invalid_run_id", "Invalid run id")
    path = evidence_api.RUNS_DIR / f"{body.run_id}.json"
    if not path.is_file():
        raise _error(404, "run_not_found", "Run not found")
    try:
        run = load_run(path)
    except (ValidationError, ValueError):
        raise _error(503, "run_unreadable", "The run trace is being written; try again") from None
    if run.status == "running":
        raise _error(409, "run_in_progress", "Wait for the run to finish before adopting")
    with _lock:
        ledger = _ledger()
        try:
            prediction = prediction_from_run(run, rank=body.rank, version=body.version)
            item, created = adopt(
                ledger,
                prediction,
                product_id=run.product_id,
                title=body.title,
                change_description=body.change_description,
                target_metric=body.target_metric,
                method=body.method,
                success_criterion=body.success_criterion,
                duration_days=body.duration_days,
                window_days=body.window_days,
            )
        except InterventionError as exc:
            raise _from_intervention_error(exc) from None
        logger.info(
            "Intervention adopted id=%s run=%s rank=%s created=%s",
            item.id, body.run_id, body.rank, created,
        )
        return _finish(ledger, item, created, [])


@router.post("")
def add_intervention(body: ManualRequest) -> dict:
    """Register an intervention a person came up with."""
    from product_config import load_product_by_id

    try:
        product = load_product_by_id(body.product_id)
    except (ValueError, FileNotFoundError) as exc:
        raise _error(400, "invalid_product", str(exc)[:200]) from None
    with _lock:
        ledger = _ledger()
        item, created = add_manual(
            ledger,
            product_id=product.id,
            title=body.title.strip(),
            change_description=body.change_description,
            target_metric=body.target_metric,
            method=body.method,
            success_criterion=body.success_criterion,
            duration_days=body.duration_days,
            window_days=body.window_days,
        )
        logger.info("Intervention added id=%s created=%s", item.id, created)
        return _finish(ledger, item, created, [])


@router.post("/{intervention_id}/implement")
def implement_intervention(intervention_id: str, body: ImplementRequest) -> dict:
    with _lock:
        ledger = _ledger()
        warnings: list[str] = []
        store = None
        try:
            item = ledger.get(intervention_id)
            store = _store_for(body.measure and item.status == "planned", warnings)
            item, changed = implement(
                ledger,
                intervention_id,
                implemented_on=body.implemented_on,
                evaluation_date=body.evaluation_date,
                store=store,
                app_id=_app_id(item.product_id),
            )
        except InterventionError as exc:
            raise _from_intervention_error(exc) from None
        finally:
            if store is not None:
                store.close()
        return _finish(ledger, item, changed, warnings)


@router.post("/{intervention_id}/evaluate")
def evaluate_intervention(intervention_id: str, body: EvaluateRequest) -> dict:
    with _lock:
        ledger = _ledger()
        warnings: list[str] = []
        store = None
        try:
            item = ledger.get(intervention_id)
            due = body.early or body.evaluated_on >= item.decision.evaluation_date
            store = _store_for(body.measure and item.status == "implemented" and due, warnings)
            item, changed = evaluate(
                ledger,
                intervention_id,
                verdict=body.verdict,
                note=body.note,
                evaluated_on=body.evaluated_on,
                store=store,
                app_id=_app_id(item.product_id),
                early=body.early,
            )
        except InterventionError as exc:
            raise _from_intervention_error(exc) from None
        finally:
            if store is not None:
                store.close()
        return _finish(ledger, item, changed, warnings)


@router.post("/{intervention_id}/measure")
def measure_intervention(intervention_id: str) -> dict:
    """Measure before / after again, e.g. once late App Store Connect data has arrived."""
    with _lock:
        ledger = _ledger()
        try:
            item = ledger.get(intervention_id)
        except InterventionError as exc:
            raise _from_intervention_error(exc) from None
        store, warning = open_store()
        if store is None:
            raise _error(503, "store_unavailable", warning or "Evidence store unavailable")
        try:
            item, changed = remeasure(
                ledger, intervention_id, store=store, app_id=_app_id(item.product_id)
            )
        except InterventionError as exc:
            raise _from_intervention_error(exc) from None
        finally:
            store.close()
        return _payload(item, changed=changed, warnings=[])


@router.post("/{intervention_id}/drop")
def drop_intervention(intervention_id: str, body: DropRequest) -> dict:
    with _lock:
        ledger = _ledger()
        try:
            item, changed = ledger.drop(intervention_id, reason=body.reason)
        except InterventionError as exc:
            raise _from_intervention_error(exc) from None
        return _payload(item, changed=changed, warnings=[])
