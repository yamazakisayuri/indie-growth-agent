"use client";

import { useLanguage } from "@/lib/language-context";
import type { GrowthReport } from "@/lib/types";

/** "Data Scope" / "Analysis Rules" headings are UI-fixed i18n. */
export function DataScope({ report }: { report: GrowthReport }) {
  const { copy } = useLanguage();

  return (
    <footer className="scope">
      <div className="scope__block">
        <h2 className="scope__heading">{copy("dataScope")}</h2>
        <ul className="scope__list">
          {report.dataScope.map((item) => (
            <li key={`${item.source}-${item.scope}`}>
              <span className="scope__source">{item.source}</span>
              <span className="scope__sep"> — </span>
              <span>{item.scope}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="scope__block">
        <h2 className="scope__heading">{copy("groundingRules")}</h2>
        <ul className="scope__list">
          {report.groundingRules.map((rule) => (
            <li key={rule}>{rule}</li>
          ))}
        </ul>
      </div>
    </footer>
  );
}
