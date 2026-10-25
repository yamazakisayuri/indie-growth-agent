"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Dashboard } from "@/components/Dashboard";
import {
  AnalyzeRequestError,
  FALLBACK_PRODUCTS,
  requestAnalyze,
  requestProducts,
  type ProductSummary,
} from "@/lib/analyze-client";
import { useLanguage } from "@/lib/language-context";
import {
  buildEmptyReport,
  hasSuccessfulReport,
  mapAnalyzeResponse,
} from "@/lib/map-report";
import {
  loadCachedReport,
  loadSelectedProductId,
  saveCachedReport,
  saveSelectedProductId,
} from "@/lib/report-cache";
import type { GrowthReport } from "@/lib/types";

/**
 * My Workspace: last successful Live Analyze from localStorage (per Product).
 * Analyze refreshes via POST { language, productId } → Agent API.
 */
export function MyWorkspace() {
  const { language, copy } = useLanguage();
  const [products, setProducts] = useState<ProductSummary[]>(FALLBACK_PRODUCTS);
  const [productId, setProductId] = useState("mahjong");
  const [liveReport, setLiveReport] = useState<GrowthReport | null>(null);
  const [cacheReady, setCacheReady] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const previousLanguage = useRef(language);
  const abortRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);

  // Hydrate last Product + last successful report from localStorage (client only).
  useEffect(() => {
    // Not validated against FALLBACK_PRODUCTS: the API catalog may list more
    // products, and it re-validates the id once it loads.
    const initialProductId = loadSelectedProductId() || "mahjong";
    const cached = loadCachedReport(initialProductId);
    /* External store (localStorage) → React state; intentional one-shot hydrate. */
    /* eslint-disable react-hooks/set-state-in-effect -- localStorage hydrate */
    setProductId(initialProductId);
    setLiveReport(cached);
    setCacheReady(true);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    requestProducts(controller.signal)
      .then((data) => {
        if (data.products.length > 0) {
          setProducts(data.products);
        }
        const catalog = data.products.length > 0 ? data.products : FALLBACK_PRODUCTS;
        const savedProductId = loadSelectedProductId();
        const nextId =
          (savedProductId &&
            catalog.some((item) => item.id === savedProductId) &&
            savedProductId) ||
          data.defaultProductId ||
          catalog[0]?.id ||
          "mahjong";
        setProductId((current) => {
          if (catalog.some((item) => item.id === current)) {
            return current;
          }
          setLiveReport(loadCachedReport(nextId));
          saveSelectedProductId(nextId);
          return nextId;
        });
      })
      .catch(() => {
        if (controller.signal.aborted) {
          return;
        }
        // Keep local fallback catalog when API is offline; drop ids it does not list.
        setProductId((current) => {
          if (FALLBACK_PRODUCTS.some((item) => item.id === current)) {
            return current;
          }
          setLiveReport(loadCachedReport("mahjong"));
          return "mahjong";
        });
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (previousLanguage.current === language) {
      return;
    }
    previousLanguage.current = language;
    // Keep last successful Analyze / Planner context across display-language switches.
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

  const onProductChange = useCallback((nextProductId: string) => {
    setProductId((current) => {
      if (nextProductId === current) {
        return current;
      }
      abortRef.current?.abort();
      abortRef.current = null;
      requestIdRef.current += 1;
      setAnalyzing(false);
      setElapsedSec(0);
      setError(null);
      setLiveReport(loadCachedReport(nextProductId));
      saveSelectedProductId(nextProductId);
      return nextProductId;
    });
  }, []);

  const report = useMemo(() => {
    if (liveReport && hasSuccessfulReport(liveReport)) {
      return liveReport;
    }
    const selected = products.find((item) => item.id === productId) ?? {
      id: productId,
      name: productId,
      type: "unknown",
    };
    return buildEmptyReport(language, {
      id: selected.id,
      name: selected.name,
      type: selected.type,
    });
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
      if (data.product?.id && data.product.id !== analyzeProductId) {
        return;
      }
      const mapped = mapAnalyzeResponse(data);
      setLiveReport(mapped);
      saveCachedReport(analyzeProductId, mapped);
      saveSelectedProductId(analyzeProductId);
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

  // Avoid flashing empty shell before localStorage hydrate.
  if (!cacheReady) {
    return <div className="dashboard" aria-busy="true" />;
  }

  return (
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
  );
}
