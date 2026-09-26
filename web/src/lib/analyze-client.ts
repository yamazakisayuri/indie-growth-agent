import type { AnalyzeApiResponse, Language } from "@/lib/types";

export class AnalyzeRequestError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AnalyzeRequestError";
  }
}

const DEFAULT_AGENT_API_URL = "http://127.0.0.1:8000";

function agentApiBaseUrl(): string {
  const raw =
    process.env.NEXT_PUBLIC_AGENT_API_URL?.trim() || DEFAULT_AGENT_API_URL;
  return raw.replace(/\/$/, "");
}

export interface ProductSummary {
  id: string;
  name: string;
  type: string;
}

export interface ProductsResponse {
  defaultProductId: string;
  products: ProductSummary[];
}

/** Call the Python Agent API for the product catalog (no secrets). */
export async function requestProducts(
  signal?: AbortSignal,
): Promise<ProductsResponse> {
  const response = await fetch(`${agentApiBaseUrl()}/api/products`, {
    method: "GET",
    signal,
  });
  if (!response.ok) {
    throw new AnalyzeRequestError("products_failed");
  }
  const payload = (await response.json().catch(() => null)) as
    | ProductsResponse
    | null;
  if (
    !payload ||
    typeof payload !== "object" ||
    !Array.isArray(payload.products)
  ) {
    throw new AnalyzeRequestError("products_failed");
  }
  return {
    defaultProductId: payload.defaultProductId || "mahjong",
    products: payload.products,
  };
}

/**
 * Call the Python Agent API directly (Browser → FastAPI).
 * Never send secrets from the browser; only language + productId are posted.
 */
export async function requestAnalyze(
  language: Language,
  productId: string,
  signal?: AbortSignal,
): Promise<AnalyzeApiResponse> {
  const response = await fetch(`${agentApiBaseUrl()}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language, productId }),
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
