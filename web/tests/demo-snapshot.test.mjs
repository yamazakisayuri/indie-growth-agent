import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { buildDemoStory, citedClaims } from "../src/lib/recorded-demo.ts";
import {
  parseBySource,
  parseDaily,
  SNAPSHOT_FILES,
  snapshotMatchesRun,
  summarizeKpis,
  summarizeRecorded,
  summarizeSnapshot,
  summarizeSources,
} from "../src/lib/sample-workspace.ts";

const STEMS = [
  "sample-base-20261025-110333",
  "sample-base-20261024-214121",
  "sample-competitor-variant-20261024-220111",
];
const sampleUrl = (name) => new URL(`../../samples/mahjong/${name}`, import.meta.url);
const recordedUrl = (name) => new URL(`../../samples/recorded/${name}`, import.meta.url);
const raw = (stem) => readFileSync(recordedUrl(`${stem}.json`), "utf8");
const loadRecorded = (stem) => ({
  ...JSON.parse(raw(stem)),
  sample: JSON.parse(readFileSync(recordedUrl(`${stem}.sample.json`), "utf8")),
  recorded: true,
});

const daily = parseDaily(readFileSync(sampleUrl("asc_daily.csv"), "utf8"));
const bySource = parseBySource(readFileSync(sampleUrl("asc_daily_by_source.csv"), "utf8"));
const csvSha256 = Object.fromEntries(
  SNAPSHOT_FILES.map((file) => [file, createHash("sha256").update(readFileSync(sampleUrl(file))).digest("hex")]),
);
const snapshot = summarizeSnapshot(daily, bySource);
const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-9, `${actual} ≠ ${expected}`);

describe("What happened in the app (snapshot)", () => {
  it("compares the same two weeks as the KPI cards", () => {
    assert.deepEqual(snapshot.previous, { start: "2026-10-09", end: "2026-10-15", days: 7 });
    assert.deepEqual(snapshot.current, { start: "2026-10-16", end: "2026-10-22", days: 7 });
  });

  it("shows first-time downloads and Browse with the numbers of the KPI cards and source table", () => {
    const kpis = summarizeKpis(daily);
    const downloads = kpis.counts.find((k) => k.id === "first_time_downloads");
    const browse = summarizeSources(bySource, daily, kpis).buckets.find((b) => b.bucket === "browse");
    assert.deepEqual([snapshot.downloads.previous, snapshot.downloads.current], [360, 315]);
    assert.deepEqual([snapshot.downloads.previous, snapshot.downloads.current], [downloads.previous, downloads.current]);
    close(snapshot.downloads.changePercent, -12.5);
    assert.deepEqual([snapshot.browseImpressions.previous, snapshot.browseImpressions.current], [9000, 19800]);
    close(snapshot.browseImpressions.changePercent, 120);
    assert.deepEqual(
      [snapshot.browseDownloads.previous, snapshot.browseDownloads.current],
      [browse.firstTimeDownloads.previous, browse.firstTimeDownloads.current],
    );
  });

  it("is unknown, not zero, without two full weeks or a Browse source", () => {
    assert.equal(summarizeSnapshot(daily.slice(0, 13), bySource), null);
    const noBrowse = summarizeSnapshot(daily, bySource.filter((row) => row.bucket !== "browse"));
    assert.deepEqual(noBrowse.browseImpressions, { previous: null, current: null, changePercent: null });
  });
});

describe("snapshotMatchesRun", () => {
  for (const stem of STEMS) {
    it(`${stem}: the run used these CSVs and periods`, () => {
      assert.equal(snapshotMatchesRun(snapshot, csvSha256, loadRecorded(stem)), true);
    });
  }

  it("refuses other data, changed ASC tables, other periods, or a run without sample metadata", () => {
    const run = loadRecorded(STEMS[0]);
    assert.equal(snapshotMatchesRun(snapshot, { ...csvSha256, "asc_daily.csv": "0".repeat(64) }, run), false);
    assert.equal(
      snapshotMatchesRun(snapshot, csvSha256, {
        ...run,
        sample: { ...run.sample, changes: [{ table: "asc_daily_by_source" }] },
      }),
      false,
    );
    assert.equal(
      snapshotMatchesRun(snapshot, csvSha256, { ...run, currentPeriod: ["2026-10-15", "2026-10-21"] }),
      false,
    );
    assert.equal(snapshotMatchesRun(snapshot, csvSha256, { ...run, sample: null }), false);
    assert.equal(snapshotMatchesRun(snapshot, {}, run), false);
  });

  it("allows competitor-only scenario changes", () => {
    const variant = loadRecorded(STEMS[2]);
    assert.ok(variant.sample.changes.length > 0);
    assert.ok(variant.sample.changes.every((change) => change.table === "competitor_listing"));
    assert.equal(snapshotMatchesRun(snapshot, csvSha256, variant), true);
  });
});

describe("Final Top 3 Actions: cited claims", () => {
  const run = loadRecorded(STEMS[0]);
  const v3 = run.steps.at(-1).output;
  const story = buildDemoStory(run);
  const final = story.versions.at(-1);

  it("resolves each cited claim id in the same version, in the recorded order", () => {
    for (const action of v3.actions) {
      const cited = final.citedByRank[action.rank];
      assert.deepEqual(cited.map((c) => c.id), action.claimIds);
      for (const claim of cited) {
        const recorded = v3.claims.find((c) => c.id === claim.id);
        assert.equal(claim.text, recorded.text);
        assert.equal(claim.kind, recorded.kind);
      }
    }
    assert.deepEqual(final.citedByRank[1].map((c) => c.id), ["C2", "C4", "C7"]);
  });

  it("keeps an id with no matching claim instead of dropping it", () => {
    assert.deepEqual(citedClaims({ claimIds: ["C1", "C99"] }, [{ id: "C1", kind: "fact", text: "x" }]), [
      { id: "C1", kind: "fact", text: "x" },
      { id: "C99", kind: null, text: null },
    ]);
    assert.deepEqual(citedClaims({ claimIds: undefined }, undefined), []);
  });

  it("gives Sample Workspace the same claims and notes per action as /demo", () => {
    const summary = summarizeRecorded(run, story);
    for (const action of summary.actions) {
      assert.deepEqual(action.claims, final.citedByRank[action.rank]);
      assert.deepEqual(action.notes, final.notesByRank[action.rank] ?? []);
    }
    assert.deepEqual(
      summary.actions.filter((a) => a.notes.length > 0).map((a) => a.rank),
      [1, 3],
    );
  });

  it("leaves every recorded trace unchanged", () => {
    for (const stem of STEMS) {
      const before = raw(stem);
      buildDemoStory(loadRecorded(stem));
      assert.equal(raw(stem), before);
    }
  });
});
