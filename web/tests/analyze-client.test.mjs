import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { analyzeErrorMessage } from "../src/lib/analyze-client.ts";

describe("analyzeErrorMessage", () => {
  it("reads FastAPI's { detail: { error, code } }", () => {
    const payload = {
      detail: {
        error: "The model (meterless) could not be called. Nightshift has no NVIDIA API key loaded.",
        code: "model_unavailable",
      },
    };
    assert.match(analyzeErrorMessage(payload), /^The model \(meterless\) could not be called/);
  });

  it("still reads a top-level error, and returns null otherwise", () => {
    assert.equal(analyzeErrorMessage({ error: "Could not complete the analysis." }), "Could not complete the analysis.");
    assert.equal(analyzeErrorMessage({ detail: "Not Found" }), null);
    assert.equal(analyzeErrorMessage({ detail: { error: "  " } }), null);
    assert.equal(analyzeErrorMessage(null), null);
  });
});
