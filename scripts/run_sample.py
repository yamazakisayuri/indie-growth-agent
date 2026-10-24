"""Live Sample: run the real Analyst and Critic on fictional sample data.

Run:
  python scripts/run_sample.py --scenario base
  python scripts/run_sample.py --scenario competitor-variant
  python scripts/run_sample.py --scenario competitor-variant --dry-run   # load only, no model

The tables come from samples/mahjong/ (plus the scenario's stated changes) and go into a
dedicated SQLite file, tmp/sample/<scenario>.sqlite; EVIDENCE_STORE is ignored. No past
decisions are recalled, so nothing from real data reaches the models. The model is
LLM_PROVIDER. The trace is tmp/evidence_runs/sample-<scenario>-<timestamp>.json, with the
scenario and its changes in a .sample.json file next to it.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import get_llm_provider, get_openai_compatible_settings  # noqa: E402
from evidence.agents import DEFAULT_MAX_QUERIES, StrandsAnalyst, StrandsCritic  # noqa: E402
from evidence.loop import DEFAULT_MAX_CRITIC_ROUNDS, comparison_periods, run_evidence_loop  # noqa: E402
from evidence.schema import EvidenceRun  # noqa: E402
from evidence.sources import EXTERNAL_TABLE_NAMES, INTERNAL_TABLE_NAMES  # noqa: E402
from sample_mode import (  # noqa: E402
    RUN_PREFIX,
    RUNS_DIR,
    SAMPLE_DIR,
    SampleError,
    build_sample_store,
    context_note,
    write_sample_meta,
)


def _model_label() -> str:
    provider = get_llm_provider()
    if provider == "openai_compatible":
        return f"openai_compatible:{get_openai_compatible_settings().model_id}"
    return provider


def _print_changes(info: dict) -> None:
    print(f"scenario {info['scenario']}: {info['scenarioDescription']}")
    if not info["changes"]:
        print("  (no changes: the base sample)")
    for change in info["changes"]:
        match = ", ".join(f"{k}={v}" for k, v in change["match"].items())
        print(
            f"  {change['table']} [{match}] {change['column']}: "
            f"{change['before']} -> {change['after']}  ({change['reason']})"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scenario", default="base", help="A scenario in scenarios.json")
    parser.add_argument(
        "--sample-dir", type=Path, default=SAMPLE_DIR,
        help="Sample CSVs and scenarios.json (default samples/mahjong; only runs on the "
        "default can become a Recorded Demo)",
    )
    parser.add_argument("--language", choices=("ja", "en"), default="ja")
    parser.add_argument("--max-rounds", type=int, default=DEFAULT_MAX_CRITIC_ROUNDS)
    parser.add_argument("--max-queries", type=int, default=DEFAULT_MAX_QUERIES)
    parser.add_argument("--dry-run", action="store_true", help="Load the store and stop; no model")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("strands").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    try:
        store, sample, info = build_sample_store(args.scenario, sample_dir=args.sample_dir)
    except SampleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    try:
        _print_changes(info)
        current, previous = comparison_periods(store)
        print(f"periods: {current[0]}..{current[1]} vs {previous[0]}..{previous[1]}")
        if args.dry_run:
            for spec in store.tables():
                count = store.query(f"SELECT COUNT(*) FROM {spec.name}").scalar()
                print(f"  {spec.name}: {count} rows")
            return

        run_id = f"{RUN_PREFIX}{args.scenario}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        path = RUNS_DIR / f"{run_id}.json"
        write_sample_meta(path, info)

        def save(run: EvidenceRun) -> None:
            path.write_text(run.model_dump_json(by_alias=True, indent=2), encoding="utf-8")

        run = run_evidence_loop(
            run_id=run_id,
            product_id=sample.app["productId"],
            product_name=sample.app["name"],
            store=store,
            analyst=StrandsAnalyst(store, max_queries=args.max_queries),
            critic=StrandsCritic(store, max_queries=args.max_queries),
            internal_tables=INTERNAL_TABLE_NAMES,
            external_tables=EXTERNAL_TABLE_NAMES,
            language=args.language,
            max_critic_rounds=args.max_rounds,
            model=_model_label(),
            context_note=context_note(sample),
            on_update=save,
        )
    finally:
        store.close()
    print(f"\nrun {run.run_id}: {run.status} ({run.model})")
    for step in run.steps:
        top = step.output.actions[0].title if step.output.actions else "(no actions)"
        print(f"- {step.version} {step.stage}: #1 {top}")
    print(f"trace: {path}")
    print(f"to keep it as a Recorded Demo: python scripts/record_sample_demo.py {run.run_id}")
    if run.status == "error":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
