import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { beforeEach, describe, it } from "node:test";

import { buildDemoStory, isFictionalRun } from "../src/lib/recorded-demo.ts";
import {
  loadCachedReport,
  loadSelectedProductId,
  loadWorkspaceMode,
  saveCachedReport,
  saveSelectedProductId,
  saveWorkspaceMode,
} from "../src/lib/report-cache.ts";
import {
  changePercent,
  parseBySource,
  parseCsv,
  parseDaily,
  ratio,
  summarizeKpis,
  summarizeRecorded,
  summarizeSources,
  total,
} from "../src/lib/sample-workspace.ts";

const sampleFile = (name) =>
  readFileSync(new URL(`../../samples/mahjong/${name}`, import.meta.url), "utf8");
const recordedFile = (name) =>
  JSON.parse(readFileSync(new URL(`../../samples/recorded/${name}`, import.meta.url), "utf8"));

function installLocalStorage() {
  const data = new Map();
  globalThis.window = {
    localStorage: {
      getItem: (key) => (data.has(key) ? data.get(key) : null),
      setItem: (key, value) => data.set(key, String(value)),
      removeItem: (key) => data.delete(key),
    },
  };
  return data;
}

const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-9, `${actual} ≠ ${expected}`);

describe("parseCsv", () => {
  it("handles quoted commas, escaped quotes, newlines, and CRLF", () => {
    const rows = parseCsv('a,b\r\n1,"x, ""y""\nz"\n2,\n');
    assert.deepEqual(rows, [
      { a: "1", b: 'x, "y"\nz' },
      { a: "2", b: "" },
    ]);
  });
});

describe("KPI math", () => {
  it("treats a missing day as unknown, not zero", () => {
    assert.equal(total([1, null, 3]), null);
    assert.equal(total([]), null);
    assert.equal(total([1, 2, 3]), 6);
  });

  it("returns null for a zero or missing denominator", () => {
    assert.equal(ratio(5, 0), null);
    assert.equal(ratio(null, 10), null);
    close(ratio(1, 4), 0.25);
    assert.equal(changePercent(10, 0), null);
    close(changePercent(42000, 30000), 40);
  });

  it("needs two full windows", () => {
    const daily = parseDaily(sampleFile("asc_daily.csv"));
    assert.equal(summarizeKpis(daily.slice(0, 13)), null);
  });

  it("makes a KPI unknown when one day in its window is missing", () => {
    const daily = parseDaily(sampleFile("asc_daily.csv"));
    daily[10] = { ...daily[10], productPageViews: null };
    const summary = summarizeKpis(daily);
    const pageViews = summary.counts.find((k) => k.id === "product_page_views");
    assert.equal(pageViews.current, null);
    assert.equal(pageViews.previous, 1800);
    assert.equal(summary.rates.find((k) => k.id === "page_view_rate").current, null);
  });
});

describe("Sample Workspace KPIs from samples/mahjong (fictional)", () => {
  const daily = parseDaily(sampleFile("asc_daily.csv"));
  const summary = summarizeKpis(daily);

  it("compares the last 7 days with the 7 before", () => {
    assert.equal(daily.length, 14);
    assert.deepEqual(summary.previous, { start: "2026-10-09", end: "2026-10-15", days: 7 });
    assert.deepEqual(summary.current, { start: "2026-10-16", end: "2026-10-22", days: 7 });
  });

  it("totals the counts", () => {
    const byId = Object.fromEntries(summary.counts.map((k) => [k.id, k]));
    assert.deepEqual([byId.impressions.previous, byId.impressions.current], [30000, 42000]);
    assert.deepEqual(
      [byId.product_page_views.previous, byId.product_page_views.current],
      [1800, 2100],
    );
    assert.deepEqual(
      [byId.first_time_downloads.previous, byId.first_time_downloads.current],
      [360, 315],
    );
    close(byId.impressions.changePercent, 40);
    close(byId.first_time_downloads.changePercent, -12.5);
  });

  it("computes rates from totals, with their numerator and denominator", () => {
    const byId = Object.fromEntries(summary.rates.map((k) => [k.id, k]));
    assert.deepEqual(
      [byId.page_view_rate.numerator, byId.page_view_rate.denominator],
      ["product_page_views", "impressions"],
    );
    close(byId.page_view_rate.previous, 0.06);
    close(byId.page_view_rate.current, 0.05);
    close(byId.page_view_rate.deltaPoints, -1);
    close(byId.download_rate.previous, 0.2);
    close(byId.download_rate.current, 0.15);
    close(byId.download_rate.deltaPoints, -5);
    close(byId.impression_download_rate.previous, 0.012);
    close(byId.impression_download_rate.current, 0.0075);
  });

  it("keeps the three sources apart from the overall total", () => {
    const sources = summarizeSources(parseBySource(sampleFile("asc_daily_by_source.csv")), daily, summary);
    assert.deepEqual(
      sources.buckets.map((b) => [b.bucket, b.impressions.previous, b.impressions.current]),
      [
        ["browse", 9000, 19800],
        ["referrer", 1500, 1600],
        ["search", 18000, 18600],
      ],
    );
    assert.equal(sources.bucketImpressions, 40000);
    assert.equal(sources.totalImpressions, 42000);
    assert.equal(sources.bucketDownloads, 295);
    assert.equal(sources.totalDownloads, 315);
  });
});

describe("Recorded Demo summary for Sample Workspace", () => {
  const run = {
    ...recordedFile("sample-base-20261024-214121.json"),
    sample: recordedFile("sample-base-20261024-214121.sample.json"),
    recorded: true,
  };
  const summary = summarizeRecorded(run, buildDemoStory(run));

  it("shows the final version's top 3 and where they came from", () => {
    assert.equal(summary.runId, "sample-base-20261024-214121");
    assert.equal(summary.scenario, "base");
    assert.equal(summary.finalVersion, "v3");
    assert.deepEqual(summary.actions.map((a) => a.rank), [1, 2, 3]);
    assert.equal(summary.actions[0].title, run.steps.at(-1).output.actions[0].title);
  });

  it("carries the Critic counts unchanged", () => {
    assert.deepEqual(
      summary.rounds.map((r) => [
        r.reviewedVersion,
        r.checks.matched,
        r.checks.mismatched,
        r.checks.unverifiable,
        r.findings,
      ]),
      [
        ["v2", 14, 0, 0, 2],
        ["v3", 14, 0, 0, 1],
      ],
    );
    assert.deepEqual(summary.outcome.finalChecks, {
      matched: 14,
      mismatched: 0,
      unverifiable: 0,
      total: 14,
    });
    assert.equal(summary.unresolved, 1);
    assert.equal(summary.knownMisjudgments, 1);
    assert.equal(summary.status, "max_rounds");
  });
});

describe("Workspace separation", () => {
  let store;
  beforeEach(() => {
    store = installLocalStorage();
  });

  it("opens Sample Workspace first and remembers My Workspace once picked", () => {
    assert.equal(loadWorkspaceMode(), "sample");
    saveWorkspaceMode("my");
    assert.equal(loadWorkspaceMode(), "my");
    saveWorkspaceMode("sample");
    assert.equal(loadWorkspaceMode(), "sample");
    store.set("indie-growth-agent:workspace", "other");
    assert.equal(loadWorkspaceMode(), "sample");
  });

  it("switching modes leaves My Workspace reports and selection alone", () => {
    const report = { analysisRunId: "run-1", dataSource: "live", product: { id: "mahjong" } };
    saveCachedReport("mahjong", report);
    saveSelectedProductId("mahjong");
    saveWorkspaceMode("sample");
    saveWorkspaceMode("my");
    assert.equal(loadCachedReport("mahjong")?.analysisRunId, "run-1");
    assert.equal(loadSelectedProductId(), "mahjong");
  });

  it("drops fictional runs from the My Workspace revision history", () => {
    const real = { runId: "mahjong-20261024-161906", sample: null, recorded: false };
    assert.equal(isFictionalRun(real), false);
    assert.equal(isFictionalRun({ ...real, runId: "x", recorded: true }), true);
    assert.equal(isFictionalRun({ ...real, sample: { dataKind: "fictional_sample" } }), true);
    assert.equal(isFictionalRun({ ...real, runId: "sample-base-20261024-212032" }), true);
  });

  it("keeps the Sample Workspace off My Workspace storage and the analysis APIs", () => {
    for (const file of ["../src/components/SampleWorkspace.tsx", "../src/lib/sample-workspace.ts"]) {
      const source = readFileSync(new URL(file, import.meta.url), "utf8");
      for (const forbidden of [
        "saveCachedReport",
        "saveSelectedProductId",
        "requestAnalyze",
        "interventions-client",
        "startEvidenceRun",
      ]) {
        assert.ok(!source.includes(forbidden), `${file} must not use ${forbidden}`);
      }
    }
  });
});
