"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  EvidenceRequestError,
  getEvidenceRun,
  listEvidenceRuns,
  type EvidenceRun,
  type EvidenceRunSummary,
} from "@/lib/evidence-client";
import type { CopyKey } from "@/lib/i18n";
import { useLanguage } from "@/lib/language-context";
import {
  buildDemoStory,
  languageName,
  pickRecordedDemo,
  outcomeCounts,
  recordedDemosByScenario,
  reviewNoteText,
  stageSuffix,
  versionLabel,
  type DemoCriticRound,
  type DemoStory,
} from "@/lib/recorded-demo";
import { DASHBOARD_PATH } from "@/lib/routes";
import { hasGloss, sampleAppName } from "@/lib/sample-glossary";
import { sampleText } from "@/lib/sample-text";
import { snapshotMatchesRun, type SampleSnapshot } from "@/lib/sample-workspace";
import {
  Badge,
  CheckTallyLine,
  ClaimList,
  DECISION_COPY,
  FINDING_COPY,
  RESOLUTION_COPY,
  RESPONSE_COPY,
  STATUS_COPY,
  SampleBanner,
  StepView,
  Stepper,
  type Tone,
} from "./EvidencePanel";
import { ActionDetails } from "./ActionDetails";
import { GlossedText } from "./GlossedText";
import { LanguageSelector } from "./LanguageSelector";
import { SampleSnapshotSection } from "./SampleSnapshot";

/** API's max list size, so committed Recorded Demos are not pushed out by newer runs. */
const RUN_LIST_LIMIT = 100;

/** The fictional sample's two-week snapshot and the digests of the CSVs it was computed from. */
export interface SnapshotData {
  snapshot: SampleSnapshot;
  csvSha256: Record<string, string>;
}

function loadErrorCopy(err: unknown): CopyKey {
  return err instanceof EvidenceRequestError && err.code === "api_unreachable"
    ? "evidenceApiUnreachable"
    : "evidenceLoadError";
}

function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

function resolutionTone(resolution: DemoCriticRound["findings"][number]["resolution"]): Tone {
  if (resolution === "resolved" || resolution === "downgraded") {
    return "up";
  }
  return resolution === "unresolved" ? "down" : "muted";
}

function ProposalsSection({ story }: { story: DemoStory }) {
  const { copy, language } = useLanguage();
  const finalIndex = story.versions.length - 1;
  const finalVersion = story.versions[finalIndex];
  const glossed = hasGloss(
    [
      ...story.versions.flatMap((version) => [
        ...version.actions.map((action) => action.title),
        ...version.changes.map((change) => change.reason),
      ]),
      ...(finalVersion?.actions ?? []).flatMap((action) => [
        action.reason,
        ...(finalVersion.citedByRank[action.rank] ?? []).map((claim) => claim.text),
      ]),
    ],
    language,
  );

  return (
    <section className="demo-section" aria-labelledby="demo-proposals">
      <h2 id="demo-proposals" className="demo-section__title">
        {copy("demoProposalsTitle")}
      </h2>
      <p className="demo-section__hint">{copy("demoProposalsHint")}</p>
      {glossed ? <p className="demo-section__hint">{copy("glossLegend")}</p> : null}
      <ol className="demo-versions">
        {story.versions.map((version, index) => {
          const final = index === finalIndex;
          return (
            <li
              key={version.version}
              className={final ? "demo-version demo-version--final" : "demo-version"}
            >
              <p className="demo-version__label">
                <span className="demo-version__id">{version.version}</span>
                {stageSuffix(version.stage, copy)}
                {final ? <Badge tone="up">{copy("demoFinal")}</Badge> : null}
              </p>
              <ol className="demo-version__actions">
                {version.actions.map((action) => (
                  <li key={action.rank}>
                    <span className="demo-rank">{action.rank}</span>
                    <div>
                      <p className="demo-version__action-title">
                        <GlossedText text={action.title} />
                      </p>
                      {final && (version.notesByRank[action.rank] ?? []).length > 0 ? (
                        <a href={`#final-action-${action.rank}`} className="demo-version__note-link">
                          {copy("demoHasKnownLimitation")}
                        </a>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ol>
              {version.changes.length > 0 ? (
                <details className="demo-version__changes">
                  <summary>{copy("demoChangeReasons")}</summary>
                  <ul>
                    {version.changes.map((change) => (
                      <li key={change.previousRank}>
                        <Badge tone={change.decision === "removed" ? "down" : "muted"}>
                          #{change.previousRank} {copy(DECISION_COPY[change.decision])}
                        </Badge>{" "}
                        <GlossedText text={change.reason} />
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/** The final version's Top 3 at full width: reason, cited claims, then known limitations. */
function FinalActionsSection({ story }: { story: DemoStory }) {
  const { copy } = useLanguage();
  const final = story.versions.at(-1);
  if (!final || final.actions.length === 0) {
    return null;
  }
  return (
    <section className="demo-section" aria-labelledby="demo-final">
      <h2 id="demo-final" className="demo-section__title">
        {copy("demoFinalActionsTitle")} — {final.version}
      </h2>
      <p className="demo-section__hint">
        {versionLabel(final.version, final.stage, copy)} · {copy("demoFinalActionsHint")}
      </p>
      <ol className="demo-final">
        {final.actions.slice(0, 3).map((action) => (
          <li key={action.rank} id={`final-action-${action.rank}`} className="demo-final__item">
            <span className="demo-rank">{action.rank}</span>
            <div className="demo-final__body">
              <h3 className="demo-final__title">
                <GlossedText text={action.title} />
              </h3>
              <p className="demo-final__reason">
                <GlossedText text={action.reason} />
              </p>
              <ActionDetails
                claims={final.citedByRank[action.rank] ?? []}
                notes={final.notesByRank[action.rank] ?? []}
              />
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function CriticSection({ run, story }: { run: EvidenceRun; story: DemoStory }) {
  const { copy, language } = useLanguage();
  const text = run.sample ? sampleText(run.sample, language) : null;

  return (
    <section className="demo-section" aria-labelledby="demo-critic">
      <h2 id="demo-critic" className="demo-section__title">
        {copy("demoCriticTitle")}
      </h2>
      <p className="demo-section__hint">{copy("demoCriticHint")}</p>

      {story.rounds.map((round) => (
        <article key={round.round} className="demo-round">
          <header className="demo-round__header">
            <h3 className="demo-round__title">
              {copy("evidenceCritic")} {round.round}
            </h3>
            <span className="demo-round__meta">
              {copy("demoReviewed")}: {versionLabel(round.reviewedVersion, round.reviewedStage, copy)}
            </span>
          </header>
          <CheckTallyLine tally={round.checks} />
          {round.findings.length === 0 ? (
            <p className="evidence__note">{copy("evidenceNoFindings")}</p>
          ) : (
            <ul className="demo-findings">
              {round.findings.map((finding) => (
                <li key={finding.id} className="demo-finding">
                  <p className="demo-finding__head">
                    <Badge tone={resolutionTone(finding.resolution)}>
                      {copy(RESOLUTION_COPY[finding.resolution])}
                    </Badge>
                    <span className="demo-finding__kind">
                      {finding.reviewNotes.length > 0
                        ? `${copy("demoRecordedClassification")}: `
                        : null}
                      {copy(FINDING_COPY[finding.kind])}
                    </span>
                  </p>
                  <p className="demo-finding__message">
                    <GlossedText text={finding.message} />
                  </p>
                  {finding.reviewNotes.map((note, i) => (
                    <p key={i} className="demo-finding__known" role="note">
                      <strong>{copy("demoKnownMisjudgment")}:</strong>{" "}
                      {reviewNoteText(note, language)}
                    </p>
                  ))}
                  <p className="demo-finding__answer">
                    {finding.answer ? (
                      <>
                        <strong>
                          {copy("evidenceAnalystAnswer")} ({round.answeredIn}):{" "}
                          {copy(RESPONSE_COPY[finding.answer.response])}
                        </strong>
                        {finding.answer.note ? (
                          <>
                            {" — "}
                            <GlossedText text={finding.answer.note} />
                          </>
                        ) : (
                          ""
                        )}
                      </>
                    ) : round.answeredIn ? null : (
                      copy("demoNoAnswer")
                    )}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </article>
      ))}

      <div className="demo-outcome" role="note">
        <h3 className="demo-round__title">{copy("demoOutcomeTitle")}</h3>
        <p className="demo-finding__head">
          <Badge tone={run.status === "converged" ? "up" : "muted"}>
            {copy(STATUS_COPY[run.status])}
          </Badge>{" "}
          <span>
            {outcomeCounts(story.outcome, copy)
              .map((part) => `· ${part}`)
              .join(" ")}
          </span>
        </p>
        <p className="evidence__note">{copy("checksAuthority")}</p>
        <p className="evidence__note">{copy("reviewTerms")}</p>
        <p className="evidence__note">{copy("recordedChecksNote")}</p>
        {text?.reviewOutcome ? <p className="evidence__note">{text.reviewOutcome}</p> : null}
        {text && text.knownLimitations.length > 0 ? (
          <details className="demo-version__changes">
            <summary>
              {copy("evidenceKnownLimitations")} ({text.knownLimitations.length})
            </summary>
            <ul>
              {text.knownLimitations.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </details>
        ) : null}
      </div>
    </section>
  );
}

function DemoRunView({ run, snapshotData }: { run: EvidenceRun; snapshotData: SnapshotData | null }) {
  const { copy, language } = useLanguage();
  const story = useMemo(() => buildDemoStory(run), [run]);
  const snapshot =
    snapshotData && snapshotMatchesRun(snapshotData.snapshot, snapshotData.csvSha256, run)
      ? snapshotData.snapshot
      : null;
  const [pinnedVersion, setPinnedVersion] = useState<string | null>(null);
  const steps = run.steps;
  const pinned = steps.findIndex((step) => step.version === pinnedVersion);
  const selectedIndex = pinned >= 0 ? pinned : steps.length - 1;
  const selectedStep = steps[selectedIndex] ?? null;
  const finalStep = steps.at(-1) ?? null;
  const text = run.sample ? sampleText(run.sample, language) : null;
  const appName = run.sample ? sampleAppName(run.sample.app, language) : null;

  return (
    <>
      <section className="demo-context" aria-label={copy("evidenceSampleDetails")}>
        <dl className="evidence__meta">
          {run.sample ? (
            <div>
              <dt>{copy("targetApp")}</dt>
              <dd title={appName !== run.sample.app.name ? run.sample.app.name : undefined}>
                {appName}
              </dd>
            </div>
          ) : null}
          {run.sample ? (
            <div>
              <dt>{copy("evidenceScenario")}</dt>
              <dd>{run.sample.scenario}</dd>
            </div>
          ) : null}
          {run.currentPeriod && run.previousPeriod ? (
            <div>
              <dt>{copy("evidencePeriod")}</dt>
              <dd>
                {run.currentPeriod.join("–")} vs {run.previousPeriod.join("–")}
              </dd>
            </div>
          ) : null}
          <div>
            <dt>{copy("evidenceModel")}</dt>
            <dd>{run.model}</dd>
          </div>
        </dl>
        {text?.scenarioDescription ? (
          <p className="evidence__note">{text.scenarioDescription}</p>
        ) : null}
        {text?.note ? <p className="evidence__note">{text.note}</p> : null}
        {run.language !== language ? (
          <p className="sample-notice" role="note">
            {copy("demoModelLanguageNote").replace("{lang}", languageName(run.language, copy))}
          </p>
        ) : null}
      </section>

      {snapshot ? <SampleSnapshotSection snapshot={snapshot} /> : null}
      <ProposalsSection story={story} />
      <FinalActionsSection story={story} />
      <CriticSection run={run} story={story} />

      {finalStep ? (
        <details className="demo-section demo-collapsible">
          <summary>
            <span className="demo-section__title">{copy("demoSqlTitle")}</span>
            <span className="demo-section__hint">
              {copy("demoSqlHint")} ({finalStep.version})
            </span>
          </summary>
          <ClaimList step={finalStep} showSql />
        </details>
      ) : null}

      <details className="demo-section demo-collapsible">
        <summary>
          <span className="demo-section__title">{copy("demoLogTitle")}</span>
          <span className="demo-section__hint">{copy("demoLogHint")}</span>
        </summary>
        <SampleBanner run={run} />
        <Stepper run={run} selected={selectedStep?.version ?? null} onSelect={setPinnedVersion} />
        {selectedStep ? (
          <StepView
            step={selectedStep}
            previous={selectedIndex > 0 ? steps[selectedIndex - 1] : null}
            next={steps[selectedIndex + 1] ?? null}
            showSql={false}
            adoptRunId={null}
          />
        ) : null}
      </details>
    </>
  );
}

/** Standalone Recorded Demo: a committed run, read from /api/evidence. Nothing runs here. */
export function RecordedDemo({ snapshotData }: { snapshotData: SnapshotData | null }) {
  const { copy, language } = useLanguage();
  const [runs, setRuns] = useState<EvidenceRunSummary[] | null>(null);
  const [pickedScenario, setPickedScenario] = useState<string | null>(null);
  const [run, setRun] = useState<EvidenceRun | null>(null);
  const [error, setError] = useState<CopyKey | null>(null);
  const demos = useMemo(() => (runs ? recordedDemosByScenario(runs) : null), [runs]);
  const selectedRunId =
    demos?.find((demo) => (demo.sample?.scenario ?? demo.runId) === pickedScenario)?.runId ??
    pickRecordedDemo(runs ?? undefined)?.runId ??
    null;

  useEffect(() => {
    const controller = new AbortController();
    listEvidenceRuns(null, controller.signal, RUN_LIST_LIMIT)
      .then((list) => {
        setRuns(list.runs);
        setError(pickRecordedDemo(list.runs) ? null : "demoNotFound");
      })
      .catch((err: unknown) => {
        if (!isAbort(err)) {
          setError(loadErrorCopy(err));
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!selectedRunId) {
      return;
    }
    const controller = new AbortController();
    getEvidenceRun(selectedRunId, controller.signal)
      .then((next) => {
        setRun(next);
        setError(null);
      })
      .catch((err: unknown) => {
        if (!isAbort(err)) {
          setError(loadErrorCopy(err));
        }
      });
    return () => controller.abort();
  }, [selectedRunId]);

  const shownRun = run && run.runId === selectedRunId ? run : null;

  return (
    <div className="dashboard demo">
      <header className="site-header">
        <div className="site-header__brand">
          <div className="site-header__title-stack">
            <p className="site-header__title">Indie Growth Agent</p>
            <div className="site-header__by-row">
              <Image
                src="/makosoyo-mark.png"
                alt=""
                width={20}
                height={20}
                className="site-header__mark"
                priority
              />
              <p className="site-header__by">{copy("brandBy")}</p>
            </div>
          </div>
        </div>
        <div className="site-header__controls">
          <LanguageSelector />
          <Link href={DASHBOARD_PATH} className="analyze-btn portfolio__nav-link">
            {copy("portfolioBackToDashboard")}
          </Link>
        </div>
      </header>

      <section className="demo-hero" aria-labelledby="demo-title">
        <h1 id="demo-title" className="demo-hero__title">
          {copy("demoTitle")}
        </h1>
        <p className="demo-hero__lead">{copy("demoLead")}</p>
        <ul className="demo-hero__tags">
          <li>{copy("demoTagRecorded")}</li>
          <li>{copy("demoTagSynthetic")}</li>
          <li>{copy("demoTagRealModel")}</li>
        </ul>
        <p className="demo-hero__flow">{copy("demoFlow")}</p>
        <p className="demo-hero__note">{copy("demoNote")}</p>
        {demos && demos.length > 1 ? (
          <div className="demo-hero__scenarios" role="group" aria-label={copy("evidenceScenario")}>
            {demos.map((demo) => (
              <button
                key={demo.runId}
                type="button"
                className={
                  demo.runId === selectedRunId
                    ? "lang-selector__btn lang-selector__btn--active"
                    : "lang-selector__btn"
                }
                aria-pressed={demo.runId === selectedRunId}
                onClick={() => setPickedScenario(demo.sample?.scenario ?? demo.runId)}
              >
                {demo.sample?.scenario ?? demo.runId}
                {demo.language !== language
                  ? ` · ${copy("demoOutputLanguage").replace("{lang}", languageName(demo.language, copy))}`
                  : null}
              </button>
            ))}
          </div>
        ) : null}
      </section>

      {error ? (
        <p className="experiments__error" role="alert">
          {copy(error)}
        </p>
      ) : null}
      {!error && !shownRun ? <p className="panel-empty">{copy("evidenceLoading")}</p> : null}
      {shownRun ? (
        <DemoRunView key={shownRun.runId} run={shownRun} snapshotData={snapshotData} />
      ) : null}
    </div>
  );
}
