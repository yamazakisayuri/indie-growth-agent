/**
 * Sample metadata text for the banner, in the UI language. The Japanese fields are the
 * originals; .sample.json may add English under `en`. Missing English falls back to them.
 */
export interface SampleText {
  note: string | null;
  scenarioDescription: string | null;
  /** One per scenario change, in order. */
  changeReasons: string[];
  reviewOutcome: string | null;
  knownLimitations: string[];
  comparisonNote: string | null;
}

interface SampleFields {
  note?: unknown;
  scenarioDescription?: unknown;
  changes?: unknown;
  reviewOutcome?: unknown;
  knownLimitations?: unknown;
  comparisonNote?: unknown;
  en?: unknown;
}

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function texts(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map(text).filter((item): item is string => item !== null)
    : [];
}

function changeReasons(changes: unknown): string[] {
  if (!Array.isArray(changes)) {
    return [];
  }
  return changes.map((change) =>
    change && typeof change === "object" ? (text((change as { reason?: unknown }).reason) ?? "") : "",
  );
}

/** Text for the banner. Malformed fields are dropped; each language falls back to the other per field. */
export function sampleText(sample: SampleFields, language: string): SampleText {
  const ja: SampleText = {
    note: text(sample.note),
    scenarioDescription: text(sample.scenarioDescription),
    changeReasons: changeReasons(sample.changes),
    reviewOutcome: text(sample.reviewOutcome),
    knownLimitations: texts(sample.knownLimitations),
    comparisonNote: text(sample.comparisonNote),
  };
  if (!sample.en || typeof sample.en !== "object") {
    return ja;
  }
  const en = sample.en as Record<string, unknown>;
  const enReasons = Array.isArray(en.changeReasons) ? en.changeReasons.map(text) : [];
  const enLimitations = texts(en.knownLimitations);
  if (language !== "en") {
    // Japanese UI: the Japanese originals, and English only where a field has no Japanese.
    return {
      note: ja.note ?? text(en.note),
      scenarioDescription: ja.scenarioDescription ?? text(en.scenarioDescription),
      changeReasons: ja.changeReasons.map((reason, i) => reason || (enReasons[i] ?? "")),
      reviewOutcome: ja.reviewOutcome ?? text(en.reviewOutcome),
      knownLimitations: ja.knownLimitations.length > 0 ? ja.knownLimitations : enLimitations,
      comparisonNote: ja.comparisonNote ?? text(en.comparisonNote),
    };
  }
  return {
    note: text(en.note) ?? ja.note,
    scenarioDescription: text(en.scenarioDescription) ?? ja.scenarioDescription,
    changeReasons: ja.changeReasons.map((reason, i) => enReasons[i] ?? reason),
    reviewOutcome: text(en.reviewOutcome) ?? ja.reviewOutcome,
    knownLimitations: enLimitations.length > 0 ? enLimitations : ja.knownLimitations,
    comparisonNote: text(en.comparisonNote) ?? ja.comparisonNote,
  };
}
