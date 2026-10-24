"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  FALLBACK_PRODUCTS,
  requestProducts,
  type ProductSummary,
} from "@/lib/analyze-client";
import { useLanguage } from "@/lib/language-context";
import {
  buildPortfolioEntries,
  type PortfolioEntry,
  type PortfolioKpiBlock,
} from "@/lib/portfolio";
import { loadCachedReport, saveSelectedProductId } from "@/lib/report-cache";
import { DASHBOARD_PATH } from "@/lib/routes";
import { LanguageSelector } from "./LanguageSelector";
import { MetricChange } from "./MetricChange";

function KpiBlock({ block }: { block: PortfolioKpiBlock }) {
  const { copy } = useLanguage();

  return (
    <div className="portfolio-kpi">
      <dt className="portfolio-kpi__title">{block.title}</dt>
      {block.status === "ok" ? (
        block.metrics.map((metric) => (
          <dd key={metric.id} className="portfolio-kpi__row">
            <span className="portfolio-kpi__label">{metric.label}</span>
            <span className="portfolio-kpi__values">
              {metric.value || metric.absolute ? (
                <span className="metric-row__absolute">
                  {metric.value || metric.absolute}
                </span>
              ) : null}
              <MetricChange changePercent={metric.changePercent} />
            </span>
          </dd>
        ))
      ) : (
        <dd className="portfolio-kpi__empty">
          {block.statusMessage ||
            copy(block.status === "not_connected" ? "notConnected" : "portfolioNoData")}
        </dd>
      )}
    </div>
  );
}

function PortfolioCard({ entry }: { entry: PortfolioEntry }) {
  const { copy } = useLanguage();
  const analyzed = entry.status === "analyzed";
  const statusLabel = copy(analyzed ? "portfolioAnalyzed" : "portfolioNotAnalyzed");

  return (
    <li
      className={
        analyzed ? "portfolio-card" : "portfolio-card portfolio-card--not-analyzed"
      }
    >
      <header className="portfolio-card__header">
        <div className="portfolio-card__identity">
          <h2 className="portfolio-card__name">{entry.product.name}</h2>
          {analyzed && entry.periodLabel ? (
            <p className="portfolio-card__period">{entry.periodLabel}</p>
          ) : null}
        </div>
        <span
          className={
            analyzed
              ? "portfolio-card__badge portfolio-card__badge--analyzed"
              : "portfolio-card__badge"
          }
        >
          {statusLabel}
        </span>
      </header>

      {entry.status === "analyzed" ? (
        <>
          <section className="portfolio-card__action">
            <h3 className="portfolio-card__label">{copy("portfolioTopAction")}</h3>
            {entry.topAction ? (
              <>
                <p className="portfolio-card__action-title">{entry.topAction.title}</p>
                {entry.topAction.reason ? (
                  <p className="portfolio-card__action-reason">
                    {entry.topAction.reason}
                  </p>
                ) : null}
              </>
            ) : (
              <p className="panel-empty">{copy("portfolioNoTopAction")}</p>
            )}
          </section>

          <section className="portfolio-card__kpis">
            <h3 className="portfolio-card__label">{copy("portfolioKpis")}</h3>
            <dl className="portfolio-card__kpi-list">
              {entry.kpis.map((block) => (
                <KpiBlock key={block.id} block={block} />
              ))}
            </dl>
          </section>
        </>
      ) : (
        <p className="portfolio-card__empty">{copy("portfolioNotAnalyzedHint")}</p>
      )}

      <footer className="portfolio-card__footer">
        {entry.status === "analyzed" ? (
          <span className="portfolio-card__run">
            run {entry.analysisRunId.slice(0, 8)}
          </span>
        ) : (
          <span />
        )}
        <Link
          href={DASHBOARD_PATH}
          className="portfolio-card__link"
          aria-label={`${copy("portfolioOpenDashboard")}: ${entry.product.name}`}
          onClick={() => saveSelectedProductId(entry.product.id)}
        >
          {copy("portfolioOpenDashboard")} →
        </Link>
      </footer>
    </li>
  );
}

/** All configured products with their last saved Live Analyze (localStorage only). */
export function PortfolioOverview() {
  const { copy } = useLanguage();
  const [products, setProducts] = useState<ProductSummary[]>(FALLBACK_PRODUCTS);
  const [cacheReady, setCacheReady] = useState(false);

  useEffect(() => {
    /* eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage is client-only */
    setCacheReady(true);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    requestProducts(controller.signal)
      .then((data) => {
        if (data.products.length > 0) {
          setProducts(data.products);
        }
      })
      .catch(() => {
        // Keep local fallback catalog when API is offline.
      });
    return () => controller.abort();
  }, []);

  const entries = useMemo(() => {
    if (!cacheReady) {
      return null;
    }
    const reports = Object.fromEntries(
      products.map((product) => [product.id, loadCachedReport(product.id)]),
    );
    return buildPortfolioEntries(products, reports);
  }, [cacheReady, products]);

  if (!entries) {
    return <div className="dashboard" aria-busy="true" />;
  }

  const analyzedCount = entries.filter((entry) => entry.status === "analyzed").length;

  return (
    <div className="dashboard portfolio">
      <header className="site-header">
        <div className="site-header__brand">
          <div className="site-header__title-stack">
            <p className="site-header__title">Indie Growth Agent</p>
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
          </div>
          <div>
            <p className="actions__eyebrow">{copy("portfolioEyebrow")}</p>
            <h1 className="actions__title">{copy("portfolioTitle")}</h1>
          </div>
          <p className="portfolio__summary">
            {entries.length} {copy("portfolioCountApps")} · {copy("portfolioAnalyzed")}{" "}
            {analyzedCount} · {copy("portfolioNotAnalyzed")}{" "}
            {entries.length - analyzedCount}
          </p>
        </div>
        <div className="site-header__controls">
          <LanguageSelector />
          <Link href={DASHBOARD_PATH} className="analyze-btn portfolio__nav-link">
            {copy("portfolioBackToDashboard")}
          </Link>
        </div>
      </header>

      <p className="portfolio__note">{copy("portfolioDataNote")}</p>

      <ul className="portfolio__grid">
        {entries.map((entry) => (
          <PortfolioCard key={entry.product.id} entry={entry} />
        ))}
      </ul>
    </div>
  );
}
