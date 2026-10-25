import type { Metadata } from "next";
import { RecordedDemo } from "@/components/RecordedDemo";
import { LanguageProvider } from "@/lib/language-context";
import { loadSampleWorkspace } from "@/lib/load-sample-workspace";
import { summarizeSnapshot } from "@/lib/sample-workspace";

export const metadata: Metadata = {
  title: "Recorded Demo · Indie Growth Agent",
};

/** The snapshot is computed from the fictional CSVs at build time; the run is read at runtime. */
export default function DemoPage() {
  const sample = loadSampleWorkspace();
  const snapshot = sample ? summarizeSnapshot(sample.daily, sample.bySource) : null;
  return (
    <LanguageProvider>
      <main className="page-shell">
        <RecordedDemo
          snapshotData={snapshot && sample ? { snapshot, csvSha256: sample.csvSha256 } : null}
        />
      </main>
    </LanguageProvider>
  );
}
