"use client";

import type { ReactNode } from "react";
import { useLanguage } from "@/lib/language-context";
import type { DisplayAction } from "@/lib/types";

/**
 * Top 3 Actions body text comes from the Agent.
 * The section heading is UI-fixed i18n — never from Agent output.
 * `renderText` may decorate that text (e.g. glosses) but must keep it as is;
 * `renderDetails` adds content under an action (e.g. cited claims, known limitations).
 */
export function TopActions<A extends DisplayAction>({
  report,
  renderText = (text) => text,
  renderDetails,
}: {
  report: { actions: A[] };
  renderText?: (text: string) => ReactNode;
  renderDetails?: (action: A) => ReactNode;
}) {
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
                <h3 className="actions__item-title">{renderText(action.title)}</h3>
                <p className="actions__item-reason">{renderText(action.reason)}</p>
                {renderDetails ? renderDetails(action) : null}
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
