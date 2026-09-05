# Indie Growth Agent — Web UI

Local dashboard. Starts on mock data; **Analyze latest data** calls the Python Agent API.

## Setup

```bash
# Terminal 1 — Python API (repo root, venv on)
source .venv/bin/activate
pip install -r requirements.txt
python api_server.py

# Terminal 2 — Next.js
cd web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Optional server-only env in `web/.env.local` (never put secrets here):

```bash
AGENT_API_URL=http://127.0.0.1:8000
```

## Flow

Browser → `POST /api/analyze` (Next.js proxy) → `POST http://127.0.0.1:8000/api/analyze` → existing ASC / GA4 / AdMob fetch + Strands / Bedrock → structured JSON → UI.

## Structure

- `src/mock/report.ts` — offline demo mock (kept)
- `src/lib/map-report.ts` — mock + API → dashboard model
- `src/app/api/analyze/route.ts` — server proxy (no secrets)
- `src/lib/i18n.ts` — UI chrome ja / en
