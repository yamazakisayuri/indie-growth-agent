"use client";

import { useState, type FormEvent } from "react";
import type { CopyKey } from "@/lib/i18n";
import { adoptAction, type PlanInput } from "@/lib/interventions-client";
import { useLanguage } from "@/lib/language-context";
import {
  PlanFields,
  emptyPlan,
  interventionErrorCopy,
  planIsComplete,
} from "./InterventionsPanel";

/** Adopts one proposed action of a finished evidence run as an intervention. */
export function AdoptActionButton({
  runId,
  rank,
  hasTestPlan,
}: {
  runId: string;
  rank: number;
  hasTestPlan: boolean;
}) {
  const { copy } = useLanguage();
  const [busy, setBusy] = useState(false);
  const [askPlan, setAskPlan] = useState(false);
  const [plan, setPlan] = useState<PlanInput>(emptyPlan);
  const [result, setResult] = useState<CopyKey | null>(null);
  const [error, setError] = useState<CopyKey | null>(null);

  async function submit(withPlan?: PlanInput) {
    setBusy(true);
    setError(null);
    try {
      const response = await adoptAction(runId, rank, withPlan);
      setResult(response.changed ? "interventionsAdopted" : "interventionsAlreadyAdopted");
      setAskPlan(false);
    } catch (err) {
      const key = interventionErrorCopy(err);
      if (key === "interventionsNeedsPlan" && !withPlan) {
        setAskPlan(true);
      } else {
        setError(key);
      }
    } finally {
      setBusy(false);
    }
  }

  function handlePlanSubmit(event: FormEvent) {
    event.preventDefault();
    if (!planIsComplete(plan)) {
      setError("interventionsErrorInvalidInput");
      return;
    }
    void submit(plan);
  }

  if (result) {
    return <p className="experiments__status">{copy(result)}</p>;
  }

  return (
    <div className="interventions__adopt">
      {askPlan ? (
        <form className="interventions__form" onSubmit={handlePlanSubmit}>
          <p className="evidence__note">{copy("interventionsNeedsPlan")}</p>
          <PlanFields plan={plan} onChange={setPlan} />
          <div className="interventions__actions">
            <button type="submit" className="experiments__draft-btn" disabled={busy}>
              {busy ? copy("interventionsAdopting") : copy("interventionsAdopt")}
            </button>
            <button
              type="button"
              className="experiments__draft-btn experiments__draft-btn--ghost"
              onClick={() => setAskPlan(false)}
              disabled={busy}
            >
              {copy("interventionsCancel")}
            </button>
          </div>
        </form>
      ) : (
        <button
          type="button"
          className="experiments__draft-btn experiments__draft-btn--ghost"
          disabled={busy}
          onClick={() => (hasTestPlan ? void submit() : setAskPlan(true))}
        >
          {busy ? copy("interventionsAdopting") : copy("interventionsAdopt")}
        </button>
      )}
      {error ? (
        <p className="experiments__error" role="alert">
          {copy(error)}
        </p>
      ) : null}
    </div>
  );
}
