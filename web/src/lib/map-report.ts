import { t, type CopyKey } from "@/lib/i18n";
import type {
  AnalyzeApiResponse,
  ApiMetricGroup,
  GrowthExperiment,
  GrowthReport,
  Language,
  MetricBlock,
} from "@/lib/types";

/** Known metric ids → UI-owned labels. Event ids (e.g. record_saved) stay raw. */
const METRIC_LABEL_KEYS: Record<string, CopyKey> = {
  impressions: "impressions",
  first_time_downloads: "firstTimeDownloads",
  active_users: "activeUsers",
  estimated_earnings: "estimatedEarnings",
  ecpm: "ecpm",
  admob_impressions: "admobImpressions",
  web_users: "webUsers",
  web_sessions: "webSessions",
  web_page_views: "webPageViews",
  mahjong_score_calculator_page_views: "mahjongPageViews",
  // Keep the identifier itself; i18n value is also "record_saved".
  record_saved: "recordSaved",
};

const METRIC_NOTE_KEYS: Record<string, CopyKey> = {
  record_saved: "recordSavedNote",
  mahjong_score_calculator_page_views: "mahjongPageViewsNote",
  mahjong_score_calculator_form_submit: "formSubmitPathNote",
  appstore_click: "appstoreClickNote",
};

const BLOCK_TITLE_KEYS: Record<string, CopyKey> = {
  app_store: "appStore",
  usage: "usage",
  revenue: "revenue",
  web: "web",
};

const BLOCK_SOURCE_KEYS: Record<string, CopyKey> = {
  app_store: "sourceAsc",
  usage: "sourceGa4",
  revenue: "sourceAdmob",
  web: "sourceWeb",
};

// Prefer backend-provided source label for revenue (AdMob / App Store Sales).
const KEEP_BACKEND_SOURCE = new Set(["revenue"]);

function resolveMetricLabel(
  id: string,
  fallback: string,
  language: Language,
): string {
  const key = METRIC_LABEL_KEYS[id];
  if (key) {
    return t(key, language);
  }
  // Keep GA4/AdMob identifiers as-is (never invent a Japanese paraphrase).
  return id || fallback;
}

function resolveMetricNote(id: string, language: Language): string | undefined {
  const key = METRIC_NOTE_KEYS[id];
  return key ? t(key, language) : undefined;
}

function mapMetricGroup(
  group: ApiMetricGroup,
  language: Language,
): MetricBlock {
  const titleKey = BLOCK_TITLE_KEYS[group.id];
  const sourceKey = BLOCK_SOURCE_KEYS[group.id];

  return {
    id: group.id,
    title: titleKey ? t(titleKey, language) : group.title,
    source:
      KEEP_BACKEND_SOURCE.has(group.id) || !sourceKey
        ? group.source
        : t(sourceKey, language),
    connected: group.connected,
    statusMessage: group.statusMessage ?? undefined,
    metrics: (group.metrics ?? []).map((metric) => ({
      id: metric.id,
      label: resolveMetricLabel(metric.id, metric.label, language),
      changePercent:
        metric.changePercent === undefined || metric.changePercent === null
          ? null
          : metric.changePercent,
      value: metric.value ?? undefined,
      absolute: metric.absolute ?? undefined,
      note:
        resolveMetricNote(metric.id, language) ??
        metric.note ??
        undefined,
    })),
  };
}

function emptyMetricGroup(
  id: ApiMetricGroup["id"],
  language: Language,
): ApiMetricGroup {
  const titleKey = BLOCK_TITLE_KEYS[id];
  const sourceKey = BLOCK_SOURCE_KEYS[id];
  return {
    id,
    title: titleKey ? t(titleKey, language) : id,
    source: sourceKey ? t(sourceKey, language) : id,
    connected: false,
    statusMessage: null,
    metrics: [],
  };
}

/** Empty dashboard shell before the first successful Live Analyze. */
export function buildEmptyReport(
  language: Language,
  product: { id: string; name: string; type: string },
): GrowthReport {
  const metricsPayload = {
    appStore: emptyMetricGroup("app_store", language),
    ga4: emptyMetricGroup("usage", language),
    admob: emptyMetricGroup("revenue", language),
    web: emptyMetricGroup("web", language),
  };

  return {
    source: "live",
    dataSource: "live",
    analysisRunId: "",
    language,
    appName: product.name,
    periodLabel: "—",
    comparisonLabel: "",
    period: {
      start: "",
      end: "",
      lookbackDays: 7,
      label: "—",
      comparisonLabel: "",
    },
    metrics: [
      mapMetricGroup(metricsPayload.appStore, language),
      mapMetricGroup(metricsPayload.ga4, language),
      mapMetricGroup(metricsPayload.admob, language),
      mapMetricGroup(metricsPayload.web, language),
    ],
    metricsPayload,
    actions: [],
    facts: [],
    speculation: [],
    dataScope: [],
    groundingRules: [
      t("grounding1", language),
      t("grounding2", language),
      t("grounding3", language),
      t("grounding4", language),
      t("grounding5", language),
    ],
    growthExperiments: [],
    plannerStatus: null,
    plannerError: null,
    knownEventsConsidered: [],
    knownEventsUsed: [],
    product,
  };
}

export function hasSuccessfulReport(report: GrowthReport | null): boolean {
  return Boolean(report?.analysisRunId);
}

/** Map Python AnalyzeResponse → dashboard GrowthReport. */
export function mapAnalyzeResponse(data: AnalyzeApiResponse): GrowthReport {
  const language = data.language;
  const analysisRunId = data.analysisRunId || `live-missing-${Date.now()}`;
  const dataSource = data.dataSource === "mock" ? "mock" : "live";

  return {
    source: dataSource,
    dataSource,
    analysisRunId,
    language,
    appName: data.app.name,
    periodLabel: data.period.label,
    comparisonLabel: data.period.comparisonLabel,
    period: {
      start: data.period.start,
      end: data.period.end,
      lookbackDays: data.period.lookbackDays,
      label: data.period.label,
      comparisonLabel: data.period.comparisonLabel,
      latestProcessingDate: data.period.latestProcessingDate,
    },
    appBundleId: data.app.bundleId,
    appStoreConnectId: data.app.appStoreConnectId,
    appTerritory: data.app.territory,
    metrics: [
      mapMetricGroup(data.metrics.appStore, language),
      mapMetricGroup(data.metrics.ga4, language),
      mapMetricGroup(data.metrics.admob, language),
      ...(data.metrics.web
        ? [mapMetricGroup(data.metrics.web, language)]
        : []),
    ],
    metricsPayload: data.metrics,
    revenueSummary: data.revenueSummary ?? undefined,
    // Analysis prose only — UI headings come from i18n in components.
    actions: data.analysis.actions.map((action) => ({
      rank: action.rank,
      title: action.title,
      reason: action.reason,
      basis: action.basis,
    })),
    facts: data.analysis.facts,
    speculation: data.analysis.speculation,
    dataScope: data.dataScope,
    // Prefer API grounding when present; fall back to UI-owned rules.
    groundingRules:
      data.groundingRules?.length > 0
        ? data.groundingRules
        : [
            t("grounding1", language),
            t("grounding2", language),
            t("grounding3", language),
            t("grounding4", language),
            t("grounding5", language),
          ],
    mostImportantFinding: data.analysis.mostImportantFinding,
    growthExperiments: (data.growthExperiments ?? []).map(
      (item): GrowthExperiment => ({
        title: item.title,
        hypothesis: item.hypothesis,
        why: item.why,
        action: item.action,
        targetMetric: item.targetMetric,
        expectedSignal: item.expectedSignal,
        suggestedDuration: item.suggestedDuration,
        evidence: item.evidence,
        playbookReference: item.playbookReference,
        analysisRunId: item.analysisRunId || analysisRunId,
      }),
    ),
    plannerStatus: data.plannerStatus ?? null,
    plannerError: data.plannerError ?? null,
    playbooksConsulted: data.playbooksConsulted ?? [],
    knownEventsConsidered: data.knownEventsConsidered ?? [],
    knownEventsUsed: data.knownEventsUsed ?? [],
    product: data.product ?? null,
    channels: data.channels ?? [],
  };
}
