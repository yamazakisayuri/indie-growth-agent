"use client";

import Image from "next/image";
import { useLanguage } from "@/lib/language-context";
import type { GrowthReport } from "@/lib/types";
import { LanguageSelector } from "./LanguageSelector";

interface HeaderProps {
  report: GrowthReport;
  analyzing: boolean;
  elapsedSec: number;
  error: string | null;
  onAnalyze: () => void;
}

function asDisplayText(value: unknown, fallback = ""): string {
  if (typeof value === "string") {
    return value;
  }
  if (
    value &&
    typeof value === "object" &&
    "ja" in value &&
    "en" in value &&
    typeof (value as { ja: unknown }).ja === "string" &&
    typeof (value as { en: unknown }).en === "string"
  ) {
    // Defensive: old mock shape { ja, en } must never crash React render.
    return (value as { ja: string; en: string }).en || fallback;
  }
  return fallback;
}

export function Header({
  report,
  analyzing,
  elapsedSec,
  error,
  onAnalyze,
}: HeaderProps) {
  const { copy } = useLanguage();
  const periodLabel = asDisplayText(report.periodLabel);
  const comparisonLabel = asDisplayText(report.comparisonLabel);

  return (
    <header className="site-header">
      <div className="site-header__brand">
        <div className="site-header__title-row">
          <div className="site-header__title-stack">
            <h1 className="site-header__title">Indie Growth Agent</h1>
            <div className="site-header__by-row">
              <Image
                src="/makosoyo-mark.png"
                alt=""
                width={20}
                height={20}
                className="site-header__mark"
                priority
              />
              <p className="site-header__by">{copy("brandBy")}</p>
            </div>
            <p className="site-header__tagline">{copy("brandTagline")}</p>
          </div>
        </div>
        <dl className="site-header__meta">
          <div>
            <dt>{copy("targetApp")}</dt>
            <dd>{asDisplayText(report.appName)}</dd>
          </div>
          <div>
            <dt>{copy("analysisPeriod")}</dt>
            <dd>
              {periodLabel}
              <span className="site-header__compare">
                {" "}
                · {comparisonLabel}
              </span>
            </dd>
          </div>
        </dl>
        {report.source === "live" && !analyzing ? (
          <p className="site-header__live-badge">{copy("usingLive")}</p>
        ) : null}
        {error ? (
          <p className="site-header__error" role="alert">
            {asDisplayText(error, copy("analyzeError"))}
          </p>
        ) : null}
        {analyzing ? (
          <div className="site-header__progress" aria-live="polite">
            <p className="site-header__status">
              {copy("analyzing")}
              <span className="site-header__elapsed"> ({elapsedSec}s)</span>
            </p>
            <p className="site-header__hint">{copy("analyzingHint")}</p>
          </div>
        ) : null}
      </div>

      <div className="site-header__controls">
        <LanguageSelector />
        <button
          type="button"
          className="analyze-btn"
          onClick={onAnalyze}
          disabled={analyzing}
        >
          {analyzing ? copy("analyzing") : copy("analyze")}
        </button>
      </div>
    </header>
  );
}
