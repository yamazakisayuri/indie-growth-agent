import type { Metadata } from "next";
import { RecordedDemo } from "@/components/RecordedDemo";
import { LanguageProvider } from "@/lib/language-context";

export const metadata: Metadata = {
  title: "Recorded Demo · Indie Growth Agent",
};

export default function DemoPage() {
  return (
    <LanguageProvider>
      <main className="page-shell">
        <RecordedDemo />
      </main>
    </LanguageProvider>
  );
}
