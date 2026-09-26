import type {
  ActionDraftResponse,
  AnalysisPeriod,
  DataSource,
  Language,
  AnalyzeApiResponse,
} from "@/lib/types";

export class DraftRequestError extends Error {
  code?: string;

  constructor(message: string, code?: string) {
    super(message);
    this.name = "DraftRequestError";
    this.code = code;
  }
}

const DEFAULT_AGENT_API_URL = "http://127.0.0.1:8000";

function agentApiBaseUrl(): string {
  const raw =
    process.env.NEXT_PUBLIC_AGENT_API_URL?.trim() || DEFAULT_AGENT_API_URL;
  return raw.replace(/\/$/, "");
}

export interface UserScreenshotInput {
  position?: number;
  fileName?: string;
  mimeType?: string;
  /** Optional human note about what the image shows. */
  description?: string;
  /** Raw base64 or data-URL; server strips the data: prefix when present. */
  dataBase64?: string;
}

export interface DraftRequestBody {
  language: Language;
  experiment: {
    title: string;
    hypothesis: string;
    why: string;
    action: string;
    targetMetric: string;
    expectedSignal: string;
    suggestedDuration: string;
    evidence: string;
    playbookReference: string;
    analysisRunId?: string;
  };
  mostImportantFinding?: string;
  facts?: string[];
  playbooksConsulted?: string[];
  app?: {
    name?: string;
    bundleId?: string;
    appStoreConnectId?: string;
    territory?: string;
  };
  period?: AnalysisPeriod;
  metrics?: AnalyzeApiResponse["metrics"];
  analysisRunId?: string;
  dataSource?: DataSource;
  /** First-class input for Screenshot Drafts. Empty → missingInputs requests upload. */
  userScreenshots?: UserScreenshotInput[];
}

/** Browser → FastAPI Draft Generator for one human-selected experiment. */
export async function requestDraft(
  body: DraftRequestBody,
  signal?: AbortSignal,
): Promise<ActionDraftResponse> {
  const response = await fetch(`${agentApiBaseUrl()}/api/draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  const payload = (await response.json().catch(() => null)) as
    | ActionDraftResponse
    | { error?: string; detail?: { error?: string; code?: string } }
    | null;

  if (!response.ok) {
    const detail =
      payload &&
      typeof payload === "object" &&
      "detail" in payload &&
      payload.detail &&
      typeof payload.detail === "object"
        ? payload.detail
        : null;
    const message =
      payload && typeof payload === "object"
        ? "error" in payload && typeof payload.error === "string"
          ? payload.error
          : detail && typeof detail.error === "string"
            ? detail.error
            : undefined
        : undefined;
    const code =
      detail && typeof detail.code === "string" ? detail.code : undefined;
    throw new DraftRequestError(message || "draft_failed", code);
  }

  if (!payload || typeof payload !== "object" || !("draft" in payload)) {
    throw new DraftRequestError("draft_failed");
  }

  return payload as ActionDraftResponse;
}
