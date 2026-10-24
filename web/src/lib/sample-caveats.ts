/** Notes a person added to a Recorded Demo's .sample.json, shown read-only. */
export interface SampleCaveats {
  reviewOutcome: string | null;
  knownLimitations: string[];
  comparisonNote: string | null;
}

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

/** The notes worth showing, or null when the metadata has none. Malformed fields are dropped. */
export function sampleCaveats(sample: {
  reviewOutcome?: unknown;
  knownLimitations?: unknown;
  comparisonNote?: unknown;
}): SampleCaveats | null {
  const caveats: SampleCaveats = {
    reviewOutcome: text(sample.reviewOutcome),
    knownLimitations: Array.isArray(sample.knownLimitations)
      ? sample.knownLimitations.map(text).filter((item): item is string => item !== null)
      : [],
    comparisonNote: text(sample.comparisonNote),
  };
  const empty =
    !caveats.reviewOutcome && caveats.knownLimitations.length === 0 && !caveats.comparisonNote;
  return empty ? null : caveats;
}
