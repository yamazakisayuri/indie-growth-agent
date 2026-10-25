"use client";

import { useLanguage } from "@/lib/language-context";

/** My Workspace before the first successful Analyze of this Product in this browser. */
export function MyWorkspaceGuide() {
  const { copy } = useLanguage();
  return (
    <section className="sample-section my-guide" aria-labelledby="my-guide">
      <h2 id="my-guide" className="sample-section__title">
        {copy("myGuideTitle")}
      </h2>
      <p className="sample-section__note">{copy("myGuideBody")}</p>
      <ol className="my-guide__steps">
        <li>{copy("myGuideStep1")}</li>
        <li>{copy("myGuideStep2")}</li>
        <li>{copy("myGuideStep3")}</li>
      </ol>
      <p className="sample-section__note">{copy("myGuideSample")}</p>
    </section>
  );
}
