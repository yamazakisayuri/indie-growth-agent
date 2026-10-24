"""Sample mode: fictional evidence tables for the demo, with named scenarios.

Two ways to use them, kept apart:
- Live Sample: load the CSVs into a dedicated SQLite file and run the real Analyst and
  Critic (scripts/run_sample.py). Never touches EVIDENCE_STORE or real ASC data.
- Recorded Demo: traces of such runs, copied into samples/recorded/ only after checks
  (scripts/record_sample_demo.py), shown without any API key, network call, or model.

Every number, app, and listing in samples/ is made up. A scenario changes named cells
and states the old value, the new value, and why.

Expected layout of a sample directory (default samples/mahjong/):
- <table>.csv for asc_daily, asc_daily_by_source, known_events, competitor_listing, with
  the columns of evidence.sources in that order; an empty field is NULL. Every `source`
  cell is 'fictional_sample', and no app_id is a configured real product or competitor.
- scenarios.json: {"dataKind": "fictional_sample", "note": ..., "app": {"productId",
  "name", "appId"}, "scenarios": {<name>: {"description": ..., "overrides": [{"table",
  "match": {column: value}, "set": {column: value}, "reason"}]}}}
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from evidence.schema import EvidenceRun
from evidence.sources import ALL_TABLES
from evidence.sqlite_store import SQLiteEvidenceStore
from evidence.store import TableSpec

ROOT = Path(__file__).resolve().parent
SAMPLE_DIR = ROOT / "samples" / "mahjong"
RECORDED_DIR = ROOT / "samples" / "recorded"
RUNS_DIR = ROOT / "tmp" / "evidence_runs"
SAMPLE_STORE_DIR = ROOT / "tmp" / "sample"
MANIFEST_FILE = "scenarios.json"
DATA_KIND = "fictional_sample"
RUN_PREFIX = "sample-"
META_SUFFIX = ".sample.json"
RECORDABLE_STATUSES = ("converged", "max_rounds")
TABLES: dict[str, TableSpec] = {spec.name: spec for spec in ALL_TABLES}


class SampleError(ValueError):
    """The sample data, a scenario, or a trace to record is not valid."""


@dataclass(frozen=True)
class Override:
    table: str
    match: Mapping[str, Any]
    set: Mapping[str, Any]
    reason: str


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    overrides: tuple[Override, ...] = ()


@dataclass(frozen=True)
class AppliedChange:
    table: str
    match: Mapping[str, Any]
    column: str
    before: Any
    after: Any
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "match": dict(self.match),
            "column": self.column,
            "before": self.before,
            "after": self.after,
            "reason": self.reason,
        }


@dataclass
class SampleSet:
    manifest: dict[str, Any]
    tables: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    @property
    def app(self) -> dict[str, Any]:
        return self.manifest["app"]

    @property
    def scenario_names(self) -> list[str]:
        return list(self.manifest["scenarios"])


def _cast(value: str, column_type: str) -> Any:
    if value == "":
        return None
    if column_type == "integer":
        return int(value)
    if column_type == "real":
        return float(value)
    return value


def read_table_csv(spec: TableSpec, path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != spec.column_names:
            raise SampleError(f"{path.name}: columns must be {', '.join(spec.column_names)}")
        types = {c.name: c.type for c in spec.columns}
        return [{name: _cast(row[name], types[name]) for name in spec.column_names} for row in reader]


def real_app_ids() -> set[str]:
    """App Store ids of every configured product and competitor, which a sample must not use."""
    from product_config import load_product_by_id, load_product_index

    ids: set[str] = set()
    try:
        entries = load_product_index().products
    except (OSError, ValueError):
        return ids
    for entry in entries:
        try:
            product = load_product_by_id(entry.id)
        except (OSError, ValueError):
            continue
        ids.update(i for i in (product.app_store.app_id, *product.competitors.app_ids) if i)
    return ids


def check_fictional(tables: Mapping[str, list[dict[str, Any]]]) -> None:
    """Refuse data that is not marked fictional or that names a real configured app."""
    real = real_app_ids()
    for name, rows in tables.items():
        for line, row in enumerate(rows, start=2):
            if "source" in row and row["source"] != DATA_KIND:
                raise SampleError(f"{name}.csv:{line}: source must be {DATA_KIND!r}")
            if row.get("app_id") in real:
                raise SampleError(f"{name}.csv:{line}: app_id {row['app_id']} is a real app")


def load_sample_set(sample_dir: Path = SAMPLE_DIR) -> SampleSet:
    """Manifest and tables. CSV columns follow evidence.sources table specs, in order."""
    manifest_path = sample_dir / MANIFEST_FILE
    if not manifest_path.is_file():
        raise SampleError(f"No sample data: {manifest_path} not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("dataKind") != DATA_KIND:
        raise SampleError(f"{MANIFEST_FILE} must declare dataKind {DATA_KIND!r}")
    for key in ("note", "app", "scenarios"):
        if key not in manifest:
            raise SampleError(f"{MANIFEST_FILE} needs {key!r}")
    missing = [f"{name}.csv" for name in TABLES if not (sample_dir / f"{name}.csv").is_file()]
    if missing:
        raise SampleError(f"{sample_dir} is missing {', '.join(missing)}")
    tables = {name: read_table_csv(spec, sample_dir / f"{name}.csv") for name, spec in TABLES.items()}
    check_fictional(tables)
    return SampleSet(manifest=manifest, tables=tables)


def load_scenario(sample: SampleSet, name: str) -> Scenario:
    raw = sample.manifest["scenarios"].get(name)
    if raw is None:
        raise SampleError(f"Unknown scenario {name!r}; expected one of {sample.scenario_names}")
    overrides = []
    for item in raw.get("overrides", []):
        override = Override(
            table=item["table"], match=item["match"], set=item["set"], reason=item.get("reason", "")
        )
        if not override.reason.strip():
            raise SampleError(f"Scenario {name}: every override needs a reason")
        overrides.append(override)
    return Scenario(name=name, description=raw["description"], overrides=tuple(overrides))


def apply_scenario(
    tables: Mapping[str, list[dict[str, Any]]], scenario: Scenario
) -> tuple[dict[str, list[dict[str, Any]]], list[AppliedChange]]:
    """A changed copy of the tables, and one AppliedChange per changed cell."""
    result = deepcopy(dict(tables))
    changes: list[AppliedChange] = []
    for override in scenario.overrides:
        spec = TABLES.get(override.table)
        if spec is None:
            raise SampleError(f"Unknown table {override.table!r}")
        unknown = [c for c in (*override.match, *override.set) if c not in spec.column_names]
        if unknown:
            raise SampleError(f"{override.table} has no column {', '.join(unknown)}")
        rows = [r for r in result[override.table] if all(r[k] == v for k, v in override.match.items())]
        if not rows:
            raise SampleError(f"No {override.table} row matches {dict(override.match)}")
        for row in rows:
            for column, after in override.set.items():
                changes.append(
                    AppliedChange(
                        table=override.table,
                        match=override.match,
                        column=column,
                        before=row[column],
                        after=after,
                        reason=override.reason,
                    )
                )
                row[column] = after
    return result, changes


def _display_path(path: Path) -> str:
    path = path.resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def csv_digests(sample_dir: Path = SAMPLE_DIR) -> dict[str, str]:
    files = sorted([*(f"{name}.csv" for name in TABLES), MANIFEST_FILE])
    return {f: hashlib.sha256((sample_dir / f).read_bytes()).hexdigest() for f in files}


def context_note(sample: SampleSet) -> str:
    app_id = sample.app["appId"]
    return "\n".join(
        [
            f"- Our app_id = '{app_id}' (asc_* tables, competitor_listing)",
            f"- known_events.product = '{sample.app['productId']}'",
            "- competitor_listing.is_self = 1 is our app; 0 are competitors",
            f"- Every table holds fictional sample data (source = '{DATA_KIND}').",
        ]
    )


def sample_info(
    sample: SampleSet,
    scenario: Scenario,
    changes: list[AppliedChange],
    sample_dir: Path = SAMPLE_DIR,
) -> dict:
    return {
        "dataKind": DATA_KIND,
        "note": sample.manifest["note"],
        "app": dict(sample.app),
        "scenario": scenario.name,
        "scenarioDescription": scenario.description,
        "changes": [c.to_dict() for c in changes],
        "sampleDir": _display_path(sample_dir),
        "csvSha256": csv_digests(sample_dir),
    }


def build_sample_store(
    scenario_name: str, *, path: Path | None = None, sample_dir: Path = SAMPLE_DIR
) -> tuple[SQLiteEvidenceStore, SampleSet, dict]:
    """A fresh SQLite store holding the sample tables after the scenario's changes."""
    sample = load_sample_set(sample_dir)
    scenario = load_scenario(sample, scenario_name)
    tables, changes = apply_scenario(sample.tables, scenario)
    path = path or SAMPLE_STORE_DIR / f"{scenario_name}.sqlite"
    if str(path) != ":memory:":
        Path(path).unlink(missing_ok=True)
    store = SQLiteEvidenceStore(path)
    for name, rows in tables.items():
        store.replace_table(TABLES[name], rows)
    return store, sample, sample_info(sample, scenario, changes, sample_dir)


def meta_path(trace_path: Path) -> Path:
    return trace_path.with_name(trace_path.stem + META_SUFFIX)


def write_sample_meta(trace_path: Path, info: Mapping[str, Any]) -> None:
    meta_path(trace_path).write_text(json.dumps(info, ensure_ascii=False, indent=2), "utf-8")


def read_sample_meta(trace_path: Path) -> dict | None:
    path = meta_path(trace_path)
    if not path.is_file():
        return None
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return meta if isinstance(meta, dict) and meta.get("dataKind") == DATA_KIND else None


def recording_problems(trace_path: Path, *, sample_dir: Path = SAMPLE_DIR) -> list[str]:
    """Why this trace may not become a Recorded Demo. Empty when it may."""
    problems = []
    if not trace_path.stem.startswith(RUN_PREFIX):
        problems.append(f"run id must start with {RUN_PREFIX!r} (a Live Sample run)")
    meta = read_sample_meta(trace_path)
    if meta is None:
        problems.append("no sample metadata next to the trace; it was not a Live Sample run")
    elif not (sample_dir / MANIFEST_FILE).is_file():
        problems.append(f"no committed sample data in {_display_path(sample_dir)}")
    elif meta.get("sampleDir") != _display_path(sample_dir):
        problems.append(f"the run used {meta.get('sampleDir')}, not {_display_path(sample_dir)}")
    elif meta.get("csvSha256") != csv_digests(sample_dir):
        problems.append("the sample CSVs changed since this run; run the Live Sample again")
    try:
        run = EvidenceRun.model_validate_json(trace_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [*problems, f"trace unreadable: {exc}"]
    if run.run_id != trace_path.stem:
        problems.append("run id in the trace does not match the file name")
    if run.status not in RECORDABLE_STATUSES:
        problems.append(f"status is {run.status}; only {', '.join(RECORDABLE_STATUSES)} runs")
    if not run.finished_at:
        problems.append("the run did not finish")
    if not run.model.strip():
        problems.append("no model recorded; only traces from a real model run")
    if not any(step.critic for step in run.steps):
        problems.append("no Critic review in the trace")
    if meta is not None and run.product_id != meta.get("app", {}).get("productId"):
        problems.append("product id differs from the sample app")
    return problems


def record_demo(
    trace_path: Path, *, recorded_dir: Path = RECORDED_DIR, sample_dir: Path = SAMPLE_DIR
) -> Path:
    problems = recording_problems(trace_path, sample_dir=sample_dir)
    if problems:
        raise SampleError("; ".join(problems))
    recorded_dir.mkdir(parents=True, exist_ok=True)
    target = recorded_dir / trace_path.name
    target.write_bytes(trace_path.read_bytes())
    meta = read_sample_meta(trace_path) or {}
    meta["recordedAt"] = datetime.now().astimezone().isoformat(timespec="seconds")
    write_sample_meta(target, meta)
    return target
