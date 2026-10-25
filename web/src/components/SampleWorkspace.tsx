"use client";

import Image from "next/image";
import Link from "next/link";
import { useMemo } from "react";
import type { CopyKey } from "@/lib/i18n";
import { useLanguage } from "@/lib/language-context";
import { DEMO_PATH, PORTFOLIO_PATH } from "@/lib/routes";
import {
  pickRepresentativeRecorded,
  summarizeKpis,
  summarizeSources,
  type CountKpi,
  type CountKpiId,
  type KpiSummary,
  type Period,
  type RateKpi,
  type RateKpiId,
  type RecordedSummary,
  type SampleWorkspaceData,
} from "@/lib/sample-workspace";
import { languageName, outcomeCounts, versionLabel } from "@/lib/recorded-demo";
import { hasGloss, sampleAppName } from "@/lib/sample-glossary";
import { ActionDetails } from "./ActionDetails";
import { GlossedText } from "./GlossedText";
import { Badge, STATUS_COPY } from "./EvidencePanel";
import { LanguageSelector } from "./LanguageSelector";
import { MetricChange } from "./MetricChange";
import { TopActions } from "./TopActions";
import { TrendChart } from "./TrendChart";

const COUNT_LABEL: Record<CountKpiId, { label: CopyKey; def: CopyKey }> = {
  impressions: { label: "sampleKpiImpressions", def: "sampleKpiImpressionsDef" },
  product_page_views: { label: "sampleKpiPageViews", def: "sampleKpiPageViewsDef" },
  first_time_downloads: { label: "sampleKpiDownloads", def: "sampleKpiDownloadsDef" },
};

const RATE_LABEL: Record<RateKpiId, CopyKey> = {
  page_view_rate: "sampleKpiPageViewRate",
  download_rate: "sampleKpiDownloadRate",
  impression_download_rate: "sampleKpiImpressionDownloadRate",
};

function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) =>
    key in values ? String(values[key]) : match,
  );
}

function useFormat() {
  const { language } = useLanguage();
  const locale = language === "ja" ? "ja-JP" : "en-US";
  return {
    number: (value: number | null) => (value === null ? "—" : value.toLocaleString(locale)),
    percent: (value: number | null, digits: number) =>
      value === null ? "—" : `${(value * 100).toFixed(digits)}%`,
    period: (p: Period) => `${p.start} – ${p.end}`,
  };
}

function SampleHeader({ data, summary }: { data: SampleWorkspaceData; summary: KpiSummary | null }) {
  const { copy, language } = useLanguage();
  const format = useFormat();
  const appName = sampleAppName(data.app, language);
  return (
    <header className="site-header">
      <div className="site-header__brand">
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
        <dl className="site-header__meta">
          <div>
            <dt>{copy("targetApp")}</dt>
            <dd title={appName !== data.app.name ? data.app.name : undefined}>{appName}</dd>
          </div>
          {summary ? (
            <div>
              <dt>{copy("analysisPeriod")}</dt>
              <dd>
                {format.period(summary.current)}
                <span className="site-header__compare">
                  {" "}
                  · vs {format.period(summary.previous)}
                </span>
              </dd>
            </div>
          ) : null}
          <div>
            <dt>{copy("sampleDataKind")}</dt>
            <dd>
              <span className="sample-badge">{copy("sampleBadge")}</span>{" "}
              {copy("sampleDataKindValue")}
            </dd>
          </div>
        </dl>
      </div>
      <div className="site-header__controls">
        <LanguageSelector />
        <div className="site-header__nav">
          <Link href={PORTFOLIO_PATH} className="analyze-btn portfolio__nav-link">
            {copy("portfolioOpen")}
          </Link>
          <Link href={DEMO_PATH} className="analyze-btn portfolio__nav-link">
            {copy("demoNavLink")}
          </Link>
        </div>
      </div>
    </header>
  );
}

function CountCard({ kpi }: { kpi: CountKpi }) {
  const { copy } = useLanguage();
  const format = useFormat();
  const labels = COUNT_LABEL[kpi.id];
  return (
    <article className="kpi-card">
      <h3 className="kpi-card__label">{copy(labels.label)}</h3>
      <p className="kpi-card__value">{format.number(kpi.current)}</p>
      <p className="kpi-card__compare">
        <MetricChange changePercent={kpi.changePercent} />
        <span>
          {copy("samplePrevious")} {format.number(kpi.previous)}
        </span>
      </p>
      <p className="kpi-card__def">{copy(labels.def)}</p>
    </article>
  );
}

function RateCard({ kpi, summary }: { kpi: RateKpi; summary: KpiSummary }) {
  const { copy } = useLanguage();
  const format = useFormat();
  const digits = kpi.id === "impression_download_rate" ? 2 : 1;
  const totals = Object.fromEntries(summary.counts.map((c) => [c.id, c]));
  const numerator = totals[kpi.numerator];
  const denominator = totals[kpi.denominator];
  const delta = kpi.deltaPoints;
  const tone = delta === null || delta === 0 ? "flat" : delta > 0 ? "up" : "down";
  return (
    <article className="kpi-card kpi-card--rate">
      <h3 className="kpi-card__label">{copy(RATE_LABEL[kpi.id])}</h3>
      <p className="kpi-card__value">{format.percent(kpi.current, digits)}</p>
      <p className="kpi-card__compare">
        <span className={`metric-change metric-change--${tone}`}>
          {delta === null ? "n/a" : `${delta > 0 ? "+" : ""}${delta.toFixed(digits)}pt`}
        </span>
        <span>
          {copy("samplePrevious")} {format.percent(kpi.previous, digits)}
        </span>
      </p>
      <p className="kpi-card__def">
        {copy(COUNT_LABEL[kpi.numerator].label)} ÷ {copy(COUNT_LABEL[kpi.denominator].label)}
        {" = "}
        {format.number(numerator?.current ?? null)} ÷ {format.number(denominator?.current ?? null)}
      </p>
    </article>
  );
}

function KpiSection({ summary }: { summary: KpiSummary }) {
  const { copy } = useLanguage();
  const format = useFormat();
  return (
    <section className="sample-section" aria-labelledby="sample-kpis">
      <h2 id="sample-kpis" className="sample-section__title">
        {copy("sampleKpiTitle")}
      </h2>
      <div className="kpi-grid">
        {summary.counts.map((kpi) => (
          <CountCard key={kpi.id} kpi={kpi} />
        ))}
        {summary.rates.map((kpi) => (
          <RateCard key={kpi.id} kpi={kpi} summary={summary} />
        ))}
      </div>
      <p className="sample-section__note">
        {fill(copy("sampleKpiNote"), {
          current: format.period(summary.current),
          previous: format.period(summary.previous),
        })}
      </p>
    </section>
  );
}

function TrendSection({ data, summary }: { data: SampleWorkspaceData; summary: KpiSummary }) {
  const { copy, language } = useLanguage();
  const format = useFormat();
  const markers = data.events.map((event, index) => ({
    date: event.date,
    label: String(index + 1),
  }));
  const series: { key: CountKpiId; field: "impressions" | "productPageViews" | "firstTimeDownloads" }[] = [
    { key: "impressions", field: "impressions" },
    { key: "product_page_views", field: "productPageViews" },
    { key: "first_time_downloads", field: "firstTimeDownloads" },
  ];
  const sources = summarizeSources(data.bySource, data.daily, summary);
  const eventsNote = copy("sampleEventsLanguageNote");

  return (
    <section className="sample-section" aria-labelledby="sample-trend">
      <h2 id="sample-trend" className="sample-section__title">
        {copy("sampleTrendTitle")}
      </h2>
      <div className="trend-grid">
        {series.map(({ key, field }) => (
          <TrendChart
            key={key}
            title={copy(COUNT_LABEL[key].label)}
            points={data.daily.map((row) => ({ date: row.date, value: row[field] }))}
            highlightFrom={summary.current.start}
            markers={markers}
            format={(value) => format.number(value)}
          />
        ))}
      </div>
      <p className="sample-section__note">{copy("sampleTrendLegend")}</p>

      <div className="sample-split">
        <div>
          <h3 className="sample-subtitle">{copy("sampleEventsTitle")}</h3>
          <ol className="sample-events">
            {data.events.map((event, index) => (
              <li key={`${event.date}-${index}`}>
                <span className="sample-events__num">{index + 1}</span>
                <div>
                  <p className="sample-events__date">
                    {event.date}
                    {event.endDate ? ` – ${event.endDate}` : ""} · {event.type}
                  </p>
                  <p className="sample-events__text">{event.description}</p>
                </div>
              </li>
            ))}
          </ol>
          {language === "en" && eventsNote ? (
            <p className="sample-section__note">{eventsNote}</p>
          ) : null}
        </div>

        <div>
          <h3 className="sample-subtitle">{copy("sampleSourcesTitle")}</h3>
          <div className="sample-table-wrap">
            <table className="sample-table">
              <thead>
                <tr>
                  <th scope="col">{copy("sampleSource")}</th>
                  <th scope="col">{copy("sampleKpiImpressions")}</th>
                  <th scope="col">{copy("sampleKpiDownloads")}</th>
                </tr>
              </thead>
              <tbody>
                {sources.buckets.map((row) => (
                  <tr key={row.bucket}>
                    <th scope="row">{row.bucket}</th>
                    <td>
                      {format.number(row.impressions.current)}
                      <span className="sample-table__prev">
                        {copy("samplePrevious")} {format.number(row.impressions.previous)}
                      </span>
                    </td>
                    <td>
                      {format.number(row.firstTimeDownloads.current)}
                      <span className="sample-table__prev">
                        {copy("samplePrevious")} {format.number(row.firstTimeDownloads.previous)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="sample-section__note">
            {fill(copy("sampleSourcesNote"), {
              buckets: sources.buckets.map((b) => b.bucket).join(" / "),
              bucketImpressions: format.number(sources.bucketImpressions),
              totalImpressions: format.number(sources.totalImpressions),
              bucketDownloads: format.number(sources.bucketDownloads),
              totalDownloads: format.number(sources.totalDownloads),
            })}
          </p>
        </div>
      </div>
    </section>
  );
}

function ActionsSection({ recorded }: { recorded: RecordedSummary | null }) {
  const { copy, language } = useLanguage();
  if (!recorded) {
    return <p className="panel-empty">{copy("sampleNoRecorded")}</p>;
  }
  const glossed = hasGloss(
    recorded.actions.flatMap((action) => [
      action.title,
      action.reason,
      ...action.claims.map((claim) => claim.text),
    ]),
    language,
  );
  return (
    <div className="sample-actions">
      <TopActions
        report={{ actions: recorded.actions }}
        renderText={(text) => <GlossedText text={text} />}
        renderDetails={(action) => <ActionDetails claims={action.claims} notes={action.notes} />}
      />
      {glossed ? <p className="sample-section__note">{copy("glossLegend")}</p> : null}
      <p className="sample-section__note">
        {fill(copy("sampleActionsSource"), {
          scenario: recorded.scenario,
          version: versionLabel(recorded.finalVersion, recorded.finalStage, copy),
          runId: recorded.runId,
          model: recorded.model,
        })}
        {recorded.language !== language
          ? ` ${fill(copy("sampleActionsLanguageNote"), { lang: languageName(recorded.language, copy) })}`
          : ""}
      </p>
    </div>
  );
}

function VerifySection({ recorded }: { recorded: RecordedSummary }) {
  const { copy } = useLanguage();
  return (
    <section className="sample-section" aria-labelledby="sample-verify">
      <h2 id="sample-verify" className="sample-section__title">
        {copy("sampleVerifyTitle")}
      </h2>
      <ul className="sample-verify">
        {recorded.rounds.map((round) => (
          <li key={round.round}>
            {fill(copy("sampleVerifyRound"), {
              round: round.round,
              version: versionLabel(round.reviewedVersion, round.reviewedStage, copy),
              matched: round.checks.matched,
              mismatched: round.checks.mismatched,
              unverifiable: round.checks.unverifiable,
              findings: round.findings,
            })}
          </li>
        ))}
      </ul>
      <p className="sample-verify__outcome">
        <Badge tone={recorded.status === "converged" ? "up" : "muted"}>
          {copy(STATUS_COPY[recorded.status])}
        </Badge>{" "}
        <span>
          {outcomeCounts(recorded.outcome, copy)
            .map((part) => `· ${part}`)
            .join(" ")}
        </span>
        <span>
          {copy("sampleVerifyKnown")}: <strong>{recorded.knownMisjudgments}</strong>
        </span>
      </p>
      <p className="sample-section__note">{copy("checksAuthority")}</p>
      <p className="sample-section__note">{copy("reviewTerms")}</p>
      <p className="sample-section__note">{copy("recordedChecksNote")}</p>
      <Link href={DEMO_PATH} className="sample-cta">
        {copy("sampleVerifyCta")} →
      </Link>
    </section>
  );
}

function DataSourcesSection({ data }: { data: SampleWorkspaceData }) {
  const { copy } = useLanguage();
  const buckets = new Set(data.bySource.map((row) => row.bucket)).size;
  const rows: { name: string; included: boolean; detail?: string }[] = [
    {
      name: copy("sampleSourceAscDaily"),
      included: true,
      detail: fill(copy("sampleDays"), { n: data.daily.length }),
    },
    {
      name: copy("sampleSourceAscBySource"),
      included: true,
      detail: fill(copy("sampleBuckets"), { n: buckets }),
    },
    {
      name: copy("sampleSourceCompetitors"),
      included: true,
      detail: fill(copy("sampleCompetitors"), { n: data.competitorCount }),
    },
    {
      name: copy("sampleSourceEvents"),
      included: true,
      detail: fill(copy("sampleEventsCount"), { n: data.events.length }),
    },
    { name: copy("sourceGa4"), included: false },
    { name: copy("sourceAdmob"), included: false },
  ];
  return (
    <section className="sample-section" aria-labelledby="sample-sources">
      <h2 id="sample-sources" className="sample-section__title">
        {copy("sampleDataSourcesTitle")}
      </h2>
      <ul className="sample-sources">
        {rows.map((row) => (
          <li key={row.name}>
            <span className="sample-sources__name">{row.name}</span>
            <span className="sample-sources__state">
              <Badge tone="muted">
                {copy(row.included ? "sampleSourceCsv" : "sampleSourceNotIncluded")}
              </Badge>
              {row.detail ? <span>{row.detail}</span> : null}
            </span>
          </li>
        ))}
      </ul>
      <p className="sample-section__note">{copy("sampleDataSourcesNote")}</p>
    </section>
  );
}

/** Fictional sample only: read-only, built from samples/ at build time. */
export function SampleWorkspace({
  data,
  onOpenMy,
}: {
  data: SampleWorkspaceData | null;
  onOpenMy: () => void;
}) {
  const { copy } = useLanguage();
  const summary = useMemo(() => (data ? summarizeKpis(data.daily) : null), [data]);
  const recorded = data ? pickRepresentativeRecorded(data.recorded) : null;

  if (!data) {
    return (
      <div className="dashboard">
        <p className="experiments__error">{copy("sampleMissing")}</p>
      </div>
    );
  }

  return (
    <div className="dashboard sample-workspace">
      <SampleHeader data={data} summary={summary} />
      <p className="sample-notice" role="note">
        <span className="sample-badge">{copy("sampleBadge")}</span> {copy("sampleNotice")}
      </p>
      {summary ? <KpiSection summary={summary} /> : null}
      {summary ? <TrendSection data={data} summary={summary} /> : null}
      <ActionsSection recorded={recorded} />
      <div className="sample-split">
        {recorded ? <VerifySection recorded={recorded} /> : null}
        <DataSourcesSection data={data} />
      </div>
      <section className="sample-section sample-my" aria-labelledby="sample-my">
        <h2 id="sample-my" className="sample-section__title">
          {copy("sampleMyOnlyTitle")}
        </h2>
        <p className="sample-section__note">{copy("sampleMyOnlyBody")}</p>
        <button type="button" className="analyze-btn sample-my__btn" onClick={onOpenMy}>
          {copy("sampleOpenMy")}
        </button>
      </section>
    </div>
  );
}
