import { t, type CopyKey } from "@/lib/i18n";
import type {
  AnalyzeApiResponse,
  ApiMetricGroup,
  GrowthExperiment,
  GrowthReport,
  Language,
  MetricBlock,
} from "@/lib/types";
import { mockReportTemplate } from "@/mock/report";

/** Known metric ids → UI-owned labels. Event ids (e.g. record_saved) stay raw. */
const METRIC_LABEL_KEYS: Record<string, CopyKey> = {
  impressions: "impressions",
  first_time_downloads: "firstTimeDownloads",
  active_users: "activeUsers",
  estimated_earnings: "estimatedEarnings",
  ecpm: "ecpm",
  admob_impressions: "admobImpressions",
  // Keep the identifier itself; i18n value is also "record_saved".
  record_saved: "recordSaved",
};

const METRIC_NOTE_KEYS: Record<string, CopyKey> = {
  record_saved: "recordSavedNote",
};

const BLOCK_TITLE_KEYS: Record<string, CopyKey> = {
  app_store: "appStore",
  usage: "usage",
  revenue: "revenue",
};

const BLOCK_SOURCE_KEYS: Record<string, CopyKey> = {
  app_store: "sourceAsc",
  usage: "sourceGa4",
  revenue: "sourceAdmob",
};

const MOCK_ANALYSIS_RUN_ID = "mock-demo";

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
    source: sourceKey ? t(sourceKey, language) : group.source,
    connected: group.connected,
    statusMessage: group.statusMessage ?? undefined,
    metrics: group.metrics.map((metric) => ({
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

function buildMockMetricsPayload(
  language: Language,
): AnalyzeApiResponse["metrics"] {
  const template = mockReportTemplate;
  const toGroup = (
    block: (typeof template.metrics)[number],
    id: ApiMetricGroup["id"],
  ): ApiMetricGroup => ({
    id,
    title: t(block.titleKey as CopyKey, language),
    source: t(block.sourceLabelKey as CopyKey, language),
    connected: true,
    statusMessage: null,
    metrics: block.metrics.map((metric) => ({
      id: metric.labelKey,
      label: t(metric.labelKey as CopyKey, language),
      changePercent: metric.changePercent,
      value: "value" in metric ? metric.value : null,
      absolute: "absolute" in metric ? metric.absolute : null,
      note:
        "noteKey" in metric && metric.noteKey
          ? t(metric.noteKey as CopyKey, language)
          : null,
    })),
  });

  return {
    appStore: toGroup(template.metrics[0], "app_store"),
    ga4: toGroup(template.metrics[1], "usage"),
    admob: toGroup(template.metrics[2], "revenue"),
  };
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
  };
}

/** Resolve mock template keys into a display report for the active UI language. */
export function buildMockReport(language: Language): GrowthReport {
  const c = (key: CopyKey) => t(key, language);
  const template = mockReportTemplate;
  const periodLabel = template.periodLabel[language];
  const metricsPayload = buildMockMetricsPayload(language);

  return {
    source: "mock",
    dataSource: "mock",
    analysisRunId: MOCK_ANALYSIS_RUN_ID,
    language,
    appName: template.appName,
    periodLabel,
    comparisonLabel: c("vsPrevious"),
    period: {
      start: "2026-08-28",
      end: "2026-09-03",
      lookbackDays: 7,
      label: periodLabel,
      comparisonLabel: c("vsPrevious"),
    },
    metrics: template.metrics.map((block) => ({
      id: block.id,
      title: c(block.titleKey as CopyKey),
      source: c(block.sourceLabelKey as CopyKey),
      connected: true,
      metrics: block.metrics.map((metric) => ({
        id: metric.labelKey,
        label: c(metric.labelKey as CopyKey),
        changePercent: metric.changePercent,
        value: "value" in metric ? metric.value : undefined,
        absolute: "absolute" in metric ? metric.absolute : undefined,
        note:
          "noteKey" in metric && metric.noteKey
            ? c(metric.noteKey as CopyKey)
            : undefined,
      })),
    })),
    metricsPayload,
    actions: template.actions.map((action) => ({
      rank: action.rank,
      title: c(action.titleKey as CopyKey),
      reason: c(action.reasonKey as CopyKey),
    })),
    facts: template.facts.map((fact) => c(fact.textKey as CopyKey)),
    speculation: template.speculation.map((item) =>
      c(item.textKey as CopyKey),
    ),
    dataScope: template.dataScope.map((item) => ({
      source: c(item.sourceKey as CopyKey),
      scope: c(item.scopeKey as CopyKey),
    })),
    groundingRules: template.groundingRules.map((rule) =>
      c(rule.textKey as CopyKey),
    ),
    plannerStatus: template.plannerStatus?.[language],
    growthExperiments: (template.growthExperiments ?? []).map((exp) => ({
      title: exp.title[language],
      hypothesis: exp.hypothesis[language],
      why: exp.why[language],
      action: exp.action[language],
      targetMetric: exp.targetMetric[language],
      expectedSignal: exp.expectedSignal[language],
      suggestedDuration: exp.suggestedDuration[language],
      evidence: exp.evidence[language],
      playbookReference: exp.playbookReference[language],
      analysisRunId: MOCK_ANALYSIS_RUN_ID,
    })),
  };
}
