"""Run the evidence revision loop (v1 -> v2 -> Critic -> v3 ...) and save the trace.

Run (after scripts/export_evidence.py has loaded the tables):
  python scripts/run_evidence.py --product-id mahjong
  python scripts/run_evidence.py --product-id mahjong --language en --max-rounds 3

The model is LLM_PROVIDER (see .env.example). The store is EVIDENCE_STORE.
The run is written to tmp/evidence_runs/<run_id>.json after every step.
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
from evidence import build_store  # noqa: E402
from evidence.agents import DEFAULT_MAX_QUERIES, StrandsAnalyst, StrandsCritic  # noqa: E402
from evidence.loop import DEFAULT_MAX_CRITIC_ROUNDS, run_evidence_loop  # noqa: E402
from evidence.schema import EvidenceRun  # noqa: E402
from evidence.sources import EXTERNAL_TABLE_NAMES, INTERNAL_TABLE_NAMES  # noqa: E402
from product_config import load_product_by_id  # noqa: E402

RUNS_DIR = ROOT / "tmp" / "evidence_runs"


def _model_label() -> str:
    provider = get_llm_provider()
    if provider == "openai_compatible":
        return f"openai_compatible:{get_openai_compatible_settings().model_id}"
    return provider


def _print_summary(run: EvidenceRun, path: Path) -> None:
    print(f"\nrun {run.run_id}: {run.status} ({run.model})")
    if run.error:
        print(f"error: {run.error}")
    for step in run.steps:
        top = step.output.actions[0].title if step.output.actions else "(no actions)"
        print(
            f"- {step.version} {step.stage}: {len(step.output.claims)} claims, "
            f"{len(step.queries)} queries, {step.duration_seconds}s; #1 {top}"
        )
        if step.critic:
            matched = sum(c.matched for c in step.critic.checks)
            print(
                f"  critic: {len(step.critic.findings)} findings, "
                f"{matched}/{len(step.critic.checks)} checks matched, {step.critic.duration_seconds}s"
            )
            for f in step.critic.findings:
                print(f"    [{f.kind} / {f.origin} / {f.resolution}] {f.claim_id}: {f.message}")
    print(f"trace: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--product-id", default=None)
    parser.add_argument("--language", choices=("ja", "en"), default="ja")
    parser.add_argument("--max-rounds", type=int, default=DEFAULT_MAX_CRITIC_ROUNDS)
    parser.add_argument("--max-queries", type=int, default=DEFAULT_MAX_QUERIES)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("strands").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    product = load_product_by_id(args.product_id)
    run_id = f"{product.id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{run_id}.json"

    def save(run: EvidenceRun) -> None:
        path.write_text(run.model_dump_json(by_alias=True, indent=2), encoding="utf-8")

    store = build_store()
    try:
        run = run_evidence_loop(
            run_id=run_id,
            product_id=product.id,
            product_name=product.name,
            store=store,
            analyst=StrandsAnalyst(store, max_queries=args.max_queries),
            critic=StrandsCritic(store, max_queries=args.max_queries),
            internal_tables=INTERNAL_TABLE_NAMES,
            external_tables=EXTERNAL_TABLE_NAMES,
            language=args.language,
            max_critic_rounds=args.max_rounds,
            model=_model_label(),
            on_update=save,
        )
    finally:
        store.close()
    _print_summary(run, path)
    if run.status == "error":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
