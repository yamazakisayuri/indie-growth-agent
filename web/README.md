# Indie Growth Agent — Web UI

Static dashboard (Next.js `output: "export"`). Shows the **last successful Live Analyze** (localStorage, per Product). **Analyze latest data** refreshes via the Python Agent API. Below Top 3 it shows the **evidence revision history** (v1 → v2 → Critic → v3 → Critic) and the **Interventions** panel; `/portfolio` shows every app side by side.

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

1. Initial view → last successful report for the selected Product (or empty prompt)
2. Product list from `GET /api/products` (local fallback catalog if the API is offline)
3. **Analyze latest data** → `POST {NEXT_PUBLIC_AGENT_API_URL}/api/analyze` with `{ language, productId }` → ASC Analytics / ASC Sales / GA4 App / GA4 Web / AdMob (as configured for that Product) + Strands Agents (model from `LLM_PROVIDER`, Bedrock by default) → JSON → UI + localStorage cache
4. Optional **Create Draft** → `POST /api/draft` (experiment context + optional screenshots)
5. **Recorded Demo** entry (top of the dashboard) → `GET /api/evidence/runs?limit=100` → switches to the Recorded Demo's Product, selects the committed `base` run in the revision history, and scrolls to it. No model call and no API keys; the run is read from `samples/recorded/`. There is no standalone Recorded Demo screen
6. **Grounding Critic panel** → `GET /api/evidence/runs?productId=…` and `GET /api/evidence/runs/{runId}` (polled while running). "Run a new verification" → `POST /api/evidence/runs` (asks for confirmation; spends model credits; one run at a time). Recorded Demo and Live Sample runs are labeled and show a fictional-data banner with the review outcome and known limitations
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
npm test        # node --test: portfolio, sample text, Recorded Demo entry
npm run lint
```

## Structure

- `src/lib/report-cache.ts` — last successful report per Product (localStorage)
- `src/lib/map-report.ts` — API → dashboard model (+ empty shell)
- `src/lib/analyze-client.ts` — browser → FastAPI products / analyze (no secrets)
- `src/lib/draft-client.ts` — browser → FastAPI draft
- `src/lib/evidence-client.ts` — browser → FastAPI `/api/evidence`
- `src/lib/interventions-client.ts` — browser → FastAPI `/api/interventions`
- `src/lib/portfolio.ts` — Portfolio cards from cached reports
- `src/lib/demo-entry.ts` — which Recorded Demo the entry opens
- `src/lib/sample-text.ts` — Japanese / English text of Recorded Demo notes
- `src/lib/routes.ts` — `/` (dashboard) and `/portfolio`
- `src/lib/i18n.ts` — UI chrome ja / en
