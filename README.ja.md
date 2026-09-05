# Indie Growth Agent

[English](README.md) | [日本語](README.ja.md)

Indie app 向けの成長分析 Agent（ハッカソン MVP）。

App Store Connect / GA4 / AdMob の観測データを集め、数字の要約ではなく **優先すべき Top 3 Actions** を返します。実行ランタイムは **Strands Agents SDK + Amazon Bedrock** で、ローカルの **Next.js Web UI**（日本語 / English）も含まれます。

## 解決する課題

インディー開発者は ASC・GA4・AdMob を別々に見がちで、期間・母集団が揃わないまま「なんとなく」優先度を決めやすいです。

この Agent は次をやります。

1. 3ソースから直近 N 日 vs 前 N 日の事実を取得する
2. Data Grounding 用の契約（期間・母集団・欠損・推測禁止）を入力に埋め込む
3. 観測に基づく **Top 3 Actions** を返す（未確認の分析機能は提案しない）

複数ダッシュボードを一つの要約にまとめることが目的ではありません。接続できた事実から、**今日どこから手を付けるべきか**を優先順位付きで提示することが価値です。

## Data Grounding

プロンプトと入力テキストに次を固定しています。

| 原則 | 内容 |
|------|------|
| Reporting period alignment | ASC の `latest_processing_date` を基準に、GA4 / AdMob も同じ直近 N 日・前 N 日を使う |
| Population scope | ASC（ストア / テリトリー）、GA4（プロパティ全体）、AdMob（設定した App ID）は別母集団 |
| Missing data ≠ zero | 未接続ソースや、行のない期間・日を「ゼロ実績が証明された」とはみなさない（入力に明記）。接続済みソース内の個別メトリクス欠落を missing と zero に分類済み、という意味ではない |
| Facts / Speculation separation | 観測可能な数値のみ Facts。推論は Speculation 枠に分離 |
| No ungrounded cross-source ratios | 母集団一致の記述がない限り、ソース間の割り算・ファネル化をしない（例: GA4 `ad_impression` ≠ AdMob `IMPRESSIONS`） |

LLM 出力はプロンプト / Data Contract で制約していますが、生成後の機械検証はしていません（Known limitations 参照）。

## 対応ソース（現在）

| ソース | 状態 | 主な用途 |
|--------|------|----------|
| App Store Connect Analytics | 必須 | インプレッション、PV、初回 DL、ソース内訳、転換率、前週比 |
| Google Analytics 4 | 任意 | activeUsers / sessions / screenPageViews、設定した key events、前週比 |
| Google AdMob Network Report | 任意 | ESTIMATED_EARNINGS / IMPRESSIONS / IMPRESSION_RPM (eCPM) / CLICKS、前週比 |

未設定のソースは `not connected` として扱い、値を捏造しません。

## ディレクトリ構成

```
indie-growth-agent/
├── agent.py              # エントリポイント（取得 → 入力整形 → Bedrock Agent）
├── format_input.py       # Data Contract / FACTS テキスト生成
├── config.py             # .env 読み込み（秘密情報はハードコードしない）
├── event_definitions.json# GA4 イベントの開発者宣言定義
├── requirements.txt
├── .env.example
├── asc/                  # App Store Connect 取得
├── ga4/                  # GA4 Data API 取得
├── admob/                # AdMob Network Report 取得
├── scripts/              # 接続確認・OAuth 補助
│   ├── verify_ga4.py
│   ├── verify_admob.py
│   ├── oauth_admob.py
│   └── list_ga4_events.py
└── secrets/              # ローカル専用（gitignored）。.p8 / refresh token など
```

## セットアップ

### 1. Python 環境

Python 3.11+ を推奨します。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 設定ファイル

```bash
cp .env.example .env
```

`.env` に実値を書き、秘密情報は `secrets/` に置きます（どちらも git 管理外）。

最低限必要なもの:

- **App Store Connect**: Issuer ID / Key ID / `.p8` 秘密鍵パス、対象アプリ、テリトリー
- **Amazon Bedrock（Strands 既定）**: 実行環境から Bedrock を呼べる AWS 認証（例: `AWS_REGION` とプロファイル / 環境変数）。認証情報自体はリポジトリに置かない
- **GA4（任意）**: Property ID + OAuth（`GOOGLE_OAUTH_*` と refresh token）またはサービスアカウント
- **AdMob（任意）**: Account ID + 別スコープの refresh token（`scripts/oauth_admob.py`）+ 必要なら `ADMOB_APP_IDS`

詳細なキー名は `.env.example` を参照してください。

### 3. 動作確認（任意）

```bash
python scripts/verify_ga4.py
python scripts/verify_admob.py
```

## 実行方法

```bash
python agent.py
```

標準出力に Agent 入力（Data Contract + FACTS）と、Bedrock 経由の回答（Most important finding / Why it matters / Top 3 actions）が流れます。

## Roadmap

### ハッカソン MVP（実装済み）

このリポジトリにすでに含まれているもの:

- App Store Connect 分析データの取得
- GA4 取得（設定時のみ）
- AdMob Network Report 取得（設定時のみ）
- Strands Agents SDK + Amazon Bedrock による分析
- Facts / Speculation grounding
- Reporting period alignment
- Population scope
- Missing data ≠ zero
- 優先順位付き Top 3 Actions
- Next.js Web UI（ローカル）
- 日本語 / English UI

### Future Roadmap（未実装）

#### Next

- Google Play / Android 対応
- アプリ選択 UI
- App Store レビュー
- IAP / サブスクリプション
- RevenueCat 連携

#### Later

- 複数アプリ横断のポートフォリオ分析
- プロアクティブな成長アラート
- 過去の提案と結果からの学習

#### Long-term vision

Indie Growth Agent は、設定された1アプリの分析から、インディー開発者の限られた時間を「次にどのアプリへ使うべきか」まで一緒に決める成長パートナーへ進化することを目指します。

```
Acquisition → Usage → Feedback → Revenue → Prioritized action
```

現時点では次も未実装です:

- AgentCore やその他ホスト基盤へのデプロイ
- 生成後の機械的な grounding 検証（スキーマ検証・出典チェック等）
- AdMob メトリクス欠損の明示的ハンドリング（部分欠損を missing として区別する等）

## Known limitations（MVP）

- **Source populations may differ** — カレンダーが揃っていても ASC / GA4 / AdMob は同一母集団ではない
- **AdMob partial metric missing handling is not implemented** — レスポンス欠落時に「未取得」と「ゼロ」を厳密には区別しない
- **LLM output is grounded by prompt / data contract but not machine-validated after generation** — 出力の事後検証はない

## License

MIT License. See [LICENSE](LICENSE).
