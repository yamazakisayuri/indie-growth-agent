"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import type { CopyKey } from "@/lib/i18n";
import {
  INTERVENTIONS_CHANGED_EVENT,
  InterventionRequestError,
  VERDICTS,
  addIntervention,
  dropIntervention,
  evaluateIntervention,
  implementIntervention,
  listInterventions,
  localToday,
  measureIntervention,
  type Intervention,
  type InterventionResult,
  type InterventionStatus,
  type Measurement,
  type PlanInput,
  type Verdict,
} from "@/lib/interventions-client";
import { useLanguage } from "@/lib/language-context";

const STATUS_COPY: Record<InterventionStatus, CopyKey> = {
  planned: "interventionsStatusPlanned",
  implemented: "interventionsStatusImplemented",
  evaluated: "interventionsStatusEvaluated",
  dropped: "interventionsStatusDropped",
};

export const VERDICT_COPY: Record<Verdict, CopyKey> = {
  improved: "interventionsVerdictImproved",
  no_change: "interventionsVerdictNoChange",
  worse: "interventionsVerdictWorse",
  inconclusive: "interventionsVerdictInconclusive",
};

const ERROR_COPY: Record<string, CopyKey> = {
  api_unreachable: "evidenceApiUnreachable",
  not_due: "interventionsErrorNotDue",
  invalid_dates: "interventionsErrorInvalidDates",
  invalid_transition: "interventionsErrorTransition",
  store_unavailable: "interventionsErrorStoreUnavailable",
  run_in_progress: "interventionsErrorRunInProgress",
  invalid_input: "interventionsErrorInvalidInput",
  missing_plan: "interventionsNeedsPlan",
};

type Tone = "up" | "down" | "muted";

export function interventionErrorCopy(err: unknown): CopyKey {
  if (err instanceof InterventionRequestError) {
    return ERROR_COPY[err.code] ?? "interventionsErrorGeneric";
  }
  return "interventionsErrorGeneric";
}

function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={`evidence__badge evidence__badge--${tone}`}>{children}</span>;
}

function statusTone(status: InterventionStatus): Tone {
  return status === "evaluated" ? "up" : status === "dropped" ? "down" : "muted";
}

function verdictTone(verdict: Verdict): Tone {
  return verdict === "improved" ? "up" : verdict === "worse" ? "down" : "muted";
}

function formatMetric(metric: string, value: number): string {
  const text = value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return metric.endsWith("_pct") ? `${text}%` : text;
}

export function emptyPlan(): PlanInput {
  return { targetMetric: "", method: "", successCriterion: "", durationDays: 14 };
}

export function planIsComplete(plan: PlanInput): boolean {
  return Boolean(
    plan.targetMetric.trim() &&
      plan.method.trim() &&
      plan.successCriterion.trim() &&
      plan.durationDays >= 1,
  );
}

/** Metric, method, success criterion, and days: shared by manual add and adopt. */
export function PlanFields({
  plan,
  onChange,
}: {
  plan: PlanInput;
  onChange: (plan: PlanInput) => void;
}) {
  const { copy } = useLanguage();
  return (
    <>
      <label className="interventions__field">
        <span>{copy("interventionsFieldMetric")}</span>
        <input
          className="interventions__input"
          value={plan.targetMetric}
          onChange={(e) => onChange({ ...plan, targetMetric: e.target.value })}
          placeholder="page_view_to_download_pct"
          required
        />
        <small className="evidence__note">{copy("interventionsMetricHint")}</small>
      </label>
      <label className="interventions__field">
        <span>{copy("interventionsFieldMethod")}</span>
        <input
          className="interventions__input"
          value={plan.method}
          onChange={(e) => onChange({ ...plan, method: e.target.value })}
          required
        />
      </label>
      <label className="interventions__field">
        <span>{copy("interventionsFieldCriterion")}</span>
        <input
          className="interventions__input"
          value={plan.successCriterion}
          onChange={(e) => onChange({ ...plan, successCriterion: e.target.value })}
          required
        />
      </label>
      <label className="interventions__field interventions__field--short">
        <span>{copy("interventionsFieldDays")}</span>
        <input
          className="interventions__input"
          type="number"
          min={1}
          max={365}
          value={plan.durationDays}
          onChange={(e) => onChange({ ...plan, durationDays: Number(e.target.value) })}
          required
        />
      </label>
    </>
  );
}

function MeasurementTable({
  baseline,
  after,
}: {
  baseline: Measurement | null;
  after: Measurement | null;
}) {
  const { copy } = useLanguage();
  const before = new Map((baseline?.metrics ?? []).map((m) => [m.metric, m]));
  const later = new Map((after?.metrics ?? []).map((m) => [m.metric, m]));
  const names = [...before.keys(), ...[...later.keys()].filter((n) => !before.has(n))];
  const skipped = [
    ...(baseline?.skipped ?? []).map((s) => `${copy("interventionsBefore")}: ${s}`),
    ...(after?.skipped ?? []).map((s) => `${copy("interventionsAfter")}: ${s}`),
  ];
  const period = (m: Measurement | null) =>
    m ? `${m.periodStart}–${m.periodEnd}` : copy("interventionsNotMeasured");

  return (
    <div className="evidence__block">
      <h4 className="evidence__block-title">{copy("interventionsMeasured")}</h4>
      {names.length > 0 ? (
        <table className="interventions__table">
          <thead>
            <tr>
              <th scope="col" />
              <th scope="col">
                {copy("interventionsBefore")}
                <br />
                <small>{period(baseline)}</small>
              </th>
              <th scope="col">
                {copy("interventionsAfter")}
                <br />
                <small>{period(after)}</small>
              </th>
            </tr>
          </thead>
          <tbody>
            {names.map((name) => {
              const b = before.get(name);
              const a = later.get(name);
              return (
                <tr key={name}>
                  <th scope="row">{name}</th>
                  <td>{b ? formatMetric(name, b.value) : "—"}</td>
                  <td>{a ? formatMetric(name, a.value) : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <p className="evidence__note">{copy("interventionsNotMeasured")}</p>
      )}
      {skipped.length > 0 ? (
        <p className="evidence__note">
          {copy("interventionsSkipped")}: {skipped.join(" / ")}
        </p>
      ) : null}
    </div>
  );
}

function InterventionItem({ item }: { item: Intervention }) {
  const { copy } = useLanguage();
  const today = localToday();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<CopyKey | null>(null);
  const [notice, setNotice] = useState<string[]>([]);
  const [implementedOn, setImplementedOn] = useState(today);
  const [verdict, setVerdict] = useState<Verdict>("inconclusive");
  const [note, setNote] = useState("");
  const [early, setEarly] = useState(false);
  const due = item.status === "implemented" && today >= item.decision.evaluationDate;

  async function run(action: () => Promise<InterventionResult>) {
    setBusy(true);
    setError(null);
    setNotice([]);
    try {
      const result = await action();
      setNotice([
        ...(result.changed ? [] : [copy("interventionsUnchanged")]),
        ...result.warnings,
      ]);
    } catch (err) {
      setError(interventionErrorCopy(err));
    } finally {
      setBusy(false);
    }
  }

  function handleDrop() {
    const reason = window.prompt(copy("interventionsDropPrompt"))?.trim();
    if (reason) {
      void run(() => dropIntervention(item.id, reason));
    }
  }

  return (
    <article className="experiments__item interventions__item">
      <h3 className="experiments__item-title">{item.decision.actionTitle}</h3>
      <p className="interventions__badges">
        <Badge tone={statusTone(item.status)}>{copy(STATUS_COPY[item.status])}</Badge>{" "}
        <Badge tone="muted">
          {copy(
            item.decision.origin === "ai_adopted"
              ? "interventionsOriginAi"
              : "interventionsOriginManual",
          )}
        </Badge>{" "}
        {due ? <Badge tone="up">{copy("interventionsDue")}</Badge> : null}
      </p>
      {item.decision.changeDescription ? (
        <p className="evidence__note">{item.decision.changeDescription}</p>
      ) : null}

      <dl className="evidence__meta">
        <div>
          <dt>{copy("interventionsFieldMetric")}</dt>
          <dd>{item.targetMetric}</dd>
        </div>
        <div>
          <dt>{copy("interventionsImplementedOn")}</dt>
          <dd>{item.implementedOn ?? "—"}</dd>
        </div>
        <div>
          <dt>{copy("interventionsEvaluationDate")}</dt>
          <dd>{item.decision.evaluationDate}</dd>
        </div>
      </dl>
      <dl className="interventions__plan">
        <dt>{copy("interventionsFieldMethod")}</dt>
        <dd>{item.decision.method}</dd>
        <dt>{copy("interventionsFieldCriterion")}</dt>
        <dd>{item.decision.successCriterion}</dd>
      </dl>

      {item.prediction ? (
        <div className="evidence__block">
          <h4 className="evidence__block-title">{copy("interventionsAiPrediction")}</h4>
          <p className="evidence__note">
            <span className="evidence__claim-id">
              {item.prediction.runId} {item.prediction.version} #{item.prediction.actionRank}
            </span>{" "}
            {item.prediction.actionReason}
          </p>
          {item.prediction.testPlan ? (
            <p className="evidence__note">
              {copy("interventionsAiCriterion")}: {item.prediction.testPlan.successCriterion}
            </p>
          ) : null}
        </div>
      ) : null}

      {item.implementedOn ? (
        <MeasurementTable baseline={item.baseline} after={item.after} />
      ) : null}

      {item.evaluation ? (
        <div className="evidence__block">
          <h4 className="evidence__block-title">{copy("interventionsHumanVerdict")}</h4>
          <p className="evidence__note">
            <Badge tone={verdictTone(item.evaluation.verdict)}>
              {copy(VERDICT_COPY[item.evaluation.verdict])}
            </Badge>{" "}
            {item.evaluation.evaluatedOn}
            {item.evaluation.note ? ` — ${item.evaluation.note}` : ""}
          </p>
        </div>
      ) : null}

      {item.dropReason ? (
        <p className="evidence__note">
          {copy("interventionsDropReason")}: {item.dropReason}
        </p>
      ) : null}

      {item.status === "planned" ? (
        <div className="interventions__actions">
          <label className="interventions__field interventions__field--short">
            <span>{copy("interventionsImplementedOn")}</span>
            <input
              className="interventions__input"
              type="date"
              value={implementedOn}
              max={today}
              onChange={(e) => setImplementedOn(e.target.value)}
            />
          </label>
          <button
            type="button"
            className="experiments__draft-btn"
            disabled={busy || !implementedOn}
            onClick={() => void run(() => implementIntervention(item.id, implementedOn))}
          >
            {copy("interventionsMarkImplemented")}
          </button>
        </div>
      ) : null}

      {item.status === "implemented" ? (
        <div className="interventions__actions">
          <label className="interventions__field interventions__field--short">
            <span>{copy("interventionsHumanVerdict")}</span>
            <select
              className="evidence__select"
              value={verdict}
              onChange={(e) => setVerdict(e.target.value as Verdict)}
            >
              {VERDICTS.map((v) => (
                <option key={v} value={v}>
                  {copy(VERDICT_COPY[v])}
                </option>
              ))}
            </select>
          </label>
          <label className="interventions__field">
            <span>{copy("interventionsNote")}</span>
            <input
              className="interventions__input"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </label>
          {!due ? (
            <label className="interventions__check">
              <input
                type="checkbox"
                checked={early}
                onChange={(e) => setEarly(e.target.checked)}
              />{" "}
              {copy("interventionsEarly")}
            </label>
          ) : null}
          <button
            type="button"
            className="experiments__draft-btn"
            disabled={busy}
            onClick={() =>
              void run(() => evaluateIntervention(item.id, verdict, note.trim(), today, early))
            }
          >
            {copy("interventionsEvaluate")}
          </button>
        </div>
      ) : null}

      {item.status !== "dropped" ? (
        <div className="interventions__actions">
          {item.status !== "planned" ? (
            <button
              type="button"
              className="experiments__draft-btn experiments__draft-btn--ghost"
              disabled={busy}
              onClick={() => void run(() => measureIntervention(item.id))}
            >
              {copy("interventionsMeasure")}
            </button>
          ) : null}
          {item.status !== "evaluated" ? (
            <button
              type="button"
              className="experiments__draft-btn experiments__draft-btn--ghost"
              disabled={busy}
              onClick={handleDrop}
            >
              {copy("interventionsDrop")}
            </button>
          ) : null}
          {busy ? <span className="experiments__status">{copy("interventionsWorking")}</span> : null}
        </div>
      ) : null}

      {error ? (
        <p className="experiments__error" role="alert">
          {copy(error)}
        </p>
      ) : null}
      {notice.length > 0 ? (
        <p className="experiments__status">
          {copy("interventionsWarning")}: {notice.join(" / ")}
        </p>
      ) : null}
    </article>
  );
}

function ManualForm({ productId, onDone }: { productId: string; onDone: () => void }) {
  const { copy } = useLanguage();
  const [title, setTitle] = useState("");
  const [change, setChange] = useState("");
  const [plan, setPlan] = useState<PlanInput>(emptyPlan);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<CopyKey | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || !planIsComplete(plan)) {
      setError("interventionsErrorInvalidInput");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await addIntervention(productId, title.trim(), change.trim(), plan);
      onDone();
    } catch (err) {
      setError(interventionErrorCopy(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="interventions__form" onSubmit={handleSubmit}>
      <label className="interventions__field">
        <span>{copy("interventionsFieldTitle")}</span>
        <input
          className="interventions__input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
        />
      </label>
      <label className="interventions__field">
        <span>{copy("interventionsFieldChange")}</span>
        <input
          className="interventions__input"
          value={change}
          onChange={(e) => setChange(e.target.value)}
        />
      </label>
      <PlanFields plan={plan} onChange={setPlan} />
      <div className="interventions__actions">
        <button type="submit" className="experiments__draft-btn" disabled={busy}>
          {busy ? copy("interventionsSubmitting") : copy("interventionsSubmit")}
        </button>
        <button
          type="button"
          className="experiments__draft-btn experiments__draft-btn--ghost"
          onClick={onDone}
          disabled={busy}
        >
          {copy("interventionsCancel")}
        </button>
      </div>
      {error ? (
        <p className="experiments__error" role="alert">
          {copy(error)}
        </p>
      ) : null}
    </form>
  );
}

/** Interventions for one product: adopted or hand-added, implemented, evaluated. */
export function InterventionsPanel({ productId }: { productId: string }) {
  const { copy } = useLanguage();
  const [items, setItems] = useState<Intervention[] | null>(null);
  const [loadError, setLoadError] = useState<CopyKey | null>(null);
  const [nonce, setNonce] = useState(0);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    const reload = () => setNonce((n) => n + 1);
    window.addEventListener(INTERVENTIONS_CHANGED_EVENT, reload);
    return () => window.removeEventListener(INTERVENTIONS_CHANGED_EVENT, reload);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    listInterventions(productId, controller.signal)
      .then((list) => {
        setItems(list);
        setLoadError(null);
      })
      .catch((err: unknown) => {
        if (!isAbort(err)) {
          setLoadError(
            err instanceof InterventionRequestError && err.code === "api_unreachable"
              ? "evidenceApiUnreachable"
              : "interventionsLoadError",
          );
        }
      });
    return () => controller.abort();
  }, [productId, nonce]);

  return (
    <section className="evidence interventions" aria-labelledby="interventions-heading">
      <header className="evidence__header">
        <p className="evidence__eyebrow">{copy("interventionsEyebrow")}</p>
        <h2 id="interventions-heading" className="evidence__heading">
          {copy("interventionsTitle")}
        </h2>
        <p className="evidence__hint">{copy("interventionsHint")}</p>
      </header>

      <div className="evidence__controls">
        {!adding ? (
          <button
            type="button"
            className="experiments__draft-btn"
            onClick={() => setAdding(true)}
            disabled={loadError === "evidenceApiUnreachable"}
          >
            {copy("interventionsNew")}
          </button>
        ) : null}
      </div>

      {adding ? <ManualForm productId={productId} onDone={() => setAdding(false)} /> : null}

      {loadError ? <p className="experiments__error">{copy(loadError)}</p> : null}
      {!items && !loadError ? (
        <p className="experiments__empty">{copy("interventionsLoading")}</p>
      ) : null}
      {items && items.length === 0 ? (
        <p className="experiments__empty">{copy("interventionsEmpty")}</p>
      ) : null}
      {items && items.length > 0 ? (
        <div className="experiments__list">
          {items.map((item) => (
            <InterventionItem key={item.id} item={item} />
          ))}
        </div>
      ) : null}
    </section>
  );
}
