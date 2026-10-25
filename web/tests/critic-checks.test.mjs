import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { t } from "../src/lib/i18n.ts";
import {
  buildDemoStory,
  checkVerdict,
  formatOutcome,
  outcomeCounts,
  proposalNotesFor,
  reviewNoteText,
  runOutcome,
  tallyChecks,
} from "../src/lib/recorded-demo.ts";
import { sampleText } from "../src/lib/sample-text.ts";

const recordedUrl = (name) => new URL(`../../samples/recorded/${name}`, import.meta.url);
const json = (url) => JSON.parse(readFileSync(url, "utf8"));
const loadRecorded = (stem) => ({
  ...json(recordedUrl(`${stem}.json`)),
  sample: json(recordedUrl(`${stem}.sample.json`)),
  recorded: true,
});
const tallies = (run) =>
  run.steps
    .filter((step) => step.critic)
    .map((step) => {
      const { matched, mismatched, unverifiable } = tallyChecks(step.critic.checks);
      return [step.version, matched, mismatched, unverifiable];
    });
const en = (key) => t(key, "en");
const ja = (key) => t(key, "ja");

/** The committed English base Recorded Demo. */
const EN_BASE = recordedUrl("sample-base-20261025-110333.json");

/** Its two known limitations, as recorded in its .sample.json (proposalNotesFor convention). */
const EN_BASE_LIMITATIONS = (({ knownLimitations, en }) => ({
  knownLimitations,
  en: { knownLimitations: en.knownLimitations },
}))(json(recordedUrl("sample-base-20261025-110333.sample.json")));

describe("checkVerdict", () => {
  it("separates matched, mismatched, and unverifiable", () => {
    assert.equal(checkVerdict({ matched: true, error: null }), "matched");
    assert.equal(checkVerdict({ matched: false, error: null }), "mismatched");
    assert.equal(checkVerdict({ matched: false, error: "  " }), "mismatched");
    assert.equal(
      checkVerdict({ matched: false, error: "Expected one row with one column, got 2 rows x 1 columns." }),
      "unverifiable",
    );
  });

  it("counts a check that returned another evidence item's value as unverifiable", () => {
    const wrongItem = {
      matched: false,
      error: "The check names evidence item 0 but returns the value of item 1; not compared.",
    };
    assert.equal(checkVerdict(wrongItem), "unverifiable");
    const run = {
      status: "converged",
      steps: [{ version: "v3", critic: { checks: [{ matched: true, error: null }, wrongItem], findings: [] } }],
    };
    assert.deepEqual(runOutcome(run).finalChecks, { matched: 1, mismatched: 0, unverifiable: 1, total: 2 });
    assert.equal(formatOutcome(runOutcome(run), en), "Converged · 0 unresolved findings · 1 unverifiable SQL check");
  });

  it("tallies an empty or missing list as zeros", () => {
    assert.deepEqual(tallyChecks(undefined), { matched: 0, mismatched: 0, unverifiable: 0, total: 0 });
  });
});

describe("committed Recorded Demos (Japanese)", () => {
  it("base: 14 matched in both rounds, nothing unverifiable", () => {
    const run = loadRecorded("sample-base-20261024-214121");
    assert.deepEqual(tallies(run), [
      ["v2", 14, 0, 0],
      ["v3", 14, 0, 0],
    ]);
    assert.equal(formatOutcome(runOutcome(run), en), "Stopped at review limit · 1 unresolved finding");
  });

  it("competitor-variant: mismatches stay mismatches", () => {
    const run = loadRecorded("sample-competitor-variant-20261024-220111");
    assert.deepEqual(tallies(run), [
      ["v2", 14, 4, 0],
      ["v3", 41, 2, 0],
    ]);
    assert.equal(runOutcome(run).unresolved, 8);
  });

  it("attaches the base note about v3 action #1 to that proposal only", () => {
    const run = loadRecorded("sample-base-20261024-214121");
    const story = buildDemoStory(run);
    const v3 = story.versions.at(-1);
    assert.deepEqual(Object.keys(v3.notesByRank), ["1"]);
    assert.match(reviewNoteText(v3.notesByRank[1][0], "en"), /^The reason for v3 action #1/);
    assert.match(reviewNoteText(v3.notesByRank[1][0], "ja"), /^v3 の提案 #1/);
    assert.deepEqual(story.versions[1].notesByRank, {});
    assert.equal(v3.actions[0].reason, run.steps.at(-1).output.actions[0].reason);
  });
});

describe("converged with an unverifiable check (31 / 0 / 1)", () => {
  const checks = [
    ...Array.from({ length: 31 }, () => ({ matched: true, error: null })),
    { matched: false, error: "Expected one row with one column, got 2 rows x 1 columns." },
  ];
  const run = {
    status: "converged",
    steps: [{ version: "v3", critic: { checks, findings: [] } }],
  };

  it("says converged means no unresolved findings, and still shows the unverifiable check", () => {
    const outcome = runOutcome(run);
    assert.deepEqual(outcome.finalChecks, { matched: 31, mismatched: 0, unverifiable: 1, total: 32 });
    assert.equal(
      formatOutcome(outcome, en),
      "Converged · 0 unresolved findings · 1 unverifiable SQL check",
    );
    assert.equal(formatOutcome(outcome, ja), "収束 · 未解決の指摘 0件 · 照合不能の SQL チェック 1件");
  });

  it("adds nothing while running and pluralizes counts", () => {
    assert.deepEqual(outcomeCounts({ ...runOutcome(run), status: "running" }, en), []);
    const two = runOutcome({ ...run, steps: [{ critic: { checks: [...checks, checks[31]], findings: [] } }] });
    assert.equal(outcomeCounts(two, en)[1], "2 unverifiable SQL checks");
  });

  it("matches the committed English base trace", () => {
    const trace = json(EN_BASE);
    assert.equal(trace.status, "converged");
    assert.deepEqual(tallies(trace), [
      ["v2", 18, 0, 0],
      ["v3", 31, 0, 1],
    ]);
    assert.equal(
      formatOutcome(runOutcome(trace), en),
      "Converged · 0 unresolved findings · 1 unverifiable SQL check",
    );
  });
});

describe("known limitations on proposals (English base trace)", () => {
  it("attach to v3 action #3 and #1 and nowhere else", () => {
    assert.equal(proposalNotesFor("v3", 3, EN_BASE_LIMITATIONS).length, 1);
    assert.equal(proposalNotesFor("v3", 1, EN_BASE_LIMITATIONS).length, 1);
    assert.equal(proposalNotesFor("v3", 2, EN_BASE_LIMITATIONS).length, 0);
    assert.equal(proposalNotesFor("v2", 3, EN_BASE_LIMITATIONS).length, 0);
    assert.equal(
      proposalNotesFor("v3", 1, { knownLimitations: ["v3 action #10 is fine."] }).length,
      0,
    );
  });

  it("leave the recorded proposal text untouched", () => {
    const trace = { ...json(EN_BASE), sample: EN_BASE_LIMITATIONS };
    const before = JSON.stringify(trace.steps);
    const v3 = buildDemoStory(trace).versions.at(-1);
    assert.match(v3.actions[2].reason, /8-10 screenshots/);
    assert.match(v3.actions[0].reason, /~300 page views\/day/);
    assert.match(reviewNoteText(v3.notesByRank[3][0], "en"), /8-10 screenshots/);
    assert.match(reviewNoteText(v3.notesByRank[1][0], "ja"), /2pp/);
    assert.equal(JSON.stringify(trace.steps), before);
  });
});

describe("sampleText for an English-only Recorded Demo", () => {
  it("shows English notes in the Japanese UI when there is no Japanese", () => {
    const text = sampleText({ knownLimitations: [], en: EN_BASE_LIMITATIONS.en }, "ja");
    assert.equal(text.knownLimitations.length, 3);
    assert.match(text.knownLimitations[0], /v3 action #3/);
  });
});
