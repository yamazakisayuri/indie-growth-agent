import { HomeApp } from "@/components/HomeApp";
import { LanguageProvider } from "@/lib/language-context";
import { loadSampleWorkspace } from "@/lib/load-sample-workspace";

/** Reads the fictional sample at build time; My Workspace stays client-side as before. */
export default function Home() {
  const sample = loadSampleWorkspace();
  return (
    <LanguageProvider>
      <HomeApp sample={sample} />
    </LanguageProvider>
  );
}
