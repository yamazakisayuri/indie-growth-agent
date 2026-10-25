import type {
  ActionChange,
  CheckOutcome,
  Claim,
  CriticFinding,
  EvidenceRun,
  EvidenceRunSummary,
  FindingResponse,
  ProposedAction,
  RevisionStep,
  SampleInfo,
} from "./evidence-client";
import type { CopyKey } from "./i18n";

export interface RecordedDemoTarget {
  productId: string;
  runId: string;
}

/** sample_mode.RUN_PREFIX: Live Sample run ids. */
const SAMPLE_RUN_PREFIX = "sample-";

/** A run on fictional sample data (Recorded Demo or Live Sample), never real app data. */
export function isFictionalRun(
  run: Pick<EvidenceRunSummary, "runId" | "sample" | "recorded">,
): boolean {
  return Boolean(run.sample) || run.recorded === true || run.runId.startsWith(SAMPLE_RUN_PREFIX);
}

/** Committed Recorded Demos only (not Live Sample or live runs), in list order. */
export function recordedDemos(runs: EvidenceRunSummary[] | undefined): EvidenceRunSummary[] {
  return Array.isArray(runs)
    ? runs.filter((run) => run && run.recorded === true && run.sample)
    : [];
}

const STAGE_LABEL_COPY: Record<RevisionStep["stage"], CopyKey> = {
  internal: "evidenceStageInternal",
  competitive: "evidenceStageCompetitive",
  critic_revision: "evidenceStageRevision",
};

/** "— Own App Data": what follows the version id in a version label. */
export function stageSuffix(
  stage: RevisionStep["stage"] | null | undefined,
  copy: (key: CopyKey) => string,
): string {
  return stage ? `— ${copy(STAGE_LABEL_COPY[stage])}` : "";
}

/** "v1 — Own App Data": the version id as recorded, then its stage in the UI language. */
export function versionLabel(
  version: string,
  stage: RevisionStep["stage"] | null | undefined,
  copy: (key: CopyKey) => string,
): string {
  return stage ? `${version} ${stageSuffix(stage, copy)}` : version;
}

const LANGUAGE_NAME_COPY: Record<string, CopyKey> = {
  ja: "languageNameJa",
  en: "languageNameEn",
};

/** A run language by name in the UI language ("Japanese", "英語"); unknown codes as they are. */
export function languageName(code: string, copy: (key: CopyKey) => string): string {
  const key = LANGUAGE_NAME_COPY[code];
  return key ? copy(key) : code;
}

/** Marked in its .sample.json as the run to show for its scenario, whatever the UI language. */
export function isRepresentative(sample: Pick<SampleInfo, "representative"> | null | undefined): boolean {
  return sample?.representative === true;
}

/**
 * One Recorded Demo per scenario, in list order: the representative run if the scenario has
 * one, else its first one listed. The UI language does not change the choice.
 */
export function recordedDemosByScenario(
  runs: EvidenceRunSummary[] | undefined,
): EvidenceRunSummary[] {
  const byScenario = new Map<string, EvidenceRunSummary>();
  for (const run of recordedDemos(runs)) {
    const scenario = run.sample?.scenario ?? run.runId;
    const kept = byScenario.get(scenario);
    if (!kept || (!isRepresentative(kept.sample) && isRepresentative(run.sample))) {
      byScenario.set(scenario, run);
    }
  }
  return [...byScenario.values()];
}

/** The Recorded Demo to open first: the base scenario if present, else the first one listed. */
export function pickRecordedDemo(
  runs: EvidenceRunSummary[] | undefined,
): RecordedDemoTarget | null {
  const recorded = recordedDemosByScenario(runs);
  const chosen =
    recorded.find((run) => run.sample?.scenario === "base") ?? recorded[0] ?? null;
  return chosen ? { productId: chosen.productId, runId: chosen.runId } : null;
}

/**
 * A Critic SQL check as judged by code (evidence/critic.py), not by the model:
 * matched, mismatched (the SQL returned a different value), or unverifiable (the check
 * could not be compared, e.g. the SQL did not return exactly one value). Unverifiable is
 * not a mismatch.
 */
export type CheckVerdict = "matched" | "mismatched" | "unverifiable";

export function checkVerdict(check: Pick<CheckOutcome, "matched" | "error">): CheckVerdict {
  if (check.matched) {
    return "matched";
  }
  return typeof check.error === "string" && check.error.trim() ? "unverifiable" : "mismatched";
}

export interface CheckTally {
  matched: number;
  mismatched: number;
  unverifiable: number;
  total: number;
}

export function tallyChecks(
  checks: Pick<CheckOutcome, "matched" | "error">[] | null | undefined,
): CheckTally {
  const tally: CheckTally = { matched: 0, mismatched: 0, unverifiable: 0, total: 0 };
  for (const check of Array.isArray(checks) ? checks : []) {
    tally[checkVerdict(check)] += 1;
    tally.total += 1;
  }
  return tally;
}

export interface RunOutcome {
  status: EvidenceRun["status"];
  /** Unresolved findings of the last Critic round; converged means this is 0. */
  unresolved: number;
  /** SQL checks of the last Critic round, or null before the first review. */
  finalChecks: CheckTally | null;
}

export const RUN_STATUS_COPY: Record<EvidenceRun["status"], CopyKey> = {
  running: "evidenceStatusRunning",
  converged: "evidenceStatusConverged",
  max_rounds: "evidenceStatusMaxRounds",
  error: "evidenceStatusError",
};

function plural(copy: (key: CopyKey) => string, n: number, one: CopyKey, other: CopyKey): string {
  return copy(n === 1 ? one : other).replace("{n}", String(n));
}

/** "0 unresolved findings", then "1 unverifiable SQL check" only when there is one. */
export function outcomeCounts(outcome: RunOutcome, copy: (key: CopyKey) => string): string[] {
  if (outcome.status === "running" || !outcome.finalChecks) {
    return [];
  }
  const parts = [plural(copy, outcome.unresolved, "outcomeUnresolvedOne", "outcomeUnresolvedOther")];
  if (outcome.finalChecks.unverifiable > 0) {
    parts.push(
      plural(
        copy,
        outcome.finalChecks.unverifiable,
        "outcomeUnverifiableOne",
        "outcomeUnverifiableOther",
      ),
    );
  }
  return parts;
}

/** "Converged · 0 unresolved findings · 1 unverifiable SQL check". */
export function formatOutcome(outcome: RunOutcome, copy: (key: CopyKey) => string): string {
  return [copy(RUN_STATUS_COPY[outcome.status]), ...outcomeCounts(outcome, copy)].join(" · ");
}

/** For display only: the loop's own stop rule decides `status`. */
export function runOutcome(run: Pick<EvidenceRun, "status" | "steps">): RunOutcome {
  const steps = Array.isArray(run.steps) ? run.steps : [];
  const last = [...steps].reverse().find((step) => step.critic)?.critic ?? null;
  return {
    status: run.status,
    unresolved: last ? last.findings.filter((f) => f.resolution === "unresolved").length : 0,
    finalChecks: last ? tallyChecks(last.checks) : null,
  };
}

export interface DemoVersion {
  version: string;
  stage: RevisionStep["stage"];
  actions: ProposedAction[];
  /** How this version treated the previous version's actions. */
  changes: ActionChange[];
  /** Known limitations about an action of this version, by rank (see proposalNotesFor). */
  notesByRank: Record<number, ReviewNote[]>;
  /** The claims each action cites, by rank, as recorded in the same version. */
  citedByRank: Record<number, CitedClaim[]>;
}

/** A claim an action cites. kind and text are null if the version has no claim with that id. */
export interface CitedClaim {
  id: string;
  kind: Claim["kind"] | null;
  text: string | null;
}

export const CLAIM_KIND_COPY: Record<Claim["kind"], CopyKey> = {
  fact: "evidenceKindFact",
  observation: "evidenceKindObservation",
  hypothesis: "evidenceKindHypothesis",
};

export function citedClaims(
  action: Pick<ProposedAction, "claimIds">,
  claims: Pick<Claim, "id" | "kind" | "text">[] | null | undefined,
): CitedClaim[] {
  const byId = new Map((Array.isArray(claims) ? claims : []).map((claim) => [claim.id, claim]));
  return (Array.isArray(action.claimIds) ? action.claimIds : []).map((id) => {
    const claim = byId.get(id);
    return { id, kind: claim?.kind ?? null, text: claim?.text ?? null };
  });
}

export interface DemoFinding {
  id: string;
  kind: CriticFinding["kind"];
  claimId: string;
  message: string;
  resolution: CriticFinding["resolution"];
  /** The Analyst's answer in the next version, if there is one. */
  answer: FindingResponse | null;
  /** Known limitations that a reviewer wrote about this finding (see reviewNotesFor). */
  reviewNotes: ReviewNote[];
}

/** One known limitation, as written in the Recorded Demo metadata (Japanese original, English if given). */
export interface ReviewNote {
  ja: string | null;
  en: string | null;
}

function noteTexts(value: unknown): (string | null)[] {
  return Array.isArray(value)
    ? value.map((item) => (typeof item === "string" && item.trim() ? item.trim() : null))
    : [];
}

function mentions(text: string | null, token: string): boolean {
  if (!text) {
    return false;
  }
  const escaped = token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(?<![\\w-])${escaped}(?![\\w-])`).test(text);
}

/**
 * Known limitations about one finding: those that name both its id (e.g. r2-f1) and its
 * recorded kind (e.g. infeasible_action). Anything vaguer is left off the finding.
 */
export function reviewNotesFor(
  finding: Pick<CriticFinding, "id" | "kind">,
  sample: Pick<SampleInfo, "knownLimitations" | "en"> | null | undefined,
): ReviewNote[] {
  if (!sample) {
    return [];
  }
  const ja = noteTexts(sample.knownLimitations);
  const en = noteTexts(sample.en?.knownLimitations);
  const notes: ReviewNote[] = [];
  for (let i = 0; i < Math.max(ja.length, en.length); i += 1) {
    const about = [ja[i] ?? null, en[i] ?? null].some(
      (text) => mentions(text, finding.id) && mentions(text, finding.kind),
    );
    if (about) {
      notes.push({ ja: ja[i] ?? null, en: en[i] ?? null });
    }
  }
  return notes;
}

/**
 * Known limitations about one proposal: those that name both its version (e.g. v3) and
 * its rank as "action #N", "proposal #N", or "提案 #N". The proposal text stays as recorded.
 */
export function proposalNotesFor(
  version: string,
  rank: number,
  sample: Pick<SampleInfo, "knownLimitations" | "en"> | null | undefined,
): ReviewNote[] {
  if (!sample) {
    return [];
  }
  const action = new RegExp(`(?:action|proposal|提案)\\s*#\\s*${rank}(?!\\d)`, "i");
  const ja = noteTexts(sample.knownLimitations);
  const en = noteTexts(sample.en?.knownLimitations);
  const notes: ReviewNote[] = [];
  for (let i = 0; i < Math.max(ja.length, en.length); i += 1) {
    const about = [ja[i] ?? null, en[i] ?? null].some(
      (text) => text !== null && mentions(text, version) && action.test(text),
    );
    if (about) {
      notes.push({ ja: ja[i] ?? null, en: en[i] ?? null });
    }
  }
  return notes;
}

/** The note in the UI language, falling back to the other one. */
export function reviewNoteText(note: ReviewNote, language: string): string {
  return (language === "en" ? (note.en ?? note.ja) : (note.ja ?? note.en)) ?? "";
}

export interface DemoCriticRound {
  round: number;
  reviewedVersion: string;
  reviewedStage: RevisionStep["stage"];
  answeredIn: string | null;
  /** The Critic's own comment (model-generated), unchanged. */
  summary: string;
  checks: CheckTally;
  findings: DemoFinding[];
}

export interface DemoStory {
  versions: DemoVersion[];
  rounds: DemoCriticRound[];
  /** Findings of the last Critic round still unresolved when the run ended. */
  unresolved: number;
  outcome: RunOutcome;
}

/** The run as "what was proposed → what the Critic questioned → how it was answered". */
export function buildDemoStory(run: EvidenceRun): DemoStory {
  const steps = Array.isArray(run.steps) ? run.steps : [];
  const versions = steps.map((step) => {
    const actions = [...step.output.actions].sort((a, b) => a.rank - b.rank);
    return {
      version: step.version,
      stage: step.stage,
      actions,
      changes: step.output.actionChanges,
      notesByRank: Object.fromEntries(
        actions
          .map((action) => [action.rank, proposalNotesFor(step.version, action.rank, run.sample)] as const)
          .filter(([, notes]) => notes.length > 0),
      ),
      citedByRank: Object.fromEntries(
        actions.map((action) => [action.rank, citedClaims(action, step.output.claims)]),
      ),
    };
  });

  const rounds: DemoCriticRound[] = [];
  steps.forEach((step, index) => {
    if (!step.critic) {
      return;
    }
    const next = steps[index + 1] ?? null;
    const answers = new Map(
      (next?.output.findingResponses ?? []).map((response) => [response.findingId, response]),
    );
    rounds.push({
      round: rounds.length + 1,
      reviewedVersion: step.version,
      reviewedStage: step.stage,
      answeredIn: next?.version ?? null,
      summary: step.critic.summary,
      checks: tallyChecks(step.critic.checks),
      findings: step.critic.findings.map((finding) => ({
        id: finding.id,
        kind: finding.kind,
        claimId: finding.claimId,
        message: finding.message,
        resolution: finding.resolution,
        answer: answers.get(finding.id) ?? null,
        reviewNotes: reviewNotesFor(finding, run.sample),
      })),
    });
  });

  const outcome = runOutcome(run);
  return { versions, rounds, unresolved: outcome.unresolved, outcome };
}
