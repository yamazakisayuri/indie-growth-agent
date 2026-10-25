import type { AnalyzeApiResponse, Language } from "@/lib/types";

export class AnalyzeRequestError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AnalyzeRequestError";
  }
}

const DEFAULT_AGENT_API_URL = "http://127.0.0.1:8000";

export function agentApiBaseUrl(): string {
  const raw =
    process.env.NEXT_PUBLIC_AGENT_API_URL?.trim() || DEFAULT_AGENT_API_URL;
  return raw.replace(/\/$/, "");
}

export interface ProductSummary {
  id: string;
  name: string;
  type: string;
}

/** Local catalog used until GET /api/products answers (or when the API is offline). */
export const FALLBACK_PRODUCTS: ProductSummary[] = [
  {
    id: "mahjong",
    name: "Mahjong Score Calculator / 麻雀点数計算",
    type: "hybrid",
  },
  {
    id: "shopping-memo",
    name: "Shopping List Memo / 買い物メモ",
    type: "mobile_app",
  },
  {
    id: "nextuta",
    name: "次うた",
    type: "hybrid",
  },
];

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
 * The safe message of a failed Analyze: FastAPI sends { detail: { error, code } }
 * (older responses may put error at the top level). Null if there is none.
 */
export function analyzeErrorMessage(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const body = payload as { error?: unknown; detail?: unknown };
  const detail =
    body.detail && typeof body.detail === "object" ? (body.detail as { error?: unknown }) : null;
  const message = detail?.error ?? body.error;
  return typeof message === "string" && message.trim() ? message.trim() : null;
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

  const payload = (await response.json().catch(() => null)) as AnalyzeApiResponse | null;

  if (!response.ok) {
    throw new AnalyzeRequestError(analyzeErrorMessage(payload) || "analyze_failed");
  }

  if (!payload || typeof payload !== "object" || !("analysis" in payload)) {
    throw new AnalyzeRequestError("analyze_failed");
  }

  return payload as AnalyzeApiResponse;
}
