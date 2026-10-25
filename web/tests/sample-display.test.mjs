import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { t } from "../src/lib/i18n.ts";
import { buildDemoStory, stageSuffix, versionLabel } from "../src/lib/recorded-demo.ts";
import { glossSegments, hasGloss, sampleAppName } from "../src/lib/sample-glossary.ts";
import { summarizeRecorded } from "../src/lib/sample-workspace.ts";

const STEMS = [
  "sample-base-20261025-110333",
  "sample-base-20261024-214121",
  "sample-competitor-variant-20261024-220111",
];
const recordedUrl = (name) => new URL(`../../samples/recorded/${name}`, import.meta.url);
const raw = (stem) => readFileSync(recordedUrl(`${stem}.json`), "utf8");
const loadRecorded = (stem) => ({
  ...JSON.parse(raw(stem)),
  sample: JSON.parse(readFileSync(recordedUrl(`${stem}.sample.json`), "utf8")),
  recorded: true,
});
const en = (key) => t(key, "en");
const ja = (key) => t(key, "ja");
const textOf = (segments) => segments.filter((s) => typeof s === "string").join("");
const glossesOf = (segments) => segments.filter((s) => typeof s !== "string").map((s) => s.gloss);

/** Every model-written text the /demo story and Sample Workspace show. */
function shownTexts(run) {
  return run.steps.flatMap((step) => [
    ...step.output.actions.flatMap((a) => [a.title, a.reason]),
    ...step.output.actionChanges.map((c) => c.reason),
    ...step.output.findingResponses.map((r) => r.note ?? ""),
    ...(step.critic ? step.critic.findings.map((f) => f.message) : []),
  ]);
}

describe("sample app name", () => {
  const app = JSON.parse(readFileSync(new URL("../../samples/mahjong/scenarios.json", import.meta.url), "utf8")).app;

  it("is English in the English UI and the original in the Japanese UI", () => {
    assert.equal(sampleAppName(app, "en"), "Mahjong Score Book (fictional sample app)");
    assert.equal(sampleAppName(app, "ja"), "麻雀スコア帳（架空のサンプルアプリ）");
    assert.equal(sampleAppName(app, "ja"), app.name);
  });

  it("never borrows the real app's name and keeps unknown apps as they are", () => {
    assert.ok(!sampleAppName(app, "en").includes("Mahjong Score Calculator"));
    assert.equal(sampleAppName({ appId: "fictional-999", name: "架空" }, "en"), "架空");
  });

  it("is the same name in every recorded demo's metadata", () => {
    for (const stem of STEMS) {
      const { sample } = loadRecorded(stem);
      assert.equal(sampleAppName(sample.app, "en"), sampleAppName(app, "en"));
    }
  });
});

describe("glosses for Japanese terms (English UI only)", () => {
  const base = loadRecorded(STEMS[0]);
  const v3 = base.steps.at(-1).output.actions;

  it("adds the meaning after the quoted keyword, keeping the original", () => {
    const segments = glossSegments(v3[1].title, "en");
    assert.equal(textOf(segments), v3[1].title);
    assert.deepEqual(glossesOf(segments), ["simple score calculation"]);
    assert.equal(segments[0], 'Revert or refine the subtitle/keyword change toward "かんたん点数計算"');
  });

  it("does not repeat the model's own translation", () => {
    const claim = base.steps[0].output.claims.find((c) => c.text.includes("(simple score calculation)"));
    assert.ok(claim, "the English base trace translates the keyword itself");
    assert.deepEqual(glossesOf(glossSegments(claim.text, "en")), []);
  });

  it("glosses a standalone quoted かんたん but not names that contain it", () => {
    const segments = glossSegments(v3[1].reason, "en");
    assert.equal(textOf(segments), v3[1].reason);
    assert.deepEqual(glossesOf(segments), ["simple"]);
    assert.match(segments[0], /uses "かんたん"$/);
    assert.deepEqual(glossesOf(glossSegments('Competitor "かんたん麻雀計算" has 960 ratings', "en")), []);
    assert.deepEqual(glossesOf(glossSegments("「かんたん」", "en")), ["simple"]);
  });

  it("adds nothing in the Japanese UI or to text without the terms", () => {
    assert.deepEqual(glossSegments(v3[1].title, "ja"), [v3[1].title]);
    assert.deepEqual(glossSegments("No Japanese here", "en"), ["No Japanese here"]);
    assert.deepEqual(glossSegments("", "en"), []);
    assert.equal(hasGloss([v3[1].title], "ja"), false);
    assert.equal(hasGloss([v3[0].title, v3[1].title], "en"), true);
  });

  it("keeps every shown text of every recorded demo unchanged, and the traces too", () => {
    for (const stem of STEMS) {
      const before = raw(stem);
      const run = loadRecorded(stem);
      for (const text of shownTexts(run)) {
        for (const language of ["en", "ja"]) {
          assert.equal(textOf(glossSegments(text, language)), text);
        }
      }
      assert.equal(raw(stem), before);
    }
  });
});

describe("version labels", () => {
  it("names the three stages in each UI language", () => {
    assert.deepEqual(
      ["internal", "competitive", "critic_revision"].map((stage, i) => versionLabel(`v${i + 1}`, stage, en)),
      ["v1 — Own App Data", "v2 — Competitor Context", "v3 — Critic-Reviewed Actions"],
    );
    assert.deepEqual(
      ["internal", "competitive", "critic_revision"].map((stage, i) => versionLabel(`v${i + 1}`, stage, ja)),
      ["v1 — 自アプリのデータ", "v2 — 競合の状況", "v3 — Critic レビュー済みの提案"],
    );
    assert.equal(stageSuffix("competitive", en), "— Competitor Context");
    assert.equal(versionLabel("v9", null, en), "v9");
  });

  it("gives /demo and Sample Workspace the same stages for the English base", () => {
    const run = loadRecorded(STEMS[0]);
    const story = buildDemoStory(run);
    const summary = summarizeRecorded(run, story);
    assert.deepEqual(
      story.versions.map((v) => versionLabel(v.version, v.stage, en)),
      ["v1 — Own App Data", "v2 — Competitor Context", "v3 — Critic-Reviewed Actions"],
    );
    assert.deepEqual(
      story.rounds.map((r) => versionLabel(r.reviewedVersion, r.reviewedStage, en)),
      ["v2 — Competitor Context", "v3 — Critic-Reviewed Actions"],
    );
    assert.equal(versionLabel(summary.finalVersion, summary.finalStage, en), "v3 — Critic-Reviewed Actions");
    assert.deepEqual(
      summary.rounds.map((r) => versionLabel(r.reviewedVersion, r.reviewedStage, en)),
      story.rounds.map((r) => versionLabel(r.reviewedVersion, r.reviewedStage, en)),
    );
  });
});
