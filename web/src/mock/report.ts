/**
 * Demo mock template for hackathon UI / offline fallback.
 * Keys are resolved through i18n in `buildMockReport`.
 * Live analysis replaces this when "Analyze latest data" succeeds.
 */

export const mockReportTemplate = {
  appName: "Mahjong Score Calculator",
  periodLabel: {
    ja: "2026年8月28日 – 9月3日",
    en: "Aug 28 – Sep 3, 2026",
  },
  metrics: [
    {
      id: "app_store" as const,
      sourceLabelKey: "sourceAsc",
      titleKey: "appStore",
      metrics: [
        { labelKey: "impressions", changePercent: -67.2 },
        { labelKey: "firstTimeDownloads", changePercent: -60.5 },
      ],
    },
    {
      id: "usage" as const,
      sourceLabelKey: "sourceGa4",
      titleKey: "usage",
      metrics: [
        { labelKey: "activeUsers", changePercent: -2.3 },
        {
          labelKey: "recordSaved",
          changePercent: -72.3,
          noteKey: "recordSavedNote",
        },
      ],
    },
    {
      id: "revenue" as const,
      sourceLabelKey: "sourceAdmob",
      titleKey: "revenue",
      metrics: [
        {
          labelKey: "estimatedEarnings",
          value: "¥31.47",
          changePercent: -41.3,
        },
        {
          labelKey: "ecpm",
          value: "¥32.51",
          changePercent: -33.6,
        },
        {
          labelKey: "admobImpressions",
          absolute: "968",
          changePercent: -11.7,
        },
      ],
    },
  ],
  actions: [
    { rank: 1 as const, titleKey: "action1Title", reasonKey: "action1Reason" },
    { rank: 2 as const, titleKey: "action2Title", reasonKey: "action2Reason" },
    { rank: 3 as const, titleKey: "action3Title", reasonKey: "action3Reason" },
  ],
  facts: [
    { textKey: "fact1" },
    { textKey: "fact2" },
    { textKey: "fact3" },
    { textKey: "fact4" },
    { textKey: "fact5" },
  ],
  speculation: [{ textKey: "speculation1" }, { textKey: "speculation2" }],
  dataScope: [
    { sourceKey: "sourceAsc", scopeKey: "scopeAsc" },
    { sourceKey: "sourceGa4", scopeKey: "scopeGa4" },
    { sourceKey: "sourceAdmob", scopeKey: "scopeAdmob" },
  ],
  groundingRules: [
    { textKey: "grounding1" },
    { textKey: "grounding2" },
    { textKey: "grounding3" },
    { textKey: "grounding4" },
    { textKey: "grounding5" },
  ],
  /** Demo Planner output so Create Draft + screenshot upload UI is reachable offline. */
  plannerStatus: {
    ja: "（デモ）モック Planner 出力 — Analyze 成功時は実データに置き換わります",
    en: "(Demo) Mock Planner output — replaced after a successful Analyze",
  },
  growthExperiments: [
    {
      title: {
        ja: "スクリーンショット1〜2枚目の改善案を草案し、App Storeページビュー転換率の向上を試みる",
        en: "Draft screenshot 1–2 improvements to lift App Store page-view conversion",
      },
      hypothesis: {
        ja: "現在のApp Storeスクリーンショット（特に1〜2枚目）が、アプリの核心的価値を検索ユーザーに瞬時に伝えられていない可能性がある。",
        en: "Current App Store screenshots (esp. 1–2) may not instantly communicate the core value to search users.",
      },
      why: {
        ja: "検索経由インプレッションが大半を占める一方、インプレッション→ページビュー率が低水準で横ばい。",
        en: "Most impressions are search-driven while impression→page-view rate stays low and flat.",
      },
      action: {
        ja: "現在のスクリーンショットを確認し、ベネフィット訴求型の改善案を草案する（人による承認後に手動更新）。",
        en: "Review current screenshots and draft benefit-led alternatives (manual update after human approval).",
      },
      targetMetric: {
        ja: "インプレッション→ページビュー率",
        en: "Impression → page view rate",
      },
      expectedSignal: {
        ja: "変更後2〜4週間で方向性の改善が見られるか",
        en: "Directional lift over 2–4 weeks after change",
      },
      suggestedDuration: {
        ja: "2〜4週間",
        en: "2–4 weeks",
      },
      evidence: {
        ja: "ASO playbook: スクリーンショット1〜2枚目が転換に最も影響する",
        en: "ASO playbook: screenshots 1–2 dominate conversion impact",
      },
      playbookReference: {
        ja: "growth-marketing-aso / Visual Assets",
        en: "growth-marketing-aso / Visual Assets",
      },
    },
  ],
};

/** @deprecated Use buildMockReport(language) — kept name for discoverability. */
export const mockReport = mockReportTemplate;
