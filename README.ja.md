# Indie Growth Agent

[English](README.md) | [日本語](README.ja.md)

Indie app 向けの成長分析 Agent（ハッカソン MVP）。

**接続できた Product チャネル**（App Store Connect Analytics、任意の ASC Sales、GA4 App、GA4 Web、AdMob）の観測データを集め、数字の要約ではなく **優先すべき Top 3 Actions** を返します。実行ランタイムは **Strands Agents SDK + Amazon Bedrock** で、**Next.js の静的 Web UI**（日本語 / English）と **Multi-Product** カタログ（`products/`）を含みます。

## 解決する課題

インディー開発者は ASC・GA4・AdMob を別々に見がちで、期間・母集団が揃わないまま「なんとなく」優先度を決めやすいです。

この Agent は次をやります。

1. 選択した Product の接続ソースから直近 N 日 vs 前 N 日の事実を取得する
2. Data Grounding 用の契約（期間・母集団・欠損・推測禁止・Revenue の安易な合算禁止）を入力に埋め込む
3. 観測に基づく **Top 3 Actions** を返す（未確認の分析機能は提案しない）

複数ダッシュボードを一つの要約にまとめることが目的ではありません。接続できた事実から、**次にどこから手を付けるべきか**を優先順位付きで提示することが価値です（対象は選択中の Product）。

## Multi-Product

分析は常に **1 Product 単位**です（カタログ: `products/index.json` + 各製品 JSON）。

- **CLI**: `python agent.py --product-id <id>`（省略時は `products/index.json` の default）
- **API**: `GET /api/products` が一覧を返し、`POST /api/analyze` は `{ language, productId }` を受け取る
- **Web UI**: Header の Product セレクタ。切替時はその Product の **前回成功した Analyze** を localStorage から復元（なければ空シェル）

**Product セレクタ ≠ ポートフォリオ分析。** 1 Product を選んで分析することは実装済みです。複数 Product を横断して比較・優先付けするポートフォリオ分析は **未実装** です（Future Roadmap 参照）。

## Data Grounding

プロンプトと入力テキストに次を固定しています。

| 原則 | 内容 |
|------|------|
| Reporting period alignment | ASC の `latest_processing_date` を基準に、GA4 / AdMob も同じ直近 N 日・前 N 日を使う |
| Population scope | ASC Analytics（ストア / テリトリー）、GA4 App（原則プロパティ全体）、GA4 Web（設定時は `hostName` EXACT）、AdMob（設定した App ID）、ASC Sales Revenue（Trends・原則 WW）は **別母集団** |
| Missing data ≠ zero | 未接続ソースや、行のない期間・日を「ゼロ実績が証明された」とはみなさない（入力に明記）。接続済みソース内の個別メトリクス欠落を missing と zero に分類済み、という意味ではない |
| Facts / Speculation separation | 観測可能な数値のみ Facts。推論は Speculation 枠に分離 |
| No ungrounded cross-source ratios | 母集団一致の記述がない限り、ソース間の割り算・ファネル化をしない（例: GA4 `ad_impression` ≠ AdMob `IMPRESSIONS`） |
| Revenue sources stay separate | AdMob **ESTIMATED_EARNINGS** と App Store Sales **Developer Proceeds** は意味・確度・通貨/スコープが異なる別ソース。並列表示し、**合算しない** |

LLM 出力はプロンプト / Data Contract で制約していますが、生成後の機械検証はしていません（Known limitations 参照）。

## 対応ソース（現在）

| ソース | 状態 | 主な用途 |
|--------|------|----------|
| App Store Connect Analytics | 必須（App Store チャネル有効時） | インプレッション、PV、初回 DL、ソース内訳、転換率、前週比 |
| App Store Connect Sales（Trends） | 任意 | Units × **Developer Proceeds**（推定。Financial Partner Share ではない）、前週比。原則 WW で、ASC Analytics のテリトリーと同一視しない |
| Google Analytics 4 **App** | 任意 | activeUsers / sessions / screenPageViews、設定した **App** key events、前週比（製品設定でフィルタしない限りプロパティ全体） |
| Google Analytics 4 **Web** | 任意 | 設定ホストの activeUsers / sessions / page views（`hostName` EXACT）、任意の **Web** key events / `featurePaths` / ページパス、前週比 |
| Google AdMob Network Report | 任意 | ESTIMATED_EARNINGS / IMPRESSIONS / IMPRESSION_RPM (eCPM) / CLICKS、前週比 |

未設定のソースは `not connected` として扱い、値を捏造しません。

Revenue UI では AdMob 推定収益と App Store Developer Proceeds を **別行** で表示します（意味・確度が異なるため合算しません）。

## ディレクトリ構成

```
indie-growth-agent/
├── agent.py                 # 共有分析エントリ（取得 → 入力整形 → Bedrock）
├── api_server.py            # FastAPI: /api/products, /api/analyze, /api/draft
├── analysis_schema.py       # Agent / API の構造化レスポンスモデル
├── report_builder.py        # 観測 metrics + 分析結果 → UI 用 JSON
├── format_input.py          # Data Contract / FACTS テキスト生成
├── product_config.py        # Multi-Product カタログ読込
├── planner.py               # 任意の成長実験 Planner（MCP / playbooks）
├── draft_generator.py       # Action Draft 生成
├── known_events.py          # Planner 向け Known Events
├── config.py                # .env / プロセス環境変数（秘密情報はハードコードしない）
├── event_definitions.json   # GA4 App イベントの開発者宣言定義（例）
├── event_definitions_web.json
├── known_events.json
├── products/                # Product カタログ
│   ├── index.json
│   ├── mahjong.json
│   ├── shopping-memo.json
│   └── nextuta.json
├── requirements.txt
├── Dockerfile               # バックエンド用コンテナイメージ
├── .dockerignore
├── .env.example
├── asc/                     # App Store Connect Analytics + Sales
│   └── sales.py
├── ga4/                     # GA4 App + GA4 Web Data API 取得
├── admob/                   # AdMob Network Report 取得
├── web/                     # Next.js 16 静的エクスポート Web UI
├── scripts/                 # 接続確認・OAuth 補助
│   ├── verify_ga4.py
│   ├── verify_admob.py
│   ├── oauth_admob.py
│   └── list_ga4_events.py
└── secrets/                 # ローカル専用（gitignored）。.p8 / refresh token など
```

## Architecture

詳細な Architecture Diagram（Mermaid）とリクエストフローは **[docs/architecture.md](docs/architecture.md)** を参照してください。

```mermaid
%%{init: {"theme": "neutral"}}%%
flowchart TB
  user([Indie developer])

  subgraph aws ["AWS"]
    amplify["AWS Amplify Hosting<br/>Next.js 16 static export<br/>ja / en UI · Product selector"]
    ecr["Amazon ECR"]
    ecs["Amazon ECS Express Mode<br/>AWS Fargate + ALB HTTPS<br/>FastAPI"]
    strands["Strands Agents SDK"]
    bedrock["Amazon Bedrock<br/>Claude"]
  end

  subgraph external ["External data sources<br/>separate populations — not one funnel"]
    ascAnalytics["App Store Connect Analytics"]
    ascSales["App Store Connect Sales<br/>Developer Proceeds"]
    ga4App["GA4 App"]
    ga4Web["GA4 Web<br/>hostName EXACT"]
    admob["Google AdMob"]
  end

  github["GitHub"] -.->|deploy UI| amplify
  github -.->|container image| ecr
  ecr -.-> ecs

  user -->|Open UI / select Product / Analyze| amplify
  amplify -->|"Browser CORS · POST /api/analyze<br/>body: language + productId"| ecs
  amplify -->|"GET /api/products · POST /api/draft"| ecs

  ecs --> ascAnalytics
  ecs --> ascSales
  ecs --> ga4App
  ecs --> ga4Web
  ecs --> admob

  ecs --> grounding["Data Contract / Grounding<br/>periods · populations · missing ≠ zero<br/>revenue sources not summed"]
  grounding --> strands
  strands -->|ECS Task Role| bedrock
  bedrock --> result["Facts / Speculation<br/>prioritized Top 3 Actions<br/>optional Growth Experiments"]
  result -->|JSON response| amplify
```

**Connected sources → grounded analysis → 1 priority list.** 秘密情報はバックエンドのプロセス環境変数に留めます。Analyze でブラウザが送るのは `{ language, productId }` のみです（API キーは送りません）。任意の Draft は `/api/draft` に実験コンテキストとスクショを送ります。

Mermaid 単体ファイル: [`docs/architecture.mmd`](docs/architecture.mmd)

## Web UI の挙動（現在）

- **初期表示**: 選択 Product の前回成功した Live Analyze（`localStorage`）。なければ空シェルと Analyze 案内
- **最新データを分析**: `POST /api/analyze` で更新し、UI とキャッシュを書き換える
- **Loading / empty / error**: Analyze 中の経過秒、初回成功前の空状態、失敗時の再試行
- **i18n / a11y**: 日本語 / English の UI クロム、focus-visible やラベルの i18n など
- **言語切替**: UI クロムは即切替。**Analyze は再実行せず**、既存の Actions / Facts / Experiments 本文も書き換えない。本文の言語を変えるには、言語を選んだうえで再度 Analyze する

詳細: [`web/README.md`](web/README.md)

## Deployment

| 層 | 採用 |
|----|------|
| Frontend | Next.js 16 **static export** → **AWS Amplify Hosting** |
| Backend | FastAPI コンテナ → **Amazon ECS Express Mode**（AWS Fargate） |
| Image | **Amazon ECR** |
| 公開 API URL | ECS Express Mode が提供する HTTPS endpoint |
| 実行時設定 | プロセスの **環境変数**（`config.py` / `.env`）。ECS では **AWS Secrets Manager** からタスク環境変数へ **注入**しうる（Task Execution Role）。アプリ自身が Secrets Manager API を呼ぶ実装ではない |
| Bedrock | **ECS Task Role**（アプリに長期 AWS アクセスキーを置かない） |
| ECR pull（起動時） | **ECS Task Execution Role** |

Frontend のビルド環境変数: `NEXT_PUBLIC_AGENT_API_URL=<ECS の HTTPS URL>`。Backend の CORS は `CORS_ALLOWED_ORIGINS` に Amplify オリジンを設定します（localhost 既定値はローカル用に残しています）。

使わない構成: App Runner、Amplify SSR、Next.js API Route プロキシ。

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

`.env` に実値を書き、秘密情報は `secrets/` に置きます（どちらも git 管理外）。チャネル ID は Multi-Product では `products/` 側を優先します。

最低限必要なもの:

- **App Store Connect**: Issuer ID / Key ID、対象アプリ / テリトリー（多くは Product JSON）。ローカルは `APP_STORE_CONNECT_PRIVATE_KEY_PATH`（`.p8`）、コンテナは `APP_STORE_CONNECT_PRIVATE_KEY`（PEM 本文。タスク環境変数 / Secrets Manager 注入でも可）
- **Amazon Bedrock（Strands 既定）**: ローカルでは Bedrock を呼べる認証（例: `AWS_REGION` とプロファイル / 環境変数）。ECS では **Task Role** を使い、アクセスキーをリポジトリに置かない
- **GA4 App / Web（任意）**: Property ID + OAuth（`GOOGLE_OAUTH_*` と refresh token）またはサービスアカウント。Web の hostname / key events / featurePaths は製品 JSON
- **AdMob（任意）**: Account ID + 別スコープの refresh token（`scripts/oauth_admob.py`）+ 必要なら App ID

詳細なキー名は `.env.example` を参照してください。Web UI は `web/.env.local` の `NEXT_PUBLIC_AGENT_API_URL` を設定します（`web/README.md` 参照）。

### 3. 動作確認（任意）

```bash
python scripts/verify_ga4.py
python scripts/verify_admob.py
```

## 実行方法

CLI:

```bash
python agent.py
# または
python agent.py --product-id mahjong
```

標準出力に Agent 入力（Data Contract + FACTS）と、Bedrock 経由の回答（Most important finding / Why it matters / Top 3 actions）が流れます。

Web UI（ローカル）:

```bash
# Terminal 1 — API
python api_server.py

# Terminal 2 — 静的エクスポート対応の Next.js
cd web
cp .env.example .env.local   # NEXT_PUBLIC_AGENT_API_URL=http://127.0.0.1:8000
npm install && npm run dev
```

ブラウザは FastAPI を直接呼びます（Next.js API Route プロキシは使いません）:

- `GET /api/products`
- `POST /api/analyze`（`{ language, productId }`）
- `POST /api/draft`（任意の Action Draft）

## Roadmap

### ハッカソン MVP（実装済み）

このリポジトリにすでに含まれているもの:

- Multi-Product カタログ（`products/`）+ Web UI の Product セレクタ
- `GET /api/products`、Analyze `{ language, productId }`、任意の `POST /api/draft`
- App Store Connect Analytics 取得
- App Store Connect Sales Developer Proceeds（任意・別 Revenue ソース）
- GA4 App 取得（設定時のみ）
- GA4 Web 取得（hostname スコープ / Web key events / featurePaths、設定時のみ）
- AdMob Network Report 取得（設定時のみ）
- Strands Agents SDK + Amazon Bedrock による分析
- Facts / Speculation grounding + Revenue 非合算ルール
- Reporting period alignment
- Population scope（GA4 Web ≠ GA4 App を含む）
- Missing data ≠ zero
- 優先順位付き Top 3 Actions
- 任意の Growth Experiments（Planner）+ Action Draft
- Next.js 16 静的エクスポート Web UI（Amplify 向け）: 前回成功レポートのキャッシュ、loading / empty / error、ja / en クロム
- Web UI 向け FastAPI（ローカル / コンテナ）
- コンテナ + Amplify / ECS Express Mode デプロイ対応

### Future Roadmap（未実装）

#### Next

- Google Play / Android 対応
- App Store レビュー
- IAP / サブスクリプション
- RevenueCat 連携

#### Later

- 複数 Product 横断の **ポートフォリオ** 分析（既存の 1 Product セレクタとは別物）
- プロアクティブな成長アラート
- 過去の提案と結果からの学習

#### Long-term vision

Indie Growth Agent は、選択した 1 Product の分析から、インディー開発者の限られた時間を「次にどの Product へ使うべきか」まで一緒に決める成長パートナーへ進化することを目指します。

```
Acquisition → Usage → Feedback → Revenue → Prioritized action
```

現時点では次も未実装です:

- Amazon Bedrock AgentCore（本プロジェクトは Amplify Hosting + ECS Express Mode を使用）
- 生成後の機械的な grounding 検証（スキーマ検証・出典チェック等）
- AdMob メトリクス欠損の明示的ハンドリング（部分欠損を missing として区別する等）

## Known limitations（MVP）

- **Source populations may differ** — カレンダーが揃っていても ASC Analytics / ASC Sales / GA4 App / GA4 Web / AdMob は同一母集団ではない
- **AdMob partial metric missing handling is not implemented** — レスポンス欠落時に「未取得」と「ゼロ」を厳密には区別しない
- **LLM output is grounded by prompt / data contract but not machine-validated after generation** — 出力の事後検証はない
- **Public analyze API** — ECS の HTTPS endpoint はブラウザから直接呼べるため、本番では保護が必要（例: WAF / レート制限）。長時間の Analyze には ALB idle timeout を既定の 60 秒より長くする必要があります
- **Language switch does not regenerate analysis** — UI クロムは即切替。分析本文は次回の Live Analyze までそのまま

## License

MIT License. See [LICENSE](LICENSE).
