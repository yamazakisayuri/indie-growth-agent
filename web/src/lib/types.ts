/**
 * Display types for the dashboard.
 * Live API responses arrive already localized for the request language.
 * Mock data is mapped into the same shape via `buildMockReport`.
 */

export type Language = "ja" | "en";

/** Explicit Analyze / Draft context source. Alias of report `source`. */
export type DataSource = "live" | "mock";

export type ReportSource = DataSource;

export interface DisplayMetric {
  id: string;
  label: string;
  changePercent: number | null;
  value?: string;
  absolute?: string;
  note?: string;
}

export interface MetricBlock {
  id: "app_store" | "usage" | "revenue" | "web";
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

export interface AnalysisPeriod {
  start: string;
  end: string;
  lookbackDays: number;
  label: string;
  comparisonLabel: string;
  latestProcessingDate?: string;
}

export interface GrowthExperiment {
  title: string;
  hypothesis: string;
  why: string;
  action: string;
  targetMetric: string;
  expectedSignal: string;
  suggestedDuration: string;
  evidence: string;
  playbookReference: string;
  /** Same Analyze run id as the parent report when present. */
  analysisRunId?: string;
}

export interface ScreenshotDraftItem {
  position: number;
  messageGoal?: string;
  currentMessage?: string;
  keep?: string;
  change?: string;
  copyDraft: string;
  recommendedScreen: string;
  why: string;
}

export interface ActionDraft {
  experimentTitle: string;
  draftType: string;
  objective: string;
  rationale: string;
  screenshots: ScreenshotDraftItem[];
  missingInputs: string[];
  notes: string;
  playbooksUsed: string[];
  noChangeRecommended?: boolean;
}

export interface ActionDraftResponse {
  draft: ActionDraft;
  analysisRunId?: string | null;
  dataSource?: DataSource | null;
  period?: Partial<AnalysisPeriod> | Record<string, unknown>;
  storeContext?: {
    available?: Record<string, unknown>;
    missingInputs?: string[];
    notes?: string[];
  };
  userScreenshotsReceived?: Array<{
    position: number;
    fileName?: string | null;
    mimeType?: string | null;
    hasImageBytes?: boolean;
    description?: string | null;
  }>;
}

export interface DataScopeRow {
  source: string;
  scope: string;
}

export interface GrowthReport {
  /** @deprecated Prefer dataSource — kept equal for existing UI. */
  source: ReportSource;
  dataSource: DataSource;
  analysisRunId: string;
  language: Language;
  appName: string;
  periodLabel: string;
  comparisonLabel: string;
  period: AnalysisPeriod;
  /** Optional raw app identity for Draft Generator. */
  appBundleId?: string;
  appStoreConnectId?: string;
  appTerritory?: string;
  metrics: MetricBlock[];
  /** API-shaped metrics for Draft request (same Analyze run). */
  metricsPayload: AnalyzeApiResponse["metrics"];
  revenueSummary?: AnalyzeApiResponse["revenueSummary"];
  actions: DisplayAction[];
  facts: string[];
  speculation: string[];
  dataScope: DataScopeRow[];
  groundingRules: string[];
  mostImportantFinding?: string;
  growthExperiments?: GrowthExperiment[];
  plannerStatus?: string | null;
  plannerError?: string | null;
  playbooksConsulted?: string[];
  knownEventsConsidered?: Array<{
    date: string;
    end_date?: string;
    type: string;
    product: string;
    description: string;
  }>;
  knownEventsUsed?: string[];
  /** Selected Product identity from AnalyzeResponse. */
  product?: {
    id: string;
    name: string;
    type: string;
  } | null;
  channels?: AnalyzeApiResponse["channels"];
}

/** Raw JSON from POST /api/analyze (Python Agent API). */
export interface AnalyzeApiResponse {
  language: Language;
  analysisRunId?: string;
  dataSource?: DataSource;
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
    web?: ApiMetricGroup;
  };
  product?: {
    id: string;
    name: string;
    type: string;
  } | null;
  channels?: Array<{
    id: string;
    kind: string;
    connected: boolean;
    status: string;
    domain?: string | null;
    propertyId?: string | null;
    note?: string | null;
  }>;
  revenueSummary?: {
    currency?: string | null;
    note?: string;
    sources: Array<{
      source: string;
      amountType?: string | null;
      amount?: number | null;
      previousAmount?: number | null;
      changePercent?: number | null;
      currency?: string | null;
      units?: number | null;
      previousUnits?: number | null;
      connected: boolean;
      status:
        | "ok"
        | "unavailable"
        | "not_connected"
        | "no_data"
        | "not_configured"
        | "permission_denied"
        | "error";
      note?: string | null;
    }>;
  } | null;
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
  growthExperiments?: GrowthExperiment[];
  plannerStatus?: string | null;
  plannerError?: string | null;
  playbooksConsulted?: string[];
  knownEventsConsidered?: Array<{
    date: string;
    end_date?: string;
    type: string;
    product: string;
    description: string;
  }>;
  knownEventsUsed?: string[];
}

export interface ApiMetricGroup {
  id: "app_store" | "usage" | "revenue" | "web";
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
