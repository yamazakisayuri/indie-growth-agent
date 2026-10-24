"use client";

import Image from "next/image";
import Link from "next/link";
import type { ProductSummary } from "@/lib/analyze-client";
import { useLanguage } from "@/lib/language-context";
import { hasSuccessfulReport } from "@/lib/map-report";
import { PORTFOLIO_PATH } from "@/lib/routes";
import type { GrowthReport } from "@/lib/types";
import { LanguageSelector } from "./LanguageSelector";

interface HeaderProps {
  report: GrowthReport;
  analyzing: boolean;
  elapsedSec: number;
  error: string | null;
  products: ProductSummary[];
  productId: string;
  onProductChange: (productId: string) => void;
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
  products,
  productId,
  onProductChange,
  onAnalyze,
}: HeaderProps) {
  const { copy } = useLanguage();
  const periodLabel = asDisplayText(report.periodLabel);
  const comparisonLabel = asDisplayText(report.comparisonLabel);
  const productLabel =
    report.product?.name ||
    products.find((item) => item.id === productId)?.name ||
    productId;
  const appLabel = hasSuccessfulReport(report)
      ? asDisplayText(report.appName, productLabel)
      : productLabel;

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
            <dt>{copy("targetProduct")}</dt>
            <dd>{asDisplayText(productLabel)}</dd>
          </div>
          <div>
            <dt>{copy("targetApp")}</dt>
            <dd>{appLabel}</dd>
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
        {hasSuccessfulReport(report) && !analyzing ? (
          <p className="site-header__live-badge">
            {copy("usingLive")}
            {report.analysisRunId ? (
              <span className="site-header__run-id">
                {" "}
                · run {report.analysisRunId.slice(0, 8)}
              </span>
            ) : null}
          </p>
        ) : null}
        {!hasSuccessfulReport(report) && !analyzing ? (
          <p className="site-header__empty-badge" role="status">
            {copy("noCachedReport")}
          </p>
        ) : null}
        {error ? (
          <div className="site-header__error-row">
            <p className="site-header__error" role="alert">
              {asDisplayText(error, copy("analyzeError"))}
            </p>
            <button
              type="button"
              className="site-header__retry-btn"
              onClick={onAnalyze}
              disabled={analyzing}
            >
              {copy("retryAnalyze")}
            </button>
          </div>
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
        <label className="product-selector">
          <span className="product-selector__label">{copy("targetProduct")}</span>
          <select
            className="product-selector__select"
            value={productId}
            disabled={analyzing}
            onChange={(event) => onProductChange(event.target.value)}
            aria-label={copy("targetProduct")}
          >
            {products.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <LanguageSelector />
        <button
          type="button"
          className="analyze-btn"
          onClick={onAnalyze}
          disabled={analyzing}
        >
          {analyzing ? copy("analyzing") : copy("analyze")}
        </button>
        {/* Leaving mid-Analyze would abort the run. */}
        <Link
          href={PORTFOLIO_PATH}
          className="analyze-btn portfolio__nav-link"
          aria-disabled={analyzing || undefined}
          tabIndex={analyzing ? -1 : undefined}
          onClick={(event) => {
            if (analyzing) {
              event.preventDefault();
            }
          }}
        >
          {copy("portfolioOpen")}
        </Link>
      </div>
    </header>
  );
}
