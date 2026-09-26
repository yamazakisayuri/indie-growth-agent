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
  web: {
    ja: "Web",
    en: "Web",
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
  sourceWeb: {
    ja: "GA4 Web",
    en: "GA4 Web",
  },
  webUsers: {
    ja: "ユーザー",
    en: "Users",
  },
  webSessions: {
    ja: "セッション",
    en: "Sessions",
  },
  webPageViews: {
    ja: "ページビュー",
    en: "Page views",
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
    ja: "AdMob 推定収益",
    en: "AdMob estimated earnings",
  },
  revenueAdmobNote: {
    ja: "AdMob ESTIMATED_EARNINGS のみ（App Store 売上は含まない）",
    en: "AdMob ESTIMATED_EARNINGS only (App Store proceeds not included)",
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
    ja: "デモ用モックデータ（Live Analyze ではありません）",
    en: "Demo mock data (not a Live Analyze)",
  },
  usingLive: {
    ja: "実データ（Live Analyze）",
    en: "Live Analyze data",
  },
  draftContextMismatch: {
    ja: "Analysis context mismatch — Experiment と Analyze 結果が別 Run です。もう一度 Analyze してから Draft を作成してください。",
    en: "Analysis context mismatch — experiment and report are from different Analyze runs. Run Analyze again, then Create Draft.",
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
  grounding4: {
    ja: "Revenue は絶対額と変化率の両方を見る（少額の大きな%だけで判断しない）",
    en: "Judge revenue with absolute amount and changePercent together",
  },
  grounding5: {
    ja: "Web と App を直接ファネル化しない（計測根拠なき Web→App DL 因果を断定しない）",
    en: "Do not funnel Web into App Store downloads without attribution evidence",
  },
  recommendedExperiments: {
    ja: "Recommended Growth Experiments",
    en: "Recommended Growth Experiments",
  },
  experimentHypothesis: {
    ja: "Hypothesis",
    en: "Hypothesis",
  },
  experimentWhy: {
    ja: "Why",
    en: "Why",
  },
  experimentAction: {
    ja: "Action",
    en: "Action",
  },
  experimentTargetMetric: {
    ja: "Target metric",
    en: "Target metric",
  },
  experimentExpectedSignal: {
    ja: "Expected signal",
    en: "Expected signal",
  },
  experimentDuration: {
    ja: "Duration",
    en: "Duration",
  },
  experimentEvidence: {
    ja: "Evidence",
    en: "Evidence",
  },
  experimentPlaybook: {
    ja: "Playbook",
    en: "Playbook",
  },
  playbooksConsulted: {
    ja: "参照 Playbook",
    en: "Playbooks consulted",
  },
  knownEventsUsed: {
    ja: "判断に使った Known Events",
    en: "Known Events used",
  },
  knownEventsConsidered: {
    ja: "渡した Known Events",
    en: "Known Events considered",
  },
  createDraft: {
    ja: "Create Draft",
    en: "Create Draft",
  },
  creatingDraft: {
    ja: "草案を生成中…",
    en: "Creating draft…",
  },
  draftUploadHint: {
    ja: "現在の App Store スクリーンショット（PNG / JPEG）。選択順が position 1, 2, … になります。未選択でも Create Draft は可能です。",
    en: "Current App Store screenshots (PNG / JPEG). Selection order becomes position 1, 2, …. Create Draft works without images.",
  },
  draftSelectImages: {
    ja: "画像を選択",
    en: "Select images",
  },
  draftClearImages: {
    ja: "選択解除",
    en: "Clear selection",
  },
  draftNoImagesSelected: {
    ja: "画像未選択（Draft は missingInputs で要求できます）",
    en: "No images selected (Draft may request them via missingInputs)",
  },
  draftImageTypeError: {
    ja: "PNG / JPEG のみ選択できます。",
    en: "Only PNG / JPEG files are accepted.",
  },
  draftNoChangeRecommended: {
    ja: "変更非推奨（現状の訴求で十分と判断）",
    en: "No change recommended (current creatives look sufficient)",
  },
  draftCurrentMessage: {
    ja: "Current message",
    en: "Current message",
  },
  draftKeep: {
    ja: "Keep",
    en: "Keep",
  },
  draftChange: {
    ja: "Change",
    en: "Change",
  },
  actionDraft: {
    ja: "Action Draft",
    en: "Action Draft",
  },
  experimentTitle: {
    ja: "Experiment",
    en: "Experiment",
  },
  draftOrphanHint: {
    ja: "Analyze 完了で Experiment 一覧が変わっても、直前の Draft 結果はここに残します。",
    en: "Draft results stay here even if Analyze replaces the experiment list.",
  },
  draftType: {
    ja: "Draft type",
    en: "Draft type",
  },
  draftObjective: {
    ja: "Objective",
    en: "Objective",
  },
  draftRationale: {
    ja: "Rationale",
    en: "Rationale",
  },
  draftScreenshot: {
    ja: "Screenshot",
    en: "Screenshot",
  },
  draftMessageGoal: {
    ja: "Message goal",
    en: "Message goal",
  },
  draftCopy: {
    ja: "Copy draft",
    en: "Copy draft",
  },
  draftRecommendedScreen: {
    ja: "Recommended screen",
    en: "Recommended screen",
  },
  draftWhy: {
    ja: "Why",
    en: "Why",
  },
  draftMissingInputs: {
    ja: "Missing inputs",
    en: "Missing inputs",
  },
  draftNotes: {
    ja: "Notes",
    en: "Notes",
  },
  draftPlaybooksUsed: {
    ja: "Playbooks used",
    en: "Playbooks used",
  },
  draftError: {
    ja: "草案を生成できませんでした。",
    en: "Could not generate the draft.",
  },
  noExperiments: {
    ja: "No experiment recommended",
    en: "No experiment recommended",
  },
  plannerError: {
    ja: "Planner / MCP エラー（Analyzer 結果は有効）",
    en: "Planner / MCP error (Analyzer result still valid)",
  },
} as const;

export type CopyKey = keyof typeof uiCopy;

export function t(key: CopyKey, language: Language): string {
  return uiCopy[key][language];
}
