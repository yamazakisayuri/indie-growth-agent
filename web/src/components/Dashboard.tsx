"use client";

import { useState } from "react";
import type { ProductSummary } from "@/lib/analyze-client";
import type { RecordedDemoTarget } from "@/lib/demo-entry";
import type { GrowthReport } from "@/lib/types";
import { AnalysisDetails } from "./AnalysisDetails";
import { DataScope } from "./DataScope";
import { DemoEntry } from "./DemoEntry";
import { EvidencePanel } from "./EvidencePanel";
import { GrowthExperiments } from "./GrowthExperiments";
import { Header } from "./Header";
import { InterventionsPanel } from "./InterventionsPanel";
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
  const [demoFocus, setDemoFocus] = useState<
    (RecordedDemoTarget & { nonce: number }) | null
  >(null);
  const focusRunId =
    demoFocus && demoFocus.productId === productId ? demoFocus.runId : undefined;

  function openRecordedDemo(target: RecordedDemoTarget) {
    setDemoFocus((current) => ({ ...target, nonce: (current?.nonce ?? 0) + 1 }));
    onProductChange(target.productId);
  }

  function changeProduct(nextProductId: string) {
    setDemoFocus(null);
    onProductChange(nextProductId);
  }

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
        onProductChange={changeProduct}
        onAnalyze={onAnalyze}
      />
      <DemoEntry disabled={analyzing} onOpen={openRecordedDemo} />
      <MetricsSummary report={report} />
      <TopActions report={report} />
      <EvidencePanel
        key={focusRunId ? `${productId}:demo:${demoFocus?.nonce}` : productId}
        productId={productId}
        initialRunId={focusRunId}
      />
      <InterventionsPanel key={`interventions:${productId}`} productId={productId} />
      <GrowthExperiments key={experimentsKey} report={report} />
      <AnalysisDetails report={report} />
      <DataScope report={report} />
    </div>
  );
}
