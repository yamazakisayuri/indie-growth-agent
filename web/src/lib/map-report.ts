import { t, type CopyKey } from "@/lib/i18n";
import type {
  AnalyzeApiResponse,
  ApiMetricGroup,
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

/** Map Python AnalyzeResponse → dashboard GrowthReport. */
export function mapAnalyzeResponse(data: AnalyzeApiResponse): GrowthReport {
  const language = data.language;

  return {
    source: "live",
    language,
    appName: data.app.name,
    periodLabel: data.period.label,
    comparisonLabel: data.period.comparisonLabel,
    metrics: [
      mapMetricGroup(data.metrics.appStore, language),
      mapMetricGroup(data.metrics.ga4, language),
      mapMetricGroup(data.metrics.admob, language),
    ],
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
    // Rule texts may come from API; the section heading is UI-fixed.
    groundingRules: [
      t("grounding1", language),
      t("grounding2", language),
      t("grounding3", language),
    ],
    mostImportantFinding: data.analysis.mostImportantFinding,
  };
}

/** Resolve mock template keys into a display report for the active UI language. */
export function buildMockReport(language: Language): GrowthReport {
  const c = (key: CopyKey) => t(key, language);
  const template = mockReportTemplate;

  return {
    source: "mock",
    language,
    appName: template.appName,
    periodLabel: template.periodLabel[language],
    comparisonLabel: c("vsPrevious"),
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
  };
}
