import type { Metadata } from "next";
import { PortfolioOverview } from "@/components/PortfolioOverview";
import { LanguageProvider } from "@/lib/language-context";

export const metadata: Metadata = {
  title: "Portfolio · Indie Growth Agent",
};

export default function PortfolioPage() {
  return (
    <LanguageProvider>
      <main className="page-shell">
        <PortfolioOverview />
      </main>
    </LanguageProvider>
  );
}
