"use client";

import type { ProductSummary } from "@/lib/analyze-client";
import type { GrowthReport } from "@/lib/types";
import { AnalysisDetails } from "./AnalysisDetails";
import { DataScope } from "./DataScope";
import { GrowthExperiments } from "./GrowthExperiments";
import { Header } from "./Header";
import { MetricsSummary } from "./MetricsSummary";
import { TopActions } from "./TopActions";

interface DashboardProps {
  report: GrowthReport;
  analyzing: boolean;
  elapsedSec: number;
  error: string | null;
  products: ProductSummary[];
  productId: string;
  onProductChange: (productId: string) => void;
  onAnalyze: () => void;
}

export function Dashboard({
  report,
  analyzing,
  elapsedSec,
  error,
  products,
  productId,
  onProductChange,
  onAnalyze,
}: DashboardProps) {
  const experimentsKey = `${productId}:${report.analysisRunId}:${report.dataSource}`;

  return (
    <div
      className={analyzing ? "dashboard dashboard__analyzing" : "dashboard"}
      aria-busy={analyzing || undefined}
    >
      <Header
        report={report}
        analyzing={analyzing}
        elapsedSec={elapsedSec}
        error={error}
        products={products}
        productId={productId}
        onProductChange={onProductChange}
        onAnalyze={onAnalyze}
      />
      <MetricsSummary report={report} />
      <TopActions report={report} />
      <GrowthExperiments key={experimentsKey} report={report} />
      <AnalysisDetails report={report} />
      <DataScope report={report} />
    </div>
  );
}
