"use client";

import { useEffect, useId, useRef, useState } from "react";
import {
  requestDraft,
  DraftRequestError,
  type UserScreenshotInput,
} from "@/lib/draft-client";
import { useLanguage } from "@/lib/language-context";
import { hasSuccessfulReport } from "@/lib/map-report";
import type {
  ActionDraft,
  GrowthExperiment,
  GrowthReport,
} from "@/lib/types";

const ACCEPTED_IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/jpg"]);

function isScreenshotExperiment(experiment: GrowthExperiment): boolean {
  const blob = [
    experiment.title,
    experiment.action,
    experiment.hypothesis,
    experiment.why,
    experiment.playbookReference,
  ]
    .join(" ")
    .toLowerCase();
  return (
    blob.includes("screenshot") ||
    blob.includes("スクリーンショット") ||
    blob.includes("スクショ") ||
    blob.includes("サムネ") ||
    blob.includes("visual asset")
  );
}

interface LocalShot {
  position: number;
  file: File;
  previewUrl: string;
}

type DraftSlot = {
  drafting: boolean;
  draft: ActionDraft | null;
  error: string | null;
};

function clearLocalShots(shots: LocalShot[]) {
  for (const shot of shots) {
    URL.revokeObjectURL(shot.previewUrl);
  }
}

async function fileToUserScreenshot(
  file: File,
  position: number,
): Promise<UserScreenshotInput> {
  const dataUrl = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error ?? new Error("read_failed"));
    reader.readAsDataURL(file);
  });
  return {
    position,
    fileName: file.name,
    mimeType: file.type || "image/png",
    dataBase64: dataUrl,
  };
}

function DraftField({
  label,
  value,
  emphasize = false,
}: {
  label: string;
  value: string;
  emphasize?: boolean;
}) {
  return (
    <div className="experiments__draft-row">
      <dt>{label}</dt>
      <dd className={emphasize ? "experiments__draft-copy" : undefined}>
        {value}
      </dd>
    </div>
  );
}

function ActionDraftView({ draft }: { draft: ActionDraft }) {
  const { copy } = useLanguage();
  return (
    <div className="experiments__draft">
      <h4 className="experiments__draft-heading">{copy("actionDraft")}</h4>
      {draft.noChangeRecommended ? (
        <p className="experiments__draft-flag">
          {copy("draftNoChangeRecommended")}
        </p>
      ) : null}

      <dl className="experiments__draft-summary">
        {draft.experimentTitle ? (
          <DraftField label={copy("experimentTitle")} value={draft.experimentTitle} />
        ) : null}
        <DraftField label={copy("draftType")} value={draft.draftType} />
        <DraftField label={copy("draftObjective")} value={draft.objective} />
        <DraftField label={copy("draftRationale")} value={draft.rationale} />
      </dl>

      {draft.screenshots?.length > 0 ? (
        <div className="experiments__draft-shots">
          {draft.screenshots.map((shot) => (
            <div
              key={`${shot.position}-${shot.copyDraft || shot.messageGoal}`}
              className="experiments__draft-shot"
            >
              <h5>
                {copy("draftScreenshot")} {shot.position}
              </h5>
              <dl className="experiments__fields">
                {shot.currentMessage ? (
                  <div>
                    <dt>{copy("draftCurrentMessage")}</dt>
                    <dd>{shot.currentMessage}</dd>
                  </div>
                ) : null}
                {shot.keep ? (
                  <div>
                    <dt>{copy("draftKeep")}</dt>
                    <dd>{shot.keep}</dd>
                  </div>
                ) : null}
                {shot.change ? (
                  <div>
                    <dt>{copy("draftChange")}</dt>
                    <dd>{shot.change}</dd>
                  </div>
                ) : null}
                {shot.messageGoal ? (
                  <div>
                    <dt>{copy("draftMessageGoal")}</dt>
                    <dd>{shot.messageGoal}</dd>
                  </div>
                ) : null}
                <div>
                  <dt>{copy("draftCopy")}</dt>
                  <dd className="experiments__draft-copy">
                    {shot.copyDraft || "—"}
                  </dd>
                </div>
                <div>
                  <dt>{copy("draftRecommendedScreen")}</dt>
                  <dd>{shot.recommendedScreen}</dd>
                </div>
                <div>
                  <dt>{copy("draftWhy")}</dt>
                  <dd>{shot.why}</dd>
                </div>
              </dl>
            </div>
          ))}
        </div>
      ) : null}

      {draft.missingInputs?.length > 0 ? (
        <div>
          <p>
            <strong>{copy("draftMissingInputs")}</strong>
          </p>
          <ul>
            {draft.missingInputs.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {draft.notes ? (
        <dl className="experiments__draft-summary">
          <DraftField label={copy("draftNotes")} value={draft.notes} />
        </dl>
      ) : null}

      {draft.playbooksUsed?.length > 0 ? (
        <dl className="experiments__draft-summary">
          <DraftField
            label={copy("draftPlaybooksUsed")}
            value={draft.playbooksUsed.join(", ")}
          />
        </dl>
      ) : null}
    </div>
  );
}

function ExperimentBlock({
  experiment,
  index,
  report,
  slot,
  onDraftStart,
  onDraftSuccess,
  onDraftError,
}: {
  experiment: GrowthExperiment;
  index: number;
  report: GrowthReport;
  slot: DraftSlot;
  onDraftStart: (experimentTitle: string) => void;
  onDraftSuccess: (experimentTitle: string, draft: ActionDraft) => void;
  onDraftError: (experimentTitle: string, message: string) => void;
}) {
  const { copy, language } = useLanguage();
  const inputId = useId();
  const needsShots = isScreenshotExperiment(experiment);
  const [localShots, setLocalShots] = useState<LocalShot[]>([]);
  const localShotsRef = useRef<LocalShot[]>([]);
  const requestSeqRef = useRef(0);

  useEffect(() => {
    localShotsRef.current = localShots;
  }, [localShots]);

  useEffect(() => {
    return () => clearLocalShots(localShotsRef.current);
  }, []);

  function handleSelectFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) {
      return;
    }
    const accepted = Array.from(fileList).filter((file) => {
      const type = (file.type || "").toLowerCase();
      if (ACCEPTED_IMAGE_TYPES.has(type)) {
        return true;
      }
      const name = file.name.toLowerCase();
      return name.endsWith(".png") || name.endsWith(".jpg") || name.endsWith(".jpeg");
    });
    if (accepted.length === 0) {
      onDraftError(experiment.title, copy("draftImageTypeError"));
      return;
    }
    setLocalShots((prev) => {
      clearLocalShots(prev);
      return accepted.map((file, i) => ({
        position: i + 1,
        file,
        previewUrl: URL.createObjectURL(file),
      }));
    });
  }

  function clearSelection() {
    setLocalShots((prev) => {
      clearLocalShots(prev);
      return [];
    });
  }

  async function handleCreateDraft() {
    const experimentTitle = experiment.title;
    const seq = ++requestSeqRef.current;

    const reportRun = report.analysisRunId;
    const expRun = experiment.analysisRunId || reportRun;
    if (!reportRun || !expRun || reportRun !== expRun) {
      onDraftError(experimentTitle, copy("draftContextMismatch"));
      return;
    }
    // Cached / empty report must never be drafted against a mismatched Live run.
    if (
      !hasSuccessfulReport(report) ||
      (expRun && expRun.startsWith("mock"))
    ) {
      onDraftError(experimentTitle, copy("draftContextMismatch"));
      return;
    }

    onDraftStart(experimentTitle);
    try {
      const userScreenshots =
        localShots.length > 0
          ? await Promise.all(
              localShots.map((shot) =>
                fileToUserScreenshot(shot.file, shot.position),
              ),
            )
          : [];

      const result = await requestDraft({
        language,
        productId: report.product?.id,
        experiment: {
          title: experiment.title,
          hypothesis: experiment.hypothesis,
          why: experiment.why,
          action: experiment.action,
          targetMetric: experiment.targetMetric,
          expectedSignal: experiment.expectedSignal,
          suggestedDuration: experiment.suggestedDuration,
          evidence: experiment.evidence,
          playbookReference: experiment.playbookReference,
          analysisRunId: expRun,
        },
        mostImportantFinding: report.mostImportantFinding,
        facts: report.facts,
        playbooksConsulted: report.playbooksConsulted,
        app: {
          name: report.appName,
          bundleId: report.appBundleId,
          appStoreConnectId: report.appStoreConnectId,
          territory: report.appTerritory,
        },
        period: report.period,
        metrics: report.metricsPayload,
        analysisRunId: reportRun,
        dataSource: report.dataSource,
        // Ephemeral request payload only — not persisted beyond this call.
        userScreenshots,
      });
      if (seq !== requestSeqRef.current) {
        return;
      }
      onDraftSuccess(experimentTitle, result.draft);
    } catch (err) {
      if (seq !== requestSeqRef.current) {
        return;
      }
      const message =
        err instanceof DraftRequestError
          ? err.code === "analysis_context_mismatch"
            ? copy("draftContextMismatch")
            : err.message
          : copy("draftError");
      onDraftError(experimentTitle, message);
    }
  }

  return (
    <article className="experiments__item">
      <h3 className="experiments__item-title">
        {index}. {experiment.title}
      </h3>
      <dl className="experiments__fields">
        <div>
          <dt>{copy("experimentHypothesis")}</dt>
          <dd>{experiment.hypothesis}</dd>
        </div>
        <div>
          <dt>{copy("experimentWhy")}</dt>
          <dd>{experiment.why}</dd>
        </div>
        <div>
          <dt>{copy("experimentAction")}</dt>
          <dd>{experiment.action}</dd>
        </div>
        <div>
          <dt>{copy("experimentTargetMetric")}</dt>
          <dd>{experiment.targetMetric}</dd>
        </div>
        <div>
          <dt>{copy("experimentExpectedSignal")}</dt>
          <dd>{experiment.expectedSignal}</dd>
        </div>
        <div>
          <dt>{copy("experimentDuration")}</dt>
          <dd>{experiment.suggestedDuration}</dd>
        </div>
        <div>
          <dt>{copy("experimentEvidence")}</dt>
          <dd>{experiment.evidence}</dd>
        </div>
        <div>
          <dt>{copy("experimentPlaybook")}</dt>
          <dd>{experiment.playbookReference}</dd>
        </div>
      </dl>

      {needsShots ? (
        <div className="experiments__upload">
          <p className="experiments__upload-hint">{copy("draftUploadHint")}</p>
          <div className="experiments__upload-controls">
            <label className="experiments__draft-btn" htmlFor={inputId}>
              {copy("draftSelectImages")}
            </label>
            <input
              id={inputId}
              type="file"
              accept="image/png,image/jpeg,.png,.jpg,.jpeg"
              multiple
              className="experiments__file-input"
              onChange={(event) => {
                handleSelectFiles(event.target.files);
                event.target.value = "";
              }}
            />
            {localShots.length > 0 ? (
              <button
                type="button"
                className="experiments__draft-btn experiments__draft-btn--ghost"
                onClick={clearSelection}
              >
                {copy("draftClearImages")}
              </button>
            ) : null}
          </div>
          {localShots.length > 0 ? (
            <ul className="experiments__upload-list">
              {localShots.map((shot) => (
                <li key={`${shot.position}-${shot.file.name}`}>
                  <img
                    src={shot.previewUrl}
                    alt=""
                    className="experiments__upload-preview"
                  />
                  <span>
                    #{shot.position} {shot.file.name}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="experiments__upload-empty">
              {copy("draftNoImagesSelected")}
            </p>
          )}
        </div>
      ) : null}

      <div className="experiments__draft-actions">
        <button
          type="button"
          className="experiments__draft-btn"
          onClick={handleCreateDraft}
          disabled={slot.drafting}
        >
          {slot.drafting ? copy("creatingDraft") : copy("createDraft")}
        </button>
      </div>

      {slot.error ? (
        <p className="experiments__error" role="alert">
          {slot.error}
        </p>
      ) : null}

      {slot.draft ? <ActionDraftView draft={slot.draft} /> : null}
    </article>
  );
}

/** Planner output next to Analyzer results. */
export function GrowthExperiments({ report }: { report: GrowthReport }) {
  const { copy } = useLanguage();
  const experiments = report.growthExperiments ?? [];
  // Survive Analyze remounts / experiment-title changes: drafts live here, not in each block.
  // Cleared when parent remounts on product switch (key includes product id).
  const [slotsByTitle, setSlotsByTitle] = useState<Record<string, DraftSlot>>(
    {},
  );

  const hasPlanner =
    experiments.length > 0 ||
    Boolean(report.plannerStatus) ||
    Boolean(report.plannerError) ||
    Object.keys(slotsByTitle).length > 0;

  const activeTitles = new Set(experiments.map((item) => item.title));
  const orphanSlots = Object.entries(slotsByTitle).filter(
    ([title, slot]) =>
      !activeTitles.has(title) && (slot.draft || slot.error || slot.drafting),
  );

  function onDraftStart(experimentTitle: string) {
    setSlotsByTitle((prev) => ({
      ...prev,
      [experimentTitle]: {
        drafting: true,
        draft: prev[experimentTitle]?.draft ?? null,
        error: null,
      },
    }));
  }

  function onDraftSuccess(experimentTitle: string, draft: ActionDraft) {
    setSlotsByTitle((prev) => ({
      ...prev,
      [experimentTitle]: { drafting: false, draft, error: null },
    }));
  }

  function onDraftError(experimentTitle: string, message: string) {
    setSlotsByTitle((prev) => ({
      ...prev,
      [experimentTitle]: {
        drafting: false,
        draft: null,
        error: message,
      },
    }));
  }

  function emptySlot(): DraftSlot {
    return { drafting: false, draft: null, error: null };
  }

  if (!hasPlanner) {
    if (!hasSuccessfulReport(report)) {
      return (
        <section className="experiments" aria-labelledby="experiments-heading">
          <h2 id="experiments-heading" className="experiments__heading">
            {copy("recommendedExperiments")}
          </h2>
          <p className="experiments__empty">{copy("experimentsAwaitAnalyze")}</p>
        </section>
      );
    }
    return null;
  }

  return (
    <section className="experiments" aria-labelledby="experiments-heading">
      <h2 id="experiments-heading" className="experiments__heading">
        {copy("recommendedExperiments")}
      </h2>

      <div className="experiments__meta">
        {report.plannerStatus ? (
          <p className="experiments__status">{report.plannerStatus}</p>
        ) : null}

        {report.plannerError ? (
          <p className="experiments__error" role="alert">
            {copy("plannerError")}: {report.plannerError}
          </p>
        ) : null}

        {report.playbooksConsulted && report.playbooksConsulted.length > 0 ? (
          <p className="experiments__playbooks">
            {copy("playbooksConsulted")}:{" "}
            {report.playbooksConsulted.join(", ")}
          </p>
        ) : null}

        {report.knownEventsUsed && report.knownEventsUsed.length > 0 ? (
          <p className="experiments__playbooks">
            {copy("knownEventsUsed")}: {report.knownEventsUsed.join(", ")}
          </p>
        ) : null}

        {report.knownEventsConsidered &&
        report.knownEventsConsidered.length > 0 ? (
          <p className="experiments__playbooks">
            {copy("knownEventsConsidered")}:{" "}
            {report.knownEventsConsidered
              .map((event) => {
                const when = event.end_date
                  ? `${event.date}–${event.end_date}`
                  : event.date;
                return `${when} (${event.type})`;
              })
              .join("; ")}
          </p>
        ) : null}
      </div>

      {experiments.length === 0 ? (
        <p className="experiments__empty">{copy("noExperiments")}</p>
      ) : (
        <div className="experiments__list">
          {experiments.map((experiment, index) => (
            <ExperimentBlock
              key={experiment.title}
              experiment={experiment}
              index={index + 1}
              report={report}
              slot={slotsByTitle[experiment.title] ?? emptySlot()}
              onDraftStart={onDraftStart}
              onDraftSuccess={onDraftSuccess}
              onDraftError={onDraftError}
            />
          ))}
        </div>
      )}

      {orphanSlots.length > 0 ? (
        <div className="experiments__orphan-drafts">
          <h3 className="experiments__orphan-heading">
            {copy("actionDraft")}
          </h3>
          <p className="experiments__upload-hint">
            {copy("draftOrphanHint")}
          </p>
          {orphanSlots.map(([title, slot]) => (
            <div key={title} className="experiments__item">
              <h4 className="experiments__item-title">{title}</h4>
              {slot.drafting ? (
                <p className="experiments__status">{copy("creatingDraft")}</p>
              ) : null}
              {slot.error ? (
                <p className="experiments__error" role="alert">
                  {slot.error}
                </p>
              ) : null}
              {slot.draft ? <ActionDraftView draft={slot.draft} /> : null}
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
