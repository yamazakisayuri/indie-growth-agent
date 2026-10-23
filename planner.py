"""Planner Agent: turn Analyzer findings into Growth Experiment candidates.

Uses Growth Agent MCP as a knowledge / playbook provider. Does not replace
the Analyzer, and must never fail the Analyze response.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.tools.mcp import MCPClient

from analysis_schema import (
    AnalyzeResponse,
    GrowthExperiment,
    PlannerStructuredOutput,
)
from config import GrowthMcpSettings, get_growth_mcp_settings, get_growth_md_text
from known_events import KnownEvent, get_known_events_for_report
from llm import build_model

logger = logging.getLogger(__name__)

# Sentinel: load from disk / config (default production behavior).
_AUTO = object()

PLANNER_SYSTEM_PROMPT = """
You are the Indie Growth Agent Planner.

Your job is NOT to restate Analyzer "Top 3 Actions".
Your job is to decide which Growth Experiments (if any) are worth trying next,
using:
1) Analyzer Facts / Speculation / Most Important Finding
2) Summary metrics, period, and data scope
3) Marketing playbooks and calculators from Growth Agent MCP tools
4) GROWTH.md when provided (standing constraints and available resources)
5) Known Events when provided (temporary human context for specific dates)

Role split:
- Analyzer already answered "what is happening in the data".
- You answer "what experiment should we run next, if any".
- Growth Agent MCP is a knowledge provider only. You choose experiments.
- GROWTH.md (when present) is standing product/operator context: budget, time,
  available tools, analytics constraints, and execution rules. Obey it.
- Known Events (when present) are temporary human context about dated incidents.
  They are NOT proven causes. Use them to re-prioritize experiments and to avoid
  wasting time investigating spikes that already have a plausible temporary
  explanation — without asserting causation.

Hard rules:
- Return 0 to 3 experiments. Fewer is better than inventing weak ideas.
- Do NOT convert Analyzer actions into experiments one-for-one.
- Do NOT invent metrics, sample sizes, channels, budgets, or causal claims
  that are not supported by the provided Analyzer Facts / metrics.
- Growth axes (observe in parallel; do not force Revenue or Web every run):
  Product growth, Conversion, Engagement (App), Engagement (Web when present),
  and Revenue (when revenueSummary / AdMob earnings / App Store proceeds are
  present). Choose
  experiments from Facts — adding a channel does NOT require proposing an
  experiment for that channel. Zero Web experiments and zero Revenue experiments
  are valid outcomes. Do NOT force pricing / IAP / monetization experiments
  merely because a single App Store proceeds row or small amount exists.
- Web channel rules:
  - Do NOT create a SEO / Web experiment merely because Web / GA4 Web exists.
  - A declared Web capability (e.g. mahjong_score_calculation) means users CAN
    do that on the site — it is NOT measured usage and NOT a GA4 event.
  - Site-wide Web users/sessions/page views are NOT feature usage of a capability.
  - When path-scoped Web metrics are present: path page views = page viewed
    (not calculation used); form_submit @ path = form submit proxy (not
    score_calculated); appstore_click = Web App Store CTA click (not ASC
    download / App first_open). Never propose Web → ASC download funnels or CVR.
  - Do not over-weight large % moves on tiny absolute Web CTA / form counts.
  - Do not force a Web or Measurement experiment merely because a capability is
    listed. Measurement is allowed when Facts show a real instrumentation gap
    that blocks a decision — still optional; zero such experiments can be correct.
  - Parallel same-window Facts are fine; Web → App Store download causation or
    funnels require attribution evidence (usually absent).
  - Cross-channel hypotheses are allowed only as labeled Speculation / hypothesis
    with a measurement plan — never as proven cause.
- Revenue judgment: use absolute amount AND changePercent together. Do not
  over-weight a large % move on a small absolute amount. Do not casually sum
  different currencies or ASC Downloads with AdMob earnings / App Store proceeds
  as one funnel. AdMob ESTIMATED_EARNINGS ≠ App Store Developer Proceeds.
  Developer Proceeds ≠ Financial Partner Share. Units ≠ Revenue. ASC Analytics
  JP ≠ Revenue WW — never funnel Downloads into Revenue.
  When previousAmount is 0, do not treat missing % as infinite growth.
- If GROWTH.md is present, every experiment must fit Budget, Time, Available,
  Not available, Analytics constraints, and Execution rules. Discard or rewrite
  ideas that require unavailable tools, paid ads, or more time/budget than allowed.
- Prefer actions that a human can approve and do manually within the stated
  weekly time budget. Never assume automatic publish or automatic execution.
- Known Events are context, not proof:
  - Never claim "Event X caused Metric Y".
  - Prefer phrasing like "coincides with", "may partly explain", "consistent with".
  - A Known Event may lower priority of an investigation experiment, or make it
    unnecessary, when it already supplies a plausible temporary explanation —
    but do not hardcode that outcome; decide from Facts + Known Events + constraints.
  - Store / review / metadata Known Events near a metric move do NOT establish
    that the store change caused the metric move.
  - The same rules apply when a Revenue move overlaps a Known Event
    (temporal overlap / correlation candidate / causality unknown).
- If evidence is too weak (small sample, missing metrics, Facts alone cannot
  support a marketing hypothesis), do NOT invent a growth tactic.
  Prefer either:
  - zero experiments plus a clear summary explaining why, OR
  - one "Measurement experiment" that says what to instrument / observe first, OR
  - one item titled "No experiment recommended" that explains the gap.
- Prefer Measurement experiment over fake marketing experiments.
- When GROWTH.md asks to prefer existing analytics, prefer experiments that use
  already-collected events/metrics; propose new instrumentation only when the
  expected value clearly justifies the implementation cost.
- When you use Growth MCP, call growth_playbook (search by query, then load by id)
  before proposing a marketing experiment grounded in that playbook.
- Calculators (ab_test_planner, etc.) are optional helpers when numbers exist.
- Every experiment must include playbook_reference (playbook id/title, or
  "none — measurement only" / "none — insufficient evidence").
- Keep Facts and Speculation distinct in your reasoning (why / evidence).
- Never claim an effect is proven when the data only shows correlation or
  a directional change.
"""

PLANNER_STRUCTURED_PROMPT = """
Fill PlannerStructuredOutput.

- summary: brief overall judgment (why these experiments, or why none / measurement).
  Mention how Known Events (if any) affected prioritization, without asserting causation.
- playbooks_consulted: list of Growth MCP playbook ids or titles you actually used
  (empty if none).
- known_events_used: short labels of Known Events that influenced this plan
  (e.g. "2026-09-20–2026-09-21 usage", "2026-09-08 store"). Empty if none influenced.
- experiments: 0–3 GrowthExperiment objects.

Each experiment fields:
title, hypothesis, why, action, target_metric, expected_signal,
suggested_duration, evidence, playbook_reference.

Language: follow the RESPONSE LANGUAGE section for all prose fields.
Do not invent UI headings.
"""


def _normalize_language(language: str | None) -> str:
    if language and language.lower().startswith("ja"):
        return "ja"
    return "en"


def _language_instruction(language: str) -> str:
    if language == "ja":
        return """

RESPONSE LANGUAGE: Japanese (ja)

Write summary and all experiment prose fields in natural Japanese.
Keep service names and metric / event identifiers in their original form
(App Store Connect, GA4, AdMob, record_saved, IMPRESSIONS, eCPM, etc.).
"""
    return """

RESPONSE LANGUAGE: English (en)

Write summary and all experiment prose fields in clear English.
Keep service names and metric / event identifiers unchanged.
"""


def _metric_lines(group: Any) -> list[str]:
    lines: list[str] = []
    connected = getattr(group, "connected", True)
    title = getattr(group, "title", "metrics")
    source = getattr(group, "source", "")
    status = getattr(group, "status_message", None) or getattr(
        group, "statusMessage", None
    )
    header = f"- {title} ({source}): "
    if not connected:
        lines.append(header + f"not connected — {status or 'no data'}")
        return lines
    lines.append(header + "connected")
    for metric in getattr(group, "metrics", []) or []:
        mid = getattr(metric, "id", "")
        label = getattr(metric, "label", mid)
        change = getattr(metric, "change_percent", None)
        if change is None:
            change = getattr(metric, "changePercent", None)
        value = getattr(metric, "value", None)
        absolute = getattr(metric, "absolute", None)
        parts = [f"{label} ({mid})"]
        if change is not None:
            sign = "+" if change >= 0 else ""
            parts.append(f"change={sign}{change}%")
        if value:
            parts.append(f"value={value}")
        if absolute:
            parts.append(f"absolute={absolute}")
        lines.append("  - " + ", ".join(parts))
    return lines


def _revenue_summary_lines(report: AnalyzeResponse) -> list[str]:
    summary = getattr(report, "revenue_summary", None)
    if summary is None:
        return ["- (not provided)"]
    currency = getattr(summary, "currency", None)
    note = getattr(summary, "note", "") or ""
    lines = [
        f"- currency (display primary): {currency or '(none)'}",
        f"- note: {note or '(none)'}",
        "- sources:",
    ]
    sources = getattr(summary, "sources", None) or []
    if not sources:
        lines.append("  - (none)")
        return lines
    for item in sources:
        if hasattr(item, "model_dump"):
            row = item.model_dump(by_alias=True)
        elif isinstance(item, dict):
            row = item
        else:
            row = {
                "source": getattr(item, "source", None),
                "amountType": getattr(item, "amount_type", None),
                "amount": getattr(item, "amount", None),
                "previousAmount": getattr(item, "previous_amount", None),
                "changePercent": getattr(item, "change_percent", None),
                "currency": getattr(item, "currency", None),
                "units": getattr(item, "units", None),
                "connected": getattr(item, "connected", None),
                "status": getattr(item, "status", None),
                "note": getattr(item, "note", None),
            }
        lines.append(
            "  - "
            f"source={row.get('source')}, amountType={row.get('amountType')}, "
            f"amount={row.get('amount')}, "
            f"previousAmount={row.get('previousAmount')}, "
            f"changePercent={row.get('changePercent')}, "
            f"currency={row.get('currency')}, units={row.get('units')}, "
            f"connected={row.get('connected')}, "
            f"status={row.get('status')}, note={row.get('note')}"
        )
    lines.append(
        "- Do not invent App Store / Play / Web revenue beyond these sources. "
        "Do not sum AdMob with App Store proceeds or across currencies. "
        "Do not force a Revenue experiment solely because this block exists "
        "(including a single small IAP)."
    )
    return lines


def build_planner_prompt(
    report: AnalyzeResponse,
    *,
    growth_md: str | None = None,
    known_events: list[KnownEvent] | None = None,
) -> str:
    """Build Planner input from Analyzer output + observed summary (not raw Actions copy)."""
    analysis = report.analysis or {}
    finding = analysis.get("mostImportantFinding") or analysis.get(
        "most_important_finding"
    ) or ""
    facts = analysis.get("facts") or []
    speculation = analysis.get("speculation") or []

    # Analyzer actions are context only — Planner must not mirror them.
    actions = analysis.get("actions") or []
    action_lines = []
    for action in actions:
        if isinstance(action, dict):
            action_lines.append(
                f"  - rank={action.get('rank')}: {action.get('title')} "
                f"(basis={action.get('basis') or 'n/a'})"
            )

    period = report.period or {}
    app = report.app or {}
    scope_lines = [
        f"- {item.source}: {item.scope}" for item in (report.data_scope or [])
    ]

    metric_lines: list[str] = []
    metrics = report.metrics or {}
    for key in ("appStore", "ga4", "admob", "web"):
        group = metrics.get(key)
        if group is not None:
            metric_lines.extend(_metric_lines(group))

    product = getattr(report, "product", None) or {}
    channels = getattr(report, "channels", None) or []
    channel_lines: list[str] = []
    if product:
        channel_lines.append(
            f"- product: id={product.get('id')}, name={product.get('name')}, "
            f"type={product.get('type')}"
        )
    for ch in channels:
        if isinstance(ch, dict):
            caps = ch.get("capabilities") or []
            cap_bit = (
                f", capabilities={caps}"
                if caps
                else ""
            )
            channel_lines.append(
                "  - "
                f"id={ch.get('id')}, kind={ch.get('kind')}, status={ch.get('status')}, "
                f"connected={ch.get('connected')}"
                + (f", domain={ch.get('domain')}" if ch.get("domain") else "")
                + (
                    f", propertyId={ch.get('propertyId')}"
                    if ch.get("propertyId")
                    else ""
                )
                + cap_bit
            )
            if caps and ch.get("id") == "web":
                channel_lines.append(
                    "    (capabilities = declared what users CAN do on Web; "
                    "NOT measured usage; NOT equal to site-wide Web GA4 metrics)"
                )
    if not channel_lines:
        channel_lines = ["- (no product config — env-only single-app mode)"]

    if growth_md:
        growth_block = [
            "GROWTH.md (standing constraints — MUST obey when choosing experiments):",
            growth_md.strip(),
            "",
            "Apply GROWTH.md to filter tools, time, budget, analytics cost, and execution.",
            "Do not propose unavailable tools or paid ads. Prefer existing GA4 events.",
            "All experiments are proposals for human approval only.",
            "",
        ]
    else:
        growth_block = [
            "GROWTH.md: (not provided — no standing budget/tool constraints file)",
            "",
        ]

    events = known_events or []
    if events:
        known_block = [
            "KNOWN EVENTS (temporary human context — NOT proven causes):",
            "Use these as prioritization context only. Never assert Event → Metric causation.",
            "Correlation / coincidence / 'may partly explain' language only.",
            *[event.prompt_line() for event in events],
            "",
        ]
    else:
        known_block = [
            "KNOWN EVENTS: (none provided for this period / product)",
            "",
        ]

    parts = [
        "PLANNER INPUT (from Indie Growth Agent Analyzer + observed metrics)",
        "",
        *growth_block,
        *known_block,
        "PRODUCT / CHANNELS:",
        *channel_lines,
        "",
        "APP:",
        f"- name: {app.get('name')}",
        f"- bundleId: {app.get('bundleId')}",
        f"- territory: {app.get('territory')}",
        "",
        "PERIOD:",
        f"- label: {period.get('label')}",
        f"- start→end: {period.get('start')} → {period.get('end')}",
        f"- lookbackDays: {period.get('lookbackDays')}",
        f"- comparison: {period.get('comparisonLabel')}",
        "",
        "DATA SCOPE:",
        *(scope_lines or ["- (none)"]),
        "",
        "SUMMARY METRICS:",
        *(metric_lines or ["- (none)"]),
        "",
        "REVENUE SUMMARY (Phase 1 may be AdMob-only; optional total omitted):",
        *_revenue_summary_lines(report),
        "",
        "ANALYZER MOST IMPORTANT FINDING:",
        finding or "(empty)",
        "",
        "ANALYZER FACTS:",
        *([f"- {f}" for f in facts] if facts else ["- (none)"]),
        "",
        "ANALYZER SPECULATION:",
        *([f"- {s}" for s in speculation] if speculation else ["- (none)"]),
        "",
        "ANALYZER ACTIONS (context only — do NOT copy into experiments):",
        *(action_lines or ["- (none)"]),
        "",
        "TASK:",
        "1) Use growth_playbook from Growth Agent MCP to retrieve relevant playbooks",
        "   for the situation described by Facts / Finding / metrics.",
        "2) If GROWTH.md is present, filter every candidate through it.",
        "3) If Known Events are present, use them to re-prioritize (especially spikes",
        "   that may already have a temporary explanation) — without asserting causation.",
        "4) Weigh Product growth / Conversion / Engagement (App) / Engagement (Web) /",
        "   Revenue from Facts. Do not invent SEO/Web experiments only because Web",
        "   channel or a Web capability exists. Do not treat site-wide Web metrics as",
        "   feature usage of a capability. Path page views ≠ calculation; form_submit",
        "   @ path ≠ score_calculated; appstore_click ≠ ASC download. Do not create",
        "   Web → ASC download funnels. Do not create a Revenue experiment only",
        "   because RevenueSummary exists. Zero Web / Revenue / Measurement",
        "   experiments can be correct.",
        "5) Decide 0–3 Growth Experiments. Prefer none or Measurement when weak.",
        "6) Fill the structured Planner output.",
    ]
    return "\n".join(parts)


def _create_mcp_client(settings: GrowthMcpSettings) -> MCPClient:
    params = StdioServerParameters(
        command=settings.command,
        args=list(settings.args),
        cwd=settings.cwd,
    )
    return MCPClient(lambda: stdio_client(params), prefix="growth")


def _experiment_to_api_dict(
    exp: GrowthExperiment,
    *,
    analysis_run_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "title": exp.title,
        "hypothesis": exp.hypothesis,
        "why": exp.why,
        "action": exp.action,
        "targetMetric": exp.target_metric,
        "expectedSignal": exp.expected_signal,
        "suggestedDuration": exp.suggested_duration,
        "evidence": exp.evidence,
        "playbookReference": exp.playbook_reference,
    }
    if analysis_run_id:
        payload["analysisRunId"] = analysis_run_id
    return payload


def _empty_planner_fields(
    *,
    status: str,
    error: str | None = None,
    known_events_considered: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "growth_experiments": [],
        "planner_status": status,
        "planner_error": error,
        "playbooks_consulted": [],
        "known_events_considered": list(known_events_considered or []),
        "known_events_used": [],
    }


def _resolve_growth_md(growth_md: Any) -> str | None:
    if growth_md is _AUTO:
        return get_growth_md_text()
    if growth_md is None:
        return None
    return str(growth_md)


def _resolve_known_events(
    report: AnalyzeResponse,
    known_events: Any,
) -> list[KnownEvent]:
    if known_events is _AUTO:
        period = report.period or {}
        app = report.app or {}
        return get_known_events_for_report(
            period_start=period.get("start"),
            period_end=period.get("end"),
            bundle_id=app.get("bundleId") or app.get("bundle_id"),
        )
    if known_events is None:
        return []
    return list(known_events)


def run_planner(
    report: AnalyzeResponse,
    *,
    growth_md: Any = _AUTO,
    known_events: Any = _AUTO,
) -> AnalyzeResponse:
    """Run Planner with Growth MCP. Raises on failure (caller should catch).

    growth_md / known_events default to auto-load from disk.
    Pass None to force omit (for A/B comparison runs).
    """
    settings = get_growth_mcp_settings()
    resolved_events = _resolve_known_events(report, known_events)
    considered = [event.to_dict() for event in resolved_events]

    if settings is None:
        logger.info("Growth MCP not configured; skipping Planner")
        return report.model_copy(
            update=_empty_planner_fields(
                status="skipped: GROWTH_MCP_COMMAND not set",
                known_events_considered=considered,
            )
        )

    lang = _normalize_language(report.language)
    resolved_md = _resolve_growth_md(growth_md)
    prompt = build_planner_prompt(
        report,
        growth_md=resolved_md,
        known_events=resolved_events,
    ) + _language_instruction(lang)

    logger.info(
        "Running Planner language=%s growth_md=%s known_events=%s mcp_command=%s args=%s",
        lang,
        "yes" if resolved_md else "no",
        len(resolved_events),
        settings.command,
        list(settings.args),
    )

    mcp_client = _create_mcp_client(settings)
    # Enter the MCP session once, then pass already-listed tools to Agent.
    # Do NOT pass the live MCPClient into Agent(tools=...) after start() — Agent
    # would call start() again and fail with "session is currently running".
    with mcp_client:
        tools = mcp_client.list_tools_sync()
        planner_agent = Agent(
            system_prompt=PLANNER_SYSTEM_PROMPT,
            tools=tools,
            model=build_model(),
        )
        result = planner_agent(
            prompt,
            structured_output_model=PlannerStructuredOutput,
            structured_output_prompt=PLANNER_STRUCTURED_PROMPT,
        )

    structured = result.structured_output
    if structured is None:
        raise RuntimeError("Planner returned no structured output")

    experiments = list(structured.experiments or [])[:3]
    run_id = getattr(report, "analysis_run_id", None) or None
    api_experiments = [
        _experiment_to_api_dict(e, analysis_run_id=run_id) for e in experiments
    ]
    status = (structured.summary or "").strip() or (
        f"{len(api_experiments)} experiment(s) proposed"
    )

    return report.model_copy(
        update={
            "growth_experiments": api_experiments,
            "planner_status": status,
            "planner_error": None,
            "playbooks_consulted": list(structured.playbooks_consulted or []),
            "known_events_considered": considered,
            "known_events_used": list(structured.known_events_used or []),
        }
    )


def attach_planner_safe(
    report: AnalyzeResponse,
    *,
    growth_md: Any = _AUTO,
    known_events: Any = _AUTO,
) -> AnalyzeResponse:
    """Run Planner after Analyzer; never raise — Analyzer result is preserved."""
    try:
        return run_planner(report, growth_md=growth_md, known_events=known_events)
    except Exception as exc:  # noqa: BLE001 — Planner is best-effort
        logger.exception("Planner failed; returning Analyzer result only")
        message = f"{type(exc).__name__}: {str(exc)[:400]}"
        try:
            considered = [
                e.to_dict()
                for e in _resolve_known_events(report, known_events)
            ]
        except Exception:  # noqa: BLE001
            considered = []
            logger.exception("Known events resolve failed during Planner fallback")
        return report.model_copy(
            update=_empty_planner_fields(
                status="planner_failed",
                error=message,
                known_events_considered=considered,
            )
        )
