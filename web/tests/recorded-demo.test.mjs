import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import { buildDemoStory, pickRecordedDemo, recordedDemos } from "../src/lib/recorded-demo.ts";

function summary(runId, overrides = {}) {
  return {
    runId,
    productId: "mahjong",
    startedAt: "2026-10-24T21:41:21+09:00",
    finishedAt: null,
    status: "max_rounds",
    model: "m",
    language: "ja",
    versions: ["v1", "v2", "v3"],
    topActions: [],
    unresolvedFindings: 0,
    error: null,
    sample: null,
    recorded: false,
    ...overrides,
  };
}

const sample = (scenario) => ({ dataKind: "fictional_sample", scenario });

describe("pickRecordedDemo", () => {
  it("prefers the base scenario over newer recorded runs", () => {
    const target = pickRecordedDemo([
      summary("live-1"),
      summary("variant", { recorded: true, sample: sample("competitor-variant") }),
      summary("base", { recorded: true, sample: sample("base") }),
    ]);
    assert.deepEqual(target, { productId: "mahjong", runId: "base" });
  });

  it("falls back to the first recorded run without a base scenario", () => {
    const target = pickRecordedDemo([
      summary("variant", { recorded: true, sample: sample("competitor-variant"), productId: "x" }),
    ]);
    assert.deepEqual(target, { productId: "x", runId: "variant" });
  });

  it("ignores Live Sample and live runs", () => {
    const runs = [summary("live-1"), summary("live-sample", { sample: sample("base") })];
    assert.equal(pickRecordedDemo(runs), null);
    assert.deepEqual(recordedDemos(runs), []);
    assert.equal(pickRecordedDemo(undefined), null);
  });
});

describe("buildDemoStory (committed base Recorded Demo)", () => {
  const run = JSON.parse(
    readFileSync(
      new URL("../../samples/recorded/sample-base-20261024-214121.json", import.meta.url),
      "utf8",
    ),
  );
  const story = buildDemoStory(run);

  it("keeps every version in order with its ranked actions", () => {
    assert.deepEqual(
      story.versions.map((v) => [v.version, v.stage, v.actions.length]),
      [
        ["v1", "internal", 3],
        ["v2", "competitive", 3],
        ["v3", "critic_revision", 3],
      ],
    );
    assert.deepEqual(
      story.versions[2].actions.map((a) => a.rank),
      [1, 2, 3],
    );
  });

  it("pairs each Critic finding with the Analyst's answer in the next version", () => {
    assert.deepEqual(
      story.rounds.map((r) => [r.round, r.reviewedVersion, r.answeredIn, r.findings.length]),
      [
        [1, "v2", "v3", 2],
        [2, "v3", null, 1],
      ],
    );
    const first = story.rounds[0].findings[0];
    assert.equal(first.id, "r1-f1");
    assert.equal(first.answer?.response, "fixed");
    assert.equal(story.rounds[1].findings[0].answer, null);
    assert.equal(story.rounds[0].checksMatched, story.rounds[0].checksTotal);
  });

  it("counts what is still unresolved, without hiding it", () => {
    assert.equal(story.unresolved, 1);
  });
});
