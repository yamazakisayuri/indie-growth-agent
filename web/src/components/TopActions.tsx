"use client";

import { useLanguage } from "@/lib/language-context";
import type { GrowthReport } from "@/lib/types";

/**
 * Top 3 Actions body text comes from the Agent.
 * The section heading is UI-fixed i18n — never from Agent output.
 */
export function TopActions({ report }: { report: GrowthReport }) {
  const { copy } = useLanguage();

  return (
    <section className="actions" aria-labelledby="actions-heading">
      <header className="actions__header">
        <p className="actions__eyebrow">{copy("topActionsHint")}</p>
        <h2 id="actions-heading" className="actions__title">
          {copy("whatShouldIDo")}
        </h2>
      </header>

      {report.actions.length === 0 ? (
        <p className="panel-empty">{copy("actionsEmpty")}</p>
      ) : (
        <ol className="actions__list">
          {report.actions.map((action) => (
            <li key={action.rank} className="actions__item">
              <div
                className="actions__rank"
                aria-label={`${copy("priority")} ${action.rank}`}
              >
                <span className="actions__rank-num">{action.rank}</span>
              </div>
              <div className="actions__body">
                <h3 className="actions__item-title">{action.title}</h3>
                <p className="actions__item-reason">{action.reason}</p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
