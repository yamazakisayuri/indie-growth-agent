import { agentApiBaseUrl } from "./analyze-client";
import type { Claim, TestPlan } from "./evidence-client";

/** Shapes of interventions/schema.py as serialized by the Agent API (camelCase). */

export type InterventionStatus = "planned" | "implemented" | "evaluated" | "dropped";
export type Verdict = "improved" | "no_change" | "worse" | "inconclusive";
export const VERDICTS: Verdict[] = ["improved", "no_change", "worse", "inconclusive"];

/** Fired on window after any change, so every panel showing interventions reloads. */
export const INTERVENTIONS_CHANGED_EVENT = "interventions:changed";

export interface MeasuredMetric {
  metric: string;
  value: number;
  periodStart: string;
  periodEnd: string;
  sql: string;
}

export interface Measurement {
  measuredAt: string;
  store: string;
  periodStart: string;
  periodEnd: string;
  metrics: MeasuredMetric[];
  skipped: string[];
}

export interface DecisionRecord {
  id: string;
  productId: string;
  origin: "ai_adopted" | "manual";
  runId: string | null;
  actionTitle: string;
  changeDescription: string;
  baseline: MeasuredMetric[];
  method: string;
  successCriterion: string;
  evaluationDate: string;
  createdAt: string;
}

export interface AiPrediction {
  runId: string;
  version: string;
  model: string;
  actionRank: number;
  actionTitle: string;
  actionReason: string;
  claims: Claim[];
  testPlan: TestPlan | null;
}

export interface HumanEvaluation {
  evaluatedOn: string;
  verdict: Verdict;
  note: string;
}

export interface Intervention {
  id: string;
  status: InterventionStatus;
  targetMetric: string;
  durationDays: number;
  windowDays: number;
  decision: DecisionRecord;
  prediction: AiPrediction | null;
  implementedOn: string | null;
  baseline: Measurement | null;
  after: Measurement | null;
  evaluation: HumanEvaluation | null;
  dropReason: string;
  memoryIds: Record<string, string>;
  updatedAt: string;
}

export interface InterventionResult {
  intervention: Intervention;
  /** False when the request repeated something already recorded. */
  changed: boolean;
  warnings: string[];
}

export interface PlanInput {
  targetMetric: string;
  method: string;
  successCriterion: string;
  durationDays: number;
}

export class InterventionRequestError extends Error {
  readonly code: string;

  constructor(code: string, message?: string) {
    super(message || code);
    this.name = "InterventionRequestError";
    this.code = code;
  }
}

async function interventionsFetch<T>(
  path: string,
  init: RequestInit,
  fallbackCode: string,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${agentApiBaseUrl()}/api/interventions${path}`, init);
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw err;
    }
    throw new InterventionRequestError("api_unreachable");
  }
  const payload = (await response.json().catch(() => null)) as
    | (T & { detail?: { code?: string; error?: string } | unknown[] })
    | null;
  if (!response.ok) {
    const detail = payload?.detail;
    if (Array.isArray(detail)) {
      throw new InterventionRequestError("invalid_input");
    }
    throw new InterventionRequestError(detail?.code || fallbackCode, detail?.error);
  }
  if (!payload || typeof payload !== "object") {
    throw new InterventionRequestError(fallbackCode);
  }
  return payload;
}

async function post(path: string, body: object): Promise<InterventionResult> {
  const result = await interventionsFetch<InterventionResult>(
    path,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    "request_failed",
  );
  window.dispatchEvent(new Event(INTERVENTIONS_CHANGED_EVENT));
  return result;
}

export async function listInterventions(
  productId: string,
  signal?: AbortSignal,
): Promise<Intervention[]> {
  const query = new URLSearchParams({ productId });
  const result = await interventionsFetch<{ interventions: Intervention[] }>(
    `?${query.toString()}`,
    { method: "GET", signal },
    "list_failed",
  );
  return result.interventions;
}

/** Plan fields are needed only when the action has no AI test plan. */
export function adoptAction(
  runId: string,
  rank: number,
  plan?: PlanInput,
): Promise<InterventionResult> {
  return post("/adopt", { runId, rank, ...plan });
}

export function addIntervention(
  productId: string,
  title: string,
  changeDescription: string,
  plan: PlanInput,
): Promise<InterventionResult> {
  return post("", { productId, title, changeDescription, ...plan });
}

export function implementIntervention(
  id: string,
  implementedOn: string,
): Promise<InterventionResult> {
  return post(`/${encodeURIComponent(id)}/implement`, { implementedOn });
}

export function evaluateIntervention(
  id: string,
  verdict: Verdict,
  note: string,
  evaluatedOn: string,
  early: boolean,
): Promise<InterventionResult> {
  return post(`/${encodeURIComponent(id)}/evaluate`, {
    verdict,
    note,
    evaluatedOn,
    early,
  });
}

export function measureIntervention(id: string): Promise<InterventionResult> {
  return post(`/${encodeURIComponent(id)}/measure`, {});
}

export function dropIntervention(id: string, reason: string): Promise<InterventionResult> {
  return post(`/${encodeURIComponent(id)}/drop`, { reason });
}

/** Today in the browser's local time zone, as YYYY-MM-DD. */
export function localToday(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}
