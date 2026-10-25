import type {
  ActionChange,
  CriticFinding,
  EvidenceRun,
  EvidenceRunSummary,
  FindingResponse,
  ProposedAction,
  RevisionStep,
  SampleInfo,
} from "./evidence-client";

export interface RecordedDemoTarget {
  productId: string;
  runId: string;
}

/** Committed Recorded Demos only (not Live Sample or live runs), in list order. */
export function recordedDemos(runs: EvidenceRunSummary[] | undefined): EvidenceRunSummary[] {
  return Array.isArray(runs)
    ? runs.filter((run) => run && run.recorded === true && run.sample)
    : [];
}

/** The Recorded Demo to open first: the base scenario if present, else the first one listed. */
export function pickRecordedDemo(
  runs: EvidenceRunSummary[] | undefined,
): RecordedDemoTarget | null {
  const recorded = recordedDemos(runs);
  const chosen =
    recorded.find((run) => run.sample?.scenario === "base") ?? recorded[0] ?? null;
  return chosen ? { productId: chosen.productId, runId: chosen.runId } : null;
}

export interface DemoVersion {
  version: string;
  stage: RevisionStep["stage"];
  actions: ProposedAction[];
  /** How this version treated the previous version's actions. */
  changes: ActionChange[];
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

/** The note in the UI language, falling back to the other one. */
export function reviewNoteText(note: ReviewNote, language: string): string {
  return (language === "en" ? (note.en ?? note.ja) : (note.ja ?? note.en)) ?? "";
}

export interface DemoCriticRound {
  round: number;
  reviewedVersion: string;
  answeredIn: string | null;
  summary: string;
  checksMatched: number;
  checksTotal: number;
  findings: DemoFinding[];
}

export interface DemoStory {
  versions: DemoVersion[];
  rounds: DemoCriticRound[];
  /** Findings of the last Critic round still unresolved when the run ended. */
  unresolved: number;
}

/** The run as "what was proposed → what the Critic questioned → how it was answered". */
export function buildDemoStory(run: EvidenceRun): DemoStory {
  const steps = Array.isArray(run.steps) ? run.steps : [];
  const versions = steps.map((step) => ({
    version: step.version,
    stage: step.stage,
    actions: [...step.output.actions].sort((a, b) => a.rank - b.rank),
    changes: step.output.actionChanges,
  }));

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
      answeredIn: next?.version ?? null,
      summary: step.critic.summary,
      checksMatched: step.critic.checks.filter((check) => check.matched).length,
      checksTotal: step.critic.checks.length,
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

  const last = rounds.at(-1);
  return {
    versions,
    rounds,
    unresolved: last
      ? last.findings.filter((finding) => finding.resolution === "unresolved").length
      : 0,
  };
}
