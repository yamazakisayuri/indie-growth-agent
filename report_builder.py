"""Build the Web/CLI AnalyzeResponse from live snapshots + structured Agent output.

Metrics / period / data scope come from observed snapshots (not the LLM).
Analysis text comes from StructuredAnalysis.
"""

from __future__ import annotations

from datetime import date, datetime

from admob.snapshot import AdMobGrowthSnapshot
from analysis_schema import (
    AnalyzeResponse,
    DataScopeItem,
    MetricGroup,
    MetricItem,
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
            "estimated_earnings": "推定収益",
            "ecpm": "eCPM",
            "admob_impressions": "インプレッション",
            "scope_asc_jp": "iOS / 日本",
            "scope_asc_all": "iOS / 全テリトリー",
            "scope_asc_other": "iOS / {territory}",
            "scope_ga4": "プロパティ全体 / 設定済みの全プラットフォーム・国",
            "scope_ga4_off": "未接続",
            "scope_admob": "設定アプリ / 全世界",
            "scope_admob_off": "未接続",
            "not_connected": "未接続（値は発明しない）",
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
        "estimated_earnings": "Estimated earnings",
        "ecpm": "eCPM",
        "admob_impressions": "Impressions",
        "scope_asc_jp": "iOS / Japan",
        "scope_asc_all": "iOS / all territories",
        "scope_asc_other": "iOS / {territory}",
        "scope_ga4": "property-wide / all configured platforms and countries",
        "scope_ga4_off": "not connected",
        "scope_admob": "configured app(s) / worldwide",
        "scope_admob_off": "not connected",
        "not_connected": "not connected (do not invent values)",
    }


def _grounding_rules(language: str) -> list[str]:
    if language == "ja":
        return [
            "Missing data ≠ zero（欠測はゼロ実績として扱わない）",
            "Facts と Speculation を分離する",
            "ソース間の母集団を同一視しない",
        ]
    return [
        "Missing data ≠ zero",
        "Facts and speculation are separated",
        "Cross-source populations are not assumed identical",
    ]


def _grounding_rules(language: str) -> list[str]:
    if language == "ja":
        return [
            "Missing data ≠ zero（欠測はゼロ実績として扱わない）",
            "Facts と Speculation を分離する",
            "ソース間の母集団を同一視しない",
        ]
    return [
        "Missing data ≠ zero",
        "Facts and speculation are separated",
        "Cross-source populations are not assumed identical",
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
) -> AnalyzeResponse:
    lang: str = "ja" if language == "ja" else "en"
    labels = _labels(lang)

    actions = sorted(analysis.actions, key=lambda a: a.rank)[:3]
    speculation = [
        s for s in analysis.speculation if s.strip() and s.strip().lower() != "none"
    ]

    metrics = {
        "appStore": _build_app_store_metrics(asc, labels),
        "ga4": _build_ga4_metrics(ga4, ga4_status, labels, lang),
        "admob": _build_admob_metrics(admob, admob_status, labels),
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
    ]

    return AnalyzeResponse(
        language="ja" if lang == "ja" else "en",
        app={
            "name": asc.app.name,
            "bundleId": asc.app.bundle_id,
            "appStoreConnectId": asc.app.id,
            "territory": asc.territory,
        },
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
    )


def response_generated_at() -> str:
    return datetime.now().isoformat(timespec="seconds")
