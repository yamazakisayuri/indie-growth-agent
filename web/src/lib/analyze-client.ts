import type { AnalyzeApiResponse, Language } from "@/lib/types";

export class AnalyzeRequestError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AnalyzeRequestError";
  }
}

/**
 * Call the Next.js proxy → local Python Agent API.
 * Never send secrets from the browser; only language is posted.
 */
export async function requestAnalyze(
  language: Language,
  signal?: AbortSignal,
): Promise<AnalyzeApiResponse> {
  const response = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language }),
    signal,
  });

  const payload = (await response.json().catch(() => null)) as
    | AnalyzeApiResponse
    | { error?: string }
    | null;

  if (!response.ok) {
    const message =
      payload &&
      typeof payload === "object" &&
      "error" in payload &&
      typeof payload.error === "string"
        ? payload.error
        : undefined;
    throw new AnalyzeRequestError(message || "analyze_failed");
  }

  if (!payload || typeof payload !== "object" || !("analysis" in payload)) {
    throw new AnalyzeRequestError("analyze_failed");
  }

  return payload as AnalyzeApiResponse;
}
