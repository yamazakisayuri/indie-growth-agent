# Indie Growth Agent — Web UI

Static site (Next.js `output: "export"`). `/` has two workspaces that never mix data: the **Sample Workspace** (opened first; fictional sample built from `samples/` at build time, no API or model call) and **My Workspace** (the **last successful Live Analyze**, localStorage per Product; **Analyze latest data** refreshes via the Python Agent API; below Top 3, the **evidence revision history** (v1 → v2 → Critic → v3 → Critic) and the **Interventions** panel). `/demo` shows the committed Recorded Demos; `/portfolio` shows every app side by side.

## Setup

```bash
# Terminal 1 — Python API (repo root, venv on)
source .venv/bin/activate
pip install -r requirements.txt
python api_server.py

# Terminal 2 — Next.js
cd web
cp .env.example .env.local   # NEXT_PUBLIC_AGENT_API_URL=http://127.0.0.1:8000
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Browser-visible env only (never put secrets here):

```bash
NEXT_PUBLIC_AGENT_API_URL=http://127.0.0.1:8000
```

## Flow

0. **Sample Workspace** (`/`, default) → no request; built at build time by `src/lib/load-sample-workspace.ts` from `samples/mahjong/*.csv` and the `base` Recorded Demos in `samples/recorded/`. KPIs (last 7 days vs previous 7), 14-day trends with Known Events, the traffic-source table, the representative Recorded Demo's final Top 3 (cited claims and known limitations under each action), and its Critic counts. The switch to My Workspace is kept in localStorage
1. **My Workspace** initial view → last successful report for the selected Product (or a guide to the first Analyze)
2. Product list from `GET /api/products` (local fallback catalog if the API is offline)
3. **Analyze latest data** → `POST {NEXT_PUBLIC_AGENT_API_URL}/api/analyze` with `{ language, productId }` → ASC Analytics / ASC Sales / GA4 App / GA4 Web / AdMob (as configured for that Product) + Strands Agents (model from `LLM_PROVIDER`, Bedrock by default) → JSON → UI + localStorage cache
4. Optional **Create Draft** → `POST /api/draft` (experiment context + optional screenshots)
5. **Recorded Demo** (`/demo`, header link) → `GET /api/evidence/runs?limit=100` and `GET /api/evidence/runs/{runId}` → opens the representative `base` run in both UI languages: the English `sample-base-20261025-110333`, marked `"representative": true` in its `.sample.json` (converged, 0 unresolved findings, final Critic SQL checks 31 matched / 0 mismatched / 1 unverifiable). The scenario switch offers one run per scenario; `competitor-variant` exists only in Japanese. When the model output language differs from the UI language, the switch and the page say so; model output is never translated, while UI labels and review notes follow the UI language. The Japanese `base` run (`sample-base-20261024-214121`: `max_rounds`, 1 unresolved finding) stays in `samples/recorded/` and in the API list, but is not offered as a second `base`. In the English UI, a few Japanese terms from the sample get a marked gloss (`[translation: …]`, `src/lib/sample-glossary.ts`) next to the unchanged original. The page reads: what the demo is → **What happened in the app** (three bar charts of the fictional data, previous vs last 7 days, each on its own zero-based scale; computed at build time in `src/app/demo/page.tsx` and shown only when the run's `.sample.json` digests and periods match those CSVs) → how the proposals changed (v1 — Own App Data → v2 — Competitor Context → v3 — Critic-Reviewed Actions, titles only) → **Final Top 3 Actions — v3** at full width (reason, cited claims, known limitations under each action) → what the Critic questioned and how the Analyst answered, with SQL checks judged by code (matched / mismatched / unverifiable), the outcome and unresolved count → SQL evidence and the full log, both collapsed. No model call and no API keys; the run is read from `samples/recorded/`, so the Agent API must be running
6. **Grounding Critic panel** (My Workspace) → `GET /api/evidence/runs?productId=…` and `GET /api/evidence/runs/{runId}` (polled while running). "Run a new verification" → `POST /api/evidence/runs` (asks for confirmation; spends model credits; one run at a time). Only real-data runs are listed; Recorded Demo and Live Sample runs (same product id) are left out. SQL checks are shown as judged by code, and the Critic's summary is labeled as model-generated
7. **Adopt** an action of a finished real-data run → `POST /api/interventions/adopt` (fictional sample runs are refused)
8. **Interventions panel** → `GET /api/interventions?productId=…`, add by hand (`POST /api/interventions`), mark implemented / record verdict / re-measure / drop (`POST /api/interventions/{id}/implement | evaluate | measure | drop`). Before / after numbers are measured by the API with SQL; the verdict is yours
9. **Portfolio** (`/portfolio`, header link) → one card per Product from the localStorage cache only. It does not call Analyze, generate values, or compare Products

Language control switches UI chrome only (kept across pages). It does **not** re-run Analyze or rewrite existing analysis prose; run Analyze again to refresh body text in the new language.

## Static build

```bash
cd web
npm run build
# artifacts in web/out/
```

## Tests

```bash
cd web
npm test        # node --test: portfolio, sample text, Recorded Demo story and choice, Critic checks, Sample Workspace, glosses, snapshot
npm run lint
```

## Structure

- `src/components/HomeApp.tsx` — `/`: Sample Workspace / My Workspace switch
- `src/components/SampleWorkspace.tsx`, `src/lib/sample-workspace.ts`, `src/lib/load-sample-workspace.ts` — Sample Workspace (fictional CSVs and Recorded Demo summary, read at build time)
- `src/components/MyWorkspace.tsx` — My Workspace (Live Analyze, as the former dashboard page)
- `src/components/SampleSnapshot.tsx` — "What happened in the app" charts on `/demo`
- `src/components/ActionDetails.tsx` — cited claims and known limitations under a recorded action (`/demo` and Sample Workspace)
- `src/lib/sample-glossary.ts` — English display name and glosses for the fictional sample (UI translations only)
- `src/lib/report-cache.ts` — last successful report per Product and the chosen workspace (localStorage)
- `src/lib/map-report.ts` — API → dashboard model (+ empty shell)
- `src/lib/analyze-client.ts` — browser → FastAPI products / analyze (no secrets)
- `src/lib/draft-client.ts` — browser → FastAPI draft
- `src/lib/evidence-client.ts` — browser → FastAPI `/api/evidence`
- `src/lib/interventions-client.ts` — browser → FastAPI `/api/interventions`
- `src/lib/portfolio.ts` — Portfolio cards from cached reports
- `src/lib/recorded-demo.ts` — which Recorded Demo `/demo` opens (the representative run per scenario), and the proposal → Critic → answer story built from its trace
- `src/lib/sample-text.ts` — Japanese / English text of Recorded Demo notes
- `src/lib/routes.ts` — `/` (Sample Workspace / My Workspace), `/portfolio`, and `/demo`
- `src/lib/i18n.ts` — UI chrome ja / en
