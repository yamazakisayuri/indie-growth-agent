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
  ],
};

/** @deprecated Use buildMockReport(language) — kept name for discoverability. */
export const mockReport = mockReportTemplate;
