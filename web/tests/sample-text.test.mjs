import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { sampleText } from "../src/lib/sample-text.ts";

const SAMPLE = {
  note: "架空のサンプルデータです。",
  scenarioDescription: " 上位競合1件だけ優位をなくした ",
  changes: [{ reason: "評価数を下げる" }, { reason: "スクショを減らす" }],
  reviewOutcome: "max_rounds（再チェック上限で終了）",
  knownLimitations: ["誤判定 r2-f1", "  ", 3, "誤判定 r2-f2"],
  comparisonNote: "因果効果とは断定できない",
  en: {
    note: "Fictional sample data.",
    scenarioDescription: "Only the top competitor loses its lead",
    changeReasons: ["Lower the rating count"],
    reviewOutcome: "max_rounds (stopped at the review limit)",
    knownLimitations: ["False finding r2-f1"],
    comparisonNote: "",
  },
};

describe("sampleText", () => {
  it("keeps the Japanese originals in the Japanese UI, dropping malformed items", () => {
    assert.deepEqual(sampleText(SAMPLE, "ja"), {
      note: "架空のサンプルデータです。",
      scenarioDescription: "上位競合1件だけ優位をなくした",
      changeReasons: ["評価数を下げる", "スクショを減らす"],
      reviewOutcome: "max_rounds（再チェック上限で終了）",
      knownLimitations: ["誤判定 r2-f1", "誤判定 r2-f2"],
      comparisonNote: "因果効果とは断定できない",
    });
  });

  it("uses English where present and falls back to Japanese per field", () => {
    assert.deepEqual(sampleText(SAMPLE, "en"), {
      note: "Fictional sample data.",
      scenarioDescription: "Only the top competitor loses its lead",
      changeReasons: ["Lower the rating count", "スクショを減らす"],
      reviewOutcome: "max_rounds (stopped at the review limit)",
      knownLimitations: ["False finding r2-f1"],
      comparisonNote: "因果効果とは断定できない",
    });
  });

  it("returns empty text for a sample without notes or English", () => {
    assert.deepEqual(sampleText({ changes: [] }, "en"), {
      note: null,
      scenarioDescription: null,
      changeReasons: [],
      reviewOutcome: null,
      knownLimitations: [],
      comparisonNote: null,
    });
  });
});
