import { agentApiBaseUrl } from "./analyze-client";
import type { Language } from "./types";

/** Shapes of evidence/schema.py as serialized by the Agent API (camelCase). */

export type ClaimKind = "fact" | "observation" | "hypothesis";
export type FindingKind =
  | "value_mismatch"
  | "unverifiable"
  | "kind_mislabel"
  | "scope_mismatch"
  | "causal_leap"
  | "infeasible_action";
export type FindingResolution = "open" | "resolved" | "downgraded" | "unresolved";
export type RevisionStage = "internal" | "competitive" | "critic_revision";
export type EvidenceRunStatus = "running" | "converged" | "max_rounds" | "error";
export type EvidenceValue = number | string | null;

export interface EvidenceItem {
  table: string;
  sql: string;
  value: EvidenceValue;
  asOf: string;
  source: string;
  scope: string;
  url: string | null;
}

export interface TestPlan {
  metric: string;
  method: string;
  durationDays: number;
  successCriterion: string;
}

export interface Claim {
  id: string;
  text: string;
  kind: ClaimKind;
  evidence: EvidenceItem[];
  testPlan: TestPlan | null;
}

export interface ProposedAction {
  rank: number;
  title: string;
  reason: string;
  claimIds: string[];
}

export interface FindingResponse {
  findingId: string;
  response: "fixed" | "downgraded" | "removed" | "disputed";
  note: string;
}

export interface ActionChange {
  previousRank: number;
  decision: "kept" | "modified" | "removed";
  reason: string;
}

export interface AnalystOutput {
  mostImportantFinding: string;
  claims: Claim[];
  actions: ProposedAction[];
  findingResponses: FindingResponse[];
  actionChanges: ActionChange[];
}

export interface CriticFinding {
  id: string;
  claimId: string;
  kind: FindingKind;
  message: string;
  origin: "code" | "critic";
  criticSql: string;
  criticValue: EvidenceValue;
  claimedValue: EvidenceValue;
  analystSql: string;
  resolution: FindingResolution;
}

export interface CheckOutcome {
  claimId: string;
  evidenceIndex: number | null;
  sql: string;
  claimedValue: EvidenceValue;
  criticValue: EvidenceValue;
  matched: boolean;
  error: string | null;
}

export interface CriticReview {
  summary: string;
  findings: CriticFinding[];
  checks: CheckOutcome[];
  durationSeconds: number;
}

export interface RevisionStep {
  version: string;
  stage: RevisionStage;
  output: AnalystOutput;
  durationSeconds: number;
  attempts: number;
  critic: CriticReview | null;
}

export interface RejectedAttempt {
  version: string;
  stage: RevisionStage;
  attempt: number;
  reason: string;
}

/** One cell a sample scenario changed (sample_mode.py AppliedChange). */
export interface SampleChange {
  table: string;
  match: Record<string, EvidenceValue>;
  column: string;
  before: EvidenceValue;
  after: EvidenceValue;
  reason: string;
}

/** Present only on runs over fictional sample data. */
export interface SampleInfo {
  dataKind: "fictional_sample";
  note: string;
  app: { productId: string; name: string; appId: string };
  scenario: string;
  scenarioDescription: string;
  changes: SampleChange[];
  recordedAt?: string;
  /** Recorded Demo notes written by a person after reviewing the run. */
  reviewOutcome?: string;
  knownLimitations?: string[];
  comparisonNote?: string;
}

interface SampleFields {
  sample?: SampleInfo | null;
  /** True for a Recorded Demo committed under samples/recorded/. */
  recorded?: boolean;
}

export interface EvidenceRun extends SampleFields {
  runId: string;
  productId: string;
  startedAt: string;
  finishedAt: string | null;
  model: string;
  language: Language;
  currentPeriod: [string, string] | null;
  previousPeriod: [string, string] | null;
  maxCriticRounds: number;
  pastDecisionIds: string[];
  status: EvidenceRunStatus;
  steps: RevisionStep[];
  rejectedAttempts: RejectedAttempt[];
  error: string | null;
}

export interface EvidenceRunSummary extends SampleFields {
  runId: string;
  productId: string;
  startedAt: string;
  finishedAt: string | null;
  status: EvidenceRunStatus;
  model: string;
  language: Language;
  versions: string[];
  topActions: (string | null)[];
  unresolvedFindings: number;
  error: string | null;
}

export interface EvidenceRunList {
  activeRunId: string | null;
  runs: EvidenceRunSummary[];
}

export class EvidenceRequestError extends Error {
  readonly code: string;

  constructor(code: string, message?: string) {
    super(message || code);
    this.name = "EvidenceRequestError";
    this.code = code;
  }
}

async function evidenceFetch<T>(
  path: string,
  init: RequestInit,
  fallbackCode: string,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${agentApiBaseUrl()}/api/evidence${path}`, init);
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw err;
    }
    throw new EvidenceRequestError("api_unreachable");
  }
  const payload = (await response.json().catch(() => null)) as
    | (T & { detail?: { code?: string; error?: string } })
    | null;
  if (!response.ok) {
    const detail = payload?.detail;
    throw new EvidenceRequestError(detail?.code || fallbackCode, detail?.error);
  }
  if (!payload || typeof payload !== "object") {
    throw new EvidenceRequestError(fallbackCode);
  }
  return payload;
}

export function listEvidenceRuns(
  productId: string,
  signal?: AbortSignal,
): Promise<EvidenceRunList> {
  const query = new URLSearchParams({ productId });
  return evidenceFetch<EvidenceRunList>(
    `/runs?${query.toString()}`,
    { method: "GET", signal },
    "list_failed",
  );
}

export function getEvidenceRun(
  runId: string,
  signal?: AbortSignal,
): Promise<EvidenceRun> {
  return evidenceFetch<EvidenceRun>(
    `/runs/${encodeURIComponent(runId)}`,
    { method: "GET", signal },
    "run_failed",
  );
}

/** Starts v1 → v2 → Critic → v3 on the API host. Only productId and language are sent. */
export async function startEvidenceRun(
  productId: string,
  language: Language,
): Promise<string> {
  const result = await evidenceFetch<{ runId: string }>(
    "/runs",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ productId, language }),
    },
    "start_failed",
  );
  return result.runId;
}
