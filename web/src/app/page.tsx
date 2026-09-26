"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Dashboard } from "@/components/Dashboard";
import {
  AnalyzeRequestError,
  requestAnalyze,
  requestProducts,
  type ProductSummary,
} from "@/lib/analyze-client";
import { LanguageProvider, useLanguage } from "@/lib/language-context";
import { buildMockReport, mapAnalyzeResponse } from "@/lib/map-report";
import type { GrowthReport } from "@/lib/types";

const FALLBACK_PRODUCTS: ProductSummary[] = [
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
];

function DashboardApp() {
  const { language, copy } = useLanguage();
  const [products, setProducts] = useState<ProductSummary[]>(FALLBACK_PRODUCTS);
  const [productId, setProductId] = useState("mahjong");
  const [liveReport, setLiveReport] = useState<GrowthReport | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const previousLanguage = useRef(language);
  const abortRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    requestProducts(controller.signal)
      .then((data) => {
        if (data.products.length > 0) {
          setProducts(data.products);
        }
        const nextId = data.defaultProductId || data.products[0]?.id || "mahjong";
        setProductId((current) => {
          if (data.products.some((item) => item.id === current)) {
            return current;
          }
          return nextId;
        });
      })
      .catch(() => {
        // Keep local fallback catalog when API is offline (mock mode).
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (previousLanguage.current === language) {
      return;
    }
    previousLanguage.current = language;
    // Keep live Analyze / Planner context across display-language switches.
    // Only abort an in-flight Analyze; never fall back to mock implicitly.
    abortRef.current?.abort();
    abortRef.current = null;
    requestIdRef.current += 1;
    setAnalyzing(false);
    setElapsedSec(0);
    setError(null);
  }, [language]);

  useEffect(() => {
    if (!analyzing) {
      return;
    }
    const timer = window.setInterval(() => {
      setElapsedSec((value) => value + 1);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [analyzing]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const clearProductScopedState = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    requestIdRef.current += 1;
    setLiveReport(null);
    setAnalyzing(false);
    setElapsedSec(0);
    setError(null);
  }, []);

  const onProductChange = useCallback(
    (nextProductId: string) => {
      if (nextProductId === productId) {
        return;
      }
      setProductId(nextProductId);
      // Drop previous Product's Analyze / Planner / Draft surface entirely.
      clearProductScopedState();
    },
    [productId, clearProductScopedState],
  );

  const report = useMemo(() => {
    if (liveReport) {
      return liveReport;
    }
    const selected =
      products.find((item) => item.id === productId) ?? FALLBACK_PRODUCTS[0];
    const mock = buildMockReport(language);
    return {
      ...mock,
      product: {
        id: selected.id,
        name: selected.name,
        type: selected.type,
      },
      // Mock stays mahjong-shaped until Analyze; clear experiments so Draft
      // cannot run against a mismatched Product.
      growthExperiments: [],
      plannerStatus: null,
      plannerError: null,
      knownEventsConsidered: [],
      knownEventsUsed: [],
    };
  }, [liveReport, language, productId, products]);

  const onAnalyze = useCallback(async () => {
    if (analyzing) {
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    const analyzeProductId = productId;

    setAnalyzing(true);
    setElapsedSec(0);
    setError(null);

    try {
      const data = await requestAnalyze(
        language,
        analyzeProductId,
        controller.signal,
      );
      if (requestId !== requestIdRef.current) {
        return;
      }
      // Discard stale responses if the user switched Product mid-flight.
      if (
        data.product?.id &&
        data.product.id !== analyzeProductId
      ) {
        return;
      }
      setLiveReport(mapAnalyzeResponse(data));
    } catch (err) {
      if (requestId !== requestIdRef.current) {
        return;
      }
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      const message =
        err instanceof AnalyzeRequestError && err.message
          ? err.message
          : copy("analyzeError");
      setError(typeof message === "string" ? message : copy("analyzeError"));
    } finally {
      if (requestId === requestIdRef.current) {
        setAnalyzing(false);
        abortRef.current = null;
      }
    }
  }, [analyzing, language, productId, copy]);

  return (
    <main className="page-shell">
      <Dashboard
        report={report}
        analyzing={analyzing}
        elapsedSec={elapsedSec}
        error={error}
        products={products}
        productId={productId}
        onProductChange={onProductChange}
        onAnalyze={onAnalyze}
      />
    </main>
  );
}

/**
 * Entry: mock report until Analyze succeeds.
 * Analyze posts { language, productId } to NEXT_PUBLIC_AGENT_API_URL /api/analyze.
 */
export default function Home() {
  return (
    <LanguageProvider>
      <DashboardApp />
    </LanguageProvider>
  );
}
