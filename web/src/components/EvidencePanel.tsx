"use client";

import { useEffect, useState, type ReactNode } from "react";
import type { CopyKey } from "@/lib/i18n";
import {
  EvidenceRequestError,
  getEvidenceRun,
  listEvidenceRuns,
  startEvidenceRun,
  type Claim,
  type CriticFinding,
  type CriticReview,
  type EvidenceRun,
  type EvidenceRunStatus,
  type EvidenceRunSummary,
  type EvidenceValue,
  type FindingResponse,
  type RevisionStep,
} from "@/lib/evidence-client";
import { useLanguage } from "@/lib/language-context";
import {
  RUN_STATUS_COPY,
  isFictionalRun,
  outcomeCounts,
  runOutcome,
  tallyChecks,
  type CheckTally,
} from "@/lib/recorded-demo";
import { sampleText } from "@/lib/sample-text";
import { AdoptActionButton } from "./AdoptActionButton";

const POLL_MS = 4000;
const VALUE_PREVIEW_CHARS = 160;

export const STATUS_COPY: Record<EvidenceRunStatus, CopyKey> = RUN_STATUS_COPY;

export const STAGE_COPY: Record<RevisionStep["stage"], CopyKey> = {
  internal: "evidenceStageInternal",
  competitive: "evidenceStageCompetitive",
  critic_revision: "evidenceStageRevision",
};

const KIND_COPY: Record<Claim["kind"], CopyKey> = {
  fact: "evidenceKindFact",
  observation: "evidenceKindObservation",
  hypothesis: "evidenceKindHypothesis",
};

export const FINDING_COPY: Record<CriticFinding["kind"], CopyKey> = {
  value_mismatch: "evidenceFindingValueMismatch",
  unverifiable: "evidenceFindingUnverifiable",
  kind_mislabel: "evidenceFindingKindMislabel",
  scope_mismatch: "evidenceFindingScopeMismatch",
  causal_leap: "evidenceFindingCausalLeap",
  infeasible_action: "evidenceFindingInfeasibleAction",
};

export const RESOLUTION_COPY: Record<CriticFinding["resolution"], CopyKey> = {
  resolved: "evidenceResolutionResolved",
  downgraded: "evidenceResolutionDowngraded",
  unresolved: "evidenceResolutionUnresolved",
  open: "evidenceResolutionOpen",
};

export const RESPONSE_COPY: Record<FindingResponse["response"], CopyKey> = {
  fixed: "evidenceResponseFixed",
  downgraded: "evidenceResponseDowngraded",
  removed: "evidenceResponseRemoved",
  disputed: "evidenceResponseDisputed",
};

export const DECISION_COPY = {
  kept: "evidenceDecisionKept",
  modified: "evidenceDecisionModified",
  removed: "evidenceDecisionRemoved",
} as const satisfies Record<string, CopyKey>;

export type Tone = "up" | "down" | "muted";

function errorCopy(err: unknown): CopyKey {
  return err instanceof EvidenceRequestError && err.code === "api_unreachable"
    ? "evidenceApiUnreachable"
    : "evidenceLoadError";
}

function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

function formatTime(iso: string, language: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString(language === "ja" ? "ja-JP" : "en-US", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatValue(value: EvidenceValue): string {
  if (value === null || value === undefined) {
    return "NULL";
  }
  const numeric = typeof value === "number" || /^-?\d+(\.\d+)?$/.test(value.trim());
  const text = numeric ? Number(value).toLocaleString() : String(value);
  return text.length > VALUE_PREVIEW_CHARS
    ? `${text.slice(0, VALUE_PREVIEW_CHARS)}…`
    : text;
}

function minutesBetween(start: string, end: string | null): string | null {
  if (!end) {
    return null;
  }
  const ms = new Date(end).getTime() - new Date(start).getTime();
  return Number.isFinite(ms) && ms >= 0 ? `${Math.round(ms / 60000)} min` : null;
}

function runOptionLabel(
  run: EvidenceRunSummary,
  language: string,
  copy: (key: CopyKey) => string,
): string {
  const versions = run.versions.length > 0 ? run.versions.join("→") : "—";
  const label = `${formatTime(run.startedAt, language)} · ${copy(STATUS_COPY[run.status])} · ${versions}`;
  if (!run.sample) {
    return label;
  }
  const kind = copy(run.recorded ? "evidenceRecordedDemo" : "evidenceLiveSample");
  return `[${kind}: ${run.sample.scenario}] ${label}`;
}

/**
 * Fictional sample data: say so, with the review outcome and unresolved count up front.
 * The scenario, changed values, known limitations, and comparison note sit in details.
 */
export function SampleBanner({ run }: { run: EvidenceRun }) {
  const { copy, language } = useLanguage();
  if (!run.sample) {
    return null;
  }
  const sample = run.sample;
  const text = sampleText(sample, language);
  const finalCritic = run.steps.at(-1)?.critic;
  const unresolved = finalCritic
    ? finalCritic.findings.filter((f) => f.resolution === "unresolved").length
    : null;
  return (
    <div className="evidence__block evidence__sample" role="note">
      <p className="evidence__block-title">
        <Badge tone="muted">
          {copy(run.recorded ? "evidenceRecordedDemo" : "evidenceLiveSample")}
        </Badge>{" "}
        {copy(run.recorded ? "evidenceRecordedHint" : "evidenceLiveSampleHint")}
      </p>
      {text.reviewOutcome ? (
        <p className="evidence__note">
          <strong>{copy("evidenceReviewOutcome")}</strong>: {text.reviewOutcome}
        </p>
      ) : null}
      {unresolved !== null ? (
        <p className="evidence__note">
          <strong>{copy("evidenceUnresolvedFindings")}</strong>: {unresolved}
        </p>
      ) : null}
      <details className="evidence__collapsible">
        <summary className="evidence__block-title">{copy("evidenceSampleDetails")}</summary>
        {text.note ? <p className="evidence__note">{text.note}</p> : null}
        <p className="evidence__note">
          {copy("evidenceScenario")}: <strong>{sample.scenario}</strong>
          {text.scenarioDescription ? ` — ${text.scenarioDescription}` : null}
        </p>
        <h4 className="evidence__block-title">{copy("evidenceScenarioChanges")}</h4>
        {sample.changes.length === 0 ? (
          <p className="evidence__note">{copy("evidenceNoScenarioChanges")}</p>
        ) : (
          <ul className="evidence__changes">
            {sample.changes.map((change, i) => (
              <li key={`${change.table}-${change.column}-${i}`}>
                <span className="evidence__claim-id">
                  {change.table} [
                  {Object.entries(change.match)
                    .map(([k, v]) => `${k}=${String(v)}`)
                    .join(", ")}
                  ] {change.column}
                </span>{" "}
                {formatValue(change.before)} → {formatValue(change.after)} —{" "}
                {text.changeReasons[i] || change.reason}
              </li>
            ))}
          </ul>
        )}
        {text.knownLimitations.length > 0 ? (
          <>
            <h4 className="evidence__block-title">{copy("evidenceKnownLimitations")}</h4>
            <ul className="evidence__changes">
              {text.knownLimitations.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </>
        ) : null}
        {text.comparisonNote ? (
          <>
            <h4 className="evidence__block-title">{copy("evidenceComparisonNote")}</h4>
            <p className="evidence__note">{text.comparisonNote}</p>
          </>
        ) : null}
      </details>
    </div>
  );
}

export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={`evidence__badge evidence__badge--${tone}`}>{children}</span>;
}

/** Code-judged SQL checks: matched / mismatched / unverifiable (never folded into mismatched). */
export function CheckTallyLine({ tally }: { tally: CheckTally }) {
  const { copy } = useLanguage();
  return (
    <p className="evidence__counts evidence__check-tally">
      <strong>{copy("checksTitle")}</strong>
      <span>
        <Badge tone="up">{copy("checksMatched")}</Badge> {tally.matched}
      </span>
      <span>
        <Badge tone={tally.mismatched > 0 ? "down" : "muted"}>{copy("checksMismatched")}</Badge>{" "}
        {tally.mismatched}
      </span>
      <span>
        <Badge tone="muted">{copy("checksUnverifiable")}</Badge> {tally.unverifiable}
      </span>
    </p>
  );
}

function claimBadge(
  claim: Claim,
  review: CriticReview | null,
  copy: (key: CopyKey) => string,
): { tone: Tone; label: string } {
  const flagged = review?.findings.some((f) => f.claimId === claim.id) ?? false;
  if (claim.kind === "hypothesis") {
    if (claim.testPlan) {
      const plan = claim.testPlan;
      return {
        tone: flagged ? "down" : "up",
        label: `${copy("evidenceBadgeTestPlan")}: ${plan.metric} / ${plan.durationDays} ${copy("evidenceDays")}`,
      };
    }
    return { tone: "down", label: copy("evidenceBadgeNoTestPlan") };
  }
  if (flagged) {
    return { tone: "down", label: copy("evidenceBadgeFlagged") };
  }
  if (claim.kind === "observation") {
    const first = claim.evidence[0];
    return {
      tone: "muted",
      label: first ? `${first.source} · ${first.asOf}` : copy("evidenceBadgeUnchecked"),
    };
  }
  if (!review) {
    return { tone: "muted", label: copy("evidenceBadgeNotReviewed") };
  }
  const checks = review.checks.filter((c) => c.claimId === claim.id);
  if (checks.length > 0 && checks.every((c) => c.matched)) {
    return { tone: "up", label: copy("evidenceBadgeVerified") };
  }
  return { tone: "muted", label: copy("evidenceBadgeUnchecked") };
}

export function Stepper({
  run,
  selected,
  onSelect,
}: {
  run: EvidenceRun;
  selected: string | null;
  onSelect: (version: string) => void;
}) {
  const { copy } = useLanguage();
  const last = run.steps[run.steps.length - 1];
  const pendingLabel =
    run.status !== "running"
      ? null
      : !last
        ? "v1"
        : last.critic
          ? `v${run.steps.length + 1}`
          : copy("evidenceCritic");

  return (
    <ol className="evidence__stepper">
      {run.steps.map((step, index) => {
        const round = run.steps.slice(0, index + 1).filter((s) => s.critic).length;
        const findings = step.critic?.findings.length ?? 0;
        return [
          <li key={step.version}>
            <button
              type="button"
              className={
                selected === step.version
                  ? "evidence__step evidence__step--active"
                  : "evidence__step"
              }
              onClick={() => onSelect(step.version)}
              aria-pressed={selected === step.version}
            >
              <span className="evidence__step-version">{step.version}</span>
              <span className="evidence__step-label">{copy(STAGE_COPY[step.stage])}</span>
            </button>
          </li>,
          step.critic ? (
            <li key={`${step.version}-critic`}>
              <button
                type="button"
                className={
                  findings > 0
                    ? "evidence__step evidence__step--critic evidence__step--flagged"
                    : "evidence__step evidence__step--critic"
                }
                onClick={() => onSelect(step.version)}
              >
                <span className="evidence__step-version">
                  {copy("evidenceCritic")} {round}
                </span>
                <span className="evidence__step-label">
                  {findings > 0
                    ? `${copy("evidenceFindingsCount")} ${findings}`
                    : copy("evidenceNoFindings")}
                </span>
              </button>
            </li>
          ) : null,
        ];
      })}
      {pendingLabel ? (
        <li>
          <span className="evidence__step evidence__step--pending">
            <span className="evidence__step-version">{pendingLabel}</span>
            <span className="evidence__step-label">{copy("evidencePending")}</span>
          </span>
        </li>
      ) : null}
    </ol>
  );
}

function SqlBlock({ sql }: { sql: string }) {
  if (!sql) {
    return null;
  }
  return <pre className="evidence__sql">{sql}</pre>;
}

export function ClaimList({
  step,
  showSql,
}: {
  step: RevisionStep;
  showSql: boolean;
}) {
  const { copy } = useLanguage();
  return (
    <ul className="evidence__claims">
      {step.output.claims.map((claim) => {
        const badge = claimBadge(claim, step.critic, copy);
        return (
          <li key={claim.id} className="evidence__claim">
            <div className="evidence__claim-head">
              <span className="evidence__claim-id">{claim.id}</span>
              <Badge tone="muted">{copy(KIND_COPY[claim.kind])}</Badge>
              <Badge tone={badge.tone}>{badge.label}</Badge>
            </div>
            <p className="evidence__claim-text">{claim.text}</p>
            {claim.evidence.length > 0 ? (
              <ul className="evidence__evidence">
                {claim.evidence.map((item, index) => (
                  <li key={`${claim.id}-${index}`}>
                    <span className="evidence__evidence-meta">
                      {item.table} · {formatValue(item.value)} · {item.asOf}
                      {item.scope ? ` · ${item.scope}` : ""}
                    </span>
                    {showSql ? <SqlBlock sql={item.sql} /> : null}
                  </li>
                ))}
              </ul>
            ) : null}
            {claim.testPlan ? (
              <p className="evidence__note">
                {claim.testPlan.method} — {claim.testPlan.successCriterion}
              </p>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

function ReviewView({
  review,
  responses,
  showSql,
}: {
  review: CriticReview;
  responses: Map<string, FindingResponse>;
  showSql: boolean;
}) {
  const { copy } = useLanguage();
  const counts = new Map<CriticFinding["resolution"], number>();
  for (const finding of review.findings) {
    counts.set(finding.resolution, (counts.get(finding.resolution) ?? 0) + 1);
  }

  return (
    <div className="evidence__block">
      <h4 className="evidence__block-title">{copy("evidenceReview")}</h4>
      <CheckTallyLine tally={tallyChecks(review.checks)} />
      <p className="evidence__note">{copy("checksAuthority")}</p>
      <p className="evidence__note">{copy("reviewTerms")}</p>
      <p className="evidence__counts">
        {(["resolved", "downgraded", "open", "unresolved"] as const).map((resolution) =>
          counts.get(resolution) ? (
            <span key={resolution}>
              {copy(RESOLUTION_COPY[resolution])}: {counts.get(resolution)}
            </span>
          ) : null,
        )}
      </p>
      <div className="evidence__comment">
        <p className="evidence__comment-label">{copy("criticComment")}</p>
        <p className="evidence__note">{review.summary}</p>
      </div>
      {review.findings.length > 0 ? (
        <ul className="evidence__findings">
          {review.findings.map((finding) => {
            const answer = responses.get(finding.id);
            const tone: Tone =
              finding.resolution === "resolved" || finding.resolution === "downgraded"
                ? "up"
                : finding.resolution === "unresolved"
                  ? "down"
                  : "muted";
            return (
              <li key={finding.id} className="evidence__finding">
                <div className="evidence__claim-head">
                  <Badge tone={tone}>{copy(RESOLUTION_COPY[finding.resolution])}</Badge>
                  <span className="evidence__finding-kind">
                    {copy(FINDING_COPY[finding.kind])}
                  </span>
                  <span className="evidence__claim-id">{finding.claimId}</span>
                  <span className="evidence__finding-origin">
                    {copy(
                      finding.origin === "code" ? "evidenceOriginCode" : "evidenceOriginCritic",
                    )}
                  </span>
                </div>
                <p className="evidence__claim-text">{finding.message}</p>
                {finding.kind === "value_mismatch" ? (
                  <dl className="evidence__values">
                    <div>
                      <dt>{copy("evidenceClaimed")}</dt>
                      <dd>{formatValue(finding.claimedValue)}</dd>
                    </div>
                    <div>
                      <dt>{copy("evidenceCriticValue")}</dt>
                      <dd>{formatValue(finding.criticValue)}</dd>
                    </div>
                  </dl>
                ) : null}
                {showSql ? (
                  <>
                    <SqlBlock sql={finding.criticSql} />
                    <SqlBlock sql={finding.analystSql} />
                  </>
                ) : null}
                {answer ? (
                  <p className="evidence__note">
                    {copy("evidenceAnalystAnswer")}: {copy(RESPONSE_COPY[answer.response])}
                    {answer.note ? ` — ${answer.note}` : ""}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

export function StepView({
  step,
  previous,
  next,
  showSql,
  adoptRunId,
}: {
  step: RevisionStep;
  previous: RevisionStep | null;
  next: RevisionStep | null;
  showSql: boolean;
  /** Set on the final version of a finished run: its actions can be adopted. */
  adoptRunId: string | null;
}) {
  const { copy } = useLanguage();
  const top = step.output.actions[0]?.title ?? null;
  const previousTop = previous?.output.actions[0]?.title ?? null;
  const responses = new Map(
    (next?.output.findingResponses ?? []).map((r) => [r.findingId, r]),
  );

  return (
    <div className="evidence__detail">
      <div className="evidence__block">
        <h4 className="evidence__block-title">{copy("evidenceMostImportant")}</h4>
        <p className="evidence__finding-text">{step.output.mostImportantFinding}</p>
      </div>

      <div className="evidence__block">
        <h4 className="evidence__block-title">{copy("evidenceActions")}</h4>
        {step.output.actions.length === 0 ? (
          <p className="evidence__note">{copy("evidenceNoActions")}</p>
        ) : (
          <ol className="evidence__actions">
            {step.output.actions.map((action) => (
              <li key={action.rank}>
                <span className="evidence__action-rank">{action.rank}</span>
                <div>
                  <p className="evidence__action-title">{action.title}</p>
                  <p className="evidence__note">{action.reason}</p>
                  {action.claimIds.length > 0 ? (
                    <p className="evidence__claim-refs">{action.claimIds.join(" · ")}</p>
                  ) : null}
                  {adoptRunId ? (
                    <AdoptActionButton
                      key={`${adoptRunId}:${action.rank}`}
                      runId={adoptRunId}
                      rank={action.rank}
                      hasTestPlan={step.output.claims.some(
                        (c) => action.claimIds.includes(c.id) && c.testPlan !== null,
                      )}
                    />
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>

      {previous ? (
        <div className="evidence__block">
          <h4 className="evidence__block-title">{copy("evidenceChanges")}</h4>
          <p className="evidence__note">
            {top === previousTop
              ? copy("evidenceTopSame")
              : `${copy("evidenceTopChanged")} ${previousTop ?? copy("evidenceNoActions")}`}
          </p>
          {step.output.actionChanges.length > 0 ? (
            <ul className="evidence__changes">
              {step.output.actionChanges.map((change) => (
                <li key={change.previousRank}>
                  <Badge tone={change.decision === "removed" ? "down" : "muted"}>
                    #{change.previousRank} {copy(DECISION_COPY[change.decision])}
                  </Badge>{" "}
                  {change.reason}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      <details className="evidence__block evidence__collapsible">
        <summary className="evidence__block-title">
          {copy("evidenceClaims")}{" "}
          <span className="evidence__summary-counts">
            {(["fact", "observation", "hypothesis"] as const)
              .map(
                (kind) =>
                  `${copy(KIND_COPY[kind])} ${step.output.claims.filter((c) => c.kind === kind).length}`,
              )
              .join(" · ")}
            {" · "}
            {copy("evidenceBadgeVerified")}{" "}
            {
              step.output.claims.filter(
                (c) => claimBadge(c, step.critic, copy).label === copy("evidenceBadgeVerified"),
              ).length
            }
          </span>
        </summary>
        <ClaimList step={step} showSql={showSql} />
      </details>

      {step.critic ? (
        <ReviewView review={step.critic} responses={responses} showSql={showSql} />
      ) : null}
    </div>
  );
}

/** Revision history of the evidence loop (v1 → v2 → Critic → v3) for one product. */
export function EvidencePanel({ productId }: { productId: string }) {
  const { copy, language } = useLanguage();
  const [runs, setRuns] = useState<EvidenceRunSummary[] | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [listNonce, setListNonce] = useState(0);
  const [listError, setListError] = useState<CopyKey | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [run, setRun] = useState<EvidenceRun | null>(null);
  const [runError, setRunError] = useState<CopyKey | null>(null);
  const [pinnedVersion, setPinnedVersion] = useState<string | null>(null);
  const [showSql, setShowSql] = useState(false);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<CopyKey | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    listEvidenceRuns(productId, controller.signal)
      .then((list) => {
        // Real-app history only: fictional runs share the product id but live in Sample Workspace and /demo.
        const real = list.runs.filter((summary) => !isFictionalRun(summary));
        setRuns(real);
        setActiveRunId(list.activeRunId);
        setListError(null);
        setSelectedRunId((current) => current ?? real[0]?.runId ?? null);
      })
      .catch((err: unknown) => {
        if (!isAbort(err)) {
          setListError(errorCopy(err));
        }
      });
    return () => controller.abort();
  }, [productId, listNonce]);

  useEffect(() => {
    if (!selectedRunId) {
      return;
    }
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let sawRunning = false;

    async function load(runId: string) {
      try {
        const next = await getEvidenceRun(runId, controller.signal);
        setRun(next);
        setRunError(null);
        if (next.status === "running") {
          sawRunning = true;
          timer = setTimeout(() => void load(runId), POLL_MS);
        } else if (sawRunning) {
          setListNonce((n) => n + 1);
        }
      } catch (err) {
        if (isAbort(err)) {
          return;
        }
        if (err instanceof EvidenceRequestError && err.code === "run_unreadable") {
          timer = setTimeout(() => void load(runId), POLL_MS);
          return;
        }
        setRunError(errorCopy(err));
      }
    }

    void load(selectedRunId);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [selectedRunId]);

  function selectRun(runId: string) {
    setRun(null);
    setRunError(null);
    setPinnedVersion(null);
    setSelectedRunId(runId);
  }

  async function handleStart() {
    if (!window.confirm(copy("evidenceStartConfirm"))) {
      return;
    }
    setStarting(true);
    setStartError(null);
    try {
      const runId = await startEvidenceRun(productId, language);
      setActiveRunId(runId);
      selectRun(runId);
      setListNonce((n) => n + 1);
    } catch (err) {
      setStartError(
        err instanceof EvidenceRequestError && err.code === "run_in_progress"
          ? "evidenceBusy"
          : err instanceof EvidenceRequestError && err.code === "api_unreachable"
            ? "evidenceApiUnreachable"
            : "evidenceStartError",
      );
    } finally {
      setStarting(false);
    }
  }

  const shownRun = run && run.runId === selectedRunId ? run : null;
  const steps = shownRun?.steps ?? [];
  const selectedIndex = (() => {
    const pinned = steps.findIndex((s) => s.version === pinnedVersion);
    return pinned >= 0 ? pinned : steps.length - 1;
  })();
  const selectedStep = selectedIndex >= 0 ? steps[selectedIndex] : null;
  const runOptions =
    runs && selectedRunId && !runs.some((r) => r.runId === selectedRunId) && shownRun
      ? [
          {
            runId: shownRun.runId,
            startedAt: shownRun.startedAt,
            status: shownRun.status,
            versions: shownRun.steps.map((s) => s.version),
            sample: shownRun.sample,
            recorded: shownRun.recorded,
          } as EvidenceRunSummary,
          ...runs,
        ]
      : (runs ?? []);
  const duration = shownRun ? minutesBetween(shownRun.startedAt, shownRun.finishedAt) : null;

  return (
    <section className="evidence" aria-labelledby="evidence-heading">
      <header className="evidence__header">
        <p className="evidence__eyebrow">{copy("evidenceEyebrow")}</p>
        <h2 id="evidence-heading" className="evidence__heading">
          {copy("evidenceTitle")}
        </h2>
        <p className="evidence__hint">{copy("evidenceHint")}</p>
      </header>

      <div className="evidence__controls">
        {runOptions.length > 0 ? (
          <label className="evidence__select-label">
            <span>{copy("evidenceRun")}</span>
            <select
              className="evidence__select"
              value={selectedRunId ?? ""}
              onChange={(event) => selectRun(event.target.value)}
            >
              {runOptions.map((option) => (
                <option key={option.runId} value={option.runId}>
                  {runOptionLabel(option, language, copy)}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <button
          type="button"
          className="experiments__draft-btn"
          onClick={handleStart}
          disabled={starting || Boolean(activeRunId) || listError === "evidenceApiUnreachable"}
        >
          {starting ? copy("evidenceStarting") : copy("evidenceStart")}
        </button>
        {shownRun && shownRun.steps.length > 0 ? (
          <button
            type="button"
            className="experiments__draft-btn experiments__draft-btn--ghost"
            onClick={() => setShowSql((v) => !v)}
            aria-pressed={showSql}
          >
            {showSql ? copy("evidenceHideSql") : copy("evidenceShowSql")}
          </button>
        ) : null}
      </div>

      {startError ? (
        <p className="experiments__error" role="alert">
          {copy(startError)}
        </p>
      ) : null}
      {listError ? <p className="experiments__error">{copy(listError)}</p> : null}
      {runs && runs.length === 0 && !selectedRunId ? (
        <p className="experiments__empty">{copy("evidenceNoRuns")}</p>
      ) : null}
      {runError ? <p className="experiments__error">{copy(runError)}</p> : null}
      {selectedRunId && !shownRun && !runError ? (
        <p className="experiments__empty">{copy("evidenceLoading")}</p>
      ) : null}

      {shownRun ? (
        <>
          <dl className="evidence__meta">
            <div>
              <dt>{copy("evidenceStatus")}</dt>
              <dd>
                <Badge
                  tone={
                    shownRun.status === "converged"
                      ? "up"
                      : shownRun.status === "error"
                        ? "down"
                        : "muted"
                  }
                >
                  {copy(STATUS_COPY[shownRun.status])}
                </Badge>
                {duration ? ` ${duration}` : ""}
                {outcomeCounts(runOutcome(shownRun), copy)
                  .map((part) => ` · ${part}`)
                  .join("")}
              </dd>
            </div>
            {shownRun.model ? (
              <div>
                <dt>{copy("evidenceModel")}</dt>
                <dd>{shownRun.model}</dd>
              </div>
            ) : null}
            {shownRun.currentPeriod && shownRun.previousPeriod ? (
              <div>
                <dt>{copy("evidencePeriod")}</dt>
                <dd>
                  {shownRun.currentPeriod.join("–")} vs {shownRun.previousPeriod.join("–")}
                </dd>
              </div>
            ) : null}
            <div>
              <dt>{copy("evidencePastDecisions")}</dt>
              <dd>{shownRun.pastDecisionIds.length}</dd>
            </div>
            {shownRun.rejectedAttempts.length > 0 ? (
              <div>
                <dt>{copy("evidenceRejected")}</dt>
                <dd>
                  {shownRun.rejectedAttempts
                    .map((a) => `${a.version}#${a.attempt}: ${a.reason}`)
                    .join(" / ")}
                </dd>
              </div>
            ) : null}
          </dl>

          <SampleBanner run={shownRun} />

          {shownRun.status === "running" ? (
            <p className="experiments__status">{copy("evidenceRunningHint")}</p>
          ) : null}
          {shownRun.error ? (
            <p className="experiments__error" role="alert">
              {shownRun.error}
            </p>
          ) : null}

          <Stepper
            run={shownRun}
            selected={selectedStep?.version ?? null}
            onSelect={setPinnedVersion}
          />

          {steps.length > 1 ? (
            <div className="evidence__trail">
              <h4 className="evidence__block-title">{copy("evidenceTopActionTrail")}</h4>
              <ol>
                {steps.map((step) => (
                  <li key={step.version}>
                    <span className="evidence__claim-id">{step.version}</span>{" "}
                    {step.output.actions[0]?.title ?? copy("evidenceNoActions")}
                  </li>
                ))}
              </ol>
            </div>
          ) : null}

          {selectedStep ? (
            <StepView
              step={selectedStep}
              previous={selectedIndex > 0 ? steps[selectedIndex - 1] : null}
              next={steps[selectedIndex + 1] ?? null}
              showSql={showSql}
              adoptRunId={
                !shownRun.sample &&
                (shownRun.status === "converged" || shownRun.status === "max_rounds") &&
                selectedIndex === steps.length - 1
                  ? shownRun.runId
                  : null
              }
            />
          ) : null}
        </>
      ) : null}
    </section>
  );
}
