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
  pickRecordedDemo,
  recordedDemos,
  reviewNoteText,
  type DemoCriticRound,
  type DemoStory,
} from "@/lib/recorded-demo";
import { DASHBOARD_PATH } from "@/lib/routes";
import { sampleText } from "@/lib/sample-text";
import {
  Badge,
  ClaimList,
  DECISION_COPY,
  FINDING_COPY,
  RESOLUTION_COPY,
  RESPONSE_COPY,
  STAGE_COPY,
  STATUS_COPY,
  SampleBanner,
  StepView,
  Stepper,
  type Tone,
} from "./EvidencePanel";
import { LanguageSelector } from "./LanguageSelector";

/** API's max list size, so committed Recorded Demos are not pushed out by newer runs. */
const RUN_LIST_LIMIT = 100;

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
  const { copy } = useLanguage();
  const finalIndex = story.versions.length - 1;

  return (
    <section className="demo-section" aria-labelledby="demo-proposals">
      <h2 id="demo-proposals" className="demo-section__title">
        {copy("demoProposalsTitle")}
      </h2>
      <p className="demo-section__hint">{copy("demoProposalsHint")}</p>
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
                {copy(STAGE_COPY[version.stage])}
                {final ? <Badge tone="up">{copy("demoFinal")}</Badge> : null}
              </p>
              <ol className="demo-version__actions">
                {version.actions.map((action) => (
                  <li key={action.rank}>
                    <span className="demo-rank">{action.rank}</span>
                    <div>
                      <p className="demo-version__action-title">{action.title}</p>
                      {final ? (
                        <p className="demo-version__action-reason">{action.reason}</p>
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
                        {change.reason}
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
              {copy("demoReviewed")}: {round.reviewedVersion}
            </span>
            <span className="demo-round__meta">
              {copy("demoRecomputed")}:{" "}
              <strong>
                {round.checksMatched}/{round.checksTotal}
              </strong>{" "}
              {copy("demoMatched")}
            </span>
          </header>
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
                  <p className="demo-finding__message">{finding.message}</p>
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
                        {finding.answer.note ? ` — ${finding.answer.note}` : ""}
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
          </Badge>
          <span>
            {copy("evidenceUnresolvedFindings")}: <strong>{story.unresolved}</strong>
          </span>
        </p>
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

function DemoRunView({ run }: { run: EvidenceRun }) {
  const { copy, language } = useLanguage();
  const story = useMemo(() => buildDemoStory(run), [run]);
  const [pinnedVersion, setPinnedVersion] = useState<string | null>(null);
  const steps = run.steps;
  const pinned = steps.findIndex((step) => step.version === pinnedVersion);
  const selectedIndex = pinned >= 0 ? pinned : steps.length - 1;
  const selectedStep = steps[selectedIndex] ?? null;
  const finalStep = steps.at(-1) ?? null;
  const text = run.sample ? sampleText(run.sample, language) : null;

  return (
    <>
      <section className="demo-context" aria-label={copy("evidenceSampleDetails")}>
        <dl className="evidence__meta">
          {run.sample ? (
            <div>
              <dt>{copy("targetApp")}</dt>
              <dd>{run.sample.app.name}</dd>
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
          <p className="evidence__note">
            {copy("demoModelLanguageNote").replace("{lang}", run.language)}
          </p>
        ) : null}
      </section>

      <ProposalsSection story={story} />
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
export function RecordedDemo() {
  const { copy } = useLanguage();
  const [demos, setDemos] = useState<EvidenceRunSummary[] | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [run, setRun] = useState<EvidenceRun | null>(null);
  const [error, setError] = useState<CopyKey | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    listEvidenceRuns(null, controller.signal, RUN_LIST_LIMIT)
      .then((list) => {
        const target = pickRecordedDemo(list.runs);
        setDemos(recordedDemos(list.runs));
        setSelectedRunId(target?.runId ?? null);
        setError(target ? null : "demoNotFound");
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
                onClick={() => setSelectedRunId(demo.runId)}
              >
                {demo.sample?.scenario ?? demo.runId}
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
      {shownRun ? <DemoRunView key={shownRun.runId} run={shownRun} /> : null}
    </div>
  );
}
