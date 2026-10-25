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
  targetProduct: {
    ja: "対象Product",
    en: "Product",
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
  mahjongPageViews: {
    ja: "/mahjong/ ページビュー",
    en: "/mahjong/ page views",
  },
  mahjongPageViewsNote: {
    ja: "点数計算ページを閲覧した（計算利用ではない）",
    en: "Score-calculation page viewed (not calculation used)",
  },
  formSubmitPathNote: {
    ja: "点数計算フォームがsubmitされた近似指標（計算成功ではない）",
    en: "Score-calculation form submitted (proxy; not score success)",
  },
  appstoreClickNote: {
    ja: "Web内のApp Store CTAクリック（ASCダウンロードではない）",
    en: "Web App Store CTA click (not ASC download)",
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
  revenueAdmobNote: {
    ja: "AdMob ESTIMATED_EARNINGS と App Store Sales Developer Proceeds を並列表示（合算しない）。Proceeds は Trends 推定であり Financial 確定額ではない。ASC Analytics と Revenue WW は別スコープ。",
    en: "AdMob ESTIMATED_EARNINGS and App Store Sales Developer Proceeds in parallel (not summed). Proceeds are Trends estimates, not Financial settled share. ASC Analytics ≠ Revenue WW.",
  },
  estimatedEarnings: {
    ja: "AdMob 推定収益",
    en: "AdMob estimated earnings",
  },
  appStoreProceeds: {
    ja: "App Store proceeds",
    en: "App Store proceeds",
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
  usingLive: {
    ja: "前回の分析結果",
    en: "Last successful Analyze",
  },
  noCachedReport: {
    ja: "まだ分析結果がありません。最新データを分析してください。",
    en: "No saved Analyze yet. Run Analyze latest data.",
  },
  draftContextMismatch: {
    ja: "分析コンテキストが一致しません。Experiment と Analyze 結果が別 Run です。もう一度 Analyze してから草案を作成してください。",
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
    ja: "おすすめの成長実験",
    en: "Recommended Growth Experiments",
  },
  experimentHypothesis: {
    ja: "仮説",
    en: "Hypothesis",
  },
  experimentWhy: {
    ja: "理由",
    en: "Why",
  },
  experimentAction: {
    ja: "アクション",
    en: "Action",
  },
  experimentTargetMetric: {
    ja: "対象指標",
    en: "Target metric",
  },
  experimentExpectedSignal: {
    ja: "期待するシグナル",
    en: "Expected signal",
  },
  experimentDuration: {
    ja: "期間",
    en: "Duration",
  },
  experimentEvidence: {
    ja: "根拠",
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
    ja: "草案を作成",
    en: "Create Draft",
  },
  creatingDraft: {
    ja: "草案を生成中…",
    en: "Creating draft…",
  },
  draftUploadHint: {
    ja: "現在の App Store スクリーンショット（PNG / JPEG）。選択順が position 1, 2, … になります。未選択でも草案作成は可能です。",
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
    ja: "現状の訴求",
    en: "Current message",
  },
  draftKeep: {
    ja: "残す点",
    en: "Keep",
  },
  draftChange: {
    ja: "変える点",
    en: "Change",
  },
  actionDraft: {
    ja: "アクション草案",
    en: "Action Draft",
  },
  experimentTitle: {
    ja: "実験",
    en: "Experiment",
  },
  draftOrphanHint: {
    ja: "Analyze 完了で Experiment 一覧が変わっても、直前の Draft 結果はここに残します。",
    en: "Draft results stay here even if Analyze replaces the experiment list.",
  },
  draftType: {
    ja: "草案タイプ",
    en: "Draft type",
  },
  draftObjective: {
    ja: "目的",
    en: "Objective",
  },
  draftRationale: {
    ja: "根拠",
    en: "Rationale",
  },
  draftScreenshot: {
    ja: "スクリーンショット",
    en: "Screenshot",
  },
  draftMessageGoal: {
    ja: "メッセージの狙い",
    en: "Message goal",
  },
  draftCopy: {
    ja: "コピー案",
    en: "Copy draft",
  },
  draftRecommendedScreen: {
    ja: "推奨画面",
    en: "Recommended screen",
  },
  draftWhy: {
    ja: "理由",
    en: "Why",
  },
  draftMissingInputs: {
    ja: "不足している入力",
    en: "Missing inputs",
  },
  draftNotes: {
    ja: "メモ",
    en: "Notes",
  },
  draftPlaybooksUsed: {
    ja: "使用 Playbook",
    en: "Playbooks used",
  },
  draftError: {
    ja: "草案を生成できませんでした。",
    en: "Could not generate the draft.",
  },
  noExperiments: {
    ja: "おすすめの実験はありません",
    en: "No experiment recommended",
  },
  experimentsAwaitAnalyze: {
    ja: "Analyze 後に成長実験が表示されます",
    en: "Growth experiments appear after Analyze",
  },
  actionsEmpty: {
    ja: "Analyze 後に優先アクションが表示されます",
    en: "Prioritized actions appear after Analyze",
  },
  factsEmpty: {
    ja: "Analyze 後に確認できたことが表示されます",
    en: "Observed facts appear after Analyze",
  },
  speculationEmpty: {
    ja: "推測はまだありません",
    en: "No speculation yet",
  },
  retryAnalyze: {
    ja: "再試行",
    en: "Retry",
  },
  metricsSummaryLabel: {
    ja: "指標サマリー",
    en: "Metrics summary",
  },
  analysisDetailsLabel: {
    ja: "分析詳細",
    en: "Analysis details",
  },
  changeVsPrevious: {
    ja: "直前期間比",
    en: "vs previous period",
  },
  plannerError: {
    ja: "Planner / MCP エラー（Analyzer 結果は有効）",
    en: "Planner / MCP error (Analyzer result still valid)",
  },
  // --- Portfolio Overview ---
  portfolioTitle: {
    ja: "ポートフォリオ",
    en: "Portfolio",
  },
  portfolioEyebrow: {
    ja: "全アプリの概要",
    en: "All apps at a glance",
  },
  portfolioOpen: {
    ja: "ポートフォリオ",
    en: "Portfolio",
  },
  portfolioBackToDashboard: {
    ja: "ダッシュボードへ",
    en: "Back to dashboard",
  },
  portfolioCountApps: {
    ja: "アプリ",
    en: "apps",
  },
  portfolioAnalyzed: {
    ja: "分析済み",
    en: "Analyzed",
  },
  portfolioNotAnalyzed: {
    ja: "未分析",
    en: "Not analyzed",
  },
  portfolioNotAnalyzedHint: {
    ja: "このブラウザに保存された分析結果はありません。ダッシュボードで「最新データを分析」を実行してください。",
    en: "No saved Analyze in this browser. Open the dashboard and run Analyze latest data.",
  },
  portfolioKpis: {
    ja: "主要指標",
    en: "Key metrics",
  },
  portfolioNoData: {
    ja: "表示できる値がありません",
    en: "No values to show",
  },
  portfolioTopAction: {
    ja: "最優先の推奨",
    en: "Top recommendation",
  },
  portfolioNoTopAction: {
    ja: "この分析には推奨アクションがありません",
    en: "This Analyze returned no recommended action",
  },
  portfolioOpenDashboard: {
    ja: "詳細を開く",
    en: "Open details",
  },
  portfolioDataNote: {
    ja: "各アプリについて、このブラウザに保存された最後の Live Analyze の結果をそのまま表示しています。この画面では値や推奨を生成しません。",
    en: "Each card shows the last successful Live Analyze saved in this browser, as-is. This view does not generate values or recommendations.",
  },
  // --- Evidence revision panel ---
  evidenceEyebrow: {
    ja: "Grounding Critic",
    en: "Grounding Critic",
  },
  evidenceTitle: {
    ja: "根拠を検証して改訂する",
    en: "Verify the evidence and revise",
  },
  evidenceHint: {
    ja: "v1（自アプリの実績）→ v2（＋競合の公開情報）→ Critic が自分で書いた SQL で数字を照合 → 指摘を受けて v3。提案に出てくる数字は、すべて根拠ストアへの SQL で再現できるかを確かめます。",
    en: "v1 (own app data) → v2 (+ public competitor data) → the Critic re-checks every number with its own SQL → v3 answers the findings. Every number in a proposal must be reproducible by SQL on the evidence store.",
  },
  evidenceRun: {
    ja: "実行",
    en: "Run",
  },
  evidenceStart: {
    ja: "新しく検証を実行",
    en: "Run a new verification",
  },
  evidenceStarting: {
    ja: "開始しています…",
    en: "Starting…",
  },
  evidenceStartConfirm: {
    ja: "v1 → v2 → Critic → v3 を新しく実行します。モデルを何度も呼ぶため、10〜20 分ほどかかり、クレジットを消費します。実行しますか？",
    en: "This starts a new v1 → v2 → Critic → v3 run. It calls the model many times, takes about 10–20 minutes, and spends credits. Start now?",
  },
  evidenceBusy: {
    ja: "別の検証を実行中です。終わってから再度お試しください。",
    en: "Another verification is still running. Try again when it finishes.",
  },
  evidenceStartError: {
    ja: "検証を開始できませんでした。",
    en: "Could not start the verification.",
  },
  evidenceApiUnreachable: {
    ja: "Agent API に接続できません。api_server.py が起動しているか確認してください。",
    en: "Cannot reach the Agent API. Check that api_server.py is running.",
  },
  evidenceLoadError: {
    ja: "検証結果を読み込めませんでした。",
    en: "Could not load the verification results.",
  },
  evidenceNoRuns: {
    ja: "このアプリの検証結果はまだありません。",
    en: "No verification runs for this app yet.",
  },
  evidenceLoading: {
    ja: "読み込んでいます…",
    en: "Loading…",
  },
  evidenceStatus: {
    ja: "状態",
    en: "Status",
  },
  evidenceStatusRunning: {
    ja: "実行中",
    en: "Running",
  },
  evidenceStatusConverged: {
    ja: "指摘なしで完了",
    en: "Converged",
  },
  evidenceStatusMaxRounds: {
    ja: "再チェック上限で終了",
    en: "Stopped at review limit",
  },
  evidenceStatusError: {
    ja: "エラー",
    en: "Error",
  },
  evidenceRunningHint: {
    ja: "各版ができるたびに表示が更新されます。このページを開いたままでも、閉じても実行は続きます。",
    en: "The view updates as each version is ready. The run continues even if you close this page.",
  },
  evidenceModel: {
    ja: "モデル",
    en: "Model",
  },
  evidencePeriod: {
    ja: "比較期間",
    en: "Periods",
  },
  evidencePastDecisions: {
    ja: "参照した過去の判断",
    en: "Past decisions recalled",
  },
  evidenceRejected: {
    ja: "コードが差し戻した回答",
    en: "Answers rejected by code",
  },
  evidenceTopActionTrail: {
    ja: "1位の提案の推移",
    en: "Top proposal by version",
  },
  evidenceNoActions: {
    ja: "（提案なし）",
    en: "(no proposals)",
  },
  evidenceStageInternal: {
    ja: "自アプリの実績",
    en: "Own app data",
  },
  evidenceStageCompetitive: {
    ja: "＋競合の公開情報",
    en: "+ competitor data",
  },
  evidenceStageRevision: {
    ja: "指摘を受けて改訂",
    en: "Revised for findings",
  },
  evidenceCritic: {
    ja: "Critic",
    en: "Critic",
  },
  evidenceFindingsCount: {
    ja: "指摘",
    en: "findings",
  },
  evidenceNoFindings: {
    ja: "指摘なし",
    en: "no findings",
  },
  evidencePending: {
    ja: "実行中…",
    en: "running…",
  },
  evidenceMostImportant: {
    ja: "最も重要な発見",
    en: "Most important finding",
  },
  evidenceActions: {
    ja: "提案",
    en: "Proposals",
  },
  evidenceChanges: {
    ja: "前の版からの変化",
    en: "Changes from the previous version",
  },
  evidenceTopSame: {
    ja: "1位の提案は前の版と同じ",
    en: "Top proposal unchanged",
  },
  evidenceTopChanged: {
    ja: "1位の提案が変わった。前の版：",
    en: "Top proposal changed. Previous:",
  },
  evidenceDecisionKept: {
    ja: "維持",
    en: "Kept",
  },
  evidenceDecisionModified: {
    ja: "修正",
    en: "Modified",
  },
  evidenceDecisionRemoved: {
    ja: "取り下げ",
    en: "Removed",
  },
  evidenceClaims: {
    ja: "主張と根拠",
    en: "Claims and evidence",
  },
  evidenceShowSql: {
    ja: "SQL を見る",
    en: "Show SQL",
  },
  evidenceHideSql: {
    ja: "SQL を隠す",
    en: "Hide SQL",
  },
  evidenceKindFact: {
    ja: "事実",
    en: "Fact",
  },
  evidenceKindObservation: {
    ja: "観察",
    en: "Observation",
  },
  evidenceKindHypothesis: {
    ja: "仮説",
    en: "Hypothesis",
  },
  evidenceBadgeVerified: {
    ja: "✓ SQL 照合済み",
    en: "✓ Verified by SQL",
  },
  evidenceBadgeFlagged: {
    ja: "指摘あり",
    en: "Flagged",
  },
  evidenceBadgeUnchecked: {
    ja: "照合なし",
    en: "Not checked",
  },
  evidenceBadgeNotReviewed: {
    ja: "未レビュー",
    en: "Not reviewed",
  },
  evidenceBadgeTestPlan: {
    ja: "検証計画あり",
    en: "Test plan",
  },
  evidenceBadgeNoTestPlan: {
    ja: "検証計画なし",
    en: "No test plan",
  },
  evidenceDays: {
    ja: "日",
    en: "days",
  },
  evidenceReview: {
    ja: "Critic のレビュー",
    en: "Critic review",
  },
  evidenceChecksMatched: {
    ja: "Critic の SQL と一致",
    en: "Critic SQL matched",
  },
  evidenceResolutionResolved: {
    ja: "解消",
    en: "Resolved",
  },
  evidenceResolutionDowngraded: {
    ja: "格下げ",
    en: "Downgraded",
  },
  evidenceResolutionUnresolved: {
    ja: "未解決",
    en: "Unresolved",
  },
  evidenceResolutionOpen: {
    ja: "次の版で残存",
    en: "Still open",
  },
  evidenceFindingValueMismatch: {
    ja: "数値の不一致",
    en: "Value mismatch",
  },
  evidenceFindingUnverifiable: {
    ja: "検証できない",
    en: "Unverifiable",
  },
  evidenceFindingKindMislabel: {
    ja: "種別の誤り",
    en: "Wrong claim kind",
  },
  evidenceFindingScopeMismatch: {
    ja: "母集団の不一致",
    en: "Scope mismatch",
  },
  evidenceFindingCausalLeap: {
    ja: "因果の飛躍",
    en: "Causal leap",
  },
  evidenceFindingInfeasibleAction: {
    ja: "App Store の機能制約に反する",
    en: "Not possible on the App Store",
  },
  evidenceOriginCode: {
    ja: "コード判定",
    en: "Code",
  },
  evidenceOriginCritic: {
    ja: "Critic 判断",
    en: "Critic",
  },
  evidenceClaimed: {
    ja: "主張の値",
    en: "Claimed",
  },
  evidenceCriticValue: {
    ja: "Critic の SQL の結果",
    en: "Critic SQL result",
  },
  evidenceAnalystAnswer: {
    ja: "次の版での回答",
    en: "Answer in the next version",
  },
  evidenceResponseFixed: {
    ja: "修正",
    en: "Fixed",
  },
  evidenceResponseDowngraded: {
    ja: "格下げ",
    en: "Downgraded",
  },
  evidenceResponseRemoved: {
    ja: "削除",
    en: "Removed",
  },
  evidenceResponseDisputed: {
    ja: "反論",
    en: "Disputed",
  },
  // --- Interventions ---
  interventionsEyebrow: {
    ja: "施策の記録と効果測定",
    en: "Interventions and outcomes",
  },
  interventionsTitle: {
    ja: "施策",
    en: "Interventions",
  },
  interventionsHint: {
    ja: "AI の提案を採用するか、自分で登録します。実施日を記録すると変更前の数値を、評価すると変更後の数値を App Store Connect の日次データから SQL で計測します。効いたかどうかの判定はあなたが行います。",
    en: "Adopt an AI proposal or add your own. Recording the implementation date measures the days before the change, and evaluating measures the days after, with SQL on App Store Connect daily data. You make the verdict.",
  },
  interventionsEmpty: {
    ja: "まだ施策はありません。上の改訂履歴から採用するか、自分で登録してください。",
    en: "No interventions yet. Adopt one from the revision history above, or add your own.",
  },
  interventionsLoading: {
    ja: "読み込み中…",
    en: "Loading…",
  },
  interventionsLoadError: {
    ja: "施策を読み込めませんでした。",
    en: "Could not load interventions.",
  },
  interventionsNew: {
    ja: "施策を自分で登録",
    en: "Add your own",
  },
  interventionsFieldTitle: {
    ja: "施策",
    en: "Change",
  },
  interventionsFieldChange: {
    ja: "変更内容（任意）",
    en: "What changes (optional)",
  },
  interventionsFieldMetric: {
    ja: "評価指標",
    en: "Evaluation metric",
  },
  interventionsFieldMethod: {
    ja: "判定方法",
    en: "How it is judged",
  },
  interventionsFieldCriterion: {
    ja: "成功基準",
    en: "Success criterion",
  },
  interventionsFieldDays: {
    ja: "評価までの日数",
    en: "Days until evaluation",
  },
  interventionsMetricHint: {
    ja: "自動で計測する指標: impressions / product_page_views / first_time_downloads / impression_to_page_view_pct / page_view_to_download_pct",
    en: "Measured automatically: impressions / product_page_views / first_time_downloads / impression_to_page_view_pct / page_view_to_download_pct",
  },
  interventionsSubmit: {
    ja: "登録する",
    en: "Add",
  },
  interventionsSubmitting: {
    ja: "登録中…",
    en: "Adding…",
  },
  interventionsCancel: {
    ja: "キャンセル",
    en: "Cancel",
  },
  interventionsStatusPlanned: {
    ja: "予定",
    en: "Planned",
  },
  interventionsStatusImplemented: {
    ja: "実施済み",
    en: "Implemented",
  },
  interventionsStatusEvaluated: {
    ja: "評価済み",
    en: "Evaluated",
  },
  interventionsStatusDropped: {
    ja: "中止",
    en: "Dropped",
  },
  interventionsOriginAi: {
    ja: "AI の提案を採用",
    en: "Adopted from AI",
  },
  interventionsOriginManual: {
    ja: "手動で登録",
    en: "Added by hand",
  },
  interventionsImplementedOn: {
    ja: "実施日",
    en: "Implemented on",
  },
  interventionsEvaluationDate: {
    ja: "評価日",
    en: "Evaluation date",
  },
  interventionsDue: {
    ja: "評価日です",
    en: "Due",
  },
  interventionsAiPrediction: {
    ja: "AI の提案",
    en: "AI proposal",
  },
  interventionsAiCriterion: {
    ja: "AI の成功基準",
    en: "AI success criterion",
  },
  interventionsMeasured: {
    ja: "計測値（SQL）",
    en: "Measured (SQL)",
  },
  interventionsBefore: {
    ja: "変更前",
    en: "Before",
  },
  interventionsAfter: {
    ja: "変更後",
    en: "After",
  },
  interventionsNotMeasured: {
    ja: "未計測",
    en: "Not measured",
  },
  interventionsSkipped: {
    ja: "計測できなかったもの",
    en: "Not measured",
  },
  interventionsHumanVerdict: {
    ja: "あなたの判定",
    en: "Your verdict",
  },
  interventionsVerdictImproved: {
    ja: "改善した",
    en: "Improved",
  },
  interventionsVerdictNoChange: {
    ja: "変化なし",
    en: "No change",
  },
  interventionsVerdictWorse: {
    ja: "悪化した",
    en: "Worse",
  },
  interventionsVerdictInconclusive: {
    ja: "判定不能",
    en: "Inconclusive",
  },
  interventionsMarkImplemented: {
    ja: "実施した",
    en: "Mark implemented",
  },
  interventionsEvaluate: {
    ja: "評価を記録",
    en: "Record verdict",
  },
  interventionsNote: {
    ja: "メモ（任意）",
    en: "Note (optional)",
  },
  interventionsEarly: {
    ja: "評価日より前に評価する",
    en: "Evaluate before the evaluation date",
  },
  interventionsMeasure: {
    ja: "もう一度計測",
    en: "Measure again",
  },
  interventionsDrop: {
    ja: "中止する",
    en: "Drop",
  },
  interventionsDropPrompt: {
    ja: "中止する理由を入力してください",
    en: "Why are you dropping this?",
  },
  interventionsDropReason: {
    ja: "中止の理由",
    en: "Reason dropped",
  },
  interventionsWorking: {
    ja: "処理中…",
    en: "Working…",
  },
  interventionsUnchanged: {
    ja: "すでに記録済みでした（変更なし）。",
    en: "Already recorded (no change).",
  },
  interventionsWarning: {
    ja: "注意",
    en: "Note",
  },
  interventionsAdopt: {
    ja: "施策として採用",
    en: "Adopt",
  },
  interventionsAdopting: {
    ja: "採用中…",
    en: "Adopting…",
  },
  interventionsAdopted: {
    ja: "施策に追加しました",
    en: "Added to interventions",
  },
  interventionsAlreadyAdopted: {
    ja: "採用済みです",
    en: "Already adopted",
  },
  interventionsNeedsPlan: {
    ja: "この提案には検証計画がありません。評価指標・判定方法・成功基準・日数を入力してください。",
    en: "This proposal has no test plan. Enter the metric, method, success criterion, and days.",
  },
  interventionsErrorNotDue: {
    ja: "まだ評価日になっていません。「評価日より前に評価する」を選ぶと記録できます。",
    en: "Not due yet. Tick “Evaluate before the evaluation date” to record it anyway.",
  },
  interventionsErrorInvalidDates: {
    ja: "評価日が変更後の計測期間より前になっています。",
    en: "The evaluation date is before the end of the after window.",
  },
  interventionsErrorTransition: {
    ja: "今の状態ではこの操作はできません。",
    en: "This step is not possible in the current state.",
  },
  interventionsErrorStoreUnavailable: {
    ja: "根拠ストアに接続できないため計測できません。",
    en: "The evidence store is unavailable, so nothing was measured.",
  },
  interventionsErrorRunInProgress: {
    ja: "実行が終わってから採用してください。",
    en: "Wait for the run to finish before adopting.",
  },
  interventionsErrorInvalidInput: {
    ja: "入力内容を確認してください。",
    en: "Check the fields and try again.",
  },
  interventionsErrorGeneric: {
    ja: "操作できませんでした。",
    en: "Could not complete this step.",
  },
  interventionsErrorSampleRun: {
    ja: "架空のサンプルデータの提案は施策として採用できません。",
    en: "Proposals from fictional sample data cannot be adopted.",
  },
  // --- Sample mode (Recorded Demo / Live Sample) ---
  evidenceRecordedDemo: {
    ja: "Recorded Demo・架空データ",
    en: "Recorded Demo · fictional data",
  },
  evidenceLiveSample: {
    ja: "Live Sample・架空データ",
    en: "Live Sample · fictional data",
  },
  evidenceRecordedHint: {
    ja: "架空のサンプルデータで実際にモデルを実行した記録です。表示するだけで、外部 API もモデルも呼びません。",
    en: "A recorded real model run on fictional sample data. Viewing it calls no external API and no model.",
  },
  evidenceLiveSampleHint: {
    ja: "架空のサンプルデータで、実際の Analyst と Critic を実行した結果です。実際のアプリの分析ではありません。",
    en: "The real Analyst and Critic run on fictional sample data. Not an analysis of a real app.",
  },
  evidenceScenario: {
    ja: "シナリオ",
    en: "Scenario",
  },
  evidenceScenarioChanges: {
    ja: "シナリオで変えた値",
    en: "Values the scenario changed",
  },
  evidenceNoScenarioChanges: {
    ja: "変更なし（基本のサンプル）",
    en: "None (the base sample)",
  },
  evidenceReviewOutcome: {
    ja: "レビュー結果",
    en: "Review outcome",
  },
  evidenceUnresolvedFindings: {
    ja: "未解決の指摘",
    en: "Unresolved findings",
  },
  evidenceSampleDetails: {
    ja: "詳細（シナリオ・変更値・既知の限界・比較上の注意）",
    en: "Details (scenario, changed values, known limitations, comparison note)",
  },
  evidenceKnownLimitations: {
    ja: "既知の限界",
    en: "Known limitations",
  },
  evidenceComparisonNote: {
    ja: "比較上の注意",
    en: "Comparison note",
  },
  // --- Recorded Demo (/demo) ---
  demoNavLink: {
    ja: "Recorded Demo",
    en: "Recorded Demo",
  },
  demoTitle: {
    ja: "根拠で裏づけた、成長の意思決定。",
    en: "Growth decisions, backed by evidence.",
  },
  demoLead: {
    ja: "AI がアプリの成長を分析し、その主張を SQL で独立に検証し、根拠と食い違えば推奨を改訂します。",
    en: "AI analyzes app growth, independently checks its claims with SQL, and revises recommendations when the evidence disagrees.",
  },
  demoTagRecorded: {
    ja: "Recorded Demo",
    en: "Recorded Demo",
  },
  demoTagSynthetic: {
    ja: "架空データ",
    en: "Synthetic Data",
  },
  demoTagRealModel: {
    ja: "実モデルで実行",
    en: "Real Model Execution",
  },
  demoFlow: {
    ja: "Analyst → 独立した Critic → 改訂後のアクション",
    en: "Analyst → Independent Critic → Revised Actions",
  },
  demoNote: {
    ja: "保存済みの実行を表示しています。API キーもモデル呼び出しも使いません。",
    en: "This page shows a saved run. It uses no API keys and makes no model calls.",
  },
  demoNotFound: {
    ja: "保存済みの Recorded Demo が見つかりませんでした。",
    en: "No saved Recorded Demo was found.",
  },
  demoModelLanguageNote: {
    ja: "提案と指摘の本文は、実行時の言語（{lang}）のままです。",
    en: "Proposal and finding text stays in the run's language ({lang}).",
  },
  demoProposalsTitle: {
    ja: "AI の提案はこう変わった",
    en: "How the AI's proposals changed",
  },
  demoProposalsHint: {
    ja: "v1 は自アプリのデータだけ、v2 は競合の公開情報を加えた版、v3 は Critic の指摘を受けて改訂した最終版です。",
    en: "v1 uses only our own app data, v2 adds public competitor data, and v3 is the final version, revised for the Critic's findings.",
  },
  demoFinal: {
    ja: "最終版",
    en: "Final",
  },
  demoChangeReasons: {
    ja: "前の版からの変更理由",
    en: "Why it changed from the previous version",
  },
  demoCriticTitle: {
    ja: "Critic が疑ったこと",
    en: "What the Critic questioned",
  },
  demoCriticHint: {
    ja: "Critic は Analyst とは別に、提案に含まれる数値を自分の SQL で再計算し、根拠と食い違う主張や実行できない提案を指摘します。Analyst は次の版で回答します。",
    en: "Separately from the Analyst, the Critic re-computes every number in a proposal with its own SQL, and flags claims the evidence does not support and actions that cannot be run. The Analyst answers in the next version.",
  },
  demoReviewed: {
    ja: "確認した版",
    en: "reviewed",
  },
  demoRecomputed: {
    ja: "Critic が SQL で再計算した数値",
    en: "Numbers the Critic re-computed with SQL",
  },
  demoMatched: {
    ja: "一致",
    en: "matched",
  },
  demoNoAnswer: {
    ja: "再チェックの上限に達したため、この指摘への回答版はありません。",
    en: "The run hit its review limit, so no version answers this finding.",
  },
  demoRecordedClassification: {
    ja: "記録された分類",
    en: "Recorded classification",
  },
  demoKnownMisjudgment: {
    ja: "既知の誤判定（実行後のレビューで確認）",
    en: "Known misjudgment (confirmed in review after the run)",
  },
  demoOutcomeTitle: {
    ja: "結果",
    en: "Outcome",
  },
  demoSqlTitle: {
    ja: "SQL の根拠",
    en: "SQL evidence",
  },
  demoSqlHint: {
    ja: "最終版の各主張と、その数値を返す SQL",
    en: "Each claim in the final version, with the SQL that returns its numbers",
  },
  demoLogTitle: {
    ja: "詳細ログ",
    en: "Full log",
  },
  demoLogHint: {
    ja: "版ごとの主張・Critic の検証結果・既知の限界",
    en: "Claims and Critic results per version, and known limitations",
  },
} as const;

export type CopyKey = keyof typeof uiCopy;

export function t(key: CopyKey, language: Language): string {
  return uiCopy[key][language];
}
