# Indie Growth Agent

[English](README.md) | [日本語](README.ja.md)

Growth-analysis agent for indie apps (Hackathon MVP).

It pulls observed metrics from **connected Product channels** (App Store Connect Analytics, optional ASC Sales, GA4 App, GA4 Web, AdMob), then returns **prioritized Top 3 Actions**—not a bare metric summary. The runtime is **Strands Agents SDK + Amazon Bedrock**, with a **Next.js static Web UI** (Japanese / English) and a **Multi-Product** catalog (`products/`).

## Problem it solves

Indie developers often check ASC, GA4, and AdMob separately and pick priorities without aligned periods or populations.

This agent:

1. Fetches last-N-day vs prior-N-day facts from the Product’s connected sources
2. Embeds a Data Grounding contract (periods, populations, missing data, no unstated causes, no ungrounded revenue summing)
3. Returns observation-based **Top 3 Actions** (and does not propose unconfirmed analytics features)

The point is not to summarize several dashboards into one narrative. It is to decide **where to start next**, with an explicit priority order, from the facts that are actually connected—for the selected Product.

## Multi-Product

Analysis is scoped to one **Product** at a time (catalog in `products/index.json` + per-product JSON).

- **CLI**: `python agent.py --product-id <id>` (default from `products/index.json`)
- **API**: `GET /api/products` lists products; `POST /api/analyze` accepts `{ language, productId }`
- **Web UI**: Product selector in the header; switching Product loads that Product’s **last successful Analyze** from localStorage (or an empty shell)

**Product selector ≠ portfolio analysis.** Choosing one Product and analyzing it is implemented. Cross-Product portfolio comparison is **not** implemented (see Future Roadmap).

## Data Grounding

These rules are fixed in the system prompt and agent input text:

| Principle | Meaning |
|-----------|---------|
| Reporting period alignment | GA4 and AdMob use the same last-N / prior-N windows anchored on ASC `latest_processing_date` |
| Population scope | ASC Analytics (store / territory), GA4 App (property-wide unless filtered), GA4 Web (`hostName` EXACT when configured), AdMob (configured app ID), and ASC Sales Revenue (worldwide Trends) are **different populations** |
| Missing data ≠ zero | A disconnected source, or a period/day with no rows, is not treated as proven zero performance (stated in the input). This does **not** mean every partial metric gap inside a connected source is classified as missing vs zero |
| Facts / Speculation separation | Only observable numbers are Facts; inferences go in Speculation frames |
| No ungrounded cross-source ratios | No division or funneling across sources unless the input states populations match (e.g. GA4 `ad_impression` ≠ AdMob `IMPRESSIONS`) |
| Revenue sources stay separate | AdMob **ESTIMATED_EARNINGS** and App Store Sales **Developer Proceeds** are different sources (meaning, certainty, currency/scope). They are shown in parallel and **must not be summed** |

LLM output is constrained by the prompt / Data Contract; there is no post-generation machine validation (see Known limitations).

## Connected sources (current)

| Source | Status | What we use |
|--------|--------|-------------|
| App Store Connect Analytics | Required (when App Store channel enabled) | Impressions, product page views, first-time downloads, source breakdown, conversion rates, period-over-period change |
| App Store Connect Sales (Trends) | Optional | Units × **Developer Proceeds** (estimated, not Financial Partner Share); period-over-period change. Scope is typically worldwide and must not be treated as identical to ASC Analytics territory |
| Google Analytics 4 **App** | Optional | activeUsers / sessions / screenPageViews, configured **App** key events, period-over-period change (property-wide unless the product config adds filters) |
| Google Analytics 4 **Web** | Optional | activeUsers / sessions / page views for a configured hostname (`hostName` EXACT), optional **Web** key events / `featurePaths` / page-path scopes, period-over-period change |
| Google AdMob Network Report | Optional | ESTIMATED_EARNINGS / IMPRESSIONS / IMPRESSION_RPM (eCPM) / CLICKS, period-over-period change |

Unset sources are marked `not connected`; values are never invented.

Revenue UI shows AdMob estimated earnings and App Store developer proceeds as **separate** rows—different meaning and certainty; do not add them into one total.

## Repository layout

```
indie-growth-agent/
├── agent.py                 # Shared analysis entry (fetch → format → Bedrock)
├── api_server.py            # FastAPI: /api/products, /api/analyze, /api/draft
├── analysis_schema.py       # Structured Agent / API response models
├── report_builder.py        # Observed metrics + analysis → JSON for the UI
├── format_input.py          # Data Contract / FACTS text builder
├── product_config.py        # Multi-Product catalog loader
├── planner.py               # Optional growth-experiment planner (MCP / playbooks)
├── draft_generator.py       # Action Draft generator
├── known_events.py          # Known product events for Planner context
├── config.py                # Loads .env / process env (no hardcoded secrets)
├── event_definitions.json   # Developer-declared GA4 App event meanings (example)
├── event_definitions_web.json
├── known_events.json
├── products/                # Product catalog
│   ├── index.json
│   ├── mahjong.json
│   ├── shopping-memo.json
│   └── nextuta.json
├── requirements.txt
├── Dockerfile               # Backend container image
├── .dockerignore
├── .env.example
├── asc/                     # App Store Connect Analytics + Sales
│   └── sales.py
├── ga4/                     # GA4 App + GA4 Web Data API fetch
├── admob/                   # AdMob Network Report fetch
├── web/                     # Next.js 16 static-export Web UI
├── scripts/                 # Connection checks / OAuth helpers
│   ├── verify_ga4.py
│   ├── verify_admob.py
│   ├── oauth_admob.py
│   └── list_ga4_events.py
└── secrets/                 # Local only (gitignored): .p8 / refresh tokens, etc.
```

## Architecture

See **[docs/architecture.md](docs/architecture.md)** for the full architecture diagram (Mermaid) and request flow.

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

**Connected sources → grounded analysis → 1 priority list.** Secrets stay on the backend (process environment). The browser sends `{ language, productId }` for Analyze (no API keys). Optional Draft posts experiment context and screenshots to `/api/draft`.

Standalone Mermaid source: [`docs/architecture.mmd`](docs/architecture.mmd)

## Web UI behavior (current)

- **Initial view**: last successful Live Analyze for the selected Product (`localStorage`), or an empty shell prompting Analyze
- **Analyze latest data**: refreshes via `POST /api/analyze`, then updates the UI and cache
- **Loading / empty / error**: Analyze progress (elapsed seconds), empty states before first success, retry on Analyze failure
- **i18n / a11y**: Japanese / English UI chrome; focus-visible and localized labels where applicable
- **Language switch**: changes UI chrome immediately. It does **not** re-run Analyze or rewrite existing analysis prose; Actions / Facts / Experiments stay in the language of the last successful Analyze until the user runs Analyze again

Details: [`web/README.md`](web/README.md)

## Deployment

| Layer | Choice |
|-------|--------|
| Frontend | Next.js 16 **static export** on **AWS Amplify Hosting** |
| Backend | FastAPI container on **Amazon ECS Express Mode** (AWS Fargate) |
| Image | **Amazon ECR** |
| Public API URL | HTTPS endpoint provided by ECS Express Mode |
| Runtime config | Process **environment variables** (`config.py` / `.env`). In ECS, values may be **injected** into the task environment from **AWS Secrets Manager** (Task Execution Role)—the app does not call Secrets Manager APIs itself |
| Bedrock | **ECS Task Role** (no long-lived AWS access keys in the app) |
| ECR pull at startup | **ECS Task Execution Role** |

Frontend build env: `NEXT_PUBLIC_AGENT_API_URL=<ECS HTTPS URL>`. Backend CORS: set `CORS_ALLOWED_ORIGINS` to the Amplify origin (localhost defaults remain for local use).

Not used: App Runner, Amplify SSR, Next.js API Route proxy.

## Setup

### 1. Python environment

Python 3.11+ recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration

```bash
cp .env.example .env
```

Put real values in `.env` and secrets under `secrets/` (both are gitignored). Product channel IDs live under `products/` (preferred over legacy env-only overlays for multi-product).

Minimum requirements:

- **App Store Connect**: Issuer ID / Key ID, target app / territory (often from Product JSON); local `.p8` via `APP_STORE_CONNECT_PRIVATE_KEY_PATH`, or PEM body via `APP_STORE_CONNECT_PRIVATE_KEY` (containers; may be supplied via task env / Secrets Manager injection)
- **Amazon Bedrock (Strands default)**: Locally, credentials that can call Bedrock (e.g. `AWS_REGION` + profile / env vars). On ECS, use the **Task Role**—do not commit access keys
- **GA4 App / Web (optional)**: Property IDs + OAuth (`GOOGLE_OAUTH_*` and refresh token) or a service account; Web hostname / key events / featurePaths come from Product JSON when enabled
- **AdMob (optional)**: Account ID + a separate-scope refresh token (`scripts/oauth_admob.py`) + app IDs when needed

See `.env.example` for key names. For the Web UI, set `NEXT_PUBLIC_AGENT_API_URL` in `web/.env.local` (see `web/README.md`).

### 3. Optional connection checks

```bash
python scripts/verify_ga4.py
python scripts/verify_admob.py
```

## Run

CLI:

```bash
python agent.py
# or
python agent.py --product-id mahjong
```

Stdout prints the agent input (Data Contract + FACTS) and the Bedrock response (Most important finding / Why it matters / Top 3 actions).

Web UI (local):

```bash
# Terminal 1 — API
python api_server.py

# Terminal 2 — static-capable Next.js app
cd web
cp .env.example .env.local   # NEXT_PUBLIC_AGENT_API_URL=http://127.0.0.1:8000
npm install && npm run dev
```

The browser calls FastAPI directly (no Next.js API Route proxy):

- `GET /api/products`
- `POST /api/analyze` with `{ language, productId }`
- `POST /api/draft` (optional Action Draft)

## Roadmap

### Hackathon MVP (implemented)

Already in this repository:

- Multi-Product catalog (`products/`) + Product selector in the Web UI
- `GET /api/products`, Analyze `{ language, productId }`, optional `POST /api/draft`
- App Store Connect Analytics fetch
- App Store Connect Sales Developer Proceeds (optional, separate revenue source)
- GA4 App fetch (optional when configured)
- GA4 Web fetch with hostname scope / Web key events / featurePaths (optional when configured)
- AdMob Network Report fetch (optional when configured)
- Strands Agents SDK + Amazon Bedrock analysis
- Facts / Speculation grounding + revenue non-summing rules
- Reporting period alignment
- Population scope (including GA4 Web ≠ GA4 App)
- Missing data ≠ zero
- Prioritized Top 3 Actions
- Optional Growth Experiments (Planner) + Action Draft
- Next.js 16 static-export Web UI (Amplify-ready): last successful report cache, loading / empty / error, ja / en chrome
- FastAPI for the Web UI (local / container)
- Container + Amplify / ECS Express Mode deployment support

### Future Roadmap (not implemented)

#### Next

- Google Play / Android support
- App Store reviews
- IAP / subscriptions
- RevenueCat integration

#### Later

- Cross-Product **portfolio** analysis (compare / prioritize across Products—not the same as the existing single-Product selector)
- Proactive growth alerts
- Historical learning from previous recommendations and outcomes

#### Long-term vision

Indie Growth Agent should evolve from analyzing one selected Product into a growth partner for indie developers that helps decide not only what action to take, but which Product deserves the developer's limited time next.

```
Acquisition → Usage → Feedback → Revenue → Prioritized action
```

Also still out of scope for now:

- Amazon Bedrock AgentCore (this project uses Amplify Hosting + ECS Express Mode instead)
- Post-generation machine grounding checks (schema / citation validation, etc.)
- Explicit AdMob partial-metric missing handling (distinguish missing vs zero)

## Known limitations (MVP)

- **Source populations may differ** — matching calendars do not make ASC Analytics / ASC Sales / GA4 App / GA4 Web / AdMob the same population
- **AdMob partial metric missing handling is not implemented** — response gaps are not strictly distinguished from true zeros
- **LLM output is grounded by prompt / data contract but not machine-validated after generation** — no post-hoc output validator
- **Public analyze API** — the ECS HTTPS endpoint is callable from the browser; protect it in production (e.g. WAF / rate limits). Long-running Analyze also needs an ALB idle timeout above the default 60s
- **Language switch does not regenerate analysis** — UI chrome switches immediately; analysis body stays until the next Live Analyze

## License

MIT License. See [LICENSE](LICENSE).
