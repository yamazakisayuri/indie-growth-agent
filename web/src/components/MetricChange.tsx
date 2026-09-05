"use client";

interface MetricChangeProps {
  changePercent: number | null;
}

function formatChange(changePercent: number): string {
  const rounded = Math.round(changePercent * 10) / 10;
  const sign = rounded > 0 ? "+" : "";
  return `${sign}${rounded}%`;
}

export function MetricChange({ changePercent }: MetricChangeProps) {
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

  return (
    <span
      className={`metric-change metric-change--${direction}`}
      title={`${formatChange(changePercent)} vs previous period`}
    >
      <span className="metric-change__arrow" aria-hidden="true">
        {arrow}
      </span>
      <span className="metric-change__value">{formatChange(changePercent)}</span>
    </span>
  );
}
