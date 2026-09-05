import { NextResponse } from "next/server";

export const runtime = "nodejs";
/** Bedrock + three data sources can take a while locally. */
export const maxDuration = 300;

const DEFAULT_AGENT_API_URL = "http://127.0.0.1:8000";

type Language = "ja" | "en";

function publicError(language: Language): string {
  return language === "ja"
    ? "分析を完了できませんでした。データ接続を確認してください。"
    : "Could not complete the analysis. Please check your data connections.";
}

/**
 * Server-side proxy to the local Python Agent API.
 * Keeps AGENT_API_URL off the client and avoids browser CORS for the Python port.
 */
export async function POST(request: Request) {
  let language: Language = "en";

  try {
    const body = (await request.json()) as { language?: string };
    if (body.language === "ja" || body.language === "en") {
      language = body.language;
    }
  } catch {
    // keep default language
  }

  const baseUrl = (
    process.env.AGENT_API_URL?.trim() || DEFAULT_AGENT_API_URL
  ).replace(/\/$/, "");

  try {
    const upstream = await fetch(`${baseUrl}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language }),
      // Local analysis can exceed default fetch timeouts in some runtimes.
      signal: AbortSignal.timeout(280_000),
    });

    const text = await upstream.text();
    let data: unknown = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = null;
    }

    if (!upstream.ok) {
      const detail =
        data &&
        typeof data === "object" &&
        data !== null &&
        "detail" in data &&
        typeof (data as { detail: unknown }).detail === "object" &&
        (data as { detail: { error?: string } }).detail?.error
          ? String((data as { detail: { error?: string } }).detail.error)
          : publicError(language);

      console.error(
        "[api/analyze] upstream failed",
        upstream.status,
        typeof data === "object" && data && "detail" in data
          ? (data as { detail: unknown }).detail
          : "non-json body",
      );

      return NextResponse.json({ error: detail }, { status: 502 });
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error(
      "[api/analyze] proxy error",
      error instanceof Error ? error.message : "unknown",
    );
    return NextResponse.json(
      { error: publicError(language) },
      { status: 502 },
    );
  }
}
