"""Format ASC (+ optional GA4) facts into Indie Growth Agent input text."""

from __future__ import annotations

from asc.snapshot import AscGrowthSnapshot, PeriodTotals
from ga4.snapshot import Ga4GrowthSnapshot, Ga4PeriodTotals


def _fmt_int(n: int) -> str:
    return f"{n:,}"


def _fmt_pct(change: float | None) -> str:
    if change is None:
        return "n/a (no prior-period baseline)"
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.1f}%"


def _fmt_rate(rate: float | None) -> str:
    if rate is None:
        return "n/a"
    return f"{rate * 100:.2f}%"


def _source_line(label: str, values: dict[str, int], total: int) -> str:
    """Always show the remainder, so recognized buckets are never read as the whole."""
    if total <= 0:
        return f"- {label}: (no rows in this period)"
    parts = [f"{k}={_fmt_int(v)}" for k, v in values.items()]
    parts.append(f"unattributed={_fmt_int(total - sum(values.values()))}")
    return f"- {label}: {', '.join(parts)} (sums to total {_fmt_int(total)})"


def _period_block(title: str, period: PeriodTotals) -> list[str]:
    return [
        f"{title} ({period.start} → {period.end}, {period.days_with_data} days with rows):",
        f"- Impressions: {_fmt_int(period.impressions)}",
        f"- Product page views: {_fmt_int(period.product_page_views)}",
        f"- First-time downloads: {_fmt_int(period.first_time_downloads)}",
        f"- Impression → page view rate: {_fmt_rate(period.impression_to_page_view_rate)}",
        f"- Page view → download rate: {_fmt_rate(period.page_view_to_download_rate)}",
        f"- Impression → download rate: {_fmt_rate(period.impression_to_download_rate)}",
        _source_line("Impressions by source", period.impressions_by_source, period.impressions),
        _source_line(
            "First-time downloads by source",
            period.downloads_by_source,
            period.first_time_downloads,
        ),
    ]


def _ga4_period_block(title: str, period: Ga4PeriodTotals, event_order: tuple[str, ...]) -> list[str]:
    lines = [
        f"{title} ({period.start} → {period.end}):",
        f"- Active users (period-scoped activeUsers): {_fmt_int(period.active_users)}",
        f"- Sessions (period total): {_fmt_int(period.sessions)}",
        f"- Screen/page views (period total screenPageViews): {_fmt_int(period.screen_page_views)}",
    ]
    if event_order:
        lines.append("- Key event counts (eventCount, configured events only):")
        for name in event_order:
            lines.append(f"  - {name}: {_fmt_int(period.key_event_counts.get(name, 0))}")
    return lines


def _ga4_key_event_changes(ga4: Ga4GrowthSnapshot) -> list[str]:
    lines = [
        "GA4 key-event period-over-period change "
        "(fact, from the two GA4 periods above only; interpret an event only via "
        "GA4 EVENT DEFINITIONS, and never read a cause into the change):"
    ]
    for name in ga4.key_event_names:
        cur = ga4.current.key_event_counts.get(name, 0)
        prev = ga4.previous.key_event_counts.get(name, 0)
        lines.append(f"- {name}: {_fmt_pct(_pct_change(cur, prev))} (current={_fmt_int(cur)}, previous={_fmt_int(prev)})")
    return lines


def _pct_change(current: int, previous: int) -> float | None:
    if previous <= 0:
        return None
    return (current - previous) / previous * 100.0


def _asc_coverage_notes(snapshot: AscGrowthSnapshot) -> list[str]:
    notes: list[str] = []
    expected = snapshot.lookback_days
    if snapshot.current.days_with_data < expected:
        notes.append(
            f"- ASC current period has rows on only {snapshot.current.days_with_data}/{expected} days; "
            "do not treat missing days as zeros unless stated."
        )
    if snapshot.previous.days_with_data < expected:
        notes.append(
            f"- ASC previous period has rows on only {snapshot.previous.days_with_data}/{expected} days; "
            "period-over-period % changes may be unstable."
        )
    if snapshot.current.first_time_downloads == 0 and snapshot.previous.first_time_downloads == 0:
        notes.append(
            "- ASC first-time downloads are 0 under the current territory filter. "
            "Do not assume global downloads without other-territory data."
        )
    if not notes:
        notes.append("- ASC period coverage looks complete for the configured lookback window.")
    return notes


def _period_alignment_notes(
    asc: AscGrowthSnapshot,
    ga4: Ga4GrowthSnapshot | None,
) -> list[str]:
    notes = [
        f"- ASC current period: {asc.current.start} → {asc.current.end}",
        f"- ASC previous period: {asc.previous.start} → {asc.previous.end}",
    ]
    if ga4 is None:
        notes.append("- GA4 periods: not available (GA4 not connected).")
        return notes

    notes.extend(
        [
            f"- GA4 current period: {ga4.current.start} → {ga4.current.end}",
            f"- GA4 previous period: {ga4.previous.start} → {ga4.previous.end}",
        ]
    )
    same_current = (
        asc.current.start == ga4.current.start and asc.current.end == ga4.current.end
    )
    same_previous = (
        asc.previous.start == ga4.previous.start and asc.previous.end == ga4.previous.end
    )
    if same_current and same_previous:
        notes.append(
            "- ASC and GA4 comparison windows match on calendar dates for this run."
        )
    else:
        notes.append(
            "- ASC and GA4 comparison windows DO NOT match. Treat each source's "
            "numbers only within that source's stated periods. Do not combine, "
            "ratio, or narrate them as the same time window."
        )
    return notes


def _population_scope_notes(
    asc: AscGrowthSnapshot,
    ga4: Ga4GrowthSnapshot | None,
) -> list[str]:
    """State what each source actually counts. Matching dates != matching populations."""
    territory = (
        "every territory (no territory filter)"
        if asc.territory == "ALL"
        else f"territory {asc.territory} only"
    )
    notes = [
        "- App Store Connect counts App Store activity for this one app record on",
        f"  Apple platforms, restricted to {territory}.",
    ]
    if ga4 is None:
        notes.append("- GA4: not connected for this run.")
        return notes

    notes.extend(
        [
            f"- GA4 counts everything reported into property {ga4.property_resource}.",
            "  This run sends NO country filter and NO platform filter, so GA4 numbers",
            "  cover every platform (iOS, Android, web — whatever that property receives)",
            "  and every country, including traffic that never touches the App Store.",
            "- The two sources therefore describe DIFFERENT populations. GA4 is not a",
            "  superset or subset of ASC in any stated way, and this input does NOT",
            "  establish that they match.",
            "- Therefore: do NOT divide, ratio, subtract, or funnel one source's numbers",
            "  into the other's. first_open vs first-time downloads is not an",
            "  install-to-open rate here. Do not describe ASC and GA4 metrics as stages",
            "  of one funnel, even when the calendar windows are identical.",
        ]
    )
    return notes


def _ga4_event_definition_notes(ga4: Ga4GrowthSnapshot) -> list[str]:
    """Declared event meanings are config-supplied facts, not model guesses."""
    lines = [
        "GA4 EVENT DEFINITIONS (developer-declared; treat as fact)",
    ]
    if not ga4.event_definitions:
        lines.append(
            "- None supplied. Treat every GA4 event name as an opaque label."
        )
    for item in ga4.event_definitions:
        lines.append(f"- {item.name} [{item.source}]: {item.definition}")
    lines.append(
        "- These definitions state what each event measures. You may rely on them"
    )
    lines.append(
        "  as facts and may ground in-product actions in them."
    )
    lines.append(
        "- A definition never explains WHY a count moved. Do not turn it into a cause."
    )
    lines.append(
        "- A definition states the trigger only. It does not rank the event's"
    )
    lines.append(
        "  importance. That a count rose or fell is a Fact; that this means more or"
    )
    lines.append(
        "  less user value, engagement, satisfaction, or product health is"
    )
    lines.append(
        "  Speculation and must sit in a Speculation frame."
    )
    undefined = ga4.undefined_event_names
    if undefined:
        lines.append("- No definition supplied for: " + ", ".join(undefined) + ".")
        lines.append(
            "  Treat those names as opaque labels: report their counts only and do"
        )
        lines.append("  not infer what they mean in-product.")
    else:
        lines.append(
            "- Any GA4 event not listed above is an opaque label: report counts only,"
        )
        lines.append("  never infer meaning from the name.")
    return lines


def _ga4_confirmed_capabilities(ga4: Ga4GrowthSnapshot) -> list[str]:
    lines = [
        "- GA4 Data API metrics fetched into the facts below (period-scoped, no date dimension):",
        "  activeUsers, sessions, screenPageViews,",
        "  and period-over-period % change for those three metrics.",
    ]
    if ga4.key_event_names:
        names = ", ".join(ga4.key_event_names)
        lines.extend(
            [
                f"- GA4 key eventCount fetched ONLY for: {names}.",
                "- Event meaning comes only from GA4 EVENT DEFINITIONS below; names",
                "  without a definition there stay opaque labels.",
                "- Do not assert why an eventCount rose or fell unless the provided",
                "  numbers alone support a purely observational statement.",
            ]
        )
    else:
        lines.append(
            "- GA4 key/custom events: not fetched in this run (do not invent event counts)."
        )
    lines.extend(
        [
            "- Other recorded GA4 events (e.g. ad_click, settings_changed, app_update,",
            "  os_update, app_remove) are intentionally omitted from this input.",
            "- GA4 retention, cohorts, user attributes/demographics, device breakdown,",
            "  individual event streams, funnels, paths, audiences, and explorations",
            "  are NOT fetched — do not speculate about them.",
            "- No other GA4 surfaces are confirmed available in this input.",
        ]
    )
    return lines


def format_agent_input(
    snapshot: AscGrowthSnapshot,
    *,
    ga4: Ga4GrowthSnapshot | None = None,
    ga4_status: str | None = None,
) -> str:
    date_span = (
        f"{snapshot.daily[0].date} → {snapshot.daily[-1].date}"
        if snapshot.daily
        else "n/a"
    )
    ga4_connected = ga4 is not None

    confirmed = [
        "CONFIRMED CAPABILITIES (from this run)",
        "- App Store Connect Analytics Reports already fetched into the facts below:",
        "  impressions, product page views, first-time downloads,",
        "  source breakdown (search/browse/referrer) plus an explicit 'unattributed'",
        "  remainder so the buckets always sum to the stated total — Apple reports",
        "  gift card / promo code / MDM installs as Unavailable and withholds referrer",
        "  sources below a privacy threshold, so unattributed > 0 is expected and is",
        "  NOT a discovery channel you can act on,",
        "  derived conversion rates from those totals,",
        "  and period-over-period change computed from those totals.",
        "- No other ASC analytics surfaces are confirmed available in this input.",
    ]
    if ga4_connected and ga4 is not None:
        confirmed.extend(_ga4_confirmed_capabilities(ga4))
    else:
        confirmed.append(
            f"- {ga4_status or 'GA4: not connected yet (do not invent values).'}"
        )

    lines = [
        "DATA CONTRACT",
        "- Connected sources for this run are listed under CONFIRMED CAPABILITIES.",
        "- AdMob: not connected yet (do not invent values).",
        "- Facts: only what is directly confirmable from the provided data below.",
        "- Speculation: label every inference beyond that data as Speculation.",
        "- Causality: if cause/effect is not proven by the data, do not assert it.",
        "  Prefer 'largest observed change' / 'appears associated with' over",
        "  'primary cause' / 'did not cause' / 'this proves'.",
        "- Period alignment: ASC and GA4 may cover different calendar windows.",
        "  Use PERIOD ALIGNMENT below. Never treat misaligned sources as the same period.",
        "- Population scope: even with identical dates, ASC and GA4 count different",
        "  populations. Use POPULATION SCOPE below. Never ratio or funnel one source",
        "  into the other unless that section states the populations match.",
        "- Platform capabilities: propose ONLY items listed under CONFIRMED",
        "  CAPABILITIES or ALLOWED LISTING ACTIONS below. Do not propose other ASC",
        "  or GA4 analytics features/reports/tiers/thresholds/dimensions even with",
        "  'if available' / '可能なら'. Omit unconfirmed capabilities entirely.",
        "- Do not invent industry averages, benchmarks, or unstated causal explanations.",
        "",
        *confirmed,
        "",
        "ALLOWED LISTING ACTIONS (always allowed to suggest)",
        "- App Store metadata / product page edits: title, subtitle, keyword field,",
        "  description, promotional text, screenshots.",
        "",
        "DISALLOWED UNLESS EXPLICITLY PRESENT IN INPUT",
        "- keyword-level analytics, analytics tiers, minimum threshold rules,",
        "- GA4 retention/cohorts, user attributes, demographics, device splits,",
        "  individual/unlisted events, funnels, paths, audiences, explorations,",
        "- Interpreting a GA4 event that has no entry under GA4 EVENT DEFINITIONS,",
        "  asserting a cause for any eventCount change, treating the ASC",
        "  'unattributed' remainder as a channel, and any other unlisted ASC/GA4",
        "  analytics feature or data-fetch method.",
        "",
        "APP",
        f"- Name: {snapshot.app.name}",
        f"- Bundle ID: {snapshot.app.bundle_id}",
        f"- App Store Connect app ID: {snapshot.app.id}",
        f"- ASC territory filter: {snapshot.territory}",
        f"- Available daily ASC row span: {date_span} ({len(snapshot.daily)} dates)",
        f"- Latest date with ASC analytics rows: {snapshot.latest_processing_date}",
        f"- ASC configured lookback: {snapshot.lookback_days} days vs previous {snapshot.lookback_days} days",
    ]

    if ga4_connected and ga4 is not None:
        lines.extend(
            [
                f"- GA4 property: {ga4.property_resource}",
                f"- GA4 configured lookback: {ga4.lookback_days} days vs previous {ga4.lookback_days} days",
            ]
        )

    lines.extend(
        [
            "",
            "PERIOD ALIGNMENT",
            *_period_alignment_notes(snapshot, ga4 if ga4_connected else None),
            "",
            "POPULATION SCOPE (what each source counts)",
            *_population_scope_notes(snapshot, ga4 if ga4_connected else None),
            "",
            "DATA QUALITY NOTES (facts about coverage)",
            *_asc_coverage_notes(snapshot),
        ]
    )
    if ga4_connected and ga4 is not None:
        lines.extend(f"- {note}" for note in ga4.notes)

    lines.extend(
        [
            "",
            "APP STORE CONNECT — FACTS",
            *_period_block("Current period", snapshot.current),
            "",
            *_period_block("Previous period", snapshot.previous),
            "",
            "ASC period-over-period change (fact, from the two ASC periods above only):",
            f"- Impressions: {_fmt_pct(snapshot.change_impressions_pct())}",
            f"- Product page views: {_fmt_pct(snapshot.change_page_views_pct())}",
            f"- First-time downloads: {_fmt_pct(snapshot.change_downloads_pct())}",
        ]
    )

    if ga4_connected and ga4 is not None:
        lines.extend(
            [
                "",
                *_ga4_event_definition_notes(ga4),
                "",
                "GA4 — FACTS",
                *_ga4_period_block("Current period", ga4.current, ga4.key_event_names),
                "",
                *_ga4_period_block("Previous period", ga4.previous, ga4.key_event_names),
                "",
                "GA4 period-over-period change (fact, from the two GA4 periods above only):",
                f"- Active users (period): {_fmt_pct(ga4.change_active_users_pct())}",
                f"- Sessions: {_fmt_pct(ga4.change_sessions_pct())}",
                f"- Screen/page views: {_fmt_pct(ga4.change_screen_page_views_pct())}",
                "",
                *_ga4_key_event_changes(ga4),
            ]
        )
    else:
        lines.extend(
            [
                "",
                "GA4 — FACTS",
                f"- {ga4_status or 'GA4: not connected yet (do not invent values).'}",
            ]
        )

    lines.extend(
        [
            "",
            "TASK",
            "Using only the facts above, identify what appears to be limiting growth",
            "and what the developer should prioritize next.",
            "Keep Facts and Speculation clearly separated.",
            "Describe relationships with observation-based language when causality is unproven.",
            "If ASC and GA4 periods differ, analyze each source in its own window;",
            "do not present them as one shared period.",
            "Regardless of the periods, keep ASC and GA4 numbers in their own",
            "populations per POPULATION SCOPE: no cross-source ratios or funnels.",
            "For GA4 key events: interpret an event only through GA4 EVENT DEFINITIONS,",
            "report observed counts/changes, and never assert why a count changed.",
            "For Top 3 actions: use ALLOWED LISTING ACTIONS, GA4 EVENT DEFINITIONS, and",
            "conclusions from CONFIRMED CAPABILITIES / facts only. Do not mention",
            "unconfirmed ASC/GA4 analytics features, even conditionally.",
            "Return exactly this shape:",
            "1. Most important finding",
            "   - Facts: only what the numbers above state.",
            "   - Speculation: inference beyond them, or \"none\".",
            "2. Why it matters",
            "   - Facts: ...",
            "   - Speculation: ...",
            "3. Top 3 actions to take today",
            "   - For each action add \"Basis:\" naming the specific fact or event",
            "     definition it rests on. Drop any action you cannot ground that way.",
            "Never leave a Facts or Speculation frame empty, and never place",
            "speculation inside a Facts frame.",
        ]
    )
    return "\n".join(lines)
