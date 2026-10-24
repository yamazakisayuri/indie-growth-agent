"""Code-side review: structural rules, re-running cited SQL, and comparing Critic checks.

The Critic model writes SQL and judges causal / scope problems. Whether a
number matches is decided here, by code, never by a model.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections.abc import Iterable, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from .schema import (
    AnalystOutput,
    CheckOutcome,
    CriticFinding,
    CriticReport,
    SqlCall,
)
from .store import EvidenceStore, EvidenceStoreError

_SCALES = (1.0, 100.0, 0.01)
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_NULL_WORDS = frozenset({"null", "none", "n/a", ""})


def to_number(value: Any) -> float | None:
    """Numbers and numeric strings ('2,258', '35.63%', '0.36') as float; else None."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    text = str(value).strip().replace(",", "")
    if text.endswith("%"):
        text = text[:-1]
    try:
        return float(Decimal(text))
    except (InvalidOperation, ValueError):
        return None


def _decimals(value: Any) -> int:
    text = str(value).strip().replace(",", "").rstrip("%")
    if "e" in text.lower():
        return 6
    return min(len(text.split(".", 1)[1].rstrip("0")), 6) if "." in text else 0


def values_match(claimed: Any, actual: Any) -> bool:
    """True when actual, rounded to the precision the claim was written with, equals it.

    A ratio written as a percent (0.3563 vs 35.63) also matches.
    """
    c, a = to_number(claimed), to_number(actual)
    if c is None or a is None:
        return False
    tolerance = 0.5 * 10 ** -_decimals(claimed) + 1e-9
    return any(abs(a * scale - c) <= tolerance for scale in _SCALES)


def is_composite(value: Any) -> bool:
    """A text value that packs several numbers, e.g. 'impressions=2248, downloads=37'."""
    if not isinstance(value, str) or to_number(value) is not None:
        return False
    text = value.strip()
    if _ISO_DATE.match(text) and len(text) <= 25:
        return False
    return len(_NUMBER.findall(text)) >= 2 or any(ch in text for ch in "=;")


def values_equal(claimed: Any, actual: Any) -> bool:
    """Numbers by values_match; single texts (e.g. a genre) by case-insensitive equality."""
    if to_number(claimed) is not None:
        return values_match(claimed, actual)
    claimed_null = claimed is None or str(claimed).strip().casefold() in _NULL_WORDS
    if claimed_null or actual is None:
        return claimed_null and actual is None
    return str(claimed).strip().casefold() == str(actual).strip().casefold()


def run_logged(store: EvidenceStore, sql: str, role: str, log: list[SqlCall]):
    started = time.monotonic()
    try:
        result = store.query(sql)
    except (EvidenceStoreError, ValueError) as exc:
        log.append(
            SqlCall(
                role=role,
                sql=sql,
                ok=False,
                error=str(exc),
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        )
        raise
    log.append(
        SqlCall(
            role=role,
            sql=sql,
            ok=True,
            row_count=len(result.rows),
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    )
    return result


def _scalar(store: EvidenceStore, sql: str, role: str, log: list[SqlCall]) -> tuple[Any, str | None]:
    try:
        return run_logged(store, sql, role, log).scalar(), None
    except (EvidenceStoreError, ValueError) as exc:
        return None, str(exc)


class FindingIds:
    def __init__(self, prefix: str) -> None:
        self._prefix = prefix
        self._n = 0

    def next(self) -> str:
        self._n += 1
        return f"{self._prefix}-f{self._n}"


def structural_findings(
    output: AnalystOutput,
    *,
    table_names: Iterable[str],
    external_tables: Iterable[str],
    ids: FindingIds,
) -> list[CriticFinding]:
    """Rules that need no model: evidence present, tables exist, external data not a fact."""
    tables = {t.lower() for t in table_names}
    external = {t.lower() for t in external_tables}
    claim_ids = {c.id for c in output.claims}
    findings: list[CriticFinding] = []

    def add(claim_id: str, kind: str, message: str) -> None:
        findings.append(
            CriticFinding(id=ids.next(), claim_id=claim_id, kind=kind, message=message, origin="code")
        )

    for claim in output.claims:
        cited = {e.table.lower() for e in claim.evidence}
        unknown = sorted(cited - tables)
        if unknown:
            add(claim.id, "unverifiable", f"Evidence cites tables that do not exist: {unknown}.")
        if claim.kind in ("fact", "observation") and not claim.evidence:
            add(claim.id, "unverifiable", f"A {claim.kind} needs at least one evidence item.")
        if any(is_composite(e.value) for e in claim.evidence):
            add(
                claim.id,
                "unverifiable",
                "An evidence value packs several numbers. Use one evidence item per number, "
                "each with SQL that returns exactly that value.",
            )
        if claim.kind == "fact":
            if cited & external:
                add(
                    claim.id,
                    "kind_mislabel",
                    "Public data about other apps is an observation, not a fact about our app.",
                )
            if any(not e.sql.strip() for e in claim.evidence):
                add(claim.id, "unverifiable", "Every fact needs the SQL that reproduces its value.")
        if claim.kind == "hypothesis" and claim.test_plan is None:
            add(claim.id, "causal_leap", "A hypothesis needs a test plan before acting on it.")

    for action in output.actions:
        missing = sorted(set(action.claim_ids) - claim_ids)
        if missing:
            add(
                missing[0],
                "unverifiable",
                f"Action {action.rank} cites claims that do not exist: {missing}.",
            )
        if action.claim_ids and not missing:
            kinds = {c.kind for c in output.claims if c.id in action.claim_ids}
            if "fact" not in kinds and "hypothesis" not in kinds:
                add(
                    action.claim_ids[0],
                    "causal_leap",
                    f"Action {action.rank} rests only on observations of other apps; "
                    "state the hypothesis and how to test it.",
                )
    return findings


def recheck_cited_sql(
    output: AnalystOutput,
    *,
    store: EvidenceStore,
    ids: FindingIds,
    log: list[SqlCall],
) -> list[CriticFinding]:
    """Re-run each SQL the Analyst cited; its result must equal the value it wrote."""
    findings: list[CriticFinding] = []
    for claim in output.claims:
        for evidence in claim.evidence:
            if not evidence.sql.strip() or evidence.value is None or is_composite(evidence.value):
                continue
            actual, error = _scalar(store, evidence.sql, "code", log)
            if error is not None:
                findings.append(
                    CriticFinding(
                        id=ids.next(),
                        claim_id=claim.id,
                        kind="unverifiable",
                        message=f"The cited SQL does not return one value: {error}",
                        origin="code",
                        analyst_sql=evidence.sql,
                        claimed_value=evidence.value,
                    )
                )
            elif not values_equal(evidence.value, actual):
                findings.append(
                    CriticFinding(
                        id=ids.next(),
                        claim_id=claim.id,
                        kind="value_mismatch",
                        message="The cited SQL returns a different value than the claim states.",
                        origin="code",
                        analyst_sql=evidence.sql,
                        critic_value=actual,
                        claimed_value=evidence.value,
                    )
                )
    return findings


def apply_critic_report(
    report: CriticReport,
    output: AnalystOutput,
    *,
    store: EvidenceStore,
    ids: FindingIds,
    log: list[SqlCall],
) -> tuple[list[CriticFinding], list[CheckOutcome]]:
    """Run the Critic's own SQL checks and turn its issues into findings."""
    claims = {c.id: c for c in output.claims}
    findings: list[CriticFinding] = []
    outcomes: list[CheckOutcome] = []

    for check in report.checks:
        claim = claims.get(check.claim_id)
        if claim is None or not claim.evidence:
            continue
        actual, error = _scalar(store, check.sql, "critic", log)
        # Models often omit evidence_index, so a check counts as matched when its value
        # equals any of the claim's evidence values; evidence_index only picks what a
        # mismatch is reported against.
        index = next(
            (
                i
                for i, e in enumerate(claim.evidence)
                if error is None and not is_composite(e.value) and values_equal(e.value, actual)
            ),
            None,
        )
        matched = index is not None
        if index is None:
            index = min(check.evidence_index, len(claim.evidence) - 1)
        evidence = claim.evidence[index]
        if not matched and error is None and is_composite(evidence.value):
            error = "The claim's evidence value packs several numbers; not compared."
        outcomes.append(
            CheckOutcome(
                claim_id=claim.id,
                evidence_index=index,
                sql=check.sql,
                claimed_value=evidence.value,
                critic_value=actual,
                matched=matched,
                error=error,
            )
        )
        if error is None and not matched:
            findings.append(
                CriticFinding(
                    id=ids.next(),
                    claim_id=claim.id,
                    kind="value_mismatch",
                    message="The Critic's own SQL returns a different value than the claim states.",
                    origin="code",
                    critic_sql=check.sql,
                    critic_value=actual,
                    claimed_value=evidence.value,
                    analyst_sql=evidence.sql,
                )
            )

    for issue in report.issues:
        if issue.claim_id not in claims:
            continue
        findings.append(
            CriticFinding(
                id=ids.next(),
                claim_id=issue.claim_id,
                kind=issue.kind,
                message=issue.message,
                origin="critic",
            )
        )
    return findings, outcomes


def dedupe(findings: Sequence[CriticFinding]) -> list[CriticFinding]:
    """Keep the first finding per (claim, kind, origin, message)."""
    seen: set[tuple[str, str, str, str]] = set()
    out: list[CriticFinding] = []
    for f in findings:
        key = (f.claim_id, f.kind, f.origin, f.message)
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def resolve_previous(
    previous: Sequence[CriticFinding],
    revised: AnalystOutput,
    current: Sequence[CriticFinding],
) -> None:
    """Mark last round's findings after the Analyst revised and the Critic looked again."""
    claims = {c.id: c for c in revised.claims}
    recurring = {(f.claim_id, f.kind) for f in current}
    for f in previous:
        if (f.claim_id, f.kind) in recurring:
            continue
        claim = claims.get(f.claim_id)
        if claim is not None and claim.kind == "hypothesis" and f.kind in (
            "causal_leap",
            "kind_mislabel",
        ):
            f.resolution = "downgraded"
        else:
            f.resolution = "resolved"


def critic_payload(output: AnalystOutput) -> str:
    """What the Critic sees: claims (without the Analyst's SQL) and actions. No reasoning."""
    claims = [
        {
            "id": c.id,
            "text": c.text,
            "kind": c.kind,
            "evidence": [
                {k: v for k, v in e.model_dump().items() if k != "sql" and v not in (None, "")}
                for e in c.evidence
            ],
            "test_plan": c.test_plan.model_dump() if c.test_plan else None,
        }
        for c in output.claims
    ]
    actions = [{"rank": a.rank, "title": a.title, "claim_ids": a.claim_ids} for a in output.actions]
    return json.dumps({"claims": claims, "actions": actions}, ensure_ascii=False, indent=2)
