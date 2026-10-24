"""Run the evidence revision loop (v1 -> v2 -> Critic -> v3 ...) and save the trace.

Run (after scripts/export_evidence.py has loaded the tables):
  python scripts/run_evidence.py --product-id mahjong
  python scripts/run_evidence.py --product-id mahjong --language en --max-rounds 3

The model is LLM_PROVIDER (see .env.example). The store is EVIDENCE_STORE.
The run is written to tmp/evidence_runs/<run_id>.json after every step.
The first lines name the model provider, the evidence store (with the rows it holds),
and the decision memory backend that this run actually used.
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

from evidence import build_store  # noqa: E402
from evidence.agents import DEFAULT_MAX_QUERIES, StrandsAnalyst, StrandsCritic  # noqa: E402
from evidence.loop import DEFAULT_MAX_CRITIC_ROUNDS, run_evidence_loop  # noqa: E402
from evidence.schema import DecisionRecord, EvidenceRun  # noqa: E402
from evidence.sources import EXTERNAL_TABLE_NAMES, INTERNAL_TABLE_NAMES  # noqa: E402
from interventions import InterventionError, InterventionLedger  # noqa: E402
from interventions.ledger import get_interventions_path  # noqa: E402
from interventions.measure import METRICS  # noqa: E402
from llm import describe_provider, model_label  # noqa: E402
from memory import (  # noqa: E402
    RECALL_TAGS,
    DecisionMemory,
    build_memory,
    recall_past_decisions,
    recall_tags,
)
from product_config import ProductConfig, load_product_by_id  # noqa: E402

RUNS_DIR = ROOT / "tmp" / "evidence_runs"
logger = logging.getLogger(__name__)


def recall_decisions(
    product: ProductConfig, *, memory: DecisionMemory, ledger: InterventionLedger
) -> list[DecisionRecord]:
    """Past decisions for this product: found in memory, read back from the intervention ledger
    with their outcome (verdict and after numbers) once evaluated.

    Read-only. Decisions reach memory only when a person adopts or registers one
    (scripts/interventions.py); running an analysis never writes memory.
    """

    def lookup(ref_id: str) -> DecisionRecord | None:
        try:
            item = ledger.get(ref_id)
        except InterventionError:
            return None
        return None if item.status == "dropped" else item.decision_with_outcome()

    # product_id already scopes the recall; extra query words (e.g. the English app
    # name) only dilute tag matches in engines that read the first few query words.
    return recall_past_decisions(
        memory,
        product_id=product.id,
        query="",
        lookup=lookup,
        tag_sets=(RECALL_TAGS, recall_tags(METRICS)),
    )


MEMORY_LABELS = {"hmem": "hmem (Meterless H-MEM engine)", "local": "local (JSONL)"}
MAX_ROUNDS_LIMIT = 3


def _load_past_decisions(product: ProductConfig) -> list[DecisionRecord]:
    try:
        memory = build_memory()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Decision memory unavailable (%s: %s); running without past decisions",
                       type(exc).__name__, exc)
        return []
    try:
        ledger = InterventionLedger(get_interventions_path())
        decisions = recall_decisions(product, memory=memory, ledger=ledger)
    finally:
        memory.close()
    print(
        f"decision memory: {MEMORY_LABELS.get(memory.name, memory.name)}, "
        f"recalled {len(decisions)} for product {product.id}"
    )
    return decisions


def _print_store(store) -> None:
    """Which store this run reads, and that it actually returns our daily rows."""
    names = [t.name for t in store.tables()]
    print(f"evidence store: {store.dialect}, tables: {', '.join(names) or '(none)'}")
    if "asc_daily" in names:
        count, first, last = store.query(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM asc_daily"
        ).rows[0]
        print(f"  asc_daily: {count} rows, {first} to {last}")


def _max_rounds(raw: str) -> int:
    value = int(raw)
    if not 1 <= value <= MAX_ROUNDS_LIMIT:
        raise argparse.ArgumentTypeError(f"must be 1 to {MAX_ROUNDS_LIMIT}")
    return value


def _context_note(product: ProductConfig) -> str:
    lines = [f"- known_events.product = '{product.id}'"]
    if product.app_store.app_id:
        lines.insert(0, f"- Our app_id = '{product.app_store.app_id}' (asc_* tables, competitor_listing)")
    lines.append("- competitor_listing.is_self = 1 is our app; 0 are competitors")
    return "\n".join(lines)


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
    final = run.final
    if final is not None and run.status != "error":
        print(f"final Top {len(final.output.actions)} ({final.version}):")
        for action in final.output.actions:
            print(f"  {action.rank}. {action.title} [claims: {', '.join(action.claim_ids)}]")
        unresolved = [
            f for f in (final.critic.findings if final.critic else []) if f.resolution == "unresolved"
        ]
        if unresolved:
            claims = sorted({f.claim_id for f in unresolved})
            print(
                f"NOT VERIFIED: {len(unresolved)} Critic finding(s) still unresolved after "
                f"{run.max_critic_rounds} review round(s), on claims {', '.join(claims)}"
            )
    print(f"trace: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--product-id", default=None)
    parser.add_argument("--language", choices=("ja", "en"), default="ja")
    parser.add_argument("--max-rounds", type=_max_rounds, default=DEFAULT_MAX_CRITIC_ROUNDS)
    parser.add_argument("--max-queries", type=int, default=DEFAULT_MAX_QUERIES)
    parser.add_argument(
        "--run-id", default=None, help="Trace file name (default: <product>-<timestamp>)"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("strands").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    product = load_product_by_id(args.product_id)
    run_id = args.run_id or f"{product.id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{run_id}.json"

    def save(run: EvidenceRun) -> None:
        path.write_text(run.model_dump_json(by_alias=True, indent=2), encoding="utf-8")

    print(f"model provider: {describe_provider()}")
    past_decisions = _load_past_decisions(product)
    print(
        f"past decisions from memory: {len(past_decisions)}"
        + (f" ({', '.join(d.id for d in past_decisions)})" if past_decisions else "")
    )

    store = build_store()
    try:
        _print_store(store)
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
            model=model_label(),
            context_note=_context_note(product),
            past_decisions=past_decisions,
            on_update=save,
        )
    finally:
        store.close()
    _print_summary(run, path)
    if run.status == "error":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
