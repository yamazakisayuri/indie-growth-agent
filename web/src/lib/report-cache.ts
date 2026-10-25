import type { GrowthReport, Language } from "@/lib/types";

const REPORTS_KEY = "indie-growth-agent:lastReports";
const PRODUCT_KEY = "indie-growth-agent:selectedProductId";
const LANGUAGE_KEY = "indie-growth-agent:language";
const WORKSPACE_KEY = "indie-growth-agent:workspace";

export type WorkspaceMode = "sample" | "my";

type ReportStore = Record<string, GrowthReport>;

function readStore(): ReportStore {
  if (typeof window === "undefined") {
    return {};
  }
  try {
    const raw = window.localStorage.getItem(REPORTS_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return {};
    }
    return parsed as ReportStore;
  } catch {
    return {};
  }
}

function writeStore(store: ReportStore) {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(REPORTS_KEY, JSON.stringify(store));
  } catch {
    // Quota / private mode — ignore; in-memory state still works.
  }
}

/** Last successful Live Analyze for a Product, if any. */
export function loadCachedReport(productId: string): GrowthReport | null {
  const report = readStore()[productId];
  if (!report || typeof report !== "object") {
    return null;
  }
  if (!report.analysisRunId || report.dataSource === "mock") {
    return null;
  }
  if (report.product?.id && report.product.id !== productId) {
    return null;
  }
  return report;
}

/** Persist a successful Live Analyze (replaces prior cache for that Product). */
export function saveCachedReport(productId: string, report: GrowthReport) {
  if (!productId || report.dataSource === "mock" || !report.analysisRunId) {
    return;
  }
  const store = readStore();
  store[productId] = report;
  writeStore(store);
}

export function loadSelectedProductId(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage.getItem(PRODUCT_KEY);
  } catch {
    return null;
  }
}

export function saveSelectedProductId(productId: string) {
  if (typeof window === "undefined" || !productId) {
    return;
  }
  try {
    window.localStorage.setItem(PRODUCT_KEY, productId);
  } catch {
    // ignore
  }
}

export function loadSelectedLanguage(): Language | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const saved = window.localStorage.getItem(LANGUAGE_KEY);
    return saved === "ja" || saved === "en" ? saved : null;
  } catch {
    return null;
  }
}

/** Sample Workspace until the user picks My Workspace. */
export function loadWorkspaceMode(): WorkspaceMode {
  if (typeof window === "undefined") {
    return "sample";
  }
  try {
    return window.localStorage.getItem(WORKSPACE_KEY) === "my" ? "my" : "sample";
  } catch {
    return "sample";
  }
}

export function saveWorkspaceMode(mode: WorkspaceMode) {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(WORKSPACE_KEY, mode);
  } catch {
    // ignore
  }
}

export function saveSelectedLanguage(language: Language) {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(LANGUAGE_KEY, language);
  } catch {
    // ignore
  }
}
