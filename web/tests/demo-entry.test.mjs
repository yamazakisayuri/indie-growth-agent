import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { pickRecordedDemo } from "../src/lib/demo-entry.ts";

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
    assert.equal(
      pickRecordedDemo([
        summary("live-1"),
        summary("live-sample", { sample: sample("base") }),
      ]),
      null,
    );
    assert.equal(pickRecordedDemo([]), null);
    assert.equal(pickRecordedDemo(undefined), null);
  });
});
