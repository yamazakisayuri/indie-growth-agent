"use client";

import { useEffect, useState } from "react";
import { useLanguage } from "@/lib/language-context";
import { loadWorkspaceMode, saveWorkspaceMode, type WorkspaceMode } from "@/lib/report-cache";
import type { SampleWorkspaceData } from "@/lib/sample-workspace";
import { MyWorkspace } from "./MyWorkspace";
import { SampleWorkspace } from "./SampleWorkspace";

function WorkspaceSwitch({
  mode,
  onChange,
}: {
  mode: WorkspaceMode;
  onChange: (mode: WorkspaceMode) => void;
}) {
  const { copy } = useLanguage();
  const options: { value: WorkspaceMode; label: string; hint: string }[] = [
    { value: "sample", label: copy("workspaceSample"), hint: copy("workspaceSampleHint") },
    { value: "my", label: copy("workspaceMy"), hint: copy("workspaceMyHint") },
  ];
  return (
    <div className="workspace-switch" role="group" aria-label={copy("workspaceLabel")}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={
            mode === option.value
              ? "workspace-switch__btn workspace-switch__btn--active"
              : "workspace-switch__btn"
          }
          aria-pressed={mode === option.value}
          onClick={() => onChange(option.value)}
        >
          <span className="workspace-switch__label">{option.label}</span>
          <span className="workspace-switch__hint">{option.hint}</span>
        </button>
      ))}
    </div>
  );
}

/** `/`: Sample Workspace (fictional, read-only) or My Workspace (real data), never mixed. */
export function HomeApp({ sample }: { sample: SampleWorkspaceData | null }) {
  const [mode, setMode] = useState<WorkspaceMode | null>(null);

  useEffect(() => {
    /* eslint-disable-next-line react-hooks/set-state-in-effect -- localStorage hydrate */
    setMode(loadWorkspaceMode());
  }, []);

  function choose(next: WorkspaceMode) {
    setMode(next);
    saveWorkspaceMode(next);
    window.scrollTo({ top: 0 });
  }

  if (!mode) {
    return <main className="page-shell" aria-busy="true" />;
  }

  return (
    <main className="page-shell">
      <div className="workspace-bar">
        <WorkspaceSwitch mode={mode} onChange={choose} />
      </div>
      {mode === "sample" ? (
        <SampleWorkspace data={sample} onOpenMy={() => choose("my")} />
      ) : (
        <MyWorkspace />
      )}
    </main>
  );
}
