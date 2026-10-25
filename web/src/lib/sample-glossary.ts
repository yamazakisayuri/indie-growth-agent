/**
 * English display text for the fictional sample in samples/mahjong/. These are translations
 * added by the UI: the CSVs, scenarios.json, and recorded traces keep the Japanese originals,
 * and a gloss is shown next to the original term, never in place of it.
 */

/** By sample app id. Not the real app's name ("Mahjong Score Calculator"), on purpose. */
const APP_NAMES_EN: Record<string, string> = {
  "fictional-001": "Mahjong Score Book (fictional sample app)",
};

/** The sample app's name in the UI language; the original when there is no translation. */
export function sampleAppName(
  app: { appId: string; name: string },
  language: string,
): string {
  return (language === "en" ? APP_NAMES_EN[app.appId] : undefined) ?? app.name;
}

interface GlossTerm {
  term: string;
  gloss: string;
  /** Only when the term stands alone in quotes, not as part of a longer word or name. */
  quotedOnly?: boolean;
}

/**
 * Japanese terms the model quoted from the sample data. "simple score calculation" is the
 * model's own translation in the English base trace.
 */
const GLOSSARY: GlossTerm[] = [
  { term: "かんたん点数計算", gloss: "simple score calculation" },
  { term: "かんたん", gloss: "simple", quotedOnly: true },
];

const OPEN_QUOTES = "\"'“‘「『";
const CLOSE_QUOTES = "\"'”’」』";

/** True if any of these texts would show a gloss in this language. */
export function hasGloss(texts: (string | null | undefined)[], language: string): boolean {
  return texts.some(
    (text) => !!text && glossSegments(text, language).some((s) => typeof s !== "string"),
  );
}

/** Recorded text, with a gloss after the first use of each term. */
export type GlossSegment = string | { gloss: string };

function alreadyGlossed(rest: string, gloss: string): boolean {
  return rest.trimStart().toLowerCase().startsWith(`(${gloss.toLowerCase()})`);
}

/**
 * Split text so that a gloss follows the first use of each glossary term (after its closing
 * quote). The string segments joined are the text unchanged. Japanese UI: no glosses.
 */
export function glossSegments(text: string, language: string): GlossSegment[] {
  if (language !== "en" || !text) {
    return text ? [text] : [];
  }
  const inserts: { at: number; gloss: string }[] = [];
  const taken: [number, number][] = [];
  for (const { term, gloss, quotedOnly } of GLOSSARY) {
    let from = 0;
    while (from <= text.length) {
      const start = text.indexOf(term, from);
      if (start < 0) {
        break;
      }
      const end = start + term.length;
      from = end;
      if (taken.some(([s, e]) => start < e && end > s)) {
        continue;
      }
      const quotedBefore = start > 0 && OPEN_QUOTES.includes(text[start - 1]);
      const quotedAfter = end < text.length && CLOSE_QUOTES.includes(text[end]);
      if (quotedOnly && !(quotedBefore && quotedAfter)) {
        continue;
      }
      taken.push([start, end]);
      const at = quotedAfter ? end + 1 : end;
      if (!alreadyGlossed(text.slice(at), gloss)) {
        inserts.push({ at, gloss });
      }
      break;
    }
  }
  inserts.sort((a, b) => a.at - b.at);
  const segments: GlossSegment[] = [];
  let cursor = 0;
  for (const { at, gloss } of inserts) {
    if (at > cursor) {
      segments.push(text.slice(cursor, at));
    }
    segments.push({ gloss });
    cursor = at;
  }
  if (cursor < text.length) {
    segments.push(text.slice(cursor));
  }
  return segments;
}
