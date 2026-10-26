# Pre-existing work (Open Agent Hackathon 2026)

Everything up to the tag [`open-agent-baseline`](https://github.com/yamazakisayuri/indie-growth-agent/tree/open-agent-baseline) (commit `cc51083`, committed 2026-10-04) was built **before** the development period, which opened on 2026-10-22 00:00 UTC.

There are no commits between `open-agent-baseline` (2026-10-04) and the start of the development period (2026-10-22 00:00 UTC). Hackathon work lives on the [`open-agent-2026`](https://github.com/yamazakisayuri/indie-growth-agent/tree/open-agent-2026) branch: the commits that come after the tag **and** have a commit date on or after 2026-10-22 00:00 UTC:

```bash
git log --since="2026-10-22T00:00:00Z" open-agent-baseline..open-agent-2026
```

## Prior submission

The first version of this project was submitted to **Agents for Humans Hackathon** (Devpost, judging ended 2026-10-09). That submission corresponds to commit `ebf9e12` (2026-09-06). The Devpost submission cites that commit by its hash from before the history rewrite described below.

## Commit hashes

On 2026-10-26 the history of this repository was rewritten to replace the commit email address with a GitHub noreply address. Only the author, committer, and tagger email changed: names, author and commit dates, file contents, and the `open-agent-baseline` tag message are unchanged, and commit messages differ only in the commit hashes they cite. Every commit hash changed, and the hashes in this document are the new ones.

## Pre-existing features

### Built for Agents for Humans Hackathon (2026-09-05 – 09-06, up to `ebf9e12`)

- Data fetchers for App Store Connect Analytics (`asc/`), GA4 (`ga4/`) and AdMob Network Report (`admob/`), plus connection-check / OAuth scripts (`scripts/`)
- Single-agent analysis on Strands Agents SDK + Amazon Bedrock (`agent.py`): last-N vs prior-N days → Top 3 Actions
- Data Grounding contract in the prompt / agent input (`format_input.py`): aligned reporting periods, separate populations, missing ≠ zero, Facts vs Speculation, no cross-source ratios
- FastAPI backend (`api_server.py`) and Next.js static-export Web UI (`web/`, Japanese / English)
- Dockerfile and AWS deployment setup (Amplify Hosting + ECS Express Mode), architecture docs (`docs/architecture.*`)

### Added after that submission, before this hackathon (2026-09-26 – 10-04, `aa0164c` – `cc51083`)

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

Based on the commits from `68f54f2` (2026-10-23) onward on `open-agent-2026` (see the `git log` command above). Track: **Track 2 — The Agent That Can Explain Why**.

- **Offline verification and provider plumbing** (`75435d0`, `1b170f2`, `df268f1`, `a1d1a5a`): `scripts/verify_offline.py`; every Strands Agent goes through `llm.build_model()`; generic OpenAI-compatible provider; list fields sent as JSON strings accepted
- **Evidence foundation** (`9bf7894`, `1c8cee8`, `062f869`): evidence schema (claims, Critic findings, runs, decisions), evidence store interface with SQLite and a read-only SQL guard, evidence tables from ASC daily data / Known Events / iTunes Lookup competitor listings (`scripts/export_evidence.py`)
- **Zetaris** (`1722426`): evidence store backend over JDBC, CSV staging into the Zetaris container, Lightning filestore tables
- **Grounding Critic and the revision loop** (`3561a7f`, `8223f8f`, `bf9180c`, `9f8160b`, `d207672`, `79887b0`, `6393167`, `482db60`, `53f6670`): v1 → v2 → Critic → v3 → Critic; code re-runs cited SQL and compares every value; Analyst answers with numeric facts but no SQL, or revisions that drop every action without a reason, are rejected
- **Decision memory** (`5696d70`, `d725ba7`, `5dadd40`, `52a64ea`, `fa31f01`): `none` / `local` backends, Meterless H-MEM backend (vendored reference, Node sidecar), past decisions and evaluated outcomes recalled as Analyst context only
- **Interventions** (`a1cc606`, `510c41d`, `5bb8603`): adopt an AI action or register by hand, before/after measured by SQL, human verdict; `/api/interventions`; Interventions panel
- **Evidence API and Web UI** (`cc9324c`, `136bf1b`, `2a1c333`, `3ee4531`): `/api/evidence` (list / read / start runs), revision-history panel under Top 3, Portfolio Overview (display of each app's saved Live Analyze; no cross-app analysis), UI language kept across pages
- **Meterless Nightshift / NVIDIA Nemotron** (`be19e4b`): `LLM_PROVIDER=meterless`, pinned to `nvidia/nemotron-3-ultra-550b-a55b`, runtime status check (`scripts/check_meterless.py`), provider errors with details and one retry for retryable failures
- **Sample mode and Recorded Demo** (`6e019e6`, `329d671`, `3de6b0f`, `53c9d2e`, `5f3d366`, `3142b81`, `cb0a94f`): fictional mahjong sample with `base` and `competitor-variant` scenarios, Live Sample on a dedicated SQLite file, committed Recorded Demo traces with review notes (Japanese `base` and `competitor-variant`; an English `base` added in this update), labeled runs in the revision history, CLI viewer (`scripts/show_sample_demo.py`)
- **Recorded Demo page `/demo`** (`c1bbc3e`, `f884d3d`, `cf8ff29`):
  - `c1bbc3e` first added a Recorded Demo entry button at the top of the dashboard that opened the run inside the Grounding Critic panel
  - `f884d3d` replaced it with a separate page, `/demo`, linked from the dashboard header next to Portfolio; the dashboard went back to showing real analysis results. `/demo` reads the committed run as a story: what the demo is, how the v1 / v2 / v3 proposals changed, what the Critic questioned and how the Analyst answered, and the outcome with the unresolved count and known limitations; SQL evidence and the full log are collapsed. A `base` / `competitor-variant` switch selects the run
  - `cf8ff29` marks a finding as a known misjudgment (confirmed in review after the run) when the Recorded Demo's known limitations name that finding and its kind (`base`: `r2-f1`; `competitor-variant`: `r2-f1`, `r2-f2`), and labels the kind as the recorded classification. The trace, the Critic text, and the unresolved count are unchanged. `.gitignore` now ignores only the root `demo/`, so `web/src/app/demo/` is tracked normally
  - This update: the English `base` run `sample-base-20261025-110333` is the representative trace (`"representative": true` in its `.sample.json`). `/demo` and the Sample Workspace's Top 3 Actions show it in both UI languages; in the Japanese UI its model output stays in English, while UI labels and review notes switch language. The Japanese `base` run `sample-base-20261024-214121` and the Japanese-only `competitor-variant` run stay committed unchanged; the English UI says that `competitor-variant`'s model output is Japanese
  - Viewing needs no model call and no API key; the page reads the traces from the local `api_server.py`
- **Sample Workspace and the submission UI** (this update): `/` opens a read-only Sample Workspace built from the fictional sample at build time, kept apart from My Workspace (the former dashboard; its revision history now lists real-data runs only). Critic SQL checks are shown as judged by code (matched / mismatched / unverifiable) and the Critic's summary is labeled as model-generated. `/demo` starts with three charts of the fictional data, compares the v1 / v2 / v3 titles, and shows the final Top 3 at full width with cited claims and known limitations; English UI labels, the sample app's English name, and marked glosses for Japanese terms are display-only (traces, SQL, claims, and Critic results unchanged)
- **Evidence loop speed** (`7beed42`): Analyst prompts query before writing claims, the SQL tool reports the queries left, the Analyst / Critic models make no silent SDK retries (the app's one logged retry remains), and v2 / v3 receive the previous version as compact JSON. Its effect on run time has not been measured in a like-for-like comparison (see below)
- **Documentation** (`68f54f2`, `51eb987`, `4f6f327`, `338d739`, `5af87ad`, and this update): pre-existing work, commit range, README (ja / en) with Quick Demo and the Critic success example, the retired AWS deployment described as past, architecture

### Not finished at the time of writing

- Faster evidence runs: the Japanese Recorded Demos took about 15 (`base`) and 24 (`competitor-variant`) minutes. The English `base` run, started after `7beed42` and `5d36f7f` were committed, took about 9.5 minutes; one run, in another language and on later code, cannot show how much of the difference `7beed42` caused
- Review outcomes differ by run (see each `samples/recorded/*.sample.json`):
  - English `base` (`sample-base-20261025-110333`): converged, 0 unresolved findings; the final Critic SQL checks were 31 matched, 0 mismatched, 1 unverifiable (the check could not be compared; it is not a mismatch). Two known limitations in its v3 actions (#3 and #1) were found in review after the run, not by the Critic. One converged run does not show that runs converge in general
  - Japanese `base` (`sample-base-20261024-214121`): stopped at the review limit (`max_rounds`) with 1 unresolved finding, filed under a kind that does not fit its content (described in its `.sample.json`)
  - Japanese `competitor-variant` (`sample-competitor-variant-20261024-220111`): `max_rounds` with 8 unresolved findings, 2 of them known false judgments (marked on `/demo` as Known misjudgment)
