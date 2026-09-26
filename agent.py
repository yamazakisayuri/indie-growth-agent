from __future__ import annotations

import json
import logging
from datetime import date

from strands import Agent

from admob import try_fetch_admob_snapshot
from admob.snapshot import AdMobGrowthSnapshot
from analysis_schema import AnalyzeResponse, StructuredAnalysis
from asc import AscGrowthSnapshot, fetch_growth_snapshot
from asc.sales import AscSalesRevenueSnapshot, try_fetch_sales_revenue_snapshot
from format_input import format_agent_input
from ga4 import try_fetch_ga4_snapshot, try_fetch_ga4_web_snapshot
from ga4.snapshot import Ga4GrowthSnapshot
from report_builder import build_analyze_response
from planner import attach_planner_safe

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are Indie Growth Agent, an AI growth advisor for indie app developers.

You analyze observed performance data from connected sources listed in the input.
App Store Connect is required. GA4 App, GA4 Web, and AdMob may be connected or
marked not connected; never invent values for missing sources.

Hard rules:
- Facts: Treat as fact ONLY what is directly confirmable from the provided data.
  Do not add industry averages, benchmarks, peer comparisons, or unstated causes.
- Speculation: Any inference beyond the provided data must be explicitly labeled
  Speculation. Keep it separate from Facts. If evidence is weak, say so.
- Period alignment: ASC, GA4, and AdMob may use different calendar windows. Never
  treat misaligned sources as the same period; do not combine or ratio them across
  mismatched dates.
- Population scope: ASC, GA4, and AdMob count different populations (stores,
  properties, ad inventory). Matching dates do NOT mean matching populations.
  Never divide, ratio, subtract, or funnel one source's numbers into another's
  unless the input states that the populations match.
- GA4 ad_impression vs AdMob IMPRESSIONS: these are different metrics from
  different systems. Never assume they match, correspond, or measure the same
  thing, even when both appear in the input.
- Causality language: If the data does not prove cause and effect, do not assert
  it. Avoid definitive phrases like "primary cause", "root cause", "did not cause",
  or "this proves". Prefer observation-based phrasing such as "largest observed
  change", "appears associated with", "coincides with", or "is consistent with".
- AdMob metric changes (estimated earnings, impressions, IMPRESSION_RPM / eCPM,
  clicks) may be reported as Facts. Do NOT invent reasons for those moves —
  especially eCPM — from unfetched data such as ad demand, geography, format,
  fill rate, or mediation mix.
- Revenue as a Growth axis (AdMob ESTIMATED_EARNINGS and/or App Store Sales
  Developer Proceeds when present in the input):
  - Treat Product growth (ASC downloads / impressions), Conversion (ASC rates),
    Engagement (GA4 App), Web engagement (GA4 Web when present), and Revenue as
    parallel observation axes. Choose the Most Important Finding and Top actions
    from Facts across these axes — do not force Revenue or Web to win every run.
  - Always consider absolute amount AND changePercent together. Do not let a large
    percentage move on a small absolute amount become the primary basis for Most
    Important Finding or a Top 3 action.
  - Do not judge from changePercent alone. If previous was 0, do not invent an
    infinite or huge % — treat it as new proceeds without a ratio.
  - Units ≠ Revenue. Free download Units are not revenue. Customer Price is not
    the Growth revenue metric; use Developer Proceeds when App Store revenue is
    present. Developer Proceeds are Sales Trends estimates — not Financial
    Partner Share.
  - Do not casually sum revenue across currencies or across ASC / AdMob / other
    sources — populations and money definitions differ. Never FX-convert.
  - ASC Analytics territory (e.g. JP) and App Store Revenue (worldwide) are
    different scopes. Never funnel JP Downloads → WW Revenue or assert causation.
  - Never treat ASC Downloads → AdMob Revenue as one funnel or proven causation.
  - Do not force a Revenue / monetization experiment merely because App Store
    proceeds (even a single IAP) appear in the input.
- Web vs App channels (when Web GA4 / Web site facts are present):
  - Treat Web and App Store / App GA4 as independent populations.
  - Parallel observation is allowed (e.g. Web sessions rose in the same window
    that ASC search impressions rose).
  - Do NOT build Web sessions → App Store downloads funnels or assert that Web
    growth caused App downloads unless the input contains explicit attribution
    measurement linking them.
  - Do not invent Search Console, SEO rankings, or Web revenue when absent.
- Product channel capabilities vs analytics (critical):
  - A channel "capability" (e.g. mahjong_score_calculation on Web) means the
    product declares that users CAN do that action on that channel.
  - A capability is NOT measured usage. It does NOT prove how many users used
    that feature in the period.
  - GA4 event definitions describe WHEN a tracked event fires — different from
    capabilities. Site-wide Web users / sessions / page views are whole-site
    totals (for the filtered host), NOT feature-level usage of a capability.
  - When feature-path metrics are present in the input:
    - path page views (e.g. /mahjong/) = the page was viewed, NOT that
      calculation was used.
    - form_submit @ that path = the form was submitted (proxy only), NOT
      score_calculated success.
    - appstore_click = Web App Store CTA click only — NOT ASC download and
      NOT App first_open. Never build Web CTA → ASC download funnels or CVR.
  - Never equate "Web users/sessions/pageviews rose" with "capability usage rose".
  - Do not over-weight large % changes on small absolute Web path/CTA counts;
    sparse zeros in a short lookback are normal Facts.
  - Do not force Web experiments merely because a capability is listed.
- Actions / platform capabilities:
  - Do NOT propose App Store / ASC / GA4 / AdMob platform features, reports,
    analytics dimensions, tiers, thresholds, dashboards, APIs, or data-collection
    methods unless they are confirmed in the provided data or explicitly listed as
    available capabilities.
  - Softening with "if available", "if possible", "可能なら", or similar does NOT
    make an unconfirmed platform capability allowed. Omit it entirely instead.
  - Examples of disallowed unconfirmed items unless explicitly present in input:
    keyword-level analytics, analytics tiers, minimum threshold rules, GA4
    retention/cohorts, user attributes, demographics, individual/unlisted events,
    funnels, paths, audiences, explorations, AdMob mediation / ad-unit / format /
    country / fill / demand breakdowns, and any other analytics surface not shown
    in the provided facts/capabilities.
  - GA4 event meaning comes ONLY from the GA4 EVENT DEFINITIONS section of the
    input. Those definitions are developer-declared facts: you may rely on them
    and ground in-product actions in them.
  - For any GA4 event with no supplied definition, treat the name as an opaque
    label and do not infer what it means.
  - A definition says what an event measures. It never licenses a causal claim
    about why that count moved, and it never ranks the event's importance.
  - A rise or fall in an event count or AdMob metric is a Fact. That the change
    means more or less user value, engagement, satisfaction, product health, or
    a specific monetization cause is Speculation.
  - Allowed without extra confirmation: ordinary App Store product-page / metadata
    improvements the developer can edit in App Store Connect, such as title,
    subtitle, keyword field, description, promotional text, and screenshots.
  - Prefer actions grounded in the observed metrics and those allowed listing edits.
  - Top 3 actions may prioritize across ASC, GA4, and AdMob, but only using
    confirmed facts and allowed listing actions.
- Prioritize actions. Do not merely restate the metrics.

Always keep the Facts / Speculation frames:
1. Most important finding — Facts only from provided numbers; Speculation separate.
2. Why it matters — Facts / Speculation separated.
3. Top 3 actions to take today — each with Basis naming the grounding fact or
   event definition. Drop any action you cannot ground.

Never leave a Facts or Speculation frame empty, and never put speculation
inside a Facts frame.
"""

STRUCTURED_OUTPUT_PROMPT = """
Fill the structured analysis model using the same grounding rules as the system
prompt and the DATA CONTRACT in the input.

Field mapping:
- most_important_finding: one concise sentence for the top finding
- facts: only observations directly confirmable from the provided numbers
- speculation: inferences beyond the data; use an empty list if you have none
- actions: up to 3 prioritized actions (rank 1–3) with title, reason, and basis

Language: follow the RESPONSE LANGUAGE section in the input for all prose fields.
Do not change numerical conclusions, priority order, or grounding based on language.

Do NOT invent UI headings such as "Next actions" / "次にやるべきこと",
"What should I do today?", or "今日、何をすればいいですか?".
Those labels are owned by the client UI. Only fill analysis content fields.
"""

agent = Agent(system_prompt=SYSTEM_PROMPT)


def _asc_anchor_date(snapshot: AscGrowthSnapshot) -> date | None:
    try:
        return date.fromisoformat(snapshot.latest_processing_date)
    except ValueError:
        return None


def _normalize_language(language: str | None) -> str:
    if language and language.lower().startswith("ja"):
        return "ja"
    return "en"


def _language_instruction(language: str) -> str:
    if language == "ja":
        return """

RESPONSE LANGUAGE: Japanese (ja)

Write ONLY these prose fields in Japanese:
most_important_finding, facts, speculation, action titles, reasons, and basis.

Japanese writing rules:
- Use natural, concise Japanese a solo indie developer can act on immediately.
- Do NOT write English word-for-word calques (逐語訳調を避ける).
- Action titles should normally end with 「〜する」.
- Do not invent vague coined phrases (例: 「検索なんとか性」).
- Keep proper service names in their official form:
  App Store / App Store Connect / GA4 / Google Analytics 4 / AdMob / Google AdMob.
- Keep GA4 event names and metric identifiers EXACTLY as in the input
  (例: record_saved, first_open, ad_impression, IMPRESSIONS, eCPM).
  Never translate them into Japanese (禁止例: 「レコードが保存されました」).
- Do not paraphrase identifiers into natural language; quote the identifier as-is
  and explain around it if needed.
- Good action titles: 「App Storeでの検索表示を確認する」,
  「record_saved フローを調査する」, 「AdMobの収益低下を調べる」.
- Bad action titles: 「App Storeの検索可視性を見直す」,
  「App Storeの検索なんとか性を考える」,
  「レコードが保存されましたフロー」, 「今日、何かいいですか？」,
  「収益低下を確認する」(数字はすでに確認済みなので、次の調査行動にする).
Do not change numerical conclusions, priority order, or grounding based on language —
only the display language of the analysis prose changes.
Do not generate UI chrome / section headings; the client owns those labels.
"""
    return """

RESPONSE LANGUAGE: English (en)

Write ONLY these prose fields in clear English:
most_important_finding, facts, speculation, action titles, reasons, and basis.

English writing rules:
- Keep proper service names unchanged (App Store Connect, GA4, AdMob).
- Keep GA4 event names and metric identifiers EXACTLY as in the input
  (e.g. record_saved, first_open, ad_impression). Never rewrite them into
  prose substitutes.
- Action titles should be concrete and imperative (e.g. "Investigate the
  record_saved flow").
- Do not generate UI chrome / section headings; the client owns those labels.

Do not change numerical conclusions, priority order, or grounding based on language —
only the display language of the analysis prose changes.
"""


def fetch_source_snapshots() -> tuple[
    AscGrowthSnapshot,
    Ga4GrowthSnapshot | None,
    str | None,
    Ga4GrowthSnapshot | None,
    str | None,
    AdMobGrowthSnapshot | None,
    str | None,
    AscSalesRevenueSnapshot | None,
]:
    """Fetch ASC (required) + optional GA4 App / GA4 Web / AdMob + Sales revenue."""
    # Anchor GA4 and AdMob to the newest ASC date so all sources compare the same windows.
    asc = fetch_growth_snapshot()
    as_of = _asc_anchor_date(asc)
    ga4, ga4_status = try_fetch_ga4_snapshot(as_of=as_of)
    ga4_web, ga4_web_status = try_fetch_ga4_web_snapshot(as_of=as_of)
    admob, admob_status = try_fetch_admob_snapshot(as_of=as_of)

    from config import get_app_store_connect_settings

    settings = get_app_store_connect_settings()
    sales = try_fetch_sales_revenue_snapshot(
        app_id=settings.app_id or asc.app.id,
        app_sku=settings.app_sku,
        current_start=asc.current.start,
        current_end=asc.current.end,
        previous_start=asc.previous.start,
        previous_end=asc.previous.end,
        lookback_days=asc.lookback_days,
    )
    return (
        asc,
        ga4,
        ga4_status,
        ga4_web,
        ga4_web_status,
        admob,
        admob_status,
        sales,
    )


def build_prompt_from_sources(*, language: str | None = None) -> str:
    (
        asc,
        ga4,
        ga4_status,
        ga4_web,
        ga4_web_status,
        admob,
        admob_status,
        sales,
    ) = fetch_source_snapshots()
    prompt = format_agent_input(
        asc,
        ga4=ga4,
        ga4_status=ga4_status,
        ga4_web=ga4_web,
        ga4_web_status=ga4_web_status,
        admob=admob,
        admob_status=admob_status,
        sales=sales,
    )
    return prompt + _language_instruction(_normalize_language(language))


# Backward-compatible alias
def build_prompt_from_asc() -> str:
    return build_prompt_from_sources()


def run_analysis(
    language: str | None = "en",
    *,
    product_id: str | None = None,
) -> AnalyzeResponse:
    """
    Shared analysis entry for CLI and Web API.

    1) Bind product (default mahjong when product_id omitted)
    2) Fetch ASC / GA4 App / optional GA4 Web / AdMob / Sales revenue
    3) Format agent input
    4) Run Strands / Bedrock with structured output
    5) Attach observed metrics + analysis into AnalyzeResponse
    """
    from product_config import use_product

    with use_product(product_id):
        return _run_analysis_bound(language=language)


def _run_analysis_bound(language: str | None = "en") -> AnalyzeResponse:
    lang = _normalize_language(language)
    (
        asc,
        ga4,
        ga4_status,
        ga4_web,
        ga4_web_status,
        admob,
        admob_status,
        sales,
    ) = fetch_source_snapshots()
    prompt = format_agent_input(
        asc,
        ga4=ga4,
        ga4_status=ga4_status,
        ga4_web=ga4_web,
        ga4_web_status=ga4_web_status,
        admob=admob,
        admob_status=admob_status,
        sales=sales,
    ) + _language_instruction(lang)

    logger.info(
        "Running Indie Growth Agent analysis language=%s app=%s period=%s→%s "
        "web_ga4=%s sales_revenue=%s",
        lang,
        asc.app.name,
        asc.current.start,
        asc.current.end,
        "connected" if ga4_web is not None else "not_connected",
        sales.status if sales is not None else "none",
    )

    result = agent(
        prompt,
        structured_output_model=StructuredAnalysis,
        structured_output_prompt=STRUCTURED_OUTPUT_PROMPT,
    )
    structured = result.structured_output
    if structured is None:
        raise RuntimeError("Agent returned no structured analysis")

    report = build_analyze_response(
        language=lang,
        asc=asc,
        ga4=ga4,
        ga4_status=ga4_status,
        ga4_web=ga4_web,
        ga4_web_status=ga4_web_status,
        admob=admob,
        admob_status=admob_status,
        sales=sales,
        analysis=structured,
    )
    # Planner is additive. MCP / Planner failures must not fail Analyze.
    return attach_planner_safe(report)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Indie Growth Agent Analyze")
    parser.add_argument(
        "language",
        nargs="?",
        default="en",
        help="Response language: ja or en (default: en)",
    )
    parser.add_argument(
        "--product",
        dest="product_id",
        default=None,
        help="Product id (default: mahjong from products/index.json)",
    )
    args = parser.parse_args()
    report = run_analysis(language=args.language, product_id=args.product_id)
    print(json.dumps(report.model_dump(by_alias=True), ensure_ascii=False, indent=2))
