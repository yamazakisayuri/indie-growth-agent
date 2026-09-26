"use client";

import { useLanguage } from "@/lib/language-context";

interface MetricChangeProps {
  changePercent: number | null;
}

function formatChange(changePercent: number): string {
  const rounded = Math.round(changePercent * 10) / 10;
  const sign = rounded > 0 ? "+" : "";
  return `${sign}${rounded}%`;
}

export function MetricChange({ changePercent }: MetricChangeProps) {
  const { copy } = useLanguage();

  if (changePercent === null || Number.isNaN(changePercent)) {
    return (
      <span className="metric-change metric-change--flat" title="n/a">
        <span className="metric-change__value">n/a</span>
      </span>
    );
  }

  const direction =
    changePercent > 0 ? "up" : changePercent < 0 ? "down" : "flat";
  const arrow = direction === "up" ? "▲" : direction === "down" ? "▼" : "–";
  const formatted = formatChange(changePercent);
  const label = `${formatted} ${copy("changeVsPrevious")}`;

  return (
    <span
      className={`metric-change metric-change--${direction}`}
      title={label}
      aria-label={label}
    >
      <span className="metric-change__arrow" aria-hidden="true">
        {arrow}
      </span>
      <span className="metric-change__value">{formatted}</span>
    </span>
  );
}
