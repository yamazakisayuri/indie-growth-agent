import type { Language } from "./types";

/**
 * UI chrome copy for ja / en.
 * Live analysis prose comes from the Agent API in the selected language.
 * Mock analysis strings also live here for the offline demo fallback.
 */
export const uiCopy = {
  brandTagline: {
    ja: "3 data sources → 1 priority list",
    en: "3 data sources → 1 priority list",
  },
  brandBy: {
    ja: "by MAKOSOYO",
    en: "by MAKOSOYO",
  },
  targetApp: {
    ja: "対象アプリ",
    en: "App",
  },
  analysisPeriod: {
    ja: "分析期間",
    en: "Period",
  },
  vsPrevious: {
    ja: "直前7日比",
    en: "vs previous 7 days",
  },
  language: {
    ja: "言語",
    en: "Language",
  },
  whatShouldIDo: {
    ja: "次にやるべきこと",
    en: "Next actions",
  },
  topActionsHint: {
    ja: "優先順位をつけた次のアクション",
    en: "Prioritized next steps",
  },
  appStore: {
    ja: "App Store",
    en: "App Store",
  },
  usage: {
    ja: "利用状況",
    en: "Usage",
  },
  revenue: {
    ja: "収益",
    en: "Revenue",
  },
  sourceAsc: {
    ja: "App Store Connect",
    en: "App Store Connect",
  },
  sourceGa4: {
    ja: "Google Analytics 4",
    en: "Google Analytics 4",
  },
  sourceAdmob: {
    ja: "Google AdMob",
    en: "Google AdMob",
  },
  impressions: {
    ja: "インプレッション",
    en: "Impressions",
  },
  firstTimeDownloads: {
    ja: "初回ダウンロード",
    en: "First-time downloads",
  },
  activeUsers: {
    ja: "アクティブユーザー",
    en: "Active users",
  },
  recordSaved: {
    ja: "record_saved",
    en: "record_saved",
  },
  recordSavedNote: {
    ja: "戦績記録が保存されたときに発火するイベント",
    en: "Fires when a match record is saved",
  },
  estimatedEarnings: {
    ja: "推定収益",
    en: "Estimated earnings",
  },
  ecpm: {
    ja: "eCPM",
    en: "eCPM",
  },
  admobImpressions: {
    ja: "インプレッション",
    en: "Impressions",
  },
  facts: {
    ja: "確認できたこと",
    en: "Facts",
  },
  speculation: {
    ja: "推測",
    en: "Speculation",
  },
  speculationLabel: {
    ja: "推測",
    en: "Speculation",
  },
  dataScope: {
    ja: "データ範囲",
    en: "Data Scope",
  },
  groundingRules: {
    ja: "分析ルール",
    en: "Analysis Rules",
  },
  priority: {
    ja: "優先度",
    en: "Priority",
  },
  analyze: {
    ja: "最新データを分析",
    en: "Analyze latest data",
  },
  analyzing: {
    ja: "データを分析しています…",
    en: "Analyzing data…",
  },
  analyzingHint: {
    ja: "App Store / GA4 / AdMob の取得と Bedrock 分析のため、通常 2〜3 分かかります。このままお待ちください。",
    en: "Fetching App Store / GA4 / AdMob and running Bedrock usually takes 2–3 minutes. Please keep this page open.",
  },
  usingMock: {
    ja: "デモ用モックデータ",
    en: "Demo mock data",
  },
  usingLive: {
    ja: "実データ",
    en: "Live data",
  },
  analyzeError: {
    ja: "分析を完了できませんでした。データ接続を確認してください。",
    en: "Could not complete the analysis. Please check your data connections.",
  },
  notConnected: {
    ja: "未接続",
    en: "Not connected",
  },
  // --- Mock action titles / reasons ---
  action1Title: {
    ja: "App Storeでの検索表示を確認する",
    en: "Check App Store search appearance",
  },
  action1Reason: {
    ja: "検索インプレッションが、観測された指標のなかで最も大きく落ち込んでいます。",
    en: "Search impressions show the largest observed decline.",
  },
  action2Title: {
    ja: "record_saved フローを調査する",
    en: "Investigate the record_saved flow",
  },
  action2Reason: {
    ja: "アクティブユーザーは比較的安定している一方で、record_saved が大きく減少しています。",
    en: "record_saved fell sharply while active users were comparatively stable.",
  },
  action3Title: {
    ja: "AdMobの収益低下を調べる",
    en: "Investigate the AdMob revenue decline",
  },
  action3Reason: {
    ja: "同じ分析期間で、AdMob の収益と eCPM の両方が低下しています。",
    en: "AdMob earnings and eCPM both declined during the same reporting window.",
  },
  // --- Mock facts ---
  fact1: {
    ja: "App Store インプレッションが 67.2% 減少",
    en: "App Store impressions decreased 67.2%",
  },
  fact2: {
    ja: "record_saved が 72.3% 減少",
    en: "record_saved decreased 72.3%",
  },
  fact3: {
    ja: "AdMob 推定収益が 41.3% 減少",
    en: "AdMob earnings decreased 41.3%",
  },
  fact4: {
    ja: "初回ダウンロードが 60.5% 減少",
    en: "First-time downloads decreased 60.5%",
  },
  fact5: {
    ja: "eCPM が 33.6% 減少",
    en: "eCPM decreased 33.6%",
  },
  // --- Mock speculation ---
  speculation1: {
    ja: "検索インプレッションの低下は、App Store 検索での可視性低下と関連している可能性がありますが、利用可能なデータだけでは原因を証明できません。",
    en: "The decline in Search impressions appears associated with reduced App Store search visibility, but the available data does not prove the cause.",
  },
  speculation2: {
    ja: "record_saved の急減は、計測実装や保存フローの問題を示唆する可能性がありますが、現状は観測事実に留まります。",
    en: "The sharp drop in record_saved may suggest an instrumentation or save-flow issue, but that remains an inference beyond the observed facts.",
  },
  // --- Mock data scope ---
  scopeAsc: {
    ja: "iOS / 日本",
    en: "iOS / Japan",
  },
  scopeGa4: {
    ja: "プロパティ全体 / 設定済みの全プラットフォーム・国",
    en: "property-wide / all configured platforms and countries",
  },
  scopeAdmob: {
    ja: "iOS アプリ / 全世界",
    en: "iOS app / worldwide",
  },
  // --- Grounding / analysis rules ---
  grounding1: {
    ja: "Missing data ≠ zero（欠測はゼロ実績として扱わない）",
    en: "Missing data ≠ zero",
  },
  grounding2: {
    ja: "Facts と Speculation を分離する",
    en: "Facts and speculation are separated",
  },
  grounding3: {
    ja: "ソース間の母集団を同一視しない",
    en: "Cross-source populations are not assumed identical",
  },
} as const;

export type CopyKey = keyof typeof uiCopy;

export function t(key: CopyKey, language: Language): string {
  return uiCopy[key][language];
}
