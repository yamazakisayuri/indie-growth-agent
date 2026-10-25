import type { EvidenceRunStatus, ProposedAction } from "./evidence-client";
import type {
  CheckTally,
  CitedClaim,
  DemoStory,
  DemoVersion,
  ReviewNote,
  RunOutcome,
} from "./recorded-demo";

/**
 * Sample Workspace: KPIs and series aggregated from the fictional CSVs in samples/mahjong/,
 * plus a summary of the committed base Recorded Demo. Nothing here calls an API or a model,
 * and nothing is written to the My Workspace caches.
 */

export interface DailyRow {
  date: string;
  impressions: number | null;
  productPageViews: number | null;
  firstTimeDownloads: number | null;
}

export interface SourceRow {
  date: string;
  bucket: string;
  impressions: number | null;
  firstTimeDownloads: number | null;
}

export interface KnownEventRow {
  date: string;
  endDate: string | null;
  type: string;
  description: string;
}

export interface RecordedSummary {
  runId: string;
  language: string;
  model: string;
  scenario: string;
  recordedAt: string | null;
  /** The run shown for its scenario in every UI language (`representative` in .sample.json). */
  representative: boolean;
  status: EvidenceRunStatus;
  finalVersion: string;
  finalStage: DemoVersion["stage"];
  /** Recorded text unchanged; `notes` are known limitations a reviewer wrote about it. */
  actions: (Pick<ProposedAction, "rank" | "title" | "reason"> & {
    notes: ReviewNote[];
    claims: CitedClaim[];
  })[];
  rounds: {
    round: number;
    reviewedVersion: string;
    reviewedStage: DemoVersion["stage"];
    checks: CheckTally;
    findings: number;
  }[];
  outcome: RunOutcome;
  unresolved: number;
  knownMisjudgments: number;
}

export interface SampleWorkspaceData {
  app: { productId: string; name: string; appId: string };
  /** Japanese original of the fictional-data note in scenarios.json. */
  note: string | null;
  daily: DailyRow[];
  bySource: SourceRow[];
  events: KnownEventRow[];
  competitorCount: number;
  /** Committed Recorded Demos of the base scenario (one per run language, if more appear). */
  recorded: RecordedSummary[];
  /** SHA-256 of the CSVs read above, keyed like a run's sample.csvSha256. */
  csvSha256: Record<string, string>;
}

/** RFC 4180-style rows: quoted fields may hold commas, quotes ("") and newlines. */
export function parseCsv(text: string): Record<string, string>[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        field += '"';
        i += 1;
      } else if (ch === '"') {
        quoted = false;
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ",") {
      row.push(field);
      field = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") {
        i += 1;
      }
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += ch;
    }
  }
  if (field !== "" || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  const [header, ...body] = rows.filter((r) => r.some((cell) => cell !== ""));
  if (!header) {
    return [];
  }
  return body.map((cells) =>
    Object.fromEntries(header.map((name, index) => [name.trim(), cells[index] ?? ""])),
  );
}

/** Empty cell → null (missing ≠ zero); anything non-numeric is rejected. */
function count(value: string | undefined, column: string): number | null {
  const text = (value ?? "").trim();
  if (text === "") {
    return null;
  }
  const number = Number(text);
  if (!Number.isFinite(number)) {
    throw new Error(`Not a number in ${column}: ${text}`);
  }
  return number;
}

export function parseDaily(text: string): DailyRow[] {
  return parseCsv(text)
    .map((row) => ({
      date: row.date,
      impressions: count(row.impressions, "impressions"),
      productPageViews: count(row.product_page_views, "product_page_views"),
      firstTimeDownloads: count(row.first_time_downloads, "first_time_downloads"),
    }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

export function parseBySource(text: string): SourceRow[] {
  return parseCsv(text).map((row) => ({
    date: row.date,
    bucket: row.source_bucket,
    impressions: count(row.impressions, "impressions"),
    firstTimeDownloads: count(row.first_time_downloads, "first_time_downloads"),
  }));
}

export function parseKnownEvents(text: string): KnownEventRow[] {
  return parseCsv(text)
    .map((row) => ({
      date: row.date,
      endDate: row.end_date?.trim() ? row.end_date.trim() : null,
      type: row.type,
      description: row.description,
    }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

export interface Period {
  start: string;
  end: string;
  days: number;
}

export type CountKpiId = "impressions" | "product_page_views" | "first_time_downloads";
export type RateKpiId = "page_view_rate" | "download_rate" | "impression_download_rate";

export interface CountKpi {
  kind: "count";
  id: CountKpiId;
  current: number | null;
  previous: number | null;
  /** Relative change in percent; null when the previous total is missing or zero. */
  changePercent: number | null;
}

export interface RateKpi {
  kind: "rate";
  id: RateKpiId;
  numerator: CountKpiId;
  denominator: CountKpiId;
  /** Ratios (0.05 = 5%); null when a total is missing or the denominator is zero. */
  current: number | null;
  previous: number | null;
  /** current − previous, in percentage points. */
  deltaPoints: number | null;
}

export interface KpiSummary {
  current: Period;
  previous: Period;
  counts: CountKpi[];
  rates: RateKpi[];
}

const COUNT_FIELDS: Record<CountKpiId, keyof Omit<DailyRow, "date">> = {
  impressions: "impressions",
  product_page_views: "productPageViews",
  first_time_downloads: "firstTimeDownloads",
};

const RATES: { id: RateKpiId; numerator: CountKpiId; denominator: CountKpiId }[] = [
  { id: "page_view_rate", numerator: "product_page_views", denominator: "impressions" },
  { id: "download_rate", numerator: "first_time_downloads", denominator: "product_page_views" },
  {
    id: "impression_download_rate",
    numerator: "first_time_downloads",
    denominator: "impressions",
  },
];

/** Sum, or null if any day lacks the value. */
export function total(values: (number | null)[]): number | null {
  if (values.length === 0 || values.some((value) => value === null)) {
    return null;
  }
  return (values as number[]).reduce((sum, value) => sum + value, 0);
}

export function ratio(numerator: number | null, denominator: number | null): number | null {
  if (numerator === null || denominator === null || denominator === 0) {
    return null;
  }
  return numerator / denominator;
}

export function changePercent(current: number | null, previous: number | null): number | null {
  if (current === null || previous === null || previous === 0) {
    return null;
  }
  return ((current - previous) / previous) * 100;
}

function period(rows: DailyRow[]): Period {
  return { start: rows[0]?.date ?? "", end: rows.at(-1)?.date ?? "", days: rows.length };
}

/** Last `windowDays` days against the `windowDays` days before them. */
export function summarizeKpis(daily: DailyRow[], windowDays = 7): KpiSummary | null {
  const rows = [...daily].sort((a, b) => a.date.localeCompare(b.date));
  if (rows.length < windowDays * 2) {
    return null;
  }
  const currentRows = rows.slice(-windowDays);
  const previousRows = rows.slice(-windowDays * 2, -windowDays);
  const totals = (subset: DailyRow[]) =>
    Object.fromEntries(
      (Object.keys(COUNT_FIELDS) as CountKpiId[]).map((id) => [
        id,
        total(subset.map((row) => row[COUNT_FIELDS[id]])),
      ]),
    ) as Record<CountKpiId, number | null>;
  const cur = totals(currentRows);
  const prev = totals(previousRows);

  return {
    current: period(currentRows),
    previous: period(previousRows),
    counts: (Object.keys(COUNT_FIELDS) as CountKpiId[]).map((id) => ({
      kind: "count",
      id,
      current: cur[id],
      previous: prev[id],
      changePercent: changePercent(cur[id], prev[id]),
    })),
    rates: RATES.map(({ id, numerator, denominator }) => {
      const current = ratio(cur[numerator], cur[denominator]);
      const previous = ratio(prev[numerator], prev[denominator]);
      return {
        kind: "rate",
        id,
        numerator,
        denominator,
        current,
        previous,
        deltaPoints:
          current === null || previous === null ? null : (current - previous) * 100,
      };
    }),
  };
}

export interface SourceBreakdown {
  buckets: {
    bucket: string;
    impressions: { current: number | null; previous: number | null };
    firstTimeDownloads: { current: number | null; previous: number | null };
  }[];
  /** Sum of the listed buckets vs the overall total for the current period. */
  bucketImpressions: number | null;
  totalImpressions: number | null;
  bucketDownloads: number | null;
  totalDownloads: number | null;
}

/** Per-bucket totals for the two periods. The buckets need not add up to the overall total. */
export function summarizeSources(
  bySource: SourceRow[],
  daily: DailyRow[],
  summary: KpiSummary,
): SourceBreakdown {
  const inPeriod = (date: string, p: Period) => date >= p.start && date <= p.end;
  const buckets = [...new Set(bySource.map((row) => row.bucket))].sort();
  const sum = (bucket: string, p: Period, field: "impressions" | "firstTimeDownloads") =>
    total(
      bySource
        .filter((row) => row.bucket === bucket && inPeriod(row.date, p))
        .map((row) => row[field]),
    );
  const rows = buckets.map((bucket) => ({
    bucket,
    impressions: {
      current: sum(bucket, summary.current, "impressions"),
      previous: sum(bucket, summary.previous, "impressions"),
    },
    firstTimeDownloads: {
      current: sum(bucket, summary.current, "firstTimeDownloads"),
      previous: sum(bucket, summary.previous, "firstTimeDownloads"),
    },
  }));
  const currentDaily = daily.filter((row) => inPeriod(row.date, summary.current));
  return {
    buckets: rows,
    bucketImpressions: total(rows.map((row) => row.impressions.current)),
    totalImpressions: total(currentDaily.map((row) => row.impressions)),
    bucketDownloads: total(rows.map((row) => row.firstTimeDownloads.current)),
    totalDownloads: total(currentDaily.map((row) => row.firstTimeDownloads)),
  };
}

export interface PeriodPair {
  previous: number | null;
  current: number | null;
  changePercent: number | null;
}

/** What happened between the two 7-day windows, from the same totals as the KPIs and sources. */
export interface SampleSnapshot {
  current: Period;
  previous: Period;
  /** All sources. */
  downloads: PeriodPair;
  browseImpressions: PeriodPair;
  browseDownloads: PeriodPair;
}

const SNAPSHOT_BUCKET = "browse";

function pair(previous: number | null, current: number | null): PeriodPair {
  return { previous, current, changePercent: changePercent(current, previous) };
}

export function summarizeSnapshot(daily: DailyRow[], bySource: SourceRow[]): SampleSnapshot | null {
  const kpis = summarizeKpis(daily);
  if (!kpis) {
    return null;
  }
  const downloads = kpis.counts.find((kpi) => kpi.id === "first_time_downloads");
  const browse = summarizeSources(bySource, daily, kpis).buckets.find(
    (row) => row.bucket === SNAPSHOT_BUCKET,
  );
  return {
    current: kpis.current,
    previous: kpis.previous,
    downloads: pair(downloads?.previous ?? null, downloads?.current ?? null),
    browseImpressions: pair(browse?.impressions.previous ?? null, browse?.impressions.current ?? null),
    browseDownloads: pair(
      browse?.firstTimeDownloads.previous ?? null,
      browse?.firstTimeDownloads.current ?? null,
    ),
  };
}

/** The CSVs, and their tables, that a snapshot is computed from. */
export const SNAPSHOT_FILES = ["asc_daily.csv", "asc_daily_by_source.csv"] as const;
const SNAPSHOT_TABLES = ["asc_daily", "asc_daily_by_source"];

/**
 * True only if the run saw exactly this data for the snapshot: same CSV digests, no scenario
 * change to those tables, and the same two periods. Otherwise the snapshot is not shown with it.
 */
export function snapshotMatchesRun(
  snapshot: Pick<SampleSnapshot, "current" | "previous">,
  csvSha256: Record<string, string>,
  run: {
    currentPeriod: [string, string] | null;
    previousPeriod: [string, string] | null;
    sample?: {
      csvSha256?: Record<string, string>;
      changes?: { table?: string }[];
    } | null;
  },
): boolean {
  const sample = run.sample;
  if (!sample?.csvSha256 || !run.currentPeriod || !run.previousPeriod) {
    return false;
  }
  const sameFiles = SNAPSHOT_FILES.every(
    (file) => !!csvSha256[file] && sample.csvSha256?.[file] === csvSha256[file],
  );
  const untouched = (sample.changes ?? []).every(
    (change) => !SNAPSHOT_TABLES.includes(change.table ?? ""),
  );
  const samePeriods =
    run.currentPeriod[0] === snapshot.current.start &&
    run.currentPeriod[1] === snapshot.current.end &&
    run.previousPeriod[0] === snapshot.previous.start &&
    run.previousPeriod[1] === snapshot.previous.end;
  return sameFiles && untouched && samePeriods;
}

/** What the Sample Workspace shows of a Recorded Demo: final actions and Critic counts. */
export function summarizeRecorded(
  run: {
    runId: string;
    language: string;
    model: string;
    status: EvidenceRunStatus;
    sample?: { scenario?: string; recordedAt?: string; representative?: boolean } | null;
  },
  story: DemoStory,
): RecordedSummary | null {
  const final = story.versions.at(-1);
  if (!final) {
    return null;
  }
  return {
    runId: run.runId,
    language: run.language,
    model: run.model,
    scenario: run.sample?.scenario ?? "",
    recordedAt: run.sample?.recordedAt ?? null,
    representative: run.sample?.representative === true,
    status: run.status,
    finalVersion: final.version,
    finalStage: final.stage,
    actions: final.actions.slice(0, 3).map(({ rank, title, reason }) => ({
      rank,
      title,
      reason,
      notes: final.notesByRank[rank] ?? [],
      claims: final.citedByRank[rank] ?? [],
    })),
    rounds: story.rounds.map((round) => ({
      round: round.round,
      reviewedVersion: round.reviewedVersion,
      reviewedStage: round.reviewedStage,
      checks: round.checks,
      findings: round.findings.length,
    })),
    outcome: story.outcome,
    unresolved: story.unresolved,
    knownMisjudgments: story.rounds
      .flatMap((round) => round.findings)
      .filter((finding) => finding.reviewNotes.length > 0).length,
  };
}

/** The representative Recorded Demo if one is marked, else the first; same rule as /demo. */
export function pickRepresentativeRecorded(recorded: RecordedSummary[]): RecordedSummary | null {
  return recorded.find((run) => run.representative) ?? recorded[0] ?? null;
}

/** The Recorded Demo in the UI language if one exists, else the first. */
export function pickRecordedForLanguage(
  recorded: RecordedSummary[],
  language: string,
): RecordedSummary | null {
  return recorded.find((run) => run.language === language) ?? recorded[0] ?? null;
}
