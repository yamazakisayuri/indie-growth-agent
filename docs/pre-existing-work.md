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

## Built during the hackathon

Based on the commits from `1a9ae83` (2026-10-23) onward on `open-agent-2026` (see the `git log` command above). Track: **Track 2 — The Agent That Can Explain Why**.

- **Offline verification and provider plumbing** (`a15d740`, `0b7ec12`, `5a9a7f5`, `48252d9`): `scripts/verify_offline.py`; every Strands Agent goes through `llm.build_model()`; generic OpenAI-compatible provider; list fields sent as JSON strings accepted
- **Evidence foundation** (`ac40a47`, `331fc9f`, `aa18c88`): evidence schema (claims, Critic findings, runs, decisions), evidence store interface with SQLite and a read-only SQL guard, evidence tables from ASC daily data / Known Events / iTunes Lookup competitor listings (`scripts/export_evidence.py`)
- **Zetaris** (`1125c12`): evidence store backend over JDBC, CSV staging into the Zetaris container, Lightning filestore tables
- **Grounding Critic and the revision loop** (`c74f637`, `728a95e`, `c822ceb`, `f855f75`, `b35aa36`, `055062f`, `e4382d3`, `9f7d574`, `e47b6ad`): v1 → v2 → Critic → v3 → Critic; code re-runs cited SQL and compares every value; Analyst answers with numeric facts but no SQL, or revisions that drop every action without a reason, are rejected
- **Decision memory** (`8f23144`, `9ae9ba4`, `db05b16`, `9f9de82`, `1de325b`): `none` / `local` backends, Meterless H-MEM backend (vendored reference, Node sidecar), past decisions and evaluated outcomes recalled as Analyst context only
- **Interventions** (`a91bb7d`, `3d19cbb`, `22efb01`): adopt an AI action or register by hand, before/after measured by SQL, human verdict; `/api/interventions`; Interventions panel
- **Evidence API and Web UI** (`e03fe9b`, `28c24e2`, `69e719b`, `f26e30d`): `/api/evidence` (list / read / start runs), revision-history panel under Top 3, Portfolio Overview (display of each app's saved Live Analyze; no cross-app analysis), UI language kept across pages
- **Meterless Nightshift / NVIDIA Nemotron** (`3e0991f`): `LLM_PROVIDER=meterless`, pinned to `nvidia/nemotron-3-ultra-550b-a55b`, runtime status check (`scripts/check_meterless.py`), provider errors with details and one retry for retryable failures
- **Sample mode and Recorded Demo** (`aea5f32`, `d0afcf0`, `0c4ff7b`, `faf589e`, `369ac58`, `74e3fe1`, `d23c927`): fictional mahjong sample with `base` and `competitor-variant` scenarios, Live Sample on a dedicated SQLite file, two committed Recorded Demo traces with review notes, labeled runs in the revision history, CLI viewer (`scripts/show_sample_demo.py`)
- **Recorded Demo page `/demo`** (`6b9d315`, `561071b`, `af50f95`):
  - `6b9d315` first added a Recorded Demo entry button at the top of the dashboard that opened the run inside the Grounding Critic panel
  - `561071b` replaced it with a separate page, `/demo`, linked from the dashboard header next to Portfolio; the dashboard went back to showing real analysis results. `/demo` reads the committed run as a story: what the demo is, how the v1 / v2 / v3 proposals changed, what the Critic questioned and how the Analyst answered, and the outcome with the unresolved count and known limitations; SQL evidence and the full log are collapsed. A `base` / `competitor-variant` switch selects the run
  - `af50f95` marks a finding as a known misjudgment (confirmed in review after the run) when the Recorded Demo's known limitations name that finding and its kind (`base`: `r2-f1`; `competitor-variant`: `r2-f1`, `r2-f2`), and labels the kind as the recorded classification. The trace, the Critic text, and the unresolved count are unchanged. `.gitignore` now ignores only the root `demo/`, so `web/src/app/demo/` is tracked normally
  - Viewing needs no model call and no API key; the page reads the traces from the local `api_server.py`
- **Evidence loop speed** (`f83beed`): Analyst prompts query before writing claims, the SQL tool reports the queries left, the Analyst / Critic models make no silent SDK retries (the app's one logged retry remains), and v2 / v3 receive the previous version as compact JSON. The effect on run time has not been measured yet
- **Documentation** (`1a9ae83`, `4f9d832`, `7c0cf31`, `669be4a`, `515337b`, and this update): pre-existing work, commit range, README (ja / en) with Quick Demo and the Critic success example, the retired AWS deployment described as past, architecture

### Not finished at the time of writing

- Faster evidence runs: the Recorded Demos took about 15 and 24 minutes; `f83beed` cuts wasted model round trips, but no run has measured the effect yet
- The Recorded Demos ended at the review limit (`max_rounds`) with unresolved Critic findings, some of them known false judgments (see each `samples/recorded/*.sample.json`, and the Known misjudgment marks on `/demo`)
