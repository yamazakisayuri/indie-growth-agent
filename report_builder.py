"""Build the Web/CLI AnalyzeResponse from live snapshots + structured Agent output.

Metrics / period / data scope come from observed snapshots (not the LLM).
Analysis text comes from StructuredAnalysis.
"""

from __future__ import annotations

from datetime import date, datetime
import uuid

from admob.snapshot import AdMobGrowthSnapshot
from analysis_schema import (
    AnalyzeResponse,
    DataScopeItem,
    MetricGroup,
    MetricItem,
    RevenueSourceItem,
    RevenueSummary,
    StructuredAnalysis,
)
from asc.snapshot import AscGrowthSnapshot
from ga4.snapshot import Ga4GrowthSnapshot


def _round_pct(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 1)


def _fmt_money(value: float, currency: str) -> str:
    if currency.upper() == "JPY":
        return f"¥{value:,.2f}"
    return f"{value:,.2f} {currency}"


def _parse_iso(day: str) -> date:
    return date.fromisoformat(day)


def _format_period_label(start: str, end: str, language: str) -> str:
    s = _parse_iso(start)
    e = _parse_iso(end)
    if language == "ja":
        if s.year == e.year:
            return f"{s.year}年{s.month}月{s.day}日 – {e.month}月{e.day}日"
        return f"{s.year}年{s.month}月{s.day}日 – {e.year}年{e.month}月{e.day}日"
    return f"{s.strftime('%b')} {s.day} – {e.strftime('%b')} {e.day}, {e.year}"


def _comparison_label(days: int, language: str) -> str:
    if language == "ja":
        return f"直前{days}日比"
    return f"vs previous {days} days"


def _labels(language: str) -> dict[str, str]:
    if language == "ja":
        return {
            "app_store": "App Store",
            "usage": "利用状況",
            "revenue": "収益",
            "source_asc": "App Store Connect",
            "source_ga4": "Google Analytics 4",
            "source_admob": "Google AdMob",
            "impressions": "インプレッション",
            "first_time_downloads": "初回ダウンロード",
            "active_users": "アクティブユーザー",
            "estimated_earnings": "AdMob 推定収益",
            "ecpm": "eCPM",
            "admob_impressions": "インプレッション",
            "web": "Web",
            "source_web": "GA4 Web",
            "web_users": "ユーザー",
            "web_sessions": "セッション",
            "web_page_views": "ページビュー",
            "scope_asc_jp": "iOS / 日本",
            "scope_asc_all": "iOS / 全テリトリー",
            "scope_asc_other": "iOS / {territory}",
            "scope_ga4": "プロパティ全体 / 設定済みの全プラットフォーム・国",
            "scope_ga4_off": "未接続",
            "scope_admob": "設定アプリ / 全世界",
            "scope_admob_off": "未接続",
            "scope_web_off": "未設定 / 未接続",
            "scope_web": "Web プロパティ / 設定ドメイン",
            "not_connected": "未接続（値は発明しない）",
            "revenue_note_admob_only": (
                "Phase 1: AdMob ESTIMATED_EARNINGS only. "
                "App Store / Play / Web revenue not included."
            ),
            "revenue_note_admob_only_ja": (
                "Phase 1: AdMob の ESTIMATED_EARNINGS のみ。"
                "App Store / Play / Web 売上は含まない。"
            ),
        }
    return {
        "app_store": "App Store",
        "usage": "Usage",
        "revenue": "Revenue",
        "source_asc": "App Store Connect",
        "source_ga4": "Google Analytics 4",
        "source_admob": "Google AdMob",
        "impressions": "Impressions",
        "first_time_downloads": "First-time downloads",
        "active_users": "Active users",
        "estimated_earnings": "AdMob estimated earnings",
        "ecpm": "eCPM",
        "admob_impressions": "Impressions",
        "web": "Web",
        "source_web": "GA4 Web",
        "web_users": "Users",
        "web_sessions": "Sessions",
        "web_page_views": "Page views",
        "scope_asc_jp": "iOS / Japan",
        "scope_asc_all": "iOS / all territories",
        "scope_asc_other": "iOS / {territory}",
        "scope_ga4": "property-wide / all configured platforms and countries",
        "scope_ga4_off": "not connected",
        "scope_admob": "configured app(s) / worldwide",
        "scope_admob_off": "not connected",
        "scope_web_off": "not configured / not connected",
        "scope_web": "Web property / configured domain",
        "not_connected": "not connected (do not invent values)",
        "revenue_note_admob_only": (
            "Phase 1: AdMob ESTIMATED_EARNINGS only. "
            "App Store / Play / Web revenue not included."
        ),
        "revenue_note_admob_only_ja": (
            "Phase 1: AdMob ESTIMATED_EARNINGS only. "
            "App Store / Play / Web revenue not included."
        ),
    }


def _grounding_rules(language: str) -> list[str]:
    if language == "ja":
        return [
            "Missing data ≠ zero（欠測はゼロ実績として扱わない）",
            "Facts と Speculation を分離する",
            "ソース間の母集団を同一視しない",
            "Revenue は絶対額と変化率の両方を見る（少額の大きな%だけで判断しない）",
            "Web と App を直接ファネル化しない（計測根拠なき Web→App DL 因果を断定しない）",
        ]
    return [
        "Missing data ≠ zero",
        "Facts and speculation are separated",
        "Cross-source populations are not assumed identical",
        "Judge revenue with absolute amount and changePercent together "
        "(do not over-weight large % on small absolute amounts)",
        "Do not funnel Web into App Store downloads without attribution evidence",
    ]


def _build_app_store_metrics(asc: AscGrowthSnapshot, labels: dict[str, str]) -> MetricGroup:
    return MetricGroup(
        id="app_store",
        title=labels["app_store"],
        source=labels["source_asc"],
        connected=True,
        metrics=[
            MetricItem(
                id="impressions",
                label=labels["impressions"],
                change_percent=_round_pct(asc.change_impressions_pct()),
                absolute=f"{asc.current.impressions:,}",
            ),
            MetricItem(
                id="first_time_downloads",
                label=labels["first_time_downloads"],
                change_percent=_round_pct(asc.change_downloads_pct()),
                absolute=f"{asc.current.first_time_downloads:,}",
            ),
        ],
    )


def _build_ga4_metrics(
    ga4: Ga4GrowthSnapshot | None,
    ga4_status: str | None,
    labels: dict[str, str],
    language: str,
) -> MetricGroup:
    del language  # event identifiers stay language-agnostic
    if ga4 is None:
        return MetricGroup(
            id="usage",
            title=labels["usage"],
            source=labels["source_ga4"],
            connected=False,
            status_message=ga4_status or labels["not_connected"],
            metrics=[],
        )

    metrics: list[MetricItem] = [
        MetricItem(
            id="active_users",
            label=labels["active_users"],
            change_percent=_round_pct(ga4.change_active_users_pct()),
            absolute=f"{ga4.current.active_users:,}",
        )
    ]
    for name in ga4.key_event_names:
        cur = ga4.current.key_event_counts.get(name, 0)
        prev = ga4.previous.key_event_counts.get(name, 0)
        change = None if prev <= 0 else ((cur - prev) / prev) * 100.0
        metrics.append(
            MetricItem(
                id=name,
                # Keep the raw event identifier; never localize/translate it here.
                label=name,
                change_percent=_round_pct(change),
                absolute=f"{cur:,}",
            )
        )
    return MetricGroup(
        id="usage",
        title=labels["usage"],
        source=labels["source_ga4"],
        connected=True,
        metrics=metrics,
    )


def _build_admob_metrics(
    admob: AdMobGrowthSnapshot | None,
    admob_status: str | None,
    labels: dict[str, str],
) -> MetricGroup:
    if admob is None or not admob.apps:
        return MetricGroup(
            id="revenue",
            title=labels["revenue"],
            source=labels["source_admob"],
            connected=False,
            status_message=admob_status or labels["not_connected"],
            metrics=[],
        )

    # Prefer the first configured app row for the summary cards.
    app = admob.apps[0]
    cur = app.current
    currency = admob.currency_code
    if not cur.has_data:
        return MetricGroup(
            id="revenue",
            title=labels["revenue"],
            source=labels["source_admob"],
            connected=True,
            status_message=(
                "no AdMob rows in current period"
                if labels["revenue"] == "Revenue"
                else "当期の AdMob 行なし"
            ),
            metrics=[],
        )

    return MetricGroup(
        id="revenue",
        title=labels["revenue"],
        source=labels["source_admob"],
        connected=True,
        metrics=[
            MetricItem(
                id="estimated_earnings",
                label=labels["estimated_earnings"],
                value=_fmt_money(cur.estimated_earnings, currency),
                change_percent=_round_pct(app.change_estimated_earnings_pct()),
            ),
            MetricItem(
                id="ecpm",
                label=labels["ecpm"],
                value=_fmt_money(cur.impression_rpm, currency),
                change_percent=_round_pct(app.change_impression_rpm_pct()),
            ),
            MetricItem(
                id="admob_impressions",
                label=labels["admob_impressions"],
                absolute=f"{cur.impressions:,}",
                change_percent=_round_pct(app.change_impressions_pct()),
            ),
        ],
    )


def _build_web_metrics(
    ga4_web: Ga4GrowthSnapshot | None,
    ga4_web_status: str | None,
    labels: dict[str, str],
    *,
    domain: str | None = None,
) -> MetricGroup:
    source = labels["source_web"]
    if domain:
        source = f"{labels['source_web']} ({domain})"
    if ga4_web is None:
        return MetricGroup(
            id="web",
            title=labels["web"],
            source=source,
            connected=False,
            status_message=ga4_web_status or labels["not_connected"],
            metrics=[],
        )

    metrics: list[MetricItem] = [
        MetricItem(
            id="web_users",
            label=labels["web_users"],
            change_percent=_round_pct(ga4_web.change_active_users_pct()),
            absolute=f"{ga4_web.current.active_users:,}",
        ),
        MetricItem(
            id="web_sessions",
            label=labels["web_sessions"],
            change_percent=_round_pct(ga4_web.change_sessions_pct()),
            absolute=f"{ga4_web.current.sessions:,}",
        ),
        MetricItem(
            id="web_page_views",
            label=labels["web_page_views"],
            change_percent=_round_pct(ga4_web.change_screen_page_views_pct()),
            absolute=f"{ga4_web.current.screen_page_views:,}",
        ),
    ]
    for name in ga4_web.key_event_names:
        cur = ga4_web.current.key_event_counts.get(name, 0)
        prev = ga4_web.previous.key_event_counts.get(name, 0)
        change = None if prev <= 0 else ((cur - prev) / prev) * 100.0
        metrics.append(
            MetricItem(
                id=name,
                label=name,
                change_percent=_round_pct(change),
                absolute=f"{cur:,}",
            )
        )
    return MetricGroup(
        id="web",
        title=labels["web"],
        source=source,
        connected=True,
        metrics=metrics,
    )


def _build_revenue_summary(
    admob: AdMobGrowthSnapshot | None,
    admob_status: str | None,
    language: str,
    labels: dict[str, str],
) -> RevenueSummary:
    note = (
        labels["revenue_note_admob_only_ja"]
        if language == "ja"
        else labels["revenue_note_admob_only"]
    )
    if admob is None or not admob.apps:
        return RevenueSummary(
            currency=None,
            note=note,
            sources=[
                RevenueSourceItem(
                    source="admob",
                    amount=None,
                    previous_amount=None,
                    change_percent=None,
                    currency=None,
                    connected=False,
                    status="not_connected",
                )
            ],
        )

    app = admob.apps[0]
    currency = admob.currency_code
    if not app.current.has_data:
        return RevenueSummary(
            currency=currency,
            note=note,
            sources=[
                RevenueSourceItem(
                    source="admob",
                    amount=None,
                    previous_amount=(
                        app.previous.estimated_earnings
                        if app.previous.has_data
                        else None
                    ),
                    change_percent=None,
                    currency=currency,
                    connected=True,
                    status="unavailable",
                )
            ],
        )

    previous_amount = (
        app.previous.estimated_earnings if app.previous.has_data else None
    )
    return RevenueSummary(
        currency=currency,
        note=note,
        sources=[
            RevenueSourceItem(
                source="admob",
                amount=app.current.estimated_earnings,
                previous_amount=previous_amount,
                change_percent=_round_pct(app.change_estimated_earnings_pct()),
                currency=currency,
                connected=True,
                status="ok",
            )
        ],
    )


def _asc_scope(asc: AscGrowthSnapshot, labels: dict[str, str]) -> str:
    if asc.territory == "JP":
        return labels["scope_asc_jp"]
    if asc.territory == "ALL":
        return labels["scope_asc_all"]
    return labels["scope_asc_other"].format(territory=asc.territory)


def build_analyze_response(
    *,
    language: str,
    asc: AscGrowthSnapshot,
    ga4: Ga4GrowthSnapshot | None,
    ga4_status: str | None,
    admob: AdMobGrowthSnapshot | None,
    admob_status: str | None,
    analysis: StructuredAnalysis,
    ga4_web: Ga4GrowthSnapshot | None = None,
    ga4_web_status: str | None = None,
) -> AnalyzeResponse:
    lang: str = "ja" if language == "ja" else "en"
    labels = _labels(lang)

    from product_config import channel_status_rows, load_product_config

    product = load_product_config()

    actions = sorted(analysis.actions, key=lambda a: a.rank)[:3]
    speculation = [
        s for s in analysis.speculation if s.strip() and s.strip().lower() != "none"
    ]

    web_domain = product.web.domain if product is not None else None
    metrics = {
        "appStore": _build_app_store_metrics(asc, labels),
        "ga4": _build_ga4_metrics(ga4, ga4_status, labels, lang),
        "admob": _build_admob_metrics(admob, admob_status, labels),
        "web": _build_web_metrics(
            ga4_web, ga4_web_status, labels, domain=web_domain
        ),
    }

    data_scope = [
        DataScopeItem(source=labels["source_asc"], scope=_asc_scope(asc, labels)),
        DataScopeItem(
            source=labels["source_ga4"],
            scope=labels["scope_ga4"] if ga4 is not None else labels["scope_ga4_off"],
        ),
        DataScopeItem(
            source=labels["source_admob"],
            scope=labels["scope_admob"] if admob is not None else labels["scope_admob_off"],
        ),
        DataScopeItem(
            source=labels["source_web"],
            scope=(
                (
                    f"{labels['scope_web']}"
                    + (f" ({web_domain})" if web_domain else "")
                )
                if ga4_web is not None
                else labels["scope_web_off"]
            ),
        ),
    ]

    product_payload = None
    if product is not None:
        product_payload = {
            "id": product.id,
            "name": product.name,
            "type": product.type,
        }

    channels = channel_status_rows(
        product=product,
        ga4_app_connected=ga4 is not None,
        ga4_web_connected=ga4_web is not None,
        admob_connected=admob is not None,
        asc_connected=True,
    )

    return AnalyzeResponse(
        language="ja" if lang == "ja" else "en",
        analysis_run_id=str(uuid.uuid4()),
        data_source="live",
        app={
            "name": asc.app.name,
            "bundleId": asc.app.bundle_id,
            "appStoreConnectId": asc.app.id,
            "territory": asc.territory,
        },
        product=product_payload,
        channels=channels,
        period={
            "start": asc.current.start,
            "end": asc.current.end,
            "lookbackDays": asc.lookback_days,
            "label": _format_period_label(asc.current.start, asc.current.end, lang),
            "comparisonLabel": _comparison_label(asc.lookback_days, lang),
            "latestProcessingDate": asc.latest_processing_date,
        },
        metrics=metrics,
        analysis={
            "mostImportantFinding": analysis.most_important_finding,
            "facts": list(analysis.facts),
            "speculation": speculation,
            "actions": [
                {
                    "rank": action.rank,
                    "title": action.title,
                    "reason": action.reason,
                    "basis": action.basis,
                }
                for action in actions
            ],
        },
        data_scope=data_scope,
        grounding_rules=_grounding_rules(lang),
        revenue_summary=_build_revenue_summary(
            admob, admob_status, lang, labels
        ),
        growth_experiments=[],
        planner_status=None,
        planner_error=None,
        playbooks_consulted=[],
        known_events_considered=[],
        known_events_used=[],
    )


def response_generated_at() -> str:
    return datetime.now().isoformat(timespec="seconds")
