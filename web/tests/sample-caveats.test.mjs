import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { sampleCaveats } from "../src/lib/sample-caveats.ts";

describe("sampleCaveats", () => {
  it("keeps the review outcome, limitations, and comparison note", () => {
    const caveats = sampleCaveats({
      reviewOutcome: " max_rounds（再チェック上限で終了） ",
      knownLimitations: ["誤判定 r2-f1", "  ", 3, "誤判定 r2-f2"],
      comparisonNote: "因果効果とは断定できない",
    });
    assert.deepEqual(caveats, {
      reviewOutcome: "max_rounds（再チェック上限で終了）",
      knownLimitations: ["誤判定 r2-f1", "誤判定 r2-f2"],
      comparisonNote: "因果効果とは断定できない",
    });
  });

  it("returns null for a sample without notes or with malformed ones", () => {
    assert.equal(sampleCaveats({}), null);
    assert.equal(
      sampleCaveats({ reviewOutcome: "", knownLimitations: "not a list", comparisonNote: 1 }),
      null,
    );
  });

  it("shows a lone field without the others", () => {
    assert.deepEqual(sampleCaveats({ comparisonNote: "note" }), {
      reviewOutcome: null,
      knownLimitations: [],
      comparisonNote: "note",
    });
  });
});
