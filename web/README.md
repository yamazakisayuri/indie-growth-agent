# Indie Growth Agent — Web UI

Static dashboard (Next.js `output: "export"`). Starts on mock data; **Analyze latest data** calls the Python Agent API directly.

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

Browser → `POST {NEXT_PUBLIC_AGENT_API_URL}/api/analyze` → ASC / GA4 / AdMob fetch + Strands / Bedrock → structured JSON → UI.

## Static build

```bash
cd web
npm run build
# artifacts in web/out/
```

## Structure

- `src/mock/report.ts` — offline demo mock (kept)
- `src/lib/map-report.ts` — mock + API → dashboard model
- `src/lib/analyze-client.ts` — browser → FastAPI (no secrets)
- `src/lib/i18n.ts` — UI chrome ja / en
