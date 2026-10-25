import type { EvidenceRunSummary } from "./evidence-client";

export interface RecordedDemoTarget {
  productId: string;
  runId: string;
}

/** The Recorded Demo the entry opens: the base scenario if present, else the first one listed. */
export function pickRecordedDemo(
  runs: EvidenceRunSummary[] | undefined,
): RecordedDemoTarget | null {
  if (!Array.isArray(runs)) {
    return null;
  }
  const recorded = runs.filter((run) => run && run.recorded === true && run.sample);
  const chosen =
    recorded.find((run) => run.sample?.scenario === "base") ?? recorded[0] ?? null;
  return chosen ? { productId: chosen.productId, runId: chosen.runId } : null;
}
