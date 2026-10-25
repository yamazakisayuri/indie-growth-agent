"use client";

import { useLanguage } from "@/lib/language-context";
import { glossSegments } from "@/lib/sample-glossary";

/** Recorded sample text as is, with a marked English gloss after Japanese terms (English UI). */
export function GlossedText({ text }: { text: string }) {
  const { copy, language } = useLanguage();
  return (
    <>
      {glossSegments(text, language).map((segment, i) =>
        typeof segment === "string" ? (
          segment
        ) : (
          <span key={i} className="term-gloss" title={copy("glossTitle")}>
            {" "}
            [{copy("glossLabel")}: {segment.gloss}]
          </span>
        ),
      )}
    </>
  );
}
