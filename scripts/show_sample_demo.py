"""Show the Recorded Demo traces in samples/recorded/ (no API key, network, or model).

Run:
  python scripts/show_sample_demo.py              # every recorded run, then base vs variant
  python scripts/show_sample_demo.py --run-id sample-base-20261025-100000

The same traces appear in the Web UI's revision history when api_server.py is running.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence.schema import EvidenceRun  # noqa: E402
from sample_mode import RECORDED_DIR, read_sample_meta  # noqa: E402


def recorded_runs(recorded_dir: Path = RECORDED_DIR) -> list[tuple[EvidenceRun, dict]]:
    runs = []
    for path in sorted(recorded_dir.glob("sample-*.json")):
        if path.name.endswith(".sample.json"):
            continue
        meta = read_sample_meta(path)
        if meta is None:
            continue
        runs.append((EvidenceRun.model_validate_json(path.read_text(encoding="utf-8")), meta))
    return runs


def describe(run: EvidenceRun, meta: dict) -> list[str]:
    lines = [
        f"== {run.run_id}  [Recorded Demo / fictional sample data]",
        f"scenario: {meta['scenario']} — {meta['scenarioDescription']}",
        f"model: {run.model}  status: {run.status}  recorded: {meta.get('recordedAt', '?')}",
    ]
    for change in meta.get("changes", []):
        match = ", ".join(f"{k}={v}" for k, v in change["match"].items())
        lines.append(
            f"  changed {change['table']} [{match}] {change['column']}: "
            f"{change['before']} -> {change['after']} ({change['reason']})"
        )
    for step in run.steps:
        top = step.output.actions[0].title if step.output.actions else "(no actions)"
        review = ""
        if step.critic:
            unresolved = sum(f.resolution == "unresolved" for f in step.critic.findings)
            review = f"  | Critic: {len(step.critic.findings)} findings, {unresolved} unresolved"
        lines.append(f"  {step.version} #1 {top}{review}")
    final = run.final
    if final:
        lines.append("  final actions:")
        lines += [f"    {a.rank}. {a.title}" for a in final.output.actions] or ["    (none)"]
    lines += review_notes(meta)
    return lines


def review_notes(meta: dict) -> list[str]:
    """reviewOutcome, knownLimitations, and comparisonNote from the .sample.json, if any."""
    lines = []
    outcome = meta.get("reviewOutcome")
    if isinstance(outcome, str) and outcome.strip():
        lines.append(f"  review outcome: {outcome.strip()}")
    limitations = meta.get("knownLimitations")
    if not isinstance(limitations, list):
        limitations = []
    items = [i.strip() for i in limitations if isinstance(i, str) and i.strip()]
    if items:
        lines.append("  known limitations:")
        lines += [f"    - {item}" for item in items]
    note = meta.get("comparisonNote")
    if isinstance(note, str) and note.strip():
        lines.append(f"  comparison note: {note.strip()}")
    return lines


def compare(runs: list[tuple[EvidenceRun, dict]]) -> list[str]:
    """Latest base vs latest competitor-variant, both in the same run language."""
    by_language: dict[str, dict[str, EvidenceRun]] = {}
    for run, meta in runs:
        by_language.setdefault(run.language, {})[meta["scenario"]] = run
    latest = next(
        (s for s in by_language.values() if "base" in s and "competitor-variant" in s), None
    )
    if latest is None:
        return []
    lines = ["== base vs competitor-variant (final version)"]
    for name in ("base", "competitor-variant"):
        final = latest[name].final
        titles = [a.title for a in final.output.actions] if final else []
        lines.append(f"  {name}: " + (" / ".join(titles) or "(none)"))
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    runs = recorded_runs()
    if args.run_id:
        runs = [(r, m) for r, m in runs if r.run_id == args.run_id]
    if not runs:
        print("No Recorded Demo yet. Record one with scripts/run_sample.py, then")
        print("scripts/record_sample_demo.py <run_id>.")
        return
    for run, meta in runs:
        print("\n".join(describe(run, meta)))
        print()
    print("\n".join(compare(runs)))


if __name__ == "__main__":
    main()
