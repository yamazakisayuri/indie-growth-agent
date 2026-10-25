"use client";

import type { CopyKey } from "@/lib/i18n";
import { useLanguage } from "@/lib/language-context";
import type { PeriodPair, Period, SampleSnapshot } from "@/lib/sample-workspace";
import { MetricChange } from "./MetricChange";

function shortDate(iso: string): string {
  const [, month, day] = iso.split("-");
  return month && day ? `${Number(month)}/${Number(day)}` : iso;
}

function shortPeriod(period: Period): string {
  return `${shortDate(period.start)}–${shortDate(period.end)}`;
}

/** Previous vs last 7 days as two bars on one zero-based scale, its own per chart. */
function PeriodBars({
  title,
  pair,
  snapshot,
}: {
  title: string;
  pair: PeriodPair;
  snapshot: SampleSnapshot;
}) {
  const { copy, language } = useLanguage();
  const format = (value: number | null) =>
    value === null ? "—" : value.toLocaleString(language === "ja" ? "ja-JP" : "en-US");
  const max = Math.max(pair.previous ?? 0, pair.current ?? 0);
  const rows: { key: string; label: CopyKey; period: Period; value: number | null }[] = [
    { key: "previous", label: "samplePrevious", period: snapshot.previous, value: pair.previous },
    { key: "current", label: "sampleCurrentPeriod", period: snapshot.current, value: pair.current },
  ];
  const summary = `${title}: ${rows
    .map((row) => `${copy(row.label)} (${shortPeriod(row.period)}) ${format(row.value)}`)
    .join(", ")}`;

  return (
    <figure className="snapshot-card" aria-label={summary}>
      <figcaption className="snapshot-card__head">
        <span className="snapshot-card__title">{title}</span>
        <MetricChange changePercent={pair.changePercent} />
      </figcaption>
      <ul className="snapshot-bars" aria-hidden="true">
        {rows.map((row) => (
          <li key={row.key} className={`snapshot-bars__row snapshot-bars__row--${row.key}`}>
            <span className="snapshot-bars__label">
              {copy(row.label)} <span className="snapshot-bars__period">{shortPeriod(row.period)}</span>
            </span>
            <span className="snapshot-bars__track">
              {row.value !== null && max > 0 ? (
                <span
                  className="snapshot-bars__bar"
                  style={{ width: `${(row.value / max) * 100}%` }}
                />
              ) : null}
            </span>
            <span className="snapshot-bars__value">{format(row.value)}</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}

/** "What happened in the app": three small charts from the fictional sample, before the proposals. */
export function SampleSnapshotSection({ snapshot }: { snapshot: SampleSnapshot }) {
  const { copy } = useLanguage();
  const charts: { key: string; title: CopyKey; pair: PeriodPair }[] = [
    { key: "downloads", title: "snapshotDownloads", pair: snapshot.downloads },
    { key: "browse-impressions", title: "snapshotBrowseImpressions", pair: snapshot.browseImpressions },
    { key: "browse-downloads", title: "snapshotBrowseDownloads", pair: snapshot.browseDownloads },
  ];
  return (
    <section className="snapshot" aria-labelledby="snapshot-title">
      <div className="snapshot__head">
        <h2 id="snapshot-title" className="snapshot__title">
          {copy("snapshotTitle")}
        </h2>
        <span className="sample-badge">{copy("sampleBadge")}</span>
      </div>
      <p className="snapshot__lead">{copy("snapshotLead")}</p>
      <div className="snapshot__grid">
        {charts.map((chart) => (
          <PeriodBars key={chart.key} title={copy(chart.title)} pair={chart.pair} snapshot={snapshot} />
        ))}
      </div>
      <p className="snapshot__note">{copy("snapshotNote")}</p>
    </section>
  );
}
