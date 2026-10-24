"""Record interventions: adopt an AI action or add one by hand, then implement and evaluate.

Examples:
  python scripts/interventions.py adopt --run mahjong-20261024-165009 --rank 1
  python scripts/interventions.py add --product mahjong --title "1枚目のスクショを結果画面に" \\
      --metric page_view_to_download_pct --method "変更前後14日比較" \\
      --criterion "+5ポイント以上" --days 14
  python scripts/interventions.py implement iv_0123456789 --on 2026-10-25
  python scripts/interventions.py evaluate iv_0123456789 --verdict inconclusive --note "母数が少ない"
  python scripts/interventions.py measure iv_0123456789
  python scripts/interventions.py list --product mahjong
  python scripts/interventions.py sync-memory

The ledger (INTERVENTIONS_PATH, default tmp/interventions/ledger.jsonl) is kept whatever
MEMORY_BACKEND is. Before / after numbers come from asc_daily in EVIDENCE_STORE.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence.store import EvidenceStore  # noqa: E402
from interventions import (  # noqa: E402
    VERDICTS,
    Intervention,
    InterventionError,
    InterventionLedger,
    Measurement,
    add_manual,
    adopt,
    evaluate,
    get_interventions_path,
    implement,
    load_run,
    prediction_from_run,
    remeasure,
    sync_memory,
)
from interventions.runtime import open_store, product_app_id, sync_memory_safely  # noqa: E402
from memory import build_memory  # noqa: E402
from product_config import load_product_by_id  # noqa: E402

RUNS_DIR = ROOT / "tmp" / "evidence_runs"


def _iso_date(raw: str) -> str:
    return date.fromisoformat(raw).isoformat()


def _run_path(value: str) -> Path:
    path = Path(value)
    if path.is_file():
        return path
    candidate = RUNS_DIR / f"{value.removesuffix('.json')}.json"
    if candidate.is_file():
        return candidate
    raise InterventionError(f"Evidence run not found: {value}")


def _measurement_lines(label: str, measurement: Measurement | None) -> list[str]:
    if measurement is None:
        return [f"  {label}: not measured"]
    lines = [f"  {label} ({measurement.period_start}..{measurement.period_end}, SQL):"]
    lines += [f"    {m.metric} = {m.value:g}" for m in measurement.metrics]
    lines += [f"    skipped {reason}" for reason in measurement.skipped]
    return lines


def _describe(item: Intervention) -> str:
    origin = "AI adopted" if item.decision.origin == "ai_adopted" else "manual"
    lines = [
        f"{item.id} [{item.status}] {item.title}",
        f"  product={item.product_id} origin={origin} metric={item.target_metric}",
        f"  implemented_on={item.implemented_on or '-'} "
        f"evaluation_date={item.decision.evaluation_date} window_days={item.window_days}",
    ]
    if item.prediction:
        lines.append(
            f"  AI prediction: run {item.prediction.run_id} {item.prediction.version} "
            f"#{item.prediction.action_rank}, {len(item.prediction.claims)} claims"
        )
    if item.baseline or item.implemented_on:
        lines += _measurement_lines("before", item.baseline)
    if item.evaluation:
        lines.append(
            f"  human evaluation ({item.evaluation.evaluated_on}): {item.evaluation.verdict}"
            + (f" — {item.evaluation.note}" if item.evaluation.note else "")
        )
        lines += _measurement_lines("after", item.after)
    if item.drop_reason:
        lines.append(f"  dropped: {item.drop_reason}")
    if item.memory_ids:
        lines.append(f"  memory: {', '.join(sorted(item.memory_ids))}")
    return "\n".join(lines)


def _open_store(skip: bool) -> EvidenceStore | None:
    if skip:
        return None
    store, warning = open_store()
    if warning:
        print(f"warning: {warning}", file=sys.stderr)
    return store


def _app_id(product_id: str) -> str | None:
    return product_app_id(product_id)


def _sync(ledger: InterventionLedger, item: Intervention) -> Intervention:
    item, warning = sync_memory_safely(ledger, item)
    if warning:
        print(f"warning: {warning}", file=sys.stderr)
    return item


def _report(item: Intervention, changed: bool, verb: str) -> None:
    print(("" if changed else f"(no change: already {verb}) ") + _describe(item))


def cmd_adopt(ledger: InterventionLedger, args: argparse.Namespace) -> None:
    run = load_run(_run_path(args.run))
    prediction = prediction_from_run(run, rank=args.rank, version=args.version)
    item, created = adopt(
        ledger,
        prediction,
        product_id=run.product_id,
        title=args.title,
        change_description=args.change,
        target_metric=args.metric,
        method=args.method,
        success_criterion=args.criterion,
        duration_days=args.days,
        window_days=args.window_days,
    )
    _report(_sync(ledger, item), created, "adopted")


def cmd_add(ledger: InterventionLedger, args: argparse.Namespace) -> None:
    product = load_product_by_id(args.product)
    item, created = add_manual(
        ledger,
        product_id=product.id,
        title=args.title,
        change_description=args.change,
        target_metric=args.metric,
        method=args.method,
        success_criterion=args.criterion,
        duration_days=args.days,
        window_days=args.window_days,
    )
    _report(_sync(ledger, item), created, "registered")


def cmd_implement(ledger: InterventionLedger, args: argparse.Namespace) -> None:
    item = ledger.get(args.id)
    store = _open_store(args.no_measure or item.status != "planned")
    try:
        item, changed = implement(
            ledger,
            args.id,
            implemented_on=args.on,
            evaluation_date=args.evaluate_on,
            store=store,
            app_id=_app_id(item.product_id),
        )
    finally:
        if store is not None:
            store.close()
    _report(_sync(ledger, item), changed, "implemented")


def cmd_evaluate(ledger: InterventionLedger, args: argparse.Namespace) -> None:
    item = ledger.get(args.id)
    store = _open_store(args.no_measure or item.status != "implemented")
    try:
        item, changed = evaluate(
            ledger,
            args.id,
            verdict=args.verdict,
            note=args.note,
            evaluated_on=args.on,
            store=store,
            app_id=_app_id(item.product_id),
            early=args.early,
        )
    finally:
        if store is not None:
            store.close()
    _report(_sync(ledger, item), changed, "evaluated")


def cmd_measure(ledger: InterventionLedger, args: argparse.Namespace) -> None:
    item = ledger.get(args.id)
    store = _open_store(False)
    if store is None:
        raise SystemExit(1)
    try:
        item, changed = remeasure(ledger, args.id, store=store, app_id=_app_id(item.product_id))
    finally:
        store.close()
    _report(item, changed, "measured with the same numbers")


def cmd_drop(ledger: InterventionLedger, args: argparse.Namespace) -> None:
    item, changed = ledger.drop(args.id, reason=args.reason)
    _report(item, changed, "dropped")


def cmd_list(ledger: InterventionLedger, args: argparse.Namespace) -> None:
    items = ledger.list_interventions(product_id=args.product, status=args.status)
    if not items:
        print("(no interventions)")
    for item in items:
        print(_describe(item))


def cmd_show(ledger: InterventionLedger, args: argparse.Namespace) -> None:
    print(ledger.get(args.id).model_dump_json(by_alias=True, indent=2))


def cmd_sync_memory(ledger: InterventionLedger, args: argparse.Namespace) -> None:
    memory = build_memory()
    try:
        before = {i.id: len(i.memory_ids) for i in ledger.list_interventions()}
        for item in ledger.list_interventions(product_id=args.product):
            sync_memory(ledger, memory, item)
        added = sum(
            len(i.memory_ids) - before.get(i.id, 0) for i in ledger.list_interventions()
        )
        print(f"memory backend {memory.name}: {added} new entries")
    finally:
        memory.close()


def _plan_options(parser: argparse.ArgumentParser, *, required: bool) -> None:
    parser.add_argument("--title", required=required)
    parser.add_argument("--change", default="", help="What exactly changes")
    parser.add_argument("--metric", required=required, help="Evaluation metric")
    parser.add_argument("--method", required=required, help="How the result is judged")
    parser.add_argument("--criterion", required=required, help="Success criterion")
    parser.add_argument("--days", type=int, required=required, help="Days until evaluation")
    parser.add_argument(
        "--window-days", type=int, default=None,
        help="Before / after window length (default: --days)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    today = date.today().isoformat()

    p = sub.add_parser("adopt", help="Adopt a proposed action from an evidence run")
    p.add_argument("--run", required=True, help="Run id in tmp/evidence_runs or a JSON path")
    p.add_argument("--rank", type=int, required=True)
    p.add_argument("--version", default=None, help="e.g. v3 (default: the final version)")
    _plan_options(p, required=False)
    p.set_defaults(func=cmd_adopt)

    p = sub.add_parser("add", help="Register an intervention by hand")
    p.add_argument("--product", required=True)
    _plan_options(p, required=True)
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("implement", help="Record the implementation date and measure before")
    p.add_argument("id")
    p.add_argument("--on", type=_iso_date, default=today)
    p.add_argument("--evaluate-on", type=_iso_date, default=None)
    p.add_argument("--no-measure", action="store_true")
    p.set_defaults(func=cmd_implement)

    p = sub.add_parser("evaluate", help="Record your verdict and measure after")
    p.add_argument("id")
    p.add_argument("--verdict", choices=VERDICTS, required=True)
    p.add_argument("--note", default="")
    p.add_argument("--on", type=_iso_date, default=today)
    p.add_argument("--early", action="store_true", help="Evaluate before the evaluation date")
    p.add_argument("--no-measure", action="store_true")
    p.set_defaults(func=cmd_evaluate)

    p = sub.add_parser(
        "measure", help="Measure before / after again (store was down, or data arrived late)"
    )
    p.add_argument("id")
    p.set_defaults(func=cmd_measure)

    p = sub.add_parser("drop", help="Stop tracking an intervention that will not be done")
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_drop)

    p = sub.add_parser("list", help="List interventions")
    p.add_argument("--product", default=None)
    p.add_argument(
        "--status", choices=("planned", "implemented", "evaluated", "dropped"), default=None
    )
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="Print one intervention as JSON")
    p.add_argument("id")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("sync-memory", help="Copy decisions and outcomes into decision memory")
    p.add_argument("--product", default=None)
    p.set_defaults(func=cmd_sync_memory)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    ledger = InterventionLedger(get_interventions_path())
    try:
        args.func(ledger, args)
    except (InterventionError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
