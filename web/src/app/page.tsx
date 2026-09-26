"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Dashboard } from "@/components/Dashboard";
import {
  AnalyzeRequestError,
  requestAnalyze,
} from "@/lib/analyze-client";
import { LanguageProvider, useLanguage } from "@/lib/language-context";
import { buildMockReport, mapAnalyzeResponse } from "@/lib/map-report";
import type { GrowthReport } from "@/lib/types";

function DashboardApp() {
  const { language, copy } = useLanguage();
  const [liveReport, setLiveReport] = useState<GrowthReport | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const previousLanguage = useRef(language);
  const abortRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);

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

  const report = useMemo(() => {
    if (liveReport) {
      return liveReport;
    }
    return buildMockReport(language);
  }, [liveReport, language]);

  const onAnalyze = useCallback(async () => {
    if (analyzing) {
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;

    setAnalyzing(true);
    setElapsedSec(0);
    setError(null);

    try {
      const data = await requestAnalyze(language, controller.signal);
      if (requestId !== requestIdRef.current) {
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
  }, [analyzing, language, copy]);

  return (
    <main className="page-shell">
      <Dashboard
        report={report}
        analyzing={analyzing}
        elapsedSec={elapsedSec}
        error={error}
        onAnalyze={onAnalyze}
      />
    </main>
  );
}

/**
 * Entry: mock report until Analyze succeeds.
 * Analyze posts { language } to NEXT_PUBLIC_AGENT_API_URL /api/analyze.
 */
export default function Home() {
  return (
    <LanguageProvider initialLanguage="en">
      <DashboardApp />
    </LanguageProvider>
  );
}
