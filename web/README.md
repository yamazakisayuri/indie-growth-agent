# Indie Growth Agent — Web UI

Static dashboard (Next.js `output: "export"`). Shows the **last successful Live Analyze** (localStorage, per Product). **Analyze latest data** refreshes via the Python Agent API.

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
3. **Analyze latest data** → `POST {NEXT_PUBLIC_AGENT_API_URL}/api/analyze` with `{ language, productId }` → ASC Analytics / ASC Sales / GA4 App / GA4 Web / AdMob (as configured for that Product) + Strands / Bedrock → JSON → UI + localStorage cache
4. Optional **Create Draft** → `POST /api/draft` (experiment context + optional screenshots)

Language control switches UI chrome only. It does **not** re-run Analyze or rewrite existing analysis prose; run Analyze again to refresh body text in the new language.

## Static build

```bash
cd web
npm run build
# artifacts in web/out/
```

## Structure

- `src/lib/report-cache.ts` — last successful report per Product (localStorage)
- `src/lib/map-report.ts` — API → dashboard model (+ empty shell)
- `src/lib/analyze-client.ts` — browser → FastAPI products / analyze (no secrets)
- `src/lib/draft-client.ts` — browser → FastAPI draft
- `src/lib/i18n.ts` — UI chrome ja / en
