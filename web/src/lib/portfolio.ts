import type { ProductSummary } from "./analyze-client";
import type {
  DisplayAction,
  DisplayMetric,
  GrowthReport,
  MetricBlock,
} from "./types";

/** Metrics shown per source block on a Portfolio card. */
export const KPIS_PER_BLOCK = 2;

export interface PortfolioKpiBlock {
  id: MetricBlock["id"];
  title: string;
  /** "ok" = has metrics to show; otherwise the card shows `statusMessage` or a default. */
  status: "ok" | "not_connected" | "no_data";
  statusMessage?: string;
  metrics: DisplayMetric[];
}

export type PortfolioEntry =
  | {
      status: "analyzed";
      product: ProductSummary;
      analysisRunId: string;
      periodLabel: string;
      kpis: PortfolioKpiBlock[];
      topAction: DisplayAction | null;
    }
  | {
      status: "not_analyzed";
      product: ProductSummary;
    };

function hasDisplayValue(metric: DisplayMetric): boolean {
  return (
    Boolean(metric.value || metric.absolute) ||
    (typeof metric.changePercent === "number" &&
      !Number.isNaN(metric.changePercent))
  );
}

/** First metrics with a value per block, in the order the Agent API returned them. */
export function selectKpis(
  blocks: MetricBlock[] | undefined,
  perBlock = KPIS_PER_BLOCK,
): PortfolioKpiBlock[] {
  if (!Array.isArray(blocks)) {
    return [];
  }
  return blocks.map((block) => {
    const base = {
      id: block.id,
      title: block.title,
      statusMessage: block.statusMessage || undefined,
    };
    if (!block.connected) {
      return { ...base, status: "not_connected", metrics: [] };
    }
    const metrics = (Array.isArray(block.metrics) ? block.metrics : [])
      .filter(hasDisplayValue)
      .slice(0, perBlock);
    return metrics.length > 0
      ? { ...base, status: "ok", metrics }
      : { ...base, status: "no_data", metrics: [] };
  });
}

/** Lowest rank wins; actions without a title are ignored. */
export function selectTopAction(
  actions: DisplayAction[] | undefined,
): DisplayAction | null {
  if (!Array.isArray(actions)) {
    return null;
  }
  let top: DisplayAction | null = null;
  for (const action of actions) {
    if (!action || typeof action.title !== "string" || !action.title.trim()) {
      continue;
    }
    if (top === null || action.rank < top.rank) {
      top = action;
    }
  }
  return top;
}

/**
 * One entry per configured product, in catalog order.
 * `reports` must already be filtered to successful Live Analyze runs
 * (see loadCachedReport); anything else is shown as not analyzed.
 */
export function buildPortfolioEntries(
  products: ProductSummary[],
  reports: Record<string, GrowthReport | null | undefined>,
): PortfolioEntry[] {
  return products.map((product) => {
    const report = reports[product.id];
    if (!report || !report.analysisRunId) {
      return { status: "not_analyzed", product };
    }
    return {
      status: "analyzed",
      product,
      analysisRunId: report.analysisRunId,
      periodLabel: typeof report.periodLabel === "string" ? report.periodLabel : "",
      kpis: selectKpis(report.metrics),
      topAction: selectTopAction(report.actions),
    };
  });
}
