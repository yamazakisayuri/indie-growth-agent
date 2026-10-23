# Pre-existing work (Open Agent Hackathon 2026)

Everything up to the tag [`open-agent-baseline`](https://github.com/yamazakisayuri/indie-growth-agent/tree/open-agent-baseline) (commit `40afb4a`, committed 2026-10-04) was built **before** the development period, which opened on 2026-10-22 00:00 UTC.

There are no commits between `open-agent-baseline` (2026-10-04) and the start of the development period (2026-10-22 00:00 UTC). Hackathon work lives on the [`open-agent-2026`](https://github.com/yamazakisayuri/indie-growth-agent/tree/open-agent-2026) branch: the commits that come after the tag **and** have a commit date on or after 2026-10-22 00:00 UTC:

```bash
git log --since="2026-10-22T00:00:00Z" open-agent-baseline..open-agent-2026
```

## Prior submission

The first version of this project was submitted to **Agents for Humans Hackathon** (Devpost, judging ended 2026-10-09). That submission corresponds to commit `00111b4` (2026-09-06).

## Pre-existing features

### Built for Agents for Humans Hackathon (2026-09-05 – 09-06, up to `00111b4`)

- Data fetchers for App Store Connect Analytics (`asc/`), GA4 (`ga4/`) and AdMob Network Report (`admob/`), plus connection-check / OAuth scripts (`scripts/`)
- Single-agent analysis on Strands Agents SDK + Amazon Bedrock (`agent.py`): last-N vs prior-N days → Top 3 Actions
- Data Grounding contract in the prompt / agent input (`format_input.py`): aligned reporting periods, separate populations, missing ≠ zero, Facts vs Speculation, no cross-source ratios
- FastAPI backend (`api_server.py`) and Next.js static-export Web UI (`web/`, Japanese / English)
- Dockerfile and AWS deployment setup (Amplify Hosting + ECS Express Mode), architecture docs (`docs/architecture.*`)

### Added after that submission, before this hackathon (2026-09-26 – 10-04, `27a1c2d` – `40afb4a`)

- Multi-Product catalog (`products/`, `product_config.py`) for mahjong / shopping-memo / nextuta, with a Product selector in the Web UI
- Revenue-aware analysis: App Store Connect Sales Developer Proceeds (`asc/sales.py`), shown separately from AdMob estimated earnings (never summed)
- GA4 Web signals (hostname scope, Web key events, feature paths) and developer-declared event meanings (`event_definitions*.json`, `known_events.*`, `store_context.py`)
- Growth experiment Planner (`planner.py`) that calls Growth Agent MCP playbooks, and Action Draft generator (`draft_generator.py`, `POST /api/draft`)
- Daily analyze cache with single-flight protection (`analyze_cache.py`, `scripts/verify_analyze_cache.py`)
- Web UI: Growth Experiments panel, last-successful-report cache, loading / empty / error states
- Fixes: ASC Analytics daily-report double counting, App Store metrics across all territories

### Not in the repository

- `demo/`: local planner run outputs and the Agents for Humans demo rough cut (gitignored, not reused as the Open Agent demo)

## Third-party dependencies

- [Growth Agent MCP](https://www.npmjs.com/package/growth-agent-mcp) (MIT, third-party OSS): marketing playbook / calculator provider used by the Planner via MCP
- Strands Agents SDK, Amazon Bedrock, FastAPI, Next.js and the other packages in `requirements.txt` / `web/package.json`

### Preparation before the development period (not in the repository)

- Zetaris: local JDBC connection check (`SELECT 1`) on 2026-10-20. Environment setup only; no code from this check is committed.

## Planned hackathon additions

**Not implemented yet.** This section lists the planned scope. Before submission it will be replaced by a "Built during the hackathon" section based on the actual commits (see the `git log` command above).

- Long-term product spine remains Top 3 → measure (adopt AI or register manually) → baseline → effect measurement
- Hackathon focus: Competitive Evidence for the mahjong app — SQL-verified claims via Zetaris + Grounding Critic (v1→v2→Critic→v3)
- Competitive analysis is a means to make proposals concrete, not a must-have for every app
- Zetaris: CSV ingest and real aggregations
- Meterless / Nemotron wiring
- `SAMPLE_MODE` with sample CSV for the mahjong demo scenario (not three products)
