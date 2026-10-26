# Indie Growth Agent

[English](README.md) | [日本語](README.ja.md)

Growth-analysis agent for indie apps (Hackathon MVP, extended for **Open Agent Hackathon 2026 — Track 2 "The Agent That Can Explain Why"**).

## Quick Demo (30 seconds)

**What it does.** The agent proposes the next growth actions for an indie app. Every evidence value behind a proposal must come with SQL that reproduces it. An independent **Critic** re-checks those values with SQL it writes itself, **code** decides whether they match, and the Analyst revises (v1 → v2 → Critic → v3 → Critic). Numbers written only in claim text or action reasons are not checked ([SQL check scope](#what-the-checks-cover-and-what-converged--resolved-mean)). Actions a person adopts are measured before/after by SQL, and the result feeds the next analysis.

**What it caught.** In the `competitor-variant` Recorded Demo, v2 reported the page-view → download rate as 5.0 → 6.67, which reads as an improvement. The Analyst's SQL had numerator and denominator swapped, and re-running that SQL returns the same wrong numbers. The Critic's own SQL found the real rate: it **fell from 20.0% to 15.0%**. The wrong numbers had also reached the #1 action's success criterion. v3 fixed both, and the second review matched every value ([details](#example-what-the-critic-caught-and-how-the-analyst-fixed-it)).

**Why this matters.** The model is not trusted to grade itself: the Critic never sees the Analyst's SQL or reasoning, value matches are decided by code, and findings that remain open are shown as unresolved instead of being hidden.

**Replay it (no API key, no model call, no `.env`):**

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python scripts/show_sample_demo.py     # every Recorded Demo: v1/v2/v3 Top 3, Critic counts, review notes
```

To see the proposals, the Critic's findings, and the SQL behind them, use the Web UI. The Recorded Demo page needs **no model call and no API key**, but it reads the saved runs from the local API server, so `api_server.py` must be running. The API starts without any model settings (`scripts/verify_api_without_model.py` checks this for each provider); only Analyze needs them:

```bash
python api_server.py                       # terminal 1
cd web && npm install && npm run dev       # terminal 2
```

1. Open `http://localhost:3000`. It opens the **Sample Workspace** (fictional data, no AI run); click **Recorded Demo** in the header to open the separate Recorded Demo page, `/demo`.
2. `/demo` opens the English `base` run in either UI language. For the example above, switch to **competitor-variant** (its model output is Japanese, and the page says so).
3. Read top to bottom: what happened in the app (three small charts of the fictional data) → how the v1 / v2 / v3 proposals changed → the final Top 3 with cited claims and known limitations → what the Critic questioned and how the Analyst answered (`r1-f3`, `r1-f7`, `r1-f13` in Critic round 1) → the outcome with the unresolved count. Findings later confirmed as wrong are marked **Known misjudgment**.
4. **SQL evidence** and the **Full log** (each version's claims, the Critic's SQL and values) are collapsed at the bottom.

**Where to look**

| To see | Look at |
|--------|---------|
| The loop and the guards | [`evidence/loop.py`](evidence/loop.py), [`evidence/critic.py`](evidence/critic.py) (code-side checks), [`evidence/agents.py`](evidence/agents.py) (independent Critic) |
| The example above, raw | [`samples/recorded/sample-competitor-variant-20261024-220111.json`](samples/recorded/sample-competitor-variant-20261024-220111.json): v2 Critic findings `r1-f3`, `r1-f7`, `r1-f13`, and v3 `findingResponses` |
| What is still not verified | Each `samples/recorded/*.sample.json` (review outcome, known limitations) and [Known limitations](#known-limitations-mvp) |
| Measurement and feedback | [`interventions/`](interventions/), [`memory/recall.py`](memory/recall.py) |
| Sponsor integrations | [`integrations/zetaris/`](integrations/zetaris/), [`integrations/meterless/`](integrations/meterless/), [`integrations/hmem/`](integrations/hmem/) |

**Contents:** [Track 2](#open-agent-hackathon-2026--track-2-the-agent-that-can-explain-why) · [Evidence loop](#evidence-revision-loop-v1--v2--critic--v3--critic) · [Interventions](#interventions-measurement-human-evaluation-and-feedback) · [Sponsor technologies](#sponsor-technologies-and-their-roles) · [Portfolio Overview](#portfolio-overview-display-vs-portfolio-analysis-not-implemented) · [Sample data and Recorded Demo](#sample-data-live-sample-and-recorded-demo) · [Architecture](#architecture) · [Setup](#setup) · [Run](#run) · [Tests](#tests) · [Roadmap](#roadmap) · [Known limitations](#known-limitations-mvp)

## Overview

It pulls observed metrics from **connected Product channels** (App Store Connect Analytics, optional ASC Sales, GA4 App, GA4 Web, AdMob), then returns **prioritized Top 3 Actions**—not a bare metric summary. The runtime is **Strands Agents SDK** with a selectable model provider (**Amazon Bedrock** by default; **Meterless Nightshift → NVIDIA Nemotron** for the hackathon runs), with a **Next.js static Web UI** (Japanese / English) and a **Multi-Product** catalog (`products/`).

For the hackathon it adds an **evidence revision loop**: an Analyst proposes actions with claims, every evidence value in a claim must come with SQL that reproduces it on an evidence store (**Zetaris** for real data; see [what this repository can show](#meterless-and-zetaris-what-this-repository-can-show)), an independent **Grounding Critic** checks the claims with its own SQL, and the Analyst revises (v1 → v2 → Critic → v3 → Critic). Adopted actions are tracked as **interventions** with before/after numbers measured by SQL and a human verdict, and those outcomes are fed back to the next Analyst through **Meterless H-MEM** decision memory.

## Open Agent Hackathon 2026 — Track 2: The Agent That Can Explain Why

The track asks for an agent that can show **why** it recommends something, not just what. In this project "why" means:

- Each proposed action points at **claims**, and each claim is labeled **fact** (our own data), **observation** (public data about other apps), or **hypothesis** (needs a test plan)
- Every evidence value of a fact or observation carries the **SQL that reproduces it** on the evidence store (numbers written only in claim text or action reasons are not checked)
- A separate **Critic** re-checks those values with SQL it writes itself; whether a value matches is decided by **code**, never by a model
- The full revision history (v1, v2, Critic findings, v3, the second review, unresolved findings) is saved as a trace and shown in the Web UI
- After a person acts on a proposal, the measured result and their verdict become context for the next analysis

### Built during the hackathon (this repository, `open-agent-2026` branch)

| Area | What was added |
|------|----------------|
| Evidence loop | Evidence schema, read-only SQL guard, SQLite and Zetaris evidence stores, evidence tables from ASC daily data / Known Events / competitor listings, Analyst + Grounding Critic loop (`evidence/`) |
| Model provider | Every Strands Agent goes through `llm.build_model()`: `bedrock` (default), `openai_compatible`, `meterless` (Meterless Nightshift, pinned to NVIDIA Nemotron 3 Ultra) |
| Interventions | Adopt an AI action or register one by hand; implement → evaluate lifecycle; before/after measured by SQL; human verdict (`interventions/`, `scripts/interventions.py`) |
| Decision memory | `none` / `local` (JSONL) / `hmem` (Meterless H-MEM reference, Node sidecar). Past decisions and outcomes are recalled before each evidence run (`memory/`, `integrations/hmem/`) |
| API | `/api/evidence` (list / read / start runs), `/api/interventions` (adopt, add, implement, evaluate, measure, drop) |
| Web UI | Sample Workspace / My Workspace on `/`, Grounding Critic revision-history panel, Interventions panel, Portfolio Overview (`/portfolio`), Recorded Demo page (`/demo`) |
| Sample mode | Fictional mahjong sample CSVs with two scenarios, Live Sample runs on a dedicated SQLite file, three committed Recorded Demo traces with review notes (English `base`; Japanese `base` and `competitor-variant`) |
| Tests | `scripts/verify_offline.py` runs 19 offline checks (no credentials, network, or model) |

Everything before the hackathon (Analyze, Data Grounding, Multi-Product, ASC / GA4 / AdMob fetchers, Planner, Draft, AWS deployment) is listed in [`docs/pre-existing-work.md`](docs/pre-existing-work.md).

## Problem it solves

Indie developers often check ASC, GA4, and AdMob separately and pick priorities without aligned periods or populations.

This agent:

1. Fetches last-N-day vs prior-N-day facts from the Product’s connected sources
2. Embeds a Data Grounding contract (periods, populations, missing data, no unstated causes, no ungrounded revenue summing)
3. Returns observation-based **Top 3 Actions** (and does not propose unconfirmed analytics features)
4. (Evidence loop) Requires SQL that reproduces every evidence value behind a proposal, has an independent Critic check those values, and keeps the revision history

The point is not to summarize several dashboards into one narrative. It is to decide **where to start next**, with an explicit priority order, from the facts that are actually connected—for the selected Product.

## Evidence revision loop (v1 → v2 → Critic → v3 → Critic)

Implemented in `evidence/loop.py`, `evidence/critic.py`, `evidence/agents.py`. Run from the CLI (`scripts/run_evidence.py`) or the Web UI (which spawns the same script).

| Step | Who | What happens |
|------|-----|--------------|
| v1 | Analyst | Uses only our own tables (`asc_daily`, `asc_daily_by_source`, `known_events`). Latest 7 days vs the 7 days before, anchored on the newest `asc_daily` row |
| v2 | Analyst | Adds the public competitor table (`competitor_listing`). Claims citing it are observations, not facts |
| Critic round 1 | Code + Critic | See below. No findings → `converged` |
| v3 | Analyst | Answers each finding (`fixed` / `downgraded` / `removed` / `disputed`) and records how each action changed (`kept` / `modified` / `removed`) |
| Critic round 2 | Code + Critic | Same review on v3. Findings still open after the last round (default 2, CLI `--max-rounds` 1–3) are marked `unresolved` and the run ends as `max_rounds` |

**What each Critic round does**

1. **Structural rules (code)**: evidence present, cited tables exist, one number per evidence item, facts need SQL, public data about other apps cannot be a fact, a hypothesis needs a test plan, an action cannot rest only on competitor observations
2. **Re-run the Analyst's cited SQL (code)**: the result must equal the written value at the precision it was written. Units are not converted (see below)
3. **Independent Critic (model)**: a fresh Strands Agent with no shared conversation. It sees claims and actions **without the Analyst's SQL or reasoning**, and never sees past decisions. It writes its own SQL checks and can raise `causal_leap`, `scope_mismatch`, `kind_mislabel`, `unverifiable`, or `infeasible_action` (an App Store limit the action or test plan breaks)
4. **Compare values (code)**: each Critic SQL result is compared by code with the evidence item the check names (`evidence_index`); a mismatch becomes a `value_mismatch` finding. A check that returns the value of a different item than the one it names is counted as unverifiable, not as a match. Only a check without `evidence_index` is compared with every item of the claim. Two mismatches in one claim stay two findings

#### What the checks cover, and what converged / resolved mean

- **Compared**: the value of each evidence item that has SQL and a single value (re-run by code), and each Critic check (compared with its evidence item)
- **Not compared**: numbers written only in claim text, action reasons, or test plans; evidence values that pack several numbers; checks whose SQL does not return exactly one value (shown as unverifiable). The Critic chooses its own checks, so not every evidence item gets one
- **Units**: counts, ratings, and amounts are never compared at 100x / 0.01x, and zero never matches a non-zero value. A rate converts between ratio and percent only when the unit is visible: the claimed value is written with `%` and the SQL returns a ratio (a division), or the SQL returns a percent (a division multiplied by 100)
- **`converged`**: the last review raised no findings. It does not mean every number is verified: unverifiable checks and numbers outside evidence items can remain
- **`resolved`**: the next review raised no finding of the same kind on the same claim. That includes a claim that was rewritten or removed, so it does not prove the fix is correct. `downgraded`: the claim became a hypothesis. `unresolved`: still open after the last round (not verified, not proven wrong)

These rules were tightened after the Recorded Demos were recorded. Their stored results are shown as recorded; see [the note below the table](#sample-data-live-sample-and-recorded-demo) for what changes when the stored values are compared with the current rules.

**Guards before review**

- All SQL from both models passes a read-only guard (single `SELECT` / `WITH`, no write keywords); SQLite also has a read-only authorizer
- A v1/v2 answer that states numeric facts without any successful SQL in that answer is rejected and retried once; a second rejection stops the run, so invented numbers never reach the Critic
- A revision that drops every action without a stated reason is rejected the same way

The trace (`tmp/evidence_runs/<run_id>.json`) is rewritten after every step and holds each version, all SQL calls (Analyst / Critic / code), Critic findings and their resolution (`resolved` / `downgraded` / `unresolved`), rejected attempts, durations, and the model label.

**Scope:** the evidence loop currently covers App Store Connect daily data, Known Events, and public competitor listings (iTunes Lookup). GA4 and AdMob are used by the Live Analyze path only. The evidence loop and Live Analyze are separate runs; the loop does not read the Live Analyze Top 3.

## Interventions, measurement, human evaluation, and feedback

Implemented in `interventions/`, `interventions_api.py`, `scripts/interventions.py`, and the Web UI Interventions panel.

```
Adopt AI action / register by hand → planned
  → implement (date)  → "before" window measured by SQL
  → evaluate (verdict) → "after" window measured by SQL + human verdict
  → decision and outcome copied to decision memory
  → next evidence run: recalled as "past decisions" for the Analyst
```

- **Adopt or register**: adopt one action (rank 1–3) of a finished real-data run, or register a change a person came up with. An adopted action keeps the AI proposal (claims, test plan, model, version) unchanged. Runs on fictional sample data cannot be adopted
- **Plan**: target metric, method, success criterion, days until evaluation, window length. Metrics: `impressions`, `product_page_views`, `first_time_downloads`, `impression_to_page_view_pct`, `page_view_to_download_pct`
- **Before / after**: computed by code with SQL on `asc_daily` in the evidence store (window before the implementation date / window after it). A window is measured only if every day has a row; a partial window is reported as skipped, never summed over fewer days. Numbers are never typed in
- **Human evaluation**: `improved` / `no_change` / `worse` / `inconclusive`, with a note. Evaluating before the evaluation date needs an explicit "early" flag
- **Feedback to the next Analyst**: decisions are written to memory when a person adopts or registers one, and outcomes when they evaluate. Running an analysis never writes memory. Before each real-data evidence run, memory is searched for this product, each hit is read back from the ledger (dropped ones are skipped), and the Analyst receives them as **context only, not evidence**—it must re-query the store for any number. The Critic never receives them
- **Storage**: the ledger (`INTERVENTIONS_PATH`, default `tmp/interventions/ledger.jsonl`) is the record whatever `MEMORY_BACKEND` is; memory holds a readable copy (`sync-memory` re-links later)

## Sponsor technologies and their roles

| Technology | Role in this project | Where |
|------------|----------------------|-------|
| **Zetaris** | Evidence store for real data when `EVIDENCE_STORE=zetaris`. Evidence tables are staged as CSV into the local Zetaris platform and registered as Lightning filestore tables; Analyst SQL, Critic SQL, code re-checks, and intervention before/after measurement then all run there over JDBC (Spark SQL) | `integrations/zetaris/` |
| **Meterless Nightshift** | Local OpenAI-compatible model runtime (`LLM_PROVIDER=meterless`). Every Strands Agent (Analyst, Critic, Analyzer, Planner, Draft) sends requests to it with a `meterless-app` header that names this app. Analyst / Critic requests that fail for a retryable reason are retried once, and provider errors are logged with their details | `integrations/meterless/`, `llm/` |
| **NVIDIA Nemotron** | The model behind the Analyst and Critic in the hackathon runs: `nvidia/nemotron-3-ultra-550b-a55b`, reached through Nightshift's NVIDIA provider (pinned because `meterless/auto` routed to a model that returned 404 on this machine) | `METERLESS_MODEL` |
| **Meterless H-MEM** | Decision memory backend (`MEMORY_BACKEND=hmem`). The official reference implementation is vendored and run as a Node.js sidecar; decisions and outcomes are stored per product and recalled before each evidence run | `integrations/hmem/` |
| Strands Agents SDK | Agent runtime for every model call, including structured output and the SQL tool | `agent.py`, `evidence/agents.py` |
| Amazon Bedrock | Default model provider (`LLM_PROVIDER` unset or `bedrock`) and the provider used in the past AWS deployment | `llm/factory.py` |

The Live Sample and Recorded Demo use a dedicated SQLite file, not Zetaris, so fictional data never enters the real evidence store.

### Meterless and Zetaris: what this repository can show

| | Meterless Nightshift | Zetaris |
|-|----------------------|---------|
| Code path | `LLM_PROVIDER=meterless` → `llm/factory.py`, `integrations/meterless/` | `EVIDENCE_STORE=zetaris` → `evidence/factory.py`, `integrations/zetaris/` |
| Offline test (in `verify_offline.py`) | `verify_meterless.py`: provider settings, the status check, and model error handling against a local fake server, not Nightshift | `verify_zetaris_store.py`: CSV staging, table registration, name qualification, and the read-only guard against a fake engine, not Zetaris |
| Live check (not in the offline suite) | `check_meterless.py` (`--chat` sends one request) | `verify_zetaris_live.py` (needs the local Zetaris platform, Java 17+, and the JDBC jar) |
| Committed run results | None recorded with `LLM_PROVIDER=meterless`. The three Recorded Demo traces record the model as `openai_compatible:nvidia/nemotron-3-ultra-550b-a55b`; the trace does not record the endpoint URL, so that they went through Nightshift's OpenAI-compatible endpoint is the developer's account, not something the files show | None. The Recorded Demos use SQLite. Evidence runs on real app data with Zetaris were run locally, but their traces hold real data and are not committed, so the repository cannot show their results |

The repository therefore shows how each integration is wired and tested against fakes; it does not by itself prove a successful live run of either.

## Multi-Product

Analysis is scoped to one **Product** at a time (catalog in `products/index.json` + per-product JSON).

- **CLI**: `python agent.py --product-id <id>` (default from `products/index.json`)
- **API**: `GET /api/products` lists products; `POST /api/analyze` accepts `{ language, productId }`
- **Web UI**: Product selector in the header; switching Product loads that Product’s **last successful Analyze** from localStorage (or an empty shell)

### Portfolio Overview (display) vs portfolio analysis (not implemented)

- **Portfolio Overview (`/portfolio`, implemented)**: one card per configured app, showing that app's **last successful Live Analyze saved in this browser** (period, top recommendation, two key metrics per source block, run id), or "not analyzed". It reads localStorage only; it does **not** call the API to analyze, generate values, or create recommendations
- **Cross-app portfolio analysis (not implemented)**: comparing apps and deciding which app deserves the developer's time next. Each card is still a separate single-Product result; numbers on different cards are not compared or ranked

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

In the Live Analyze path, LLM output is constrained by the prompt / Data Contract; there is no post-generation machine validation there (see Known limitations). The evidence loop adds machine checks (SQL re-runs, structural rules, the Critic) for its own proposals. Evidence tables keep population columns (`territory`, `country`, `source`) and keep missing values as NULL, never 0.

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

### Evidence tables (evidence loop)

Loaded by `scripts/export_evidence.py` into `EVIDENCE_STORE`:

| Table | Source | Kind |
|-------|--------|------|
| `asc_daily` | App Store Connect Analytics daily totals (needs ASC credentials) | Our data → facts |
| `asc_daily_by_source` | ASC daily impressions / first-time downloads by search / browse / referrer | Our data → facts |
| `known_events` | Developer-written context (`known_events.json`) | Context only; nearness does not prove cause |
| `competitor_listing` | Public App Store listing (iTunes Lookup, no key) for our app and the fixed competitor list in the Product JSON (`competitors`) | External → observations |

## Sample data, Live Sample, and Recorded Demo

For the demo there is a **fictional** mahjong sample in `samples/mahjong/` (`sample_mode.py`). Every number, app, and listing in it is made up (`source = fictional_sample`, app id `fictional-001`); loading refuses data that names a configured real app.

| Scenario | Content |
|----------|---------|
| `base` | 14 days (2026-10-09 to 2026-10-22). Impressions up 40% in the latest 7 days while the page-view rate and first-time downloads fell; browse impressions grew most; top competitors lead in rating count, screenshot count, and update recency |
| `competitor-variant` | Same as `base` except one competitor (`fictional-101`) loses those three leads. Every changed cell is listed with old value, new value, and reason in `scenarios.json` |

Three ways to use it, kept apart:

| Mode | Model call | Store | How |
|------|-----------|-------|-----|
| **Fictional CSV only** | No | `tmp/sample/<scenario>.sqlite` | `python scripts/run_sample.py --scenario base --dry-run` loads the CSVs (plus scenario changes), prints the periods and row counts, and stops |
| **Live Sample** | Yes (`LLM_PROVIDER`) | Dedicated SQLite, `EVIDENCE_STORE` ignored | `python scripts/run_sample.py --scenario base` runs the real Analyst and Critic. No past decisions are recalled. Trace: `tmp/evidence_runs/sample-<scenario>-<timestamp>.json` + `.sample.json` |
| **Recorded Demo** | No (no API key, network, or model) | Committed trace | Traces in `samples/recorded/`, copied from Live Sample runs only after checks (`scripts/record_sample_demo.py`: sample run id, unchanged CSVs, finished, model recorded, at least one Critic review) |

### Example: what the Critic caught and how the Analyst fixed it

From `sample-competitor-variant-20261024-220111` (v2 → Critic round 1 → v3 → Critic round 2). Fictional data: prior 7 days 30,000 impressions / 1,800 page views / 360 downloads; latest 7 days 42,000 / 2,100 / 315.

| | v2 (Analyst) | Critic round 1 | v3 (Analyst) | Critic round 2 |
|-|--------------|----------------|--------------|----------------|
| Claim C1 (prior 7 days) | impression → page-view rate **16.67**, page-view → download rate **5.0** | Critic SQL `SUM(product_page_views) * 100.0 / SUM(impressions)` returns **6.0**; code files `value_mismatch` (claimed 16.67). Same for the download rate (**20.0** vs 5.0) | **6.0%** and **20.0%** | Matched |
| Claim C2 (latest 7 days) | **20.0** and **6.67** | Critic SQL returns **5.0** and **15.0**; `value_mismatch` | **5.0%** and **15.0%** | Matched |
| Action #1 success criterion (claim C14) | "page-view → download rate improves from **6.67 to 5.0 or lower**" (a target in the wrong direction, built on the swapped numbers) | Critic: the criterion uses the wrong values, and "improve" points the number down (`scope_mismatch`) | "from **15.0% to 20.0% or higher**" | No finding |

Why this needed an independent check: v2's SQL was `SUM(impressions) * 1.0 / SUM(product_page_views)` (and `SUM(product_page_views) * 1.0 / SUM(first_time_downloads)`), so **re-running the Analyst's own SQL reproduces 16.67 and 5.0**. The numbers were self-consistent but meant the opposite of their labels. The Critic, which never sees the Analyst's SQL, wrote the rates from their definitions, and code compared the values. The Critic also explained the swap in its finding: the correct prior rates are 6.0% (1,800 / 30,000) and 20.0% (360 / 1,800). In v3 the Analyst answered each of these findings as `fixed`, and the second review matched all ten C1 / C2 values; these findings are marked `resolved`.

In the same round, v3 also fixed a test plan that asked PPO for a search-only conversion rate (PPO does not split results by traffic source; `resolved`). Not everything was fixed: the causal-leap findings on C5, C6, and C12 were answered but raised again in round 2 and remain unresolved (see the table below).

**Committed Recorded Demos** (results differ by run; not every finding is resolved in the Japanese runs):

| Run | Model output | Model label in the trace | Result | Run time |
|-----|--------------|--------------------------|--------|----------|
| `sample-base-20261025-110333` (representative `base`) | English | `openai_compatible:nvidia/nemotron-3-ultra-550b-a55b` | `converged`, 0 unresolved findings; final Critic SQL checks 31 matched / 0 mismatched / 1 unverifiable; 2 known limitations in v3 actions #1 and #3 | about 9.5 min |
| `sample-base-20261024-214121` | Japanese | `openai_compatible:nvidia/nemotron-3-ultra-550b-a55b` | `max_rounds`, 1 unresolved finding in v3 | about 15 min |
| `sample-competitor-variant-20261024-220111` | Japanese | `openai_compatible:nvidia/nemotron-3-ultra-550b-a55b` | `max_rounds`, 8 unresolved findings in v3 (2 are known false judgments) | about 24 min |

The traces record the model as `openai_compatible` with the model id. According to the developer, the endpoint was Nightshift's OpenAI-compatible endpoint; the traces do not record the endpoint URL. Each `.sample.json` carries a review outcome and known limitations (in Japanese and English); the Japanese runs also carry a comparison note.

**Recorded results vs the current check rules.** The counts in the table are as recorded, judged by the code at record time, which allowed 100x / 0.01x matches even for counts and did not use the `evidence_index` the Critic named. Comparing the stored values again with the current rules (no model run) changes only the final Critic round of `competitor-variant`: the C16 check (number of free competitors, 5, against each app's price, 0.0) becomes a mismatch, so its checks become 40 matched / 3 mismatched instead of 41 / 2. The C8 check (an average rating of 4.1) was paired with the rating-count item 410 and now matches the 4.1 item instead. In its first round, C1 and C2 each had two mismatched checks, but the old deduplication recorded one finding each. The base runs' counts do not change. The `evidence_index` the Critic named is not stored, so whether each match was against the named item cannot be checked. The traces are unchanged; these notes are in each `.sample.json` under known limitations. The English `base` is marked `"representative": true`, so `/demo` and the Sample Workspace show it in either UI language; the Japanese `base` stays committed and is shown by the CLI viewer and the API. One converged run does not show that runs converge in general. The difference between the two scenarios must **not** be read as a causal effect of the competitor data change: one run per scenario cannot separate model variance from the data difference, and the run conditions differed.

**Playing the Recorded Demo**

```bash
# CLI: every recorded run, then base vs competitor-variant
python scripts/show_sample_demo.py
python scripts/show_sample_demo.py --run-id sample-base-20261024-214121
```

In the Web UI, fictional and real data never share a screen:

- **Sample Workspace (`/`, opened first)**: fictional sample only, built from `samples/` at build time with no API or model call. KPIs for the last 7 days against the previous 7, 14-day trends with Known Events, the traffic-source table, the representative Recorded Demo's final Top 3 (cited claims and known limitations under each action), and its Critic verification counts
- **My Workspace (`/`, switch at the top)**: real analysis results for the selected Product (Live Analyze, evidence runs in the Grounding Critic panel, interventions). The choice is kept in `localStorage`
- **Recorded Demo (`/demo`)**: a separate page for the committed Recorded Demos only

Viewing `/demo` needs no model call and no API key, but the page reads the runs from `/api/evidence`, so `python api_server.py` (and `npm run dev`) must be running. The page:

- opens the representative English `base` run in either UI language, with a switch between `base` and `competitor-variant`. When the model output language differs from the UI language, the switch and the page say so; model output is never translated, while UI labels and review notes follow the UI language. In the English UI, a few Japanese terms from the sample get a marked gloss (`[translation: …]`) next to the original
- states that the run is a saved Recorded Demo on fictional data, executed by a real model
- starts with **What happened in the app**: three charts of the fictional data (first-time downloads, Browse impressions, Browse first-time downloads; previous vs last 7 days, each on its own zero-based scale). They are shown only when the run's `.sample.json` digests and periods match the CSVs the page was built from
- compares the v1 / v2 / v3 Top 3 titles side by side (v1 — Own App Data, v2 — Competitor Context, v3 — Critic-Reviewed Actions), with the reason for each change, then shows the **Final Top 3 Actions — v3** at full width: reason, cited claims, and known limitations under each action
- lists what the Critic questioned in each round: the finding, its recorded resolution, the SQL checks judged by code (matched / mismatched / unverifiable), and the Analyst's answer in the next version
- marks a finding as **Known misjudgment (confirmed in review after the run)** when the Recorded Demo's known limitations name that finding and its kind, and labels the kind as "Recorded classification" (`competitor-variant`: `r2-f1`, `r2-f2`). The trace, the Critic's text, and the unresolved count are shown unchanged
- shows the outcome (review status, unresolved count, unverifiable checks, known limitations)
- keeps **SQL evidence** (each final claim with its SQL) and the **Full log** (each version's claims, the Critic's checks with SQL and values, the comparison note) collapsed

The Grounding Critic panel in My Workspace lists real-data runs only; Recorded Demo and Live Sample runs (same product id) are left out of it.

## Repository layout

```
indie-growth-agent/
├── agent.py                 # Shared analysis entry (fetch → format → model)
├── api_server.py            # FastAPI: /api/products, /api/analyze, /api/draft (+ evidence / interventions routers)
├── evidence_api.py          # /api/evidence: list, read, start evidence runs
├── interventions_api.py     # /api/interventions: adopt, add, implement, evaluate, measure, drop
├── analysis_schema.py       # Structured Agent / API response models
├── report_builder.py        # Observed metrics + analysis → JSON for the UI
├── format_input.py          # Data Contract / FACTS text builder
├── product_config.py        # Multi-Product catalog loader
├── planner.py               # Optional growth-experiment planner (MCP / playbooks)
├── draft_generator.py       # Action Draft generator
├── known_events.py          # Known product events for Planner context
├── sample_mode.py           # Fictional sample data, scenarios, Recorded Demo rules
├── config.py                # Loads .env / process env (no hardcoded secrets)
├── event_definitions.json   # Developer-declared GA4 App event meanings (example)
├── event_definitions_web.json
├── known_events.json
├── products/                # Product catalog
│   ├── index.json
│   ├── mahjong.json
│   ├── shopping-memo.json
│   └── nextuta.json
├── evidence/                # Evidence schema, stores, SQL guard, Analyst / Critic, revision loop
├── interventions/           # Ledger, lifecycle, SQL measurement, memory link
├── memory/                  # Decision memory interface (none / local) and recall
├── llm/                     # Model provider selection and provider error handling
├── integrations/
│   ├── zetaris/             # Zetaris evidence store (JDBC, CSV staging)
│   ├── meterless/           # Meterless Nightshift settings and runtime status
│   └── hmem/                # Meterless H-MEM adapter + vendored reference (Node sidecar)
├── samples/
│   ├── mahjong/             # Fictional sample CSVs + scenarios.json
│   └── recorded/            # Committed Recorded Demo traces + .sample.json notes
├── requirements.txt
├── Dockerfile               # Backend container image
├── .dockerignore
├── .env.example
├── asc/                     # App Store Connect Analytics + Sales
│   └── sales.py
├── ga4/                     # GA4 App + GA4 Web Data API fetch
├── admob/                   # AdMob Network Report fetch
├── web/                     # Next.js 16 static-export Web UI
├── scripts/                 # Run / record / show scripts, connection checks, offline verification
│   ├── run_evidence.py      # Evidence loop on real data
│   ├── export_evidence.py   # Load evidence tables into EVIDENCE_STORE
│   ├── interventions.py     # Intervention CLI
│   ├── run_sample.py        # Live Sample (or --dry-run)
│   ├── record_sample_demo.py
│   ├── show_sample_demo.py  # Recorded Demo viewer
│   ├── check_meterless.py   # Nightshift status
│   ├── verify_offline.py    # All offline checks
│   ├── verify_ga4.py
│   ├── verify_admob.py
│   ├── oauth_admob.py
│   └── list_ga4_events.py
├── docs/                    # Architecture, pre-existing work
└── secrets/                 # Local only (gitignored): .p8 / refresh tokens, etc.
```

## Architecture

See **[docs/architecture.md](docs/architecture.md)** for the full architecture diagrams (Mermaid) and request flows.

### Live Analyze (past AWS deployment, no longer running)

This is how Live Analyze was deployed for the Agents for Humans Hackathon (September 2026). That AWS environment was retired in October 2026; **there is no public deployment now**. Everything in this README runs locally (see [Run](#run)).

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

### Evidence loop and interventions (hackathon, local)

```mermaid
%%{init: {"theme": "neutral"}}%%
flowchart TB
  dev([Indie developer])

  subgraph local ["Local machine"]
    ui["Next.js Web UI<br/>Sample Workspace · My Workspace<br/>Grounding Critic panel · Interventions panel<br/>Recorded Demo page /demo · Portfolio Overview"]
    api["FastAPI<br/>/api/evidence · /api/interventions"]
    loop["Evidence loop<br/>scripts/run_evidence.py"]
    analyst["Analyst<br/>Strands Agent + SQL tool"]
    critic["Grounding Critic<br/>fresh Strands Agent + own SQL<br/>no Analyst SQL, no past decisions"]
    checks["Code checks<br/>structural rules · re-run cited SQL<br/>compare values"]
    ledger["Intervention ledger<br/>JSONL"]
    hmem["Meterless H-MEM<br/>decision memory (Node sidecar)"]
    nightshift["Meterless Nightshift<br/>OpenAI-compatible runtime"]
    zetaris["Zetaris platform<br/>evidence store · JDBC / Spark SQL"]
  end

  nvidia["NVIDIA Nemotron 3 Ultra"]
  sources["ASC daily · Known Events<br/>iTunes Lookup competitor listings"]

  sources -->|scripts/export_evidence.py| zetaris
  dev --> ui
  ui --> api
  api -->|spawn| loop
  hmem -->|recall past decisions<br/>context only| loop
  loop --> analyst
  loop --> critic
  loop --> checks
  analyst -->|read-only SQL| zetaris
  critic -->|read-only SQL| zetaris
  checks -->|re-run SQL| zetaris
  analyst --> nightshift
  critic --> nightshift
  nightshift --> nvidia
  loop -->|trace v1 → v2 → Critic → v3 → Critic| api
  api -->|adopt / implement / evaluate| ledger
  ledger -->|before / after SQL| zetaris
  ledger -->|decision + outcome| hmem
```

The Live Sample uses the same loop on `tmp/sample/<scenario>.sqlite` instead of Zetaris, with no memory recall. The Recorded Demo is read from `samples/recorded/` with no model.

## Web UI behavior (current)

- **Initial view**: last successful Live Analyze for the selected Product (`localStorage`), or an empty shell prompting Analyze
- **Analyze latest data**: refreshes via `POST /api/analyze`, then updates the UI and cache
- **Loading / empty / error**: Analyze progress (elapsed seconds), empty states before first success, retry on Analyze failure
- **i18n / a11y**: Japanese / English UI chrome; focus-visible and localized labels where applicable
- **Language switch**: changes UI chrome immediately and is kept across pages. It does **not** re-run Analyze or rewrite existing analysis prose; Actions / Facts / Experiments stay in the language of the last successful Analyze until the user runs Analyze again
- **`/`: Sample Workspace / My Workspace**: opens the Sample Workspace (fictional data, read-only, no AI run); My Workspace shows real analysis results for the selected Product. The two are never mixed, and the choice is kept across visits. The header links to Portfolio and Recorded Demo
- **Recorded Demo (`/demo`)**: separate page for the committed Recorded Demos (representative English `base` / `competitor-variant`); see [Sample data, Live Sample, and Recorded Demo](#sample-data-live-sample-and-recorded-demo). No model call or API key; needs the local `api_server.py`
- **Grounding Critic panel** (My Workspace, under Top 3): run selector (real-data runs only), "Run a new verification" (confirmation; one run started from the API at a time), v1 / v2 / v3 steps, claims with evidence and SQL, SQL checks judged by code (matched / mismatched / unverifiable), the Critic's comment labeled as model-generated, Critic findings with resolution, and an adopt button per action on finished real-data runs
- **Interventions panel**: list, add by hand, mark implemented, record verdict, re-measure, drop; shows the AI prediction, before / after numbers, skipped windows, and your verdict
- **Portfolio Overview** (`/portfolio`, header link): one card per app from saved Live Analyze results (see Multi-Product)

Details: [`web/README.md`](web/README.md)

## Deployment (past AWS setup, retired)

**There is no publicly running deployment.** The setup below was used for the Agents for Humans Hackathon (September 2026) and was retired in October 2026. The Dockerfile and these notes stay in the repository as a record and for redeploying; no URL from that environment is maintained. To try the project, run it locally (see [Quick Demo](#quick-demo-30-seconds) and [Run](#run)).

| Layer | Choice (at the time) |
|-------|----------------------|
| Frontend | Next.js 16 **static export** on **AWS Amplify Hosting** |
| Backend | FastAPI container on **Amazon ECS Express Mode** (AWS Fargate) |
| Image | **Amazon ECR** |
| Public API URL | HTTPS endpoint provided by ECS Express Mode |
| Runtime config | Process **environment variables** (`config.py` / `.env`). In ECS, values may be **injected** into the task environment from **AWS Secrets Manager** (Task Execution Role)—the app does not call Secrets Manager APIs itself |
| Bedrock | **ECS Task Role** (no long-lived AWS access keys in the app) |
| ECR pull at startup | **ECS Task Execution Role** |

When redeploying: frontend build env `NEXT_PUBLIC_AGENT_API_URL=<ECS HTTPS URL>`, and backend `CORS_ALLOWED_ORIGINS` set to the Amplify origin (localhost defaults remain for local use).

Not used: App Runner, Amplify SSR, Next.js API Route proxy.

The hackathon additions (evidence loop, Zetaris, Meterless Nightshift, H-MEM) run **locally** and were never deployed to AWS. The Dockerfile was not updated for them (no Java / Node in the image, and Nightshift / Zetaris run on the developer's machine).

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
- **Model provider**: `LLM_PROVIDER` unset / `bedrock` uses Amazon Bedrock (locally, credentials that can call Bedrock, e.g. `AWS_REGION` + profile; if redeployed to ECS, the **Task Role**—do not commit access keys). `.env.example` sets `LLM_PROVIDER=meterless` for the hackathon setup (see [Switching the model provider](#switching-the-model-provider-bedrock--meterless))
- **GA4 App / Web (optional)**: Property IDs + OAuth (`GOOGLE_OAUTH_*` and refresh token) or a service account; Web hostname / key events / featurePaths come from Product JSON when enabled
- **AdMob (optional)**: Account ID + a separate-scope refresh token (`scripts/oauth_admob.py`) + app IDs when needed

See `.env.example` for key names. For the Web UI, set `NEXT_PUBLIC_AGENT_API_URL` in `web/.env.local` (see `web/README.md`).

### 3. Hackathon stack (optional; each part falls back to a local default)

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_PROVIDER` | `bedrock` | `bedrock` / `openai_compatible` / `meterless` |
| `METERLESS_BASE_URL` | `http://127.0.0.1:8088/v1` | Nightshift runtime (any pasted form is normalized to `<host>/v1`) |
| `METERLESS_RUNTIME_TOKEN` | — (required for `meterless`) | Token Nightshift writes to `<stateDir>/proxy-token` (`rt-local` is rejected) |
| `METERLESS_MODEL` | `nvidia/nemotron-3-ultra-550b-a55b` | Model id sent to Nightshift |
| `METERLESS_APP` / `METERLESS_TIMEOUT_SECONDS` / `METERLESS_TTFB_MS` | `indie-growth-agent` / `600` / `240000` | App id header, request timeout, time to first token |
| `OPENAI_COMPATIBLE_BASE_URL` / `_API_KEY` / `_MODEL` / `_HEADERS` / `_TIMEOUT_SECONDS` | — | For `LLM_PROVIDER=openai_compatible` |
| `EVIDENCE_STORE` | `sqlite` | `sqlite` / `zetaris` |
| `EVIDENCE_SQLITE_PATH` | `tmp/evidence.sqlite` | SQLite evidence store |
| `ZETARIS_USER` / `ZETARIS_PASSWORD` | — | Zetaris login (`.env` only) |
| `ZETARIS_JDBC_JAR` / `ZETARIS_JAVA_HOME` / `ZETARIS_JDBC_URL` / `ZETARIS_DATABASE` | — / `JAVA_HOME` / `jdbc:zetaris:lightning@localhost:10000` / `INDIE_GROWTH` | JDBC driver (Java 17+ via JPype) |
| `ZETARIS_DOCKER_CONTAINER` / `ZETARIS_STAGING_DIR` / `ZETARIS_QUERY_TIMEOUT_SECONDS` | `zetaris-driver-1` / `/home/zetaris/customer-data/shared/indie_growth` / `60` | Where CSVs are staged inside the Zetaris container |
| `MEMORY_BACKEND` | `none` | `none` / `local` / `hmem` |
| `MEMORY_LOCAL_DIR` | `tmp/memory` | JSONL memory |
| `HMEM_DIR` / `HMEM_NODE` / `HMEM_RECALL_THRESHOLD` | `tmp/hmem` / `node` / `0.25` | H-MEM sidecar (Node.js 22.7+, no npm packages) |
| `INTERVENTIONS_PATH` | `tmp/interventions/ledger.jsonl` | Intervention ledger |

Prerequisites when enabled: Meterless Nightshift running locally; the local Zetaris platform running in Docker plus Java 17+ and the Zetaris JDBC jar; Node.js 22.7+ for H-MEM.

#### Switching the model provider (Bedrock / Meterless)

`LLM_PROVIDER` picks the model for every Strands Agent: My Workspace's Analyze (and its Planner / Draft) and the evidence loop's Analyst and Critic. There is no separate setting per feature.

| | `LLM_PROVIDER=bedrock` (default) | `LLM_PROVIDER=meterless` |
|---|---|---|
| Model | Strands' default `BedrockModel` (`global.anthropic.claude-sonnet-4-6` in the installed Strands); the app has no Bedrock model-id variable | `METERLESS_MODEL` (default `nvidia/nemotron-3-ultra-550b-a55b`) |
| Where it goes | Amazon Bedrock in the AWS session's region (environment or profile, e.g. `AWS_REGION`), else `us-west-2` | Nightshift at `METERLESS_BASE_URL`, which forwards to the provider of the model id (NVIDIA for Nemotron) |
| Credentials | AWS credentials outside the repo: `AWS_PROFILE` / `aws login` / SSO / an IAM role. Prefer an IAM user or role allowed only to invoke Bedrock models, not the root user | `METERLESS_RUNTIME_TOKEN` in `.env`; the provider key (e.g. NVIDIA) is held by Nightshift, not by this app |
| Check | `aws sts get-caller-identity` | `python scripts/check_meterless.py` (no model request), `--chat` (one short request) |

Notes:

- `.env` does not override variables already set in the shell, so `LLM_PROVIDER=bedrock python api_server.py` switches for one run without editing `.env`. The API builds the Analyze model on the first Analyze request and keeps it: **restart `api_server.py` after switching**. The API starts even when the provider's settings are missing (the Recorded Demo and `/api/evidence` need no model); Analyze then answers `model_unavailable` before fetching any data. Each evidence run is a new process and reads the setting when it starts
- A pinned provider model (Nemotron) may not appear in Nightshift's `GET /v1/models`; that alone does not mean it is unavailable. `check_meterless.py --chat` shows whether it answers. A `meterless_detail` of `nvidia_key_missing` means Nightshift has no NVIDIA API key loaded: set the key again in Nightshift. Do not switch `METERLESS_MODEL` to `meterless/auto`: on this machine it routes to an NVIDIA model that answers 404
- When the model cannot be called, Analyze answers `model_unavailable` with the provider and a hint (for example, AWS credentials expired, no NVIDIA key in Nightshift, or the provider's settings not loaded); other failures stay `analyze_failed`. The API log records only `provider`, a reason code, and the HTTP status (`Analyze model error ...`), never the response body or credentials
- Recorded Demos are saved traces and do not depend on the current provider

### 4. Optional connection checks

```bash
python scripts/verify_ga4.py
python scripts/verify_admob.py
python scripts/check_meterless.py            # Nightshift status (GET /v1/models, no model request)
python scripts/check_meterless.py --chat     # plus one short request (spends provider credits)
EVIDENCE_STORE=zetaris python scripts/verify_zetaris_live.py   # live Zetaris check (Docker)
```

## Run

CLI:

```bash
python agent.py
# or
python agent.py --product-id mahjong
```

Stdout prints the agent input (Data Contract + FACTS) and the model response (Most important finding / Why it matters / Top 3 actions).

Evidence loop on real data:

```bash
python scripts/export_evidence.py --product-id mahjong      # load evidence tables into EVIDENCE_STORE
python scripts/run_evidence.py --product-id mahjong         # v1 → v2 → Critic → v3 → Critic (default 2 rounds)
python scripts/run_evidence.py --product-id mahjong --language en --max-rounds 3
```

The first lines name the model provider, the evidence store (with its `asc_daily` rows), and the memory backend actually used. One run takes several minutes per step (the Recorded Demos took about 9.5, 15, and 24 minutes).

Interventions:

```bash
python scripts/interventions.py adopt --run <run_id> --rank 1
python scripts/interventions.py add --product mahjong --title "..." \
    --metric page_view_to_download_pct --method "before/after 14 days" --criterion "+5 points" --days 14
python scripts/interventions.py implement <id> --on 2026-10-25
python scripts/interventions.py evaluate <id> --verdict inconclusive --note "..."
python scripts/interventions.py measure <id>      # re-measure (late data, store was down)
python scripts/interventions.py list --product mahjong
python scripts/interventions.py sync-memory
```

Sample data:

```bash
python scripts/run_sample.py --scenario base --dry-run           # fictional CSV only, no model
python scripts/run_sample.py --scenario competitor-variant       # Live Sample (model call)
python scripts/record_sample_demo.py <sample-run-id>             # keep as Recorded Demo
python scripts/show_sample_demo.py                               # Recorded Demo, no model
```

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
- `GET /api/evidence/runs`, `GET /api/evidence/runs/{runId}`, `POST /api/evidence/runs` (starts `scripts/run_evidence.py`; one at a time)
- `GET /api/interventions`, `POST /api/interventions`, `POST /api/interventions/adopt`, `POST /api/interventions/{id}/implement | evaluate | measure | drop`

## Tests

All offline (no credentials, network, or model calls):

```bash
python scripts/verify_offline.py   # 18 checks: import smoke + every verify_* script below
cd web && npm test                 # Web unit tests (portfolio, sample text, Recorded Demo story and choice, Critic checks, Sample Workspace, glosses, snapshot)
cd web && npm run lint && npm run build
```

`verify_offline.py` runs each check in its own subprocess: Analyze cache, LLM provider selection, OpenAI-compatible and Meterless providers (local fake servers), structured output lists, evidence schema, SQL guard and SQLite store, evidence tables, Zetaris store (fake engine), evidence loop and Critic rules (stub models), `/api/evidence`, API startup and Recorded Demo reads without model settings, decision memory, H-MEM conformance suite + adapter (skipped without Node.js), interventions, `/api/interventions`, sample mode, and the memory → evidence-run integration.

Not part of the offline suite (need live services): `verify_ga4.py`, `verify_admob.py`, `verify_zetaris_live.py`, `check_meterless.py`.

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
- Next.js 16 static-export Web UI: last successful report cache, loading / empty / error, ja / en chrome
- FastAPI for the Web UI (local / container)
- Dockerfile and AWS deployment setup (Amplify Hosting + ECS Express Mode; deployed in September 2026, retired in October 2026)

### Open Agent Hackathon 2026 (implemented)

- Selectable model provider (`bedrock` / `openai_compatible` / `meterless`) for every Strands Agent
- Evidence tables, read-only SQL guard, SQLite and Zetaris evidence stores
- Analyst + independent Grounding Critic revision loop (v1 → v2 → Critic → v3 → Critic) with code-side value checks and saved traces
- Interventions: AI adoption or manual registration, SQL before/after measurement, human verdict
- Decision memory (`local`, Meterless H-MEM) and recall of past decisions and outcomes as Analyst context
- `/api/evidence`, `/api/interventions`, Grounding Critic and Interventions panels in the Web UI
- Portfolio Overview (display of each app's saved Live Analyze)
- Fictional sample data, Live Sample, Recorded Demo (CLI viewer, `/demo` page), Sample Workspace kept apart from My Workspace
- Offline verification runner

### Not finished yet

- **Faster evidence runs**: one run took about 15–24 minutes with Nemotron 3 Ultra through Nightshift. Work has started (`7beed42`: fewer wasted model round trips, no silent SDK retries for the Analyst / Critic, shorter revision prompts), but no run has measured the effect yet
- Reducing Critic false judgments seen in the Recorded Demos (counts compared with per-app values; finding kind not matching the content)

### Future Roadmap (not implemented)

#### Next

- Google Play / Android support
- App Store reviews
- IAP / subscriptions
- RevenueCat integration
- GA4 / AdMob tables in the evidence loop

#### Later

- Cross-Product **portfolio** analysis (compare / prioritize across Products—not the same as the existing single-Product selector or the display-only Portfolio Overview)
- Proactive growth alerts
- A public deployment again, including the evidence loop / Zetaris / Meterless / H-MEM

#### Long-term vision

Indie Growth Agent should evolve from analyzing one selected Product into a growth partner for indie developers that helps decide not only what action to take, but which Product deserves the developer's limited time next.

```
Acquisition → Usage → Feedback → Revenue → Prioritized action → Measured outcome
```

Also still out of scope for now:

- Amazon Bedrock AgentCore (the past deployment used Amplify Hosting + ECS Express Mode instead)
- Post-generation machine grounding checks for the Live Analyze Top 3 (the evidence loop has its own checks)
- Explicit AdMob partial-metric missing handling (distinguish missing vs zero)

## Known limitations (MVP)

- **Source populations may differ** — matching calendars do not make ASC Analytics / ASC Sales / GA4 App / GA4 Web / AdMob the same population
- **AdMob partial metric missing handling is not implemented** — response gaps are not strictly distinguished from true zeros
- **Live Analyze output is grounded by prompt / data contract but not machine-validated after generation** — only the evidence loop re-runs SQL and has a Critic
- **The Critic can be wrong and runs end with unresolved findings** — both Japanese Recorded Demos ended at the review limit (`max_rounds`) with unresolved findings, including known false `value_mismatch` judgments and a finding filed under the wrong kind. The English `base` converged, but review after the run found two v3 action reasons the Critic did not flag (known limitations). "Unresolved" means not verified, not proven wrong
- **Recorded Demo check results predate the current check rules** — they were judged with 100x / 0.01x matching and without the Critic's `evidence_index`. Re-judging the stored values changes one check in `competitor-variant` (see [Recorded results vs the current check rules](#sample-data-live-sample-and-recorded-demo)); the traces are not rewritten and no run uses the current rules yet
- **SQL checks cover evidence values only** — numbers written only in claim text or action reasons are not compared, so a converged run can still contain unchecked numbers
- **Evidence runs are slow** — several minutes per step; about 9.5–24 minutes per run in the Recorded Demos
- **One run per scenario** — the Recorded Demos cannot separate model variance from the scenario difference
- **Evidence loop scope** — App Store Connect daily data, Known Events, and public listings only; competitor data is the public listing (no screenshots' content, no reviews)
- **Before / after measurement** reads `asc_daily` rows with territory `ALL` (the Product JSONs use `ALL`); a window with any missing day is skipped. The verdict is the person's, not a statistical test
- **The Recorded Demo page needs the local API** — `/demo` makes no model call, but it reads the saved runs from `/api/evidence`; without `python api_server.py` it cannot show them (the CLI viewer works without it)
- **Live Sample model label** — with `LLM_PROVIDER=meterless`, `scripts/run_sample.py` records only `meterless` as the model (without the model id)
- **No public deployment** — the past AWS environment was retired; Zetaris, Nightshift, and H-MEM run on the developer's machine
- **No API authentication** — `/api/analyze`, `/api/evidence`, and `/api/interventions` have no authentication; run them locally. A public deployment would need protection (e.g. WAF / rate limits) and, for long-running Analyze, an ALB idle timeout above the default 60s
- **Language switch does not regenerate analysis** — UI chrome switches immediately; analysis body stays until the next Live Analyze

## License

MIT License. See [LICENSE](LICENSE). The vendored Meterless H-MEM reference keeps its own license in [`integrations/hmem/vendor/LICENSE`](integrations/hmem/vendor/LICENSE).
