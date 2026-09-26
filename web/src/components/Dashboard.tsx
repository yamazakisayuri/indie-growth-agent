"use client";

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
  onAnalyze: () => void;
}

export function Dashboard({
  report,
  analyzing,
  elapsedSec,
  error,
  onAnalyze,
}: DashboardProps) {
  return (
    <div className="dashboard">
      <Header
        report={report}
        analyzing={analyzing}
        elapsedSec={elapsedSec}
        error={error}
        onAnalyze={onAnalyze}
      />
      <MetricsSummary report={report} />
      <TopActions report={report} />
      <GrowthExperiments report={report} />
      <AnalysisDetails report={report} />
      <DataScope report={report} />
    </div>
  );
}
