"""Append-only JSONL ledger of interventions, independent of MEMORY_BACKEND.

Every change is one event line; the current state is rebuilt by replaying the file,
so nothing is rewritten. Repeating a status change that already happened writes
nothing, and adopting the same AI action twice returns the existing intervention.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from config import _resolve_path, load_env

from .schema import HumanEvaluation, Intervention, InterventionStatus, Measurement

DEFAULT_INTERVENTIONS_PATH = "tmp/interventions/ledger.jsonl"


class InterventionError(RuntimeError):
    """The requested lifecycle change is not allowed."""


def get_interventions_path() -> Path:
    """Ledger file (INTERVENTIONS_PATH, relative to the repo)."""
    load_env()
    raw = os.getenv("INTERVENTIONS_PATH", "").strip() or DEFAULT_INTERVENTIONS_PATH
    return _resolve_path(raw)


def _local_now() -> datetime:
    return datetime.now().astimezone()


def _normalize_title(title: str) -> str:
    return " ".join(title.split()).casefold()


class InterventionLedger:
    def __init__(
        self, path: str | Path, *, clock: Callable[[], datetime] | None = None
    ) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock or _local_now
        self._lock = threading.RLock()
        self._items: dict[str, Intervention] = {}
        self._replay()

    @property
    def path(self) -> Path:
        return self._path

    def _replay(self) -> None:
        if not self._path.is_file():
            return
        for line_no, line in enumerate(self._path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                self._apply(event)
            except (ValueError, KeyError, TypeError) as exc:
                raise InterventionError(
                    f"{self._path}:{line_no} is not an intervention event: {exc}"
                ) from exc

    def _apply(self, event: dict[str, Any]) -> None:
        action = event["action"]
        data = event["data"]
        if action == "create":
            item = Intervention.model_validate(data)
            self._items[item.id] = item
            return
        item = self._items[event["interventionId"]]
        update: dict[str, Any] = {"updated_at": event["timestamp"]}
        if action == "implement":
            update["status"] = "implemented"
            update["implemented_on"] = data["implementedOn"]
            update["baseline"] = (
                Measurement.model_validate(data["baseline"]) if data.get("baseline") else None
            )
            baseline = update["baseline"].metrics if update["baseline"] else []
            update["decision"] = item.decision.model_copy(
                update={"evaluation_date": data["evaluationDate"], "baseline": baseline}
            )
        elif action == "evaluate":
            update["status"] = "evaluated"
            update["evaluation"] = HumanEvaluation.model_validate(data["evaluation"])
            update["after"] = (
                Measurement.model_validate(data["after"]) if data.get("after") else None
            )
        elif action == "measure":
            if data.get("baseline"):
                update["baseline"] = Measurement.model_validate(data["baseline"])
                update["decision"] = item.decision.model_copy(
                    update={"baseline": update["baseline"].metrics}
                )
            if data.get("after"):
                update["after"] = Measurement.model_validate(data["after"])
        elif action == "drop":
            update["status"] = "dropped"
            update["drop_reason"] = data.get("reason", "")
        elif action == "remember":
            update["memory_ids"] = {**item.memory_ids, data["key"]: data["memoryId"]}
        else:
            raise ValueError(f"unknown action {action!r}")
        self._items[item.id] = Intervention.model_validate(
            {**item.model_dump(), **update}
        )

    def _append(self, intervention_id: str, action: str, data: dict[str, Any]) -> Intervention:
        event = {
            "id": f"ive_{uuid.uuid4().hex[:12]}",
            "interventionId": intervention_id,
            "action": action,
            "timestamp": self.now_iso(),
            "data": data,
        }
        self._apply(event)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        return self._items[intervention_id]

    def now_iso(self) -> str:
        return self._clock().isoformat(timespec="seconds")

    def today(self) -> str:
        return self._clock().date().isoformat()

    @staticmethod
    def new_id() -> str:
        return f"iv_{uuid.uuid4().hex[:10]}"

    def get(self, intervention_id: str) -> Intervention:
        with self._lock:
            item = self._items.get(intervention_id)
        if item is None:
            raise InterventionError(f"Unknown intervention {intervention_id}")
        return item

    def list_interventions(
        self, *, product_id: str | None = None, status: InterventionStatus | None = None
    ) -> list[Intervention]:
        with self._lock:
            items = list(self._items.values())
        return [
            item
            for item in sorted(items, key=lambda i: i.decision.created_at)
            if (product_id is None or item.product_id == product_id)
            and (status is None or item.status == status)
        ]

    def find_duplicate(self, candidate: Intervention) -> Intervention | None:
        """An active intervention for the same AI action, or with the same manual title."""
        for item in self.list_interventions(product_id=candidate.product_id):
            if item.status == "dropped":
                continue
            if candidate.prediction is not None and item.prediction is not None:
                if (item.prediction.run_id, item.prediction.action_rank) == (
                    candidate.prediction.run_id,
                    candidate.prediction.action_rank,
                ):
                    return item
            elif candidate.prediction is None and item.prediction is None:
                if _normalize_title(item.title) == _normalize_title(candidate.title):
                    return item
        return None

    def create(self, candidate: Intervention) -> tuple[Intervention, bool]:
        """Store a new intervention. Returns (stored, created); created is False for a duplicate."""
        with self._lock:
            existing = self.find_duplicate(candidate)
            if existing is not None:
                return existing, False
            if candidate.id in self._items:
                raise InterventionError(f"Intervention {candidate.id} already exists")
            if candidate.status != "planned":
                raise InterventionError("A new intervention starts as planned")
            stored = self._append(candidate.id, "create", candidate.model_dump(by_alias=True))
        return stored, True

    def implement(
        self,
        intervention_id: str,
        *,
        implemented_on: str,
        evaluation_date: str,
        baseline: Measurement | None,
    ) -> tuple[Intervention, bool]:
        with self._lock:
            item = self._items.get(intervention_id)
            if item is None:
                raise InterventionError(f"Unknown intervention {intervention_id}")
            if item.status in ("implemented", "evaluated") and item.implemented_on == implemented_on:
                return item, False
            if item.status != "planned":
                raise InterventionError(
                    f"{intervention_id} is {item.status}"
                    + (f" (implemented on {item.implemented_on})" if item.implemented_on else "")
                    + "; only a planned intervention can be implemented"
                )
            stored = self._append(
                intervention_id,
                "implement",
                {
                    "implementedOn": implemented_on,
                    "evaluationDate": evaluation_date,
                    "baseline": baseline.model_dump(by_alias=True) if baseline else None,
                },
            )
        return stored, True

    def evaluate(
        self,
        intervention_id: str,
        *,
        evaluation: HumanEvaluation,
        after: Measurement | None,
    ) -> tuple[Intervention, bool]:
        with self._lock:
            item = self._items.get(intervention_id)
            if item is None:
                raise InterventionError(f"Unknown intervention {intervention_id}")
            if item.status == "evaluated" and item.evaluation is not None:
                if (item.evaluation.verdict, item.evaluation.note) == (
                    evaluation.verdict,
                    evaluation.note,
                ):
                    return item, False
                raise InterventionError(
                    f"{intervention_id} was already evaluated as {item.evaluation.verdict}"
                    f" on {item.evaluation.evaluated_on}"
                )
            if item.status != "implemented":
                raise InterventionError(
                    f"{intervention_id} is {item.status}; only an implemented intervention "
                    "can be evaluated"
                )
            stored = self._append(
                intervention_id,
                "evaluate",
                {
                    "evaluation": evaluation.model_dump(by_alias=True),
                    "after": after.model_dump(by_alias=True) if after else None,
                },
            )
        return stored, True

    def remeasure(
        self,
        intervention_id: str,
        *,
        baseline: Measurement | None,
        after: Measurement | None,
    ) -> tuple[Intervention, bool]:
        """Replace measurements whose numbers or skip reasons changed (e.g. late ASC data)."""

        def differs(new: Measurement | None, old: Measurement | None) -> bool:
            if new is None:
                return False
            return old is None or (new.metrics, new.skipped) != (old.metrics, old.skipped)

        with self._lock:
            item = self._items.get(intervention_id)
            if item is None:
                raise InterventionError(f"Unknown intervention {intervention_id}")
            if item.status not in ("implemented", "evaluated"):
                raise InterventionError(f"{intervention_id} is {item.status}; nothing to measure")
            if after is not None and item.status != "evaluated":
                raise InterventionError(f"{intervention_id} is not evaluated yet")
            data = {
                "baseline": baseline.model_dump(by_alias=True)
                if differs(baseline, item.baseline) else None,
                "after": after.model_dump(by_alias=True)
                if differs(after, item.after) else None,
            }
            if not data["baseline"] and not data["after"]:
                return item, False
            stored = self._append(intervention_id, "measure", data)
        return stored, True

    def drop(self, intervention_id: str, *, reason: str) -> tuple[Intervention, bool]:
        with self._lock:
            item = self._items.get(intervention_id)
            if item is None:
                raise InterventionError(f"Unknown intervention {intervention_id}")
            if item.status == "dropped":
                return item, False
            if item.status == "evaluated":
                raise InterventionError(f"{intervention_id} is already evaluated")
            stored = self._append(intervention_id, "drop", {"reason": reason})
        return stored, True

    def link_memory(self, intervention_id: str, *, key: str, memory_id: str) -> Intervention:
        with self._lock:
            item = self._items.get(intervention_id)
            if item is None:
                raise InterventionError(f"Unknown intervention {intervention_id}")
            if item.memory_ids.get(key) == memory_id:
                return item
            return self._append(
                intervention_id, "remember", {"key": key, "memoryId": memory_id}
            )
