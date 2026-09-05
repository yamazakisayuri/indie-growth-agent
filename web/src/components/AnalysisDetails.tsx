"use client";

import { useLanguage } from "@/lib/language-context";
import type { GrowthReport } from "@/lib/types";

/** Section headings are UI-fixed. List items are Agent analysis prose. */
export function AnalysisDetails({ report }: { report: GrowthReport }) {
  const { copy } = useLanguage();

  return (
    <section className="analysis" aria-label="Analysis details">
      <div className="analysis__facts">
        <h2 className="analysis__heading">{copy("facts")}</h2>
        <ul className="analysis__list">
          {report.facts.map((fact) => (
            <li key={fact}>{fact}</li>
          ))}
        </ul>
      </div>

      <div className="analysis__speculation">
        <h2 className="analysis__heading">{copy("speculation")}</h2>
        <ul className="analysis__list">
          {report.speculation.length > 0 ? (
            report.speculation.map((item) => <li key={item}>{item}</li>)
          ) : (
            <li>—</li>
          )}
        </ul>
      </div>
    </section>
  );
}
