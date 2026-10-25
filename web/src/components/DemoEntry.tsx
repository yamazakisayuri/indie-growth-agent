"use client";

import { useState } from "react";
import { pickRecordedDemo, type RecordedDemoTarget } from "@/lib/demo-entry";
import { EvidenceRequestError, listEvidenceRuns } from "@/lib/evidence-client";
import type { CopyKey } from "@/lib/i18n";
import { useLanguage } from "@/lib/language-context";

/** API's max list size, so committed Recorded Demos are not pushed out by newer runs. */
const RUN_LIST_LIMIT = 100;

/** Entry to the committed Recorded Demo: no Analyze, no API keys, no model calls. */
export function DemoEntry({
  disabled,
  onOpen,
}: {
  disabled: boolean;
  onOpen: (target: RecordedDemoTarget) => void;
}) {
  const { copy } = useLanguage();
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState<CopyKey | null>(null);

  async function handleOpen() {
    setOpening(true);
    setError(null);
    try {
      const list = await listEvidenceRuns(null, undefined, RUN_LIST_LIMIT);
      const target = pickRecordedDemo(list.runs);
      if (target) {
        onOpen(target);
      } else {
        setError("demoEntryNotFound");
      }
    } catch (err) {
      setError(
        err instanceof EvidenceRequestError && err.code === "api_unreachable"
          ? "evidenceApiUnreachable"
          : "demoEntryNotFound",
      );
    } finally {
      setOpening(false);
    }
  }

  return (
    <section className="demo-entry" aria-labelledby="demo-entry-heading">
      <h2 id="demo-entry-heading" className="demo-entry__title">
        {copy("demoEntryTitle")}
      </h2>
      <p className="demo-entry__lead">{copy("demoEntryLead")}</p>
      <ul className="demo-entry__tags">
        <li>{copy("demoEntryTagRecorded")}</li>
        <li>{copy("demoEntryTagSynthetic")}</li>
        <li>{copy("demoEntryTagRealModel")}</li>
      </ul>
      <div className="demo-entry__cta-row">
        <button
          type="button"
          className="demo-entry__cta"
          onClick={handleOpen}
          disabled={disabled || opening}
        >
          <span className="demo-entry__cta-label">{copy("demoEntryCta")}</span>
          <span className="demo-entry__cta-flow">{copy("demoEntryFlow")}</span>
        </button>
        <p className="demo-entry__note">{copy("demoEntryNote")}</p>
      </div>
      {error ? (
        <p className="experiments__error" role="alert">
          {copy(error)}
        </p>
      ) : null}
    </section>
  );
}
