"use client";

import type { DisplayMetric, GrowthReport } from "@/lib/types";
import { useLanguage } from "@/lib/language-context";
import { MetricChange } from "./MetricChange";

function MetricRow({ metric }: { metric: DisplayMetric }) {
  const isSecondary = Boolean(metric.absolute) && !metric.value;

  return (
    <div className={isSecondary ? "metric-row metric-row--secondary" : "metric-row"}>
      <div className="metric-row__label-block">
        <span className="metric-row__label">{metric.label}</span>
        {metric.note ? <span className="metric-row__note">{metric.note}</span> : null}
      </div>
      <div className="metric-row__values">
        {metric.value ? (
          <span className="metric-row__absolute">{metric.value}</span>
        ) : null}
        {metric.absolute ? (
          <span className="metric-row__absolute metric-row__absolute--muted">
            {metric.absolute}
          </span>
        ) : null}
        <MetricChange changePercent={metric.changePercent} />
      </div>
    </div>
  );
}

export function MetricsSummary({ report }: { report: GrowthReport }) {
  const { copy } = useLanguage();

  return (
    <section className="metrics" aria-label="Metrics summary">
      {report.metrics.map((block) => (
        <article key={block.id} className="metrics__card">
          <header className="metrics__card-header">
            <h2 className="metrics__title">{block.title}</h2>
            <p className="metrics__source">{block.source}</p>
            {block.id === "revenue" ? (
              <p className="metrics__source-note">{copy("revenueAdmobNote")}</p>
            ) : null}
          </header>
          {block.connected && block.metrics.length > 0 ? (
            <div className="metrics__list">
              {block.metrics.map((metric) => (
                <MetricRow key={metric.id} metric={metric} />
              ))}
            </div>
          ) : (
            <p className="metrics__empty">
              {block.statusMessage || copy("notConnected")}
            </p>
          )}
        </article>
      ))}
    </section>
  );
}
