import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import type { EvidenceRun, SampleInfo } from "./evidence-client";
import { buildDemoStory } from "./recorded-demo";
import {
  parseBySource,
  parseCsv,
  parseDaily,
  parseKnownEvents,
  SNAPSHOT_FILES,
  summarizeRecorded,
  type RecordedSummary,
  type SampleWorkspaceData,
} from "./sample-workspace";

/**
 * Server only (build time for the static export): reads the committed fictional sample and
 * its base-scenario Recorded Demos. Read-only; no API, no model, no My Workspace data.
 */
const SAMPLES_DIR = path.resolve(process.cwd(), "..", "samples");

function read(file: string): string {
  return readFileSync(file, "utf8");
}

function loadRecorded(recordedDir: string): RecordedSummary[] {
  if (!existsSync(recordedDir)) {
    return [];
  }
  const summaries: RecordedSummary[] = [];
  for (const name of readdirSync(recordedDir).sort()) {
    if (!name.endsWith(".sample.json")) {
      continue;
    }
    const sample = JSON.parse(read(path.join(recordedDir, name))) as SampleInfo;
    const tracePath = path.join(recordedDir, name.replace(/\.sample\.json$/, ".json"));
    if (sample.dataKind !== "fictional_sample" || sample.scenario !== "base" || !existsSync(tracePath)) {
      continue;
    }
    const run = { ...(JSON.parse(read(tracePath)) as EvidenceRun), sample, recorded: true };
    const summary = summarizeRecorded(run, buildDemoStory(run));
    if (summary) {
      summaries.push(summary);
    }
  }
  return summaries;
}

export function loadSampleWorkspace(samplesDir = SAMPLES_DIR): SampleWorkspaceData | null {
  const dir = path.join(samplesDir, "mahjong");
  const scenariosPath = path.join(dir, "scenarios.json");
  if (!existsSync(scenariosPath)) {
    return null;
  }
  const scenarios = JSON.parse(read(scenariosPath)) as {
    dataKind?: string;
    note?: string;
    app?: { productId?: string; name?: string; appId?: string };
  };
  if (scenarios.dataKind !== "fictional_sample") {
    return null;
  }
  return {
    app: {
      productId: scenarios.app?.productId ?? "",
      name: scenarios.app?.name ?? "",
      appId: scenarios.app?.appId ?? "",
    },
    note: scenarios.note ?? null,
    daily: parseDaily(read(path.join(dir, "asc_daily.csv"))),
    bySource: parseBySource(read(path.join(dir, "asc_daily_by_source.csv"))),
    events: parseKnownEvents(read(path.join(dir, "known_events.csv"))),
    competitorCount: parseCsv(read(path.join(dir, "competitor_listing.csv"))).filter(
      (row) => row.is_self !== "1",
    ).length,
    recorded: loadRecorded(path.join(samplesDir, "recorded")),
    csvSha256: Object.fromEntries(
      SNAPSHOT_FILES.map((file) => [
        file,
        createHash("sha256").update(readFileSync(path.join(dir, file))).digest("hex"),
      ]),
    ),
  };
}
