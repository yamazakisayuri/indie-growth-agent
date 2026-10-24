"""/api/evidence: list, read, and start evidence revision runs for the Web UI.

A run is the trace scripts/run_evidence.py writes to tmp/evidence_runs/<run_id>.json
after every step. Starting a run spawns that script, so the Web UI and the CLI
produce the same trace and the API process never holds the model loop.
At most one run started here is active at a time: every run spends model credits.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError

from evidence.schema import EvidenceRun

ROOT = Path(__file__).resolve().parent
RUNS_DIR = ROOT / "tmp" / "evidence_runs"
RUN_SCRIPT = ROOT / "scripts" / "run_evidence.py"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")
DEFAULT_LIST_LIMIT = 20
READ_ATTEMPTS = 3

logger = logging.getLogger("indie_growth_api.evidence")
router = APIRouter(prefix="/api/evidence")


class StartEvidenceRequest(BaseModel):
    language: Literal["ja", "en"] = Field(default="ja")
    product_id: str | None = Field(default=None, alias="productId")

    model_config = {"populate_by_name": True}


@dataclass
class Launch:
    run_id: str
    product_id: str
    language: Literal["ja", "en"]
    started_at: str
    process: subprocess.Popen

    @property
    def alive(self) -> bool:
        return self.process.poll() is None


_lock = threading.Lock()
_launches: dict[str, Launch] = {}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": message, "code": code})


def spawn_run(run_id: str, product_id: str, language: str) -> subprocess.Popen:
    """Start scripts/run_evidence.py; its log goes next to the trace."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = RUNS_DIR / f"{run_id}.log"
    with log_path.open("w", encoding="utf-8") as log:
        return subprocess.Popen(
            [
                sys.executable,
                str(RUN_SCRIPT),
                "--product-id",
                product_id,
                "--language",
                language,
                "--run-id",
                run_id,
            ],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def _active_launch() -> Launch | None:
    return next((launch for launch in _launches.values() if launch.alive), None)


def _read_run(path: Path) -> EvidenceRun | None:
    """Parse a trace file. The loop rewrites it after every step, so retry a partial read."""
    for attempt in range(READ_ATTEMPTS):
        try:
            return EvidenceRun.model_validate_json(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except ValidationError as exc:
            if attempt == READ_ATTEMPTS - 1:
                logger.warning("Evidence run %s unreadable: %s", path.name, str(exc)[:200])
                return None
            time.sleep(0.05)
    return None


def _with_launch_state(run: EvidenceRun | None, launch: Launch | None) -> EvidenceRun | None:
    """Fill in what the trace cannot say: not written yet, or its process died mid-run."""
    if launch is None:
        return run
    if run is None:
        run = EvidenceRun(
            run_id=launch.run_id,
            product_id=launch.product_id,
            started_at=launch.started_at,
            language=launch.language,
        )
        if not launch.alive:
            run.status = "error"
            run.error = (
                "The run stopped before its first step. "
                f"See tmp/evidence_runs/{launch.run_id}.log on the API host."
            )
        return run
    if run.status == "running" and not launch.alive:
        run.status = "error"
        run.error = run.error or "The run process exited before finishing."
    return run


def _summary(run: EvidenceRun) -> dict:
    last_review = next((s.critic for s in reversed(run.steps) if s.critic), None)
    return {
        "runId": run.run_id,
        "productId": run.product_id,
        "startedAt": run.started_at,
        "finishedAt": run.finished_at,
        "status": run.status,
        "model": run.model,
        "language": run.language,
        "versions": [step.version for step in run.steps],
        "topActions": [
            step.output.actions[0].title if step.output.actions else None for step in run.steps
        ],
        "unresolvedFindings": sum(
            f.resolution == "unresolved" for f in (last_review.findings if last_review else [])
        ),
        "error": run.error,
    }


def _check_run_id(run_id: str) -> None:
    if not RUN_ID_PATTERN.match(run_id):
        raise _error(400, "invalid_run_id", "Invalid run id")


@router.get("/runs")
def list_runs(
    product_id: str | None = Query(default=None, alias="productId"),
    limit: int = Query(default=DEFAULT_LIST_LIMIT, ge=1, le=100),
) -> dict:
    """Newest runs first, optionally for one product. activeRunId: the run started here, if any."""
    with _lock:
        launches = dict(_launches)
        active = _active_launch()
    runs: dict[str, EvidenceRun] = {}
    paths = sorted(RUNS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in paths:
        if not RUN_ID_PATTERN.match(path.stem):
            continue
        run = _with_launch_state(_read_run(path), launches.get(path.stem))
        if run is not None:
            runs[run.run_id] = run
    for run_id, launch in launches.items():
        if run_id not in runs:
            runs[run_id] = _with_launch_state(None, launch)  # type: ignore[assignment]
    selected = [r for r in runs.values() if not product_id or r.product_id == product_id]
    selected.sort(key=lambda r: r.started_at, reverse=True)
    return {
        "activeRunId": active.run_id if active else None,
        "runs": [_summary(r) for r in selected[:limit]],
    }


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    _check_run_id(run_id)
    path = RUNS_DIR / f"{run_id}.json"
    with _lock:
        launch = _launches.get(run_id)
    run = _with_launch_state(_read_run(path), launch)
    if run is None:
        if path.exists():
            raise _error(503, "run_unreadable", "The run trace is being written; try again")
        raise _error(404, "run_not_found", "Run not found")
    return run.model_dump(by_alias=True, mode="json")


@router.post("/runs", status_code=202)
def start_run(body: StartEvidenceRequest) -> dict:
    """Start v1 -> v2 -> Critic -> v3 for a product. Poll GET /runs/{runId} for progress."""
    from product_config import load_product_by_id

    try:
        product = load_product_by_id(body.product_id)
    except ValueError as exc:
        raise _error(400, "invalid_product", str(exc)[:200]) from None
    with _lock:
        active = _active_launch()
        if active is not None:
            raise _error(409, "run_in_progress", f"Run {active.run_id} is still running")
        run_id = f"{product.id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        if (RUNS_DIR / f"{run_id}.json").exists() or run_id in _launches:
            raise _error(409, "run_in_progress", f"Run {run_id} already exists")
        process = spawn_run(run_id, product.id, body.language)
        _launches[run_id] = Launch(
            run_id=run_id,
            product_id=product.id,
            language=body.language,
            started_at=_now(),
            process=process,
        )
    logger.info(
        "Evidence run started runId=%s product=%s language=%s pid=%s",
        run_id,
        product.id,
        body.language,
        process.pid,
    )
    return {"runId": run_id}
