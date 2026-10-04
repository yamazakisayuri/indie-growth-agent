"""Build the Web/CLI AnalyzeResponse from live snapshots + structured Agent output.

Metrics / period / data scope come from observed snapshots (not the LLM).
Analysis text comes from StructuredAnalysis.
"""

from __future__ import annotations

from datetime import date
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
from asc.sales import AscSalesRevenueSnapshot
from asc.snapshot import AscGrowthSnapshot
from ga4.snapshot import Ga4GrowthSnapshot


def _round_pct(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 1)


def _fmt_money(value: float, currency: str | None) -> str:
    if not currency:
        return f"{value:,.2f}"
    code = currency.upper()
    if code == "JPY":
        return f"¥{value:,.2f}"
    if code == "USD":
        return f"${value:,.2f}"
    return f"{value:,.2f} {code}"


def _fmt_money_with_code(value: float, currency: str | None) -> str:
    base = _fmt_money(value, currency)
    if currency:
        code = currency.upper()
        if code in ("JPY", "USD") and code not in base:
            return f"{base} {code}"
        if code not in ("JPY", "USD"):
            return base
        return f"{base} {code}"
    return base


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
            "app_store_proceeds": "App Store proceeds",
            "paid_units_note": "有料ユニット（無料DLは含まない）",
            "ecpm": "eCPM",
            "admob_impressions": "インプレッション",
            "web": "Web",
            "source_web": "GA4 Web",
            "source_revenue": "AdMob / App Store Sales",
            "web_users": "ユーザー",
            "web_sessions": "セッション",
            "web_page_views": "ページビュー",
            "web_page_views_note": "サイト全体（設定ドメイン）",
            "mahjong_page_views": "/mahjong/ ページビュー",
            "mahjong_page_views_note": "点数計算ページを閲覧した（計算利用ではない）",
            "form_submit_path_note": "点数計算フォームがsubmitされた近似指標（計算成功ではない）",
            "appstore_click_note": "Web内のApp Store CTAクリック（ASCダウンロードではない）",
            "scope_asc_jp": "iOS / 日本",
            "scope_asc_all": "iOS / 全テリトリー",
            "scope_asc_other": "iOS / {territory}",
            "scope_asc_revenue_ww": "App Store Sales proceeds / 全世界 (WW)",
            "scope_asc_revenue_off": "App Store Sales proceeds / 未設定または取得不可",
            "scope_ga4": "プロパティ全体 / 設定済みの全プラットフォーム・国",
            "scope_ga4_off": "未接続",
            "scope_admob": "設定アプリ / 全世界",
            "scope_admob_off": "未接続",
            "scope_web_off": "未設定 / 未接続",
            "scope_web": "Web プロパティ / 設定ドメイン",
            "not_connected": "未接続（値は発明しない）",
            "revenue_note": (
                "AdMob ESTIMATED_EARNINGS と App Store Sales Developer Proceeds を並列表示。"
                "合算しない。Proceeds は Trends 推定であり Financial 確定 Partner Share ではない。"
                "ASC Analytics（例: JP）と Revenue（WW）は別スコープ。"
            ),
            "revenue_note_en": (
                "AdMob ESTIMATED_EARNINGS and App Store Sales Developer Proceeds shown "
                "in parallel — not summed. Proceeds are Trends estimates, not Financial "
                "Partner Share. ASC Analytics territory (e.g. JP) ≠ Revenue WW scope."
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
        "app_store_proceeds": "App Store proceeds",
        "paid_units_note": "paid units (excludes free downloads)",
        "ecpm": "eCPM",
        "admob_impressions": "Impressions",
        "web": "Web",
        "source_web": "GA4 Web",
        "source_revenue": "AdMob / App Store Sales",
        "web_users": "Users",
        "web_sessions": "Sessions",
        "web_page_views": "Page views",
        "web_page_views_note": "Site-wide (configured host)",
        "mahjong_page_views": "/mahjong/ page views",
        "mahjong_page_views_note": "Score-calculation page viewed (not calculation used)",
        "form_submit_path_note": "Score-calculation form submitted (proxy; not score success)",
        "appstore_click_note": "Web App Store CTA click (not ASC download)",
        "scope_asc_jp": "iOS / Japan",
        "scope_asc_all": "iOS / all territories",
        "scope_asc_other": "iOS / {territory}",
        "scope_asc_revenue_ww": "App Store Sales proceeds / worldwide (WW)",
        "scope_asc_revenue_off": "App Store Sales proceeds / not configured or unavailable",
        "scope_ga4": "property-wide / all configured platforms and countries",
        "scope_ga4_off": "not connected",
        "scope_admob": "configured app(s) / worldwide",
        "scope_admob_off": "not connected",
        "scope_web_off": "not configured / not connected",
        "scope_web": "Web property / configured domain",
        "not_connected": "not connected (do not invent values)",
        "revenue_note": (
            "AdMob ESTIMATED_EARNINGS and App Store Sales Developer Proceeds shown "
            "in parallel — not summed. Proceeds are Trends estimates, not Financial "
            "Partner Share. ASC Analytics territory (e.g. JP) ≠ Revenue WW scope."
        ),
        "revenue_note_en": (
            "AdMob ESTIMATED_EARNINGS and App Store Sales Developer Proceeds shown "
            "in parallel — not summed. Proceeds are Trends estimates, not Financial "
            "Partner Share. ASC Analytics territory (e.g. JP) ≠ Revenue WW scope."
        ),
    }


def _grounding_rules(language: str) -> list[str]:
    if language == "ja":
        return [
            "Missing data ≠ zero（欠測はゼロ実績として扱わない）",
            "Facts と Speculation を分離する",
            "ソース間の母集団を同一視しない",
            "Units ≠ Revenue。無料DL UnitsをRevenueとして扱わない",
            "Customer Price ≠ Developer Proceeds。Revenue主指標は Developer Proceeds",
            "Developer Proceeds ≠ Financial 確定 Partner Share（Trends推定）",
            "AdMob ESTIMATED_EARNINGS ≠ App Store proceeds。source間を単純合算しない",
            "通貨間を換算・合算しない",
            "ASC Analytics（例: JP）と App Store Revenue（WW）は別スコープ。"
            "JP Downloads → WW Revenue のファネル化・因果断定をしない",
            "Revenue は絶対額と変化率の両方を見る（少額の大きな%だけで判断しない）",
            "Revenueが存在するだけでRevenue Experimentを強制しない",
            "Web と App を直接ファネル化しない（計測根拠なき Web→App DL 因果を断定しない）",
            "capability ≠ usage。path page view ≠ 機能利用。form_submit は submit 近似のみ",
            "appstore_click は Web CTA クリックのみ（ASC DL / first_open ではない）",
            "少数イベントの大きな変化率を過大評価しない",
        ]
    return [
        "Missing data ≠ zero",
        "Facts and speculation are separated",
        "Cross-source populations are not assumed identical",
        "Units ≠ Revenue; do not treat free download Units as revenue",
        "Customer Price ≠ Developer Proceeds; primary ASC amount is Developer Proceeds",
        "Developer Proceeds ≠ settled Financial Partner Share (Trends estimate)",
        "AdMob ESTIMATED_EARNINGS ≠ App Store proceeds; do not sum sources",
        "Do not FX-convert or sum across currencies",
        "ASC Analytics territory (e.g. JP) ≠ App Store Revenue WW — "
        "never funnel JP Downloads into WW Revenue or assert causation",
        "Judge revenue with absolute amount and changePercent together "
        "(do not over-weight large % on small absolute amounts)",
        "Do not force a Revenue experiment merely because App Store proceeds exist",
        "Do not funnel Web into App Store downloads without attribution evidence",
        "capability ≠ usage; path page views ≠ feature usage; form_submit is submit proxy only",
        "appstore_click is Web CTA click only (not ASC download / first_open)",
        "Do not over-weight large % changes on small absolute Web event counts",
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


def _build_revenue_metrics(
    admob: AdMobGrowthSnapshot | None,
    admob_status: str | None,
    sales: AscSalesRevenueSnapshot | None,
    labels: dict[str, str],
) -> MetricGroup:
    metrics: list[MetricItem] = []
    connected = False

    if admob is not None and admob.apps:
        app = admob.apps[0]
        cur = app.current
        currency = admob.currency_code
        if cur.has_data:
            connected = True
            metrics.append(
                MetricItem(
                    id="estimated_earnings",
                    label=labels["estimated_earnings"],
                    value=_fmt_money_with_code(cur.estimated_earnings, currency),
                    change_percent=_round_pct(app.change_estimated_earnings_pct()),
                )
            )
            metrics.append(
                MetricItem(
                    id="ecpm",
                    label=labels["ecpm"],
                    value=_fmt_money_with_code(cur.impression_rpm, currency),
                    change_percent=_round_pct(app.change_impression_rpm_pct()),
                )
            )
            metrics.append(
                MetricItem(
                    id="admob_impressions",
                    label=labels["admob_impressions"],
                    absolute=f"{cur.impressions:,}",
                    change_percent=_round_pct(app.change_impressions_pct()),
                )
            )

    if sales is not None and sales.status == "ok":
        connected = True
        if sales.current.by_currency:
            for row in sales.current.by_currency:
                change = sales.change_percent_for(row.currency)
                note = labels["paid_units_note"]
                if row.units:
                    note = f"{row.units} paid unit{'s' if row.units != 1 else ''} · {note}"
                metrics.append(
                    MetricItem(
                        id=f"app_store_proceeds_{row.currency.lower()}",
                        label=f"{labels['app_store_proceeds']} ({row.currency})",
                        value=_fmt_money_with_code(row.amount, row.currency),
                        change_percent=_round_pct(change),
                        note=note,
                    )
                )
        else:
            # ok + zero paid proceeds, no currency observed — do not invent USD/JPY.
            metrics.append(
                MetricItem(
                    id="app_store_proceeds",
                    label=labels["app_store_proceeds"],
                    value="0",
                    change_percent=None,
                    note=labels["paid_units_note"],
                )
            )
    elif sales is not None and sales.status == "not_configured":
        pass  # note via status_message / revenueSummary
    elif sales is not None and sales.status in (
        "permission_denied",
        "unavailable",
        "error",
        "no_data",
    ):
        pass

    status_message = None
    if not metrics:
        parts: list[str] = []
        if admob is None or not admob.apps:
            parts.append(admob_status or labels["not_connected"])
        elif admob.apps and not admob.apps[0].current.has_data:
            parts.append(
                "no AdMob rows in current period"
                if labels["revenue"] == "Revenue"
                else "当期の AdMob 行なし"
            )
        if sales is not None and sales.status != "ok":
            parts.append(
                sales.status_message
                or f"App Store Sales: {sales.status}"
            )
        status_message = " / ".join(parts) if parts else labels["not_connected"]

    return MetricGroup(
        id="revenue",
        title=labels["revenue"],
        source=labels["source_revenue"],
        connected=connected and bool(metrics),
        status_message=status_message,
        metrics=metrics,
    )


def _admob_source_items(
    admob: AdMobGrowthSnapshot | None,
    admob_status: str | None,
) -> list[RevenueSourceItem]:
    if admob is None or not admob.apps:
        return [
            RevenueSourceItem(
                source="admob",
                amount_type="estimated_earnings",
                amount=None,
                previous_amount=None,
                change_percent=None,
                currency=None,
                connected=False,
                status="not_connected",
                note=admob_status,
            )
        ]

    app = admob.apps[0]
    currency = admob.currency_code
    if not app.current.has_data:
        return [
            RevenueSourceItem(
                source="admob",
                amount_type="estimated_earnings",
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
        ]

    previous_amount = (
        app.previous.estimated_earnings if app.previous.has_data else None
    )
    return [
        RevenueSourceItem(
            source="admob",
            amount_type="estimated_earnings",
            amount=app.current.estimated_earnings,
            previous_amount=previous_amount,
            change_percent=_round_pct(app.change_estimated_earnings_pct()),
            currency=currency,
            connected=True,
            status="ok",
        )
    ]


def _app_store_source_items(
    sales: "AscSalesRevenueSnapshot | None",
) -> list[RevenueSourceItem]:
    if sales is None:
        return [
            RevenueSourceItem(
                source="app_store",
                amount_type="developer_proceeds",
                connected=False,
                status="not_connected",
            )
        ]

    if sales.status != "ok":
        mapped = sales.status
        if mapped not in (
            "ok",
            "unavailable",
            "not_connected",
            "no_data",
            "not_configured",
            "permission_denied",
            "error",
        ):
            mapped = "error"
        return [
            RevenueSourceItem(
                source="app_store",
                amount_type="developer_proceeds",
                amount=None,
                previous_amount=None,
                change_percent=None,
                currency=None,
                units=None,
                connected=sales.vendor_configured,
                status=mapped,  # type: ignore[arg-type]
                note=sales.status_message,
            )
        ]

    # ok — zero or more currencies. Do not invent a currency when none observed.
    if not sales.current.by_currency and not sales.previous.by_currency:
        return [
            RevenueSourceItem(
                source="app_store",
                amount_type="developer_proceeds",
                amount=0.0,
                previous_amount=0.0,
                change_percent=None,
                currency=None,
                units=0,
                previous_units=0,
                connected=True,
                status="ok",
                note="No paid proceeds rows in Analyzer windows (not an error).",
            )
        ]

    currencies = sorted(
        {
            *(c.currency for c in sales.current.by_currency),
            *(c.currency for c in sales.previous.by_currency),
        }
    )
    items: list[RevenueSourceItem] = []
    for currency in currencies:
        cur_map = {c.currency: c for c in sales.current.by_currency}
        prev_map = {c.currency: c for c in sales.previous.by_currency}
        cur = cur_map.get(currency)
        prev = prev_map.get(currency)
        amount = cur.amount if cur else 0.0
        prev_amount = prev.amount if prev else 0.0
        units = cur.units if cur else 0
        prev_units = prev.units if prev else 0
        change = None if prev_amount == 0 else ((amount - prev_amount) / prev_amount) * 100.0
        note = None
        if prev_amount == 0 and amount > 0:
            note = "New proceeds vs prior period (no % change; previous was 0)."
        items.append(
            RevenueSourceItem(
                source="app_store",
                amount_type="developer_proceeds",
                amount=amount,
                previous_amount=prev_amount,
                change_percent=_round_pct(change),
                currency=currency,
                units=units,
                previous_units=prev_units,
                connected=True,
                status="ok",
                note=note,
            )
        )
    return items


def _build_revenue_summary(
    admob: AdMobGrowthSnapshot | None,
    admob_status: str | None,
    sales: "AscSalesRevenueSnapshot | None",
    language: str,
    labels: dict[str, str],
) -> RevenueSummary:
    note = labels["revenue_note"] if language == "ja" else labels["revenue_note_en"]
    sources = _admob_source_items(admob, admob_status) + _app_store_source_items(sales)

    # Display primary currency: prefer AdMob when ok, else first app_store currency.
    primary: str | None = None
    for item in sources:
        if item.source == "admob" and item.status == "ok" and item.currency:
            primary = item.currency
            break
    if primary is None:
        for item in sources:
            if item.source == "app_store" and item.status == "ok" and item.currency:
                primary = item.currency
                break

    return RevenueSummary(
        currency=primary,
        note=note,
        sources=sources,
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
            note=labels.get("web_page_views_note"),
        ),
    ]
    for path in ga4_web.feature_paths:
        cur = ga4_web.feature_path_current(path.id)
        prev = ga4_web.feature_path_previous(path.id)
        if path.include_page_views and cur is not None:
            prev_views = prev.page_views if prev is not None else 0
            change = None if prev_views <= 0 else ((cur.page_views - prev_views) / prev_views) * 100.0
            metric_id = f"{path.id}_page_views"
            metrics.append(
                MetricItem(
                    id=metric_id,
                    label=labels.get("mahjong_page_views", metric_id),
                    change_percent=_round_pct(change),
                    absolute=f"{cur.page_views:,}",
                    note=labels.get("mahjong_page_views_note"),
                )
            )
        if cur is None:
            continue
        for event_name in path.reference_event_names:
            c = cur.reference_event_counts.get(event_name, 0)
            p = prev.reference_event_counts.get(event_name, 0) if prev else 0
            change = None if p <= 0 else ((c - p) / p) * 100.0
            note_key = f"{event_name}_path_note"
            metrics.append(
                MetricItem(
                    id=f"{path.id}_{event_name}",
                    label=event_name,
                    change_percent=_round_pct(change),
                    absolute=f"{c:,}",
                    note=labels.get(note_key) or labels.get("form_submit_path_note"),
                )
            )
    for name in ga4_web.key_event_names:
        cur = ga4_web.current.key_event_counts.get(name, 0)
        prev = ga4_web.previous.key_event_counts.get(name, 0)
        change = None if prev <= 0 else ((cur - prev) / prev) * 100.0
        note = None
        if name == "appstore_click":
            note = labels.get("appstore_click_note")
        metrics.append(
            MetricItem(
                id=name,
                label=name,
                change_percent=_round_pct(change),
                absolute=f"{cur:,}",
                note=note,
            )
        )
    return MetricGroup(
        id="web",
        title=labels["web"],
        source=source,
        connected=True,
        metrics=metrics,
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
    sales: "AscSalesRevenueSnapshot | None" = None,
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
        "admob": _build_revenue_metrics(admob, admob_status, sales, labels),
        "web": _build_web_metrics(
            ga4_web, ga4_web_status, labels, domain=web_domain
        ),
    }

    data_scope = [
        DataScopeItem(source=labels["source_asc"], scope=_asc_scope(asc, labels)),
        DataScopeItem(
            source="App Store Sales (Revenue)",
            scope=(
                labels["scope_asc_revenue_ww"]
                if sales is not None and sales.status == "ok"
                else labels["scope_asc_revenue_off"]
            ),
        ),
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
            admob, admob_status, sales, lang, labels
        ),
        growth_experiments=[],
        planner_status=None,
        planner_error=None,
        playbooks_consulted=[],
        known_events_considered=[],
        known_events_used=[],
    )
