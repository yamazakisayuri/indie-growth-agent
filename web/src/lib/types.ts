/**
 * Display types for the dashboard.
 * Live API responses arrive already localized for the request language.
 * Mock data is mapped into the same shape via `buildMockReport`.
 */

export type Language = "ja" | "en";

export type ReportSource = "mock" | "live";

export interface DisplayMetric {
  id: string;
  label: string;
  changePercent: number | null;
  value?: string;
  absolute?: string;
  note?: string;
}

export interface MetricBlock {
  id: "app_store" | "usage" | "revenue";
  title: string;
  source: string;
  connected: boolean;
  statusMessage?: string;
  metrics: DisplayMetric[];
}

export interface DisplayAction {
  rank: number;
  title: string;
  reason: string;
  basis?: string;
}

export interface DataScopeRow {
  source: string;
  scope: string;
}

export interface GrowthReport {
  source: ReportSource;
  language: Language;
  appName: string;
  periodLabel: string;
  comparisonLabel: string;
  metrics: MetricBlock[];
  actions: DisplayAction[];
  facts: string[];
  speculation: string[];
  dataScope: DataScopeRow[];
  groundingRules: string[];
  mostImportantFinding?: string;
}

/** Raw JSON from POST /api/analyze (Python → Next proxy). */
export interface AnalyzeApiResponse {
  language: Language;
  app: {
    name: string;
    bundleId?: string;
    appStoreConnectId?: string;
    territory?: string;
  };
  period: {
    start: string;
    end: string;
    lookbackDays: number;
    label: string;
    comparisonLabel: string;
    latestProcessingDate?: string;
  };
  metrics: {
    appStore: ApiMetricGroup;
    ga4: ApiMetricGroup;
    admob: ApiMetricGroup;
  };
  analysis: {
    mostImportantFinding: string;
    facts: string[];
    speculation: string[];
    actions: Array<{
      rank: number;
      title: string;
      reason: string;
      basis?: string;
    }>;
  };
  dataScope: DataScopeRow[];
  groundingRules: string[];
}

export interface ApiMetricGroup {
  id: "app_store" | "usage" | "revenue";
  title: string;
  source: string;
  connected: boolean;
  statusMessage?: string | null;
  metrics: Array<{
    id: string;
    label: string;
    changePercent?: number | null;
    value?: string | null;
    absolute?: string | null;
    note?: string | null;
  }>;
}
