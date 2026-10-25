import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { t } from "../src/lib/i18n.ts";
import {
  buildDemoStory,
  formatOutcome,
  languageName,
  pickRecordedDemo,
  recordedDemosByScenario,
  reviewNoteText,
  runOutcome,
  tallyChecks,
} from "../src/lib/recorded-demo.ts";
import { sampleText } from "../src/lib/sample-text.ts";
import { pickRepresentativeRecorded, summarizeRecorded } from "../src/lib/sample-workspace.ts";

const EN_BASE = "sample-base-20261025-110333";
const JA_BASE = "sample-base-20261024-214121";
const JA_VARIANT = "sample-competitor-variant-20261024-220111";

const recordedUrl = (name) => new URL(`../../samples/recorded/${name}`, import.meta.url);
const json = (url) => JSON.parse(readFileSync(url, "utf8"));
const loadRecorded = (stem) => ({
  ...json(recordedUrl(`${stem}.json`)),
  sample: json(recordedUrl(`${stem}.sample.json`)),
  recorded: true,
});
const en = (key) => t(key, "en");

/** SHA-256 of the Live Sample trace it was recorded from (tmp/evidence_runs, not in git). */
const SOURCE_TRACE_SHA256 = "8a27656862acfc51c81c08f243bc5e66ef10c471c146d355b1348e3b5e1a7263";

/** What GET /api/evidence/runs lists for a committed trace (newest first). */
function listed(stem) {
  const run = loadRecorded(stem);
  return {
    runId: run.runId,
    productId: run.productId,
    startedAt: run.startedAt,
    finishedAt: run.finishedAt,
    status: run.status,
    model: run.model,
    language: run.language,
    versions: run.steps.map((step) => step.version),
    topActions: [],
    unresolvedFindings: runOutcome(run).unresolved,
    error: null,
    sample: run.sample,
    recorded: true,
  };
}
const apiList = () => [listed(EN_BASE), listed(JA_VARIANT), listed(JA_BASE)];

describe("English base Recorded Demo (committed)", () => {
  const run = loadRecorded(EN_BASE);

  it("is the converged English base run with 8 claims kept in v3", () => {
    assert.equal(run.runId, EN_BASE);
    assert.equal(run.language, "en");
    assert.equal(run.status, "converged");
    assert.equal(run.sample.scenario, "base");
    assert.equal(run.sample.dataKind, "fictional_sample");
    assert.ok(run.sample.recordedAt);
    assert.deepEqual(
      run.steps.map((step) => [step.version, step.output.claims.length]),
      [
        ["v1", 5],
        ["v2", 8],
        ["v3", 8],
      ],
    );
  });

  it("has 31 matched, 0 mismatched, 1 unverifiable in the final Critic round and no findings left", () => {
    const final = run.steps.at(-1).critic;
    assert.deepEqual(tallyChecks(final.checks), {
      matched: 31,
      mismatched: 0,
      unverifiable: 1,
      total: 32,
    });
    assert.equal(runOutcome(run).unresolved, 0);
    assert.equal(
      formatOutcome(runOutcome(run), en),
      "Converged · 0 unresolved findings · 1 unverifiable SQL check",
    );
  });

  it("is byte-identical to the Live Sample trace it was recorded from", () => {
    const digest = createHash("sha256").update(readFileSync(recordedUrl(`${EN_BASE}.json`))).digest("hex");
    assert.equal(digest, SOURCE_TRACE_SHA256);
  });

  it("attaches the two known limitations to v3 action #3 and #1 only, in both languages", () => {
    const story = buildDemoStory(run);
    const v3 = story.versions.at(-1);
    assert.deepEqual(Object.keys(v3.notesByRank).sort(), ["1", "3"]);
    assert.match(reviewNoteText(v3.notesByRank[3][0], "en"), /^The reason for v3 action #3 .*8-10 screenshots/);
    assert.match(reviewNoteText(v3.notesByRank[3][0], "ja"), /^v3 の提案 #3 .*8〜10枚/);
    assert.match(reviewNoteText(v3.notesByRank[1][0], "en"), /^In v3 action #1, about 300 page views\/day/);
    assert.match(reviewNoteText(v3.notesByRank[1][0], "ja"), /^v3 の提案 #1 の約300 PV\/日.*2pp/);
    for (const version of story.versions.slice(0, -1)) {
      assert.deepEqual(version.notesByRank, {});
    }
    for (const round of story.rounds) {
      for (const finding of round.findings) {
        assert.deepEqual(finding.reviewNotes, [], `${finding.id} must not get a proposal note`);
      }
    }
  });

  it("shows the model output, SQL, and Critic summary as recorded", () => {
    const before = JSON.stringify(run.steps);
    const story = buildDemoStory(run);
    const v3 = story.versions.at(-1);
    const recordedV3 = run.steps.at(-1).output.actions;
    assert.deepEqual(
      v3.actions.map((a) => [a.rank, a.title, a.reason]),
      recordedV3.map((a) => [a.rank, a.title, a.reason]),
    );
    assert.match(v3.actions[2].reason, /Top 3 competitors have 8-10 screenshots/);
    assert.match(v3.actions[0].reason, /~300 page views\/day gives sufficient power to detect a 2pp difference/);
    assert.deepEqual(
      story.rounds.map((round) => round.summary),
      run.steps.filter((step) => step.critic).map((step) => step.critic.summary),
    );
    assert.equal(JSON.stringify(run.steps), before);
  });

  it("gives the review outcome and limitations in each UI language", () => {
    const enText = sampleText(run.sample, "en");
    const jaText = sampleText(run.sample, "ja");
    assert.match(enText.reviewOutcome, /^converged\. .*31 matched, 0 mismatched, 1 unverifiable/);
    assert.match(jaText.reviewOutcome, /^converged（収束）.*一致31・不一致0・照合不能1/);
    assert.equal(enText.knownLimitations.length, 2);
    assert.equal(jaText.knownLimitations.length, 2);
    assert.match(enText.knownLimitations[0], /^The reason for v3 action #3/);
    assert.match(jaText.knownLimitations[1], /^v3 の提案 #1/);
  });
});

describe("reviewOutcome agrees with what the saved trace computes", () => {
  const EN_UNRESOLVED = { 0: "No finding is", 1: "One finding is", 8: "Eight findings are" };

  for (const stem of [EN_BASE, JA_BASE, JA_VARIANT]) {
    it(stem, () => {
      const run = loadRecorded(stem);
      const outcome = runOutcome(run);
      const checks = outcome.finalChecks;
      const ja = run.sample.reviewOutcome;
      const enText = run.sample.en.reviewOutcome;

      assert.ok(ja.startsWith(`${run.status}（`), ja);
      assert.ok(enText.startsWith(`${run.status} (`) || enText.startsWith(`${run.status}.`), enText);
      if (run.status === "converged") {
        assert.equal(outcome.unresolved, 0);
      }

      assert.match(ja, new RegExp(`未解決の指摘[がは]${outcome.unresolved}件`));
      assert.ok(EN_UNRESOLVED[outcome.unresolved], `no wording for ${outcome.unresolved}`);
      assert.ok(enText.includes(EN_UNRESOLVED[outcome.unresolved]), enText);

      const jaSql = ja.match(/一致(\d+)・不一致(\d+)・照合不能(\d+)/);
      const enSql = enText.match(/(\d+) matched, (\d+) mismatched, (\d+) unverifiable/);
      for (const found of [jaSql, enSql]) {
        if (found) {
          assert.deepEqual(found.slice(1).map(Number), [
            checks.matched,
            checks.mismatched,
            checks.unverifiable,
          ]);
        }
      }
      if (stem === EN_BASE) {
        assert.ok(jaSql && enSql, "the English base states its final SQL checks");
      }

      const finalRound = run.steps.filter((step) => step.critic).at(-1).critic;
      const unresolvedIds = finalRound.findings
        .filter((f) => f.resolution === "unresolved")
        .map((f) => f.id);
      for (const id of [...ja.matchAll(/r\d+-f\d+/g), ...enText.matchAll(/r\d+-f\d+/g)].map((m) => m[0])) {
        assert.ok(unresolvedIds.includes(id), `${id} is not an unresolved final finding`);
      }
    });
  }
});

describe("Recorded Demo choice (/demo): the English base in every UI language", () => {
  it("marks only the English base as representative", () => {
    assert.equal(loadRecorded(EN_BASE).sample.representative, true);
    assert.equal(loadRecorded(JA_BASE).sample.representative, undefined);
    assert.equal(loadRecorded(JA_VARIANT).sample.representative, undefined);
  });

  it("opens the English base first and lists one demo per scenario", () => {
    assert.equal(pickRecordedDemo(apiList())?.runId, EN_BASE);
    assert.equal(pickRecordedDemo([...apiList()].reverse())?.runId, EN_BASE);
    assert.deepEqual(
      recordedDemosByScenario(apiList()).map((run) => [run.sample.scenario, run.runId, run.language]),
      [
        ["base", EN_BASE, "en"],
        ["competitor-variant", JA_VARIANT, "ja"],
      ],
    );
  });

  it("keeps the Japanese base listed by the API but not offered as a second base", () => {
    assert.ok(apiList().some((run) => run.runId === JA_BASE));
    assert.ok(!recordedDemosByScenario(apiList()).some((run) => run.runId === JA_BASE));
  });

  it("falls back to the first listed run when no run is representative", () => {
    const onlyJa = [listed(JA_VARIANT), listed(JA_BASE)];
    assert.equal(pickRecordedDemo(onlyJa)?.runId, JA_BASE);
    assert.deepEqual(recordedDemosByScenario(undefined), []);
  });

  it("names the model output language when it differs from the UI language", () => {
    const enCopy = (key) => t(key, "en");
    const jaCopy = (key) => t(key, "ja");
    const variant = recordedDemosByScenario(apiList())[1];
    assert.equal(variant.language, "ja");
    assert.equal(
      enCopy("demoOutputLanguage").replace("{lang}", languageName(variant.language, enCopy)),
      "Japanese output",
    );
    assert.match(
      enCopy("demoModelLanguageNote").replace("{lang}", languageName(variant.language, enCopy)),
      /^The model output of this run .* was recorded in Japanese and is not translated\./,
    );
    assert.match(
      jaCopy("demoModelLanguageNote").replace("{lang}", languageName("en", jaCopy)),
      /^この実行のモデル出力.*は英語で記録されており、翻訳していません。/,
    );
    assert.equal(languageName("fr", enCopy), "fr");
  });
});

describe("Sample Workspace Top 3 Actions follow the same choice", () => {
  const summaries = [JA_BASE, EN_BASE].map((stem) => {
    const run = loadRecorded(stem);
    return summarizeRecorded(run, buildDemoStory(run));
  });
  const pick = pickRepresentativeRecorded(summaries);

  it("uses the English base, the same run /demo opens", () => {
    assert.equal(pick.runId, EN_BASE);
    assert.equal(pick.runId, pickRecordedDemo(apiList())?.runId);
    assert.equal(pickRepresentativeRecorded([...summaries].reverse()).runId, EN_BASE);
    assert.deepEqual(
      pick.actions.map((a) => a.title),
      loadRecorded(EN_BASE).steps.at(-1).output.actions.map((a) => a.title),
    );
    assert.deepEqual(
      pick.actions.filter((a) => a.notes.length > 0).map((a) => a.rank),
      [1, 3],
    );
    assert.equal(pickRepresentativeRecorded([]), null);
  });

  it("reports the English outcome exactly", () => {
    assert.equal(pick.status, "converged");
    assert.equal(pick.knownMisjudgments, 0);
    assert.equal(
      formatOutcome(pick.outcome, en),
      "Converged · 0 unresolved findings · 1 unverifiable SQL check",
    );
  });
});
