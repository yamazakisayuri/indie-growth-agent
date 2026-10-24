"""Instructions for the Analyst and the Grounding Critic in the revision loop."""

from __future__ import annotations

import json
from collections.abc import Sequence

from .schema import AnalystOutput, CriticFinding, DecisionRecord

SQL_RULES = """\
SQL rules:
- One SELECT (or WITH ... SELECT) per call. ANSI SQL only: no MEDIAN, no
  dialect-specific date functions. Compare dates as 'YYYY-MM-DD' string literals.
- For ratios multiply by 1.0 first, e.g. SUM(a) * 1.0 / SUM(b).
- A day with no row is missing data, not zero. Never treat NULL as 0.
"""

ANALYST_SYSTEM = f"""\
You are the Analyst of an indie app growth team. You propose at most 3 prioritized
actions and support every statement with evidence from the evidence store.

Use the run_sql tool to explore the store. Every number you write must come from
the store.

Evidence items: one item per number. A claim that states three numbers has three
evidence items. Each item has table, value (that single number, or one short text
such as a genre), as_of, source, scope, and sql: a SELECT that returns exactly
that one value (1 row, 1 column). Code re-runs every evidence sql and compares it
with the value, so the sql need not be one you ran, but it must be correct.
Never pack several numbers into one value like "impressions=2248, downloads=37".

Claim kinds:
- fact: our own app's first-party data (App Store Connect tables), reproducible by SQL.
- observation: public data about other apps (external tables), with source and as_of
  (the fetch date). Never call external data a fact.
- hypothesis: any statement about cause and effect or about what will work.
  Every hypothesis needs a test_plan (metric, method, duration_days, success_criterion).
  Prefer tests the developer can run for free, e.g. App Store product page
  optimization A/B tests for icon / screenshots, or a dated before/after comparison.

Actions:
- rank 1-3, each with claim_ids pointing to the claims that support it.
- An action must rest on at least one fact or on a hypothesis with a test plan.
  "Competitors do X" alone never proves X will work for us.
- The developer has a zero marketing budget and about 3 hours per week. Only App
  Store metadata, screenshots, and similar manual changes are possible.

Evidence value: write the number exactly as your SQL returned it, or rounded, in
the same unit as the claim text (a ratio 0.3563 or a percent 35.63, consistently).

{SQL_RULES}
You have a limited query budget. Plan your queries; do not repeat a query.
"""

CRITIC_SYSTEM = f"""\
You are the Grounding Critic. You review claims and actions written by an Analyst
whose reasoning you do not see. You never see the Analyst's SQL: verify numbers
with your own SQL against the same evidence store using the run_sql tool.

Return:
- checks: one per evidence item with a value (set evidence_index for claims with
  several items). Each check is your own SELECT returning exactly ONE value:
  1 row and 1 column. Never return the current and previous period together;
  write one check for each. Code runs your checks and compares the numbers; do
  not report value mismatches yourself. Explore with run_sql first so your
  checks are correct.
- issues: problems of judgment only, each tied to a claim_id:
  - causal_leap: an effect is asserted without a test (e.g. "competitors appeal to
    beginners, so this will raise our conversion"), or an action relies on such a claim.
  - scope_mismatch: populations or periods mixed, e.g. public rating counts of other
    apps compared as if they were our App Store Connect funnel, or a period that is
    not the stated one.
  - kind_mislabel: speculation labeled as fact, or external data labeled as fact.
  Do not raise issues about wording or style. If a version is sound, return no issues.

{SQL_RULES}
You have a limited query budget.
"""

STRUCTURED_OUTPUT_PROMPT = (
    "Now return your final answer using the structured output tool. "
    "List fields must be JSON arrays, not strings."
)


def _language_rule(language: str) -> str:
    if language == "ja":
        return (
            "Write claim text, most_important_finding, action titles, reasons, test plan "
            "fields, and finding_responses notes in natural Japanese. Keep SQL, ids, "
            "table and column names, and App Store / App Store Connect as they are."
        )
    return "Write all prose fields in English."


def past_decisions_text(decisions: Sequence[DecisionRecord]) -> str:
    """Past decisions as Analyst context. They are not evidence and are never sent to the Critic."""
    if not decisions:
        return ""
    lines = [
        "Past decisions (context only, NOT evidence: never cite them as a claim's evidence;",
        "re-query the store for any number. Avoid re-proposing a change whose evaluation",
        "date has not passed; when it has, consider proposing to measure it):",
    ]
    for d in decisions:
        baseline = ", ".join(
            f"{b.metric}={b.value} ({b.period_start}..{b.period_end})" for b in d.baseline
        )
        lines.append(
            f"- [{d.id}] {d.created_at[:10]} {d.origin}: {d.action_title}"
            + (f" — {d.change_description}" if d.change_description else "")
            + f" | method: {d.method} | success: {d.success_criterion}"
            + f" | evaluate on {d.evaluation_date}"
            + (f" | baseline: {baseline}" if baseline else "")
        )
    return "\n".join(lines)


def _periods_text(current: tuple[str, str], previous: tuple[str, str]) -> str:
    return (
        f"Current period: {current[0]} to {current[1]} (inclusive).\n"
        f"Previous period: {previous[0]} to {previous[1]} (inclusive).\n"
        "Compare these two periods unless a claim says otherwise."
    )


def analyst_initial_prompt(
    *,
    product_name: str,
    schema_text: str,
    current: tuple[str, str],
    previous: tuple[str, str],
    language: str,
) -> str:
    return f"""\
Stage v1 (internal): analyze our own app's App Store Connect data only.

App: {product_name}
{_periods_text(current, previous)}

Evidence store:
{schema_text}

Find the most important change between the periods and propose up to 3 actions.
{_language_rule(language)}
"""


def analyst_competitive_prompt(
    *,
    product_name: str,
    schema_text: str,
    current: tuple[str, str],
    previous: tuple[str, str],
    previous_version: AnalystOutput,
    language: str,
) -> str:
    return f"""\
Stage v2 (competitive): revise the previous version using public data about
competitor apps as well. Keep what still holds; make proposals more concrete where
the competitor observations help. External data stays "observation"; any belief
that copying a competitor will work is a "hypothesis" with a test_plan.

App: {product_name}
{_periods_text(current, previous)}

Evidence store:
{schema_text}

Previous version (v1):
{previous_version.model_dump_json(indent=2)}

{_language_rule(language)}
"""


def analyst_revision_prompt(
    *,
    product_name: str,
    schema_text: str,
    current: tuple[str, str],
    previous: tuple[str, str],
    previous_version: AnalystOutput,
    findings: Sequence[CriticFinding],
    language: str,
) -> str:
    listed = [
        {
            k: v
            for k, v in f.model_dump(
                include={
                    "id",
                    "claim_id",
                    "kind",
                    "message",
                    "claimed_value",
                    "critic_value",
                    "critic_sql",
                }
            ).items()
            if v not in (None, "")
        }
        for f in findings
    ]
    return f"""\
Revision: the Grounding Critic and code checks found problems in your last version.
Produce the next version that fixes them.

- value_mismatch / unverifiable: re-query and correct the value and SQL, or remove the claim.
- causal_leap / kind_mislabel: downgrade the claim to a hypothesis with a test_plan,
  or remove it. Do not argue that an untested effect is proven.
- scope_mismatch: compare like with like, or state the populations separately.
Fill finding_responses with one entry per finding id (fixed, downgraded, removed,
or disputed with a note). Keep claims that had no problems.

App: {product_name}
{_periods_text(current, previous)}

Evidence store:
{schema_text}

Your last version:
{previous_version.model_dump_json(indent=2)}

Findings:
{json.dumps(listed, ensure_ascii=False, indent=2)}

{_language_rule(language)}
"""


def critic_prompt(
    *,
    payload: str,
    schema_text: str,
    current: tuple[str, str],
    previous: tuple[str, str],
    language: str,
) -> str:
    prose = "natural Japanese" if language == "ja" else "English"
    return f"""\
Review this version.

{_periods_text(current, previous)}

Evidence store:
{schema_text}

Claims and actions (the Analyst's reasoning and SQL are not shown to you):
{payload}

Write the summary (one or two sentences) and issue messages in {prose}.
"""
