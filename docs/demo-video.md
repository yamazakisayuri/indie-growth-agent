# Demo video — Open Agent Hackathon 2026 (Track 02)

Recording script for the submission video. Target length **2:55** (limit 3:00; the hackathon allows 1–4 minutes).

Written against `6c349dc`. Everything on screen comes from the committed Recorded Demos in `samples/recorded/` and from pre-recorded checks that make no model call. No model is run for the video.

## Ground rules

- **Fictional data only.** The app screens show the fictional mahjong sample (`samples/mahjong/`) and the committed Recorded Demos. No real app metrics, no real-data traces, no My Workspace, no Portfolio.
- **No model calls.** Do not press Analyze, do not start an evidence run or a Live Sample, and do not run `check_meterless.py --chat`. The Recorded Demo page (`/demo`) reads saved traces and calls no model.
- **No endpoints or credentials.** Do not show `.env`, environment variables, base URLs, JDBC URLs, hosts, ports, users, tokens, keys, or home-directory paths. The terminal shots filter them out before they reach the screen (see [Terminal shots](#terminal-shots-zetaris-and-nightshift)).
- **Say only what the files show.**
  - The Recorded Demos ran on a dedicated SQLite file, not Zetaris.
  - The traces record the model as `openai_compatible:nvidia/nemotron-3-ultra-550b-a55b`, without the endpoint URL.
  - "Converged" means the last review raised no findings, not that every number is correct.
  - The difference between `base` and `competitor-variant` is not a causal effect of the data change (one run per scenario, different output language and run conditions).
  - Use "checked by SQL" or "matched", not "verified" or "proven".

## Traces used

| Run | Used for | Result as recorded |
|-----|----------|--------------------|
| `sample-base-20261025-110333` (English `base`, representative) | Main story: scenes 3–6, 8, 10 | `converged`; Critic round 1 on v2: 18 matched / 0 mismatched / 0 unverifiable, 5 findings; round 2 on v3: 31 / 0 / 1, 0 findings; 2 known limitations on v3 actions #1 and #3 |
| `sample-competitor-variant-20261024-220111` (Japanese output) | Scene 7 only: a value mismatch and the Known misjudgment marks | `max_rounds`, 8 unresolved findings in v3, 2 of them known misjudgments (`r2-f1`, `r2-f2`) |

The Japanese `base` run (`sample-base-20261024-214121`) is not used.

## Timeline

| # | Time | Length | Scene | Source | Words |
|---|------|--------|-------|--------|-------|
| 1 | 0:00–0:10 | 10 s | The indie developer's problem | Title card | 20 |
| 2 | 0:10–0:25 | 15 s | Sample Workspace | `/` | 24 |
| 3 | 0:25–0:35 | 10 s | A saved run, no model call | `/demo` (`base`) | 19 |
| 4 | 0:35–0:52 | 17 s | v1 → v2 → v3 | `/demo` (`base`) | 26 |
| 5 | 0:52–1:14 | 22 s | Critic round 1 and the revision loop | `/demo` (`base`) | 37 |
| 6 | 1:14–1:32 | 18 s | SQL checks and "unverifiable" | `/demo` (`base`) + trace JSON in Cursor | 29 |
| 7 | 1:32–1:50 | 18 s | A real mismatch, and Critic misjudgments | `/demo` (`competitor-variant`) | 30 |
| 8 | 1:50–2:05 | 15 s | Converged is not a guarantee | `/demo` (`base`) | 24 |
| 9 | 2:05–2:35 | 30 s | Zetaris, Meterless / NVIDIA, Cursor | Pre-recorded checks | 54 |
| 10 | 2:35–2:55 | 20 s | Final Top 3 and closing line | `/demo` (`base`) + end card | 33 |

Total: **2:55** (5 s margin), **296 words** of narration. Every scene stays at or under 2 words per second, so the voice-over fits with pauses.

## Scenes

Narration is spoken in English and burned in as English subtitles. "Caption" means an on-screen label added in editing, separate from the subtitles.

### 1. The indie developer's problem (0:00–0:10)

- **Screen:** title card. "Indie Growth Agent" and "Open Agent Hackathon 2026 · Track 02: The Agent That Can Explain Why".
- **Operation:** none (still image).
- **Narration:** "Indie developers get a few hours a week for growth. AI can suggest changes — but which numbers can you trust?"
- **Caption (small, lower third):** "Extends a pre-existing project. Pre-existing work: docs/pre-existing-work.md"

### 2. Sample Workspace (0:10–0:25)

- **Screen:** `http://localhost:3000` in the English UI. Sample Workspace: the header (fictional app, period, "Fictional sample"), the notice that every number is made up, **Key metrics**, **14-day trend**.
- **Operation:** start at the top, pause on the notice, then scroll slowly to Key metrics and the 14-day trend.
- **Narration:** "This is a fictional sample app. Impressions rose 40 percent, but the page-view rate and first-time downloads fell. What should change next, and why?"
- **Caption:** "Fictional data · no AI runs on this page"
- Figures behind the narration (from `samples/mahjong/asc_daily.csv`): impressions 30,000 → 42,000, page views 1,800 → 2,100 (rate 6.0% → 5.0%), first-time downloads 360 → 315.

### 3. A saved run, no model call (0:25–0:35)

- **Screen:** `/demo`. The headline "Growth decisions, backed by evidence.", the tags **Recorded Demo · Synthetic Data · Real Model Execution**, the flow "Analyst → Independent Critic → Critic-Reviewed Actions", the note "This page shows a saved run. It uses no API keys and makes no model calls.", and the context row (Target app, Scenario `base`, Period, Model).
- **Operation:** click **Recorded Demo** in the header (or "See the full verification (Recorded Demo) →"). Let the page load on `base`, then hold.
- **Narration:** "A saved run, replayed with no model call. An Analyst proposes; an independent Critic checks with its own SQL."

### 4. v1 → v2 → v3 (0:35–0:52)

- **Screen:** **How the AI's proposals changed**: v1 — Own App Data, v2 — Competitor Context, v3 — Critic-Reviewed Actions (Final).
- **Operation:** scroll to the section, move the pointer across v1, v2, v3, then open the change reasons under v3 (each says "kept").
- **Narration:** "v1 uses only the app's own data. v2 adds public competitor listings, as observations, never facts. v3 answers the Critic: same three actions, corrected claims underneath."
- What changed, for reference: v1 has 5 claims; v2 has 8 and its action #3 now cites a competitor observation and runs after action #1; v3 keeps all three actions and rewrites claims C5–C8.

### 5. Critic round 1 and the revision loop (0:52–1:14)

- **Screen:** **What the Critic questioned** → Critic 1 (Reviewed: v2 — Competitor Context). Tally "SQL checks (judged by code)": Matched 18 · Mismatched 0 · Unverifiable 0. Then the five findings and the Analyst's answers in v3.
- **Operation:** hold on the tally, then scroll through the findings. Highlight two:
  - **Resolved · Wrong claim kind** (C6): the claim says all three top competitors updated in October 2026; one updated on 2026-09-24. Analyst answer: Fixed.
  - **Downgraded · Causal leap** (C7): "likely caused" the drop, while the subtitle/keyword change and the screenshot change overlap. Analyst answer: softened to "may have contributed".
- **Narration:** "In round one, all 18 SQL checks matched, yet the Critic raised five findings. One claim said all three top competitors updated in October; one updated in September. Two causal guesses became hypotheses with a test plan."
- **Caption:** "The Critic never sees the Analyst's SQL or reasoning"

### 6. SQL checks and "unverifiable" (1:14–1:32)

- **Shot 6a (1:14–1:23, 9 s), browser:** Critic 2 (Reviewed: v3) tally: Matched 31 · Mismatched 0 · Unverifiable 1, with "No findings". Then open **SQL evidence** and show one final claim with its SQL and the badge "✓ Matched Critic SQL".
- **Shot 6b (1:23–1:32, 9 s), Cursor:** the unverifiable check in the committed trace, enlarged (see [Enlarged JSON shot](#enlarged-json-shot-scene-6b)).
- **Narration:** "Round two: 31 of 32 checks matched, none mismatched. One query returned two rows instead of one value, so code marks it unverifiable — not a match, not a mismatch."
- **Captions:**
  - 6a: "Matches are decided by code, not by the model"
  - 6a (small): "Counts as judged at record time. Re-comparing the stored values with the current rules leaves this run's counts unchanged."
  - 6b: "Committed trace · Critic check on claim C5 · fictional data"

### 7. A real mismatch, and Critic misjudgments (1:32–1:50)

- **Screen:** `/demo`, switched to **competitor-variant** (its button says the output is Japanese). Critic 1: **Resolved · Value mismatch** on C1 with Claimed 16.67 and Critic value 6.0. Then Critic 2: findings marked **Known misjudgment (confirmed in review after the run)** with "Recorded classification".
- **Operation:** click the `competitor-variant` button at the top, scroll to Critic 1 and hold on the C1 mismatch, then scroll to Critic 2 and hold on one Known misjudgment mark.
- **Narration:** "In another run, the Analyst's SQL swapped numerator and denominator: 16.67 where the Critic's SQL returned 6. v3 fixed it. That run still ended unresolved, with two Critic misjudgments marked."
- **Captions:**
  - "Model output in Japanese"
  - "Impression → page-view rate, prior 7 days: 1,800 / 30,000 = 6.0%"
  - "Ended at the review limit: 8 unresolved, 2 known misjudgments"
- Do not compare this run's Top 3 with `base` as an effect of the data change.

### 8. Converged is not a guarantee (1:50–2:05)

- **Screen:** switch back to `base`. **Outcome**: "Converged · 0 unresolved findings · 1 unverifiable SQL check", the note that defines Converged and Resolved, and **Known limitations (3)** opened.
- **Operation:** click `base`, scroll to Outcome, open Known limitations, and highlight the first two items:
  - The reason for v3 action #3 says the top 3 competitors have 8–10 screenshots; the SQL evidence of its claims does not support that range.
  - v3 action #1 claims 14 days give enough power to detect a 2pp difference; there is no basis for that in the evidence.
- **Narration:** "The main run converged: the last review raised no findings. Converged does not mean correct. Review afterwards found two weak spots the Critic missed."
- **Caption:** "Converged = no findings in the last review. Not: every number is correct."

### 9. Zetaris, Meterless / NVIDIA, Cursor (2:05–2:35)

All shots are pre-recorded. None of them calls a model. Commands, expected output, and masking are in [Terminal shots](#terminal-shots-zetaris-and-nightshift).

| Time | Shot | Narration |
|------|------|-----------|
| 2:05–2:10 | M1: the "Evidence loop and interventions" diagram in `docs/architecture.md` (Markdown preview) | "The demo uses a separate SQLite file. Here is the real setup." |
| 2:10–2:18 | M2: Zetaris live check | "On real data, evidence lives in Zetaris. Analyst, Critic, and code checks all query it over JDBC." |
| 2:18–2:26 | M3: Nightshift status check | "Models run through Meterless Nightshift, pinned to NVIDIA Nemotron 3 Ultra; decisions are kept in Meterless H-MEM." |
| 2:26–2:30 | M4: the Model field on `/demo` (close-up) | "The trace records the model." |
| 2:30–2:35 | M5: the repository open in Cursor, with the result of `verify_offline.py` | "Built in Cursor." |

Captions:

- M1: point at the Zetaris, Meterless Nightshift, Meterless H-MEM, and NVIDIA Nemotron 3 Ultra boxes in turn.
- M2: "Zetaris live check · probe table round trip · table schemas only, no data rows"
- M3: "Nightshift status check (GET /v1/models) · no model request"
- M4: "Model recorded in the trace: openai_compatible:nvidia/nemotron-3-ultra-550b-a55b. The trace does not store the endpoint."
- M5: "Offline checks against fakes · no credentials, network, or model"

### 10. Final Top 3 and closing line (2:35–2:55)

- **Screen (2:35–2:48):** `/demo` `base`, **Final Top 3 Actions — v3** at full width, with the reason, cited claims, and "Known limitation ↓" under each action:
  1. Run a Product Page Optimization A/B test on screenshots 1-3 (new vs. previous) for 14 days
  2. Revert or refine the subtitle/keyword change toward "かんたん点数計算" and monitor Browse CVR for 7 days
  3. Add a calculation-flow screenshot or preview video (step-by-step score calculation) and test via PPO after Action 1 completes
- **Operation:** scroll up to the Final Top 3 section and hold. Move slowly across the three actions and the Known limitation notes under #1 and #3.
- **Narration:** "The final Top 3: test screenshots one to three, revisit the keyword change, then test a calculation-flow screenshot — each with its evidence and limits."
- **Screen (2:48–2:55):** end card. Main line: **"Don't just generate recommendations. Challenge the evidence behind them."** Below it: "Indie Growth Agent · Open Agent Hackathon 2026 · Track 02" and "Zetaris · Meterless · NVIDIA Nemotron · Cursor".
- **Narration:** "Don't just generate recommendations. Challenge the evidence behind them."
- The English UI shows "かんたん点数計算" with the marked gloss "[translation: simple score calculation]". Keep it in frame; no extra caption is needed.

## Enlarged JSON shot (scene 6b)

File: `samples/recorded/sample-base-20261025-110333.json`, lines 2046–2054 (the second Critic round, reviewing v3):

```json
          {
            "claimId": "C5",
            "evidenceIndex": 0,
            "sql": "SELECT rating_count FROM competitor_listing WHERE fetched_on = '2026-10-22' AND country = 'jp' AND is_self = 0 AND primary_genre = 'Utilities' ORDER BY rating_count",
            "claimedValue": "かんたん麻雀計算（架空）",
            "criticValue": null,
            "matched": false,
            "error": "Expected one row with one column, got 2 rows x 1 columns."
          },
```

Setup in Cursor, before recording:

1. Open the file and go to line 2046 (Ctrl+G, `2046`). Put line 2046 near the top of the editor.
2. Turn on word wrap (View → Word Wrap, or Option+Z) so the 186-character `sql` line wraps instead of running off screen.
3. Hide everything but the editor: close the file explorer, the agent chat, the terminal panel, and the other tabs, and turn on Zen mode if possible.
4. Zoom in (Cmd+=) until lines 2046–2054 fill the frame and stay readable at 1080p. The two key lines must be at least about 40 px tall in the recording.
5. Do not edit the file. If Cursor marks it as modified, close it without saving.

Shot, 9 s:

| Time in shot | Frame | Highlight |
|--------------|-------|-----------|
| 0–3 s | Lines 2046–2054 | Box around `"claimId": "C5"` and the wrapped `sql` |
| 3–9 s | Punch in (crop about 2x in editing) on lines 2051–2053 | Boxes on `"matched": false` and `"error": "Expected one row with one column, got 2 rows x 1 columns."` |

Record a still frame of the punched-in lines too, so the edit can hold on it if the narration runs long.

## Terminal shots: Zetaris and Nightshift

Both checks are recorded ahead of time, off the app screens. Neither one sends a model request.

Common setup:

- A terminal used only for the recording: large font, neutral prompt (`export PS1='$ '`), no history on screen (`clear`), window title not showing a path.
- `cd` into the repository and `source .venv/bin/activate` before recording starts, then `clear`.
- Run each command once off camera first and read the full output. Record only after a clean run.
- The commands pipe through `sed` so URLs and the home-directory path never reach the screen. Keep the pipe even if the first run prints nothing to replace.

### M2: Zetaris live check

Needs: Docker running the local Zetaris platform (`zetaris-platform`), Java 17+, and `ZETARIS_*` in `.env`.

Command:

```bash
EVIDENCE_STORE=zetaris python scripts/verify_zetaris_live.py 2>&1 | sed -E "s#${HOME}#~#g; s#jdbc:[^ '\")]+#<jdbc url>#g"
```

What it does: connects over JDBC, writes and re-reads the probe table `zetaris_live_check` (rows with values 1, 2, then 40), reconnects, and prints the table list and column schemas of the evidence store. It reads table names, descriptions, and columns from the store's `evidence_tables` metadata; it does not read any data rows of the evidence tables.

Expected output on success (the time and the table list vary):

```text
OK connected (zetaris (Spark SQL)) in N.Ns
OK replace_table round trip; a replaced table is re-read on the same connection
OK table specs survive reconnect: asc_daily, asc_daily_by_source, competitor_listing, known_events, zetaris_live_check
SQL dialect: zetaris (Spark SQL) (write ANSI SQL; SELECT only).
- asc_daily: App Store Connect Analytics daily totals for our own app. …
    date date
    app_id text
    …
- zetaris_live_check: Round-trip check written by scripts/verify_zetaris_live.py
    day date
    label text
    value integer

Zetaris live check passed.
```

For the 8-second shot, use the three `OK` lines and the final `Zetaris live check passed.` line. Scroll through or cut the schema in the middle.

Masking and when not to use the take:

| What | Where it could appear | Action |
|------|-----------------------|--------|
| JDBC URL, host, port | Not printed on success; possible in a JVM or driver message | Replaced by `sed` (`<jdbc url>`); re-check every frame |
| User, password | Not printed (settings mask the password as `***` and the script does not print settings) | If either appears anywhere, discard the take |
| Home-directory paths (jar, `JAVA_HOME`) | JVM warnings on stderr | Replaced by `sed` (`~`) |
| Data rows | Not printed | If any data row appears, discard the take |
| Any traceback or `Zetaris:` error | A failed run | Do not use. Fix it off camera and record again |

The run overwrites the probe table `zetaris_live_check` in the evidence store each time. That is its intended effect; it does not touch other tables.

### M3: Nightshift status check

Needs: Meterless Nightshift running and `METERLESS_*` in `.env`.

Command (status only; no `--chat`, no `--detect`):

```bash
python scripts/check_meterless.py | sed -E "s#https?://[^ '\")]+#<base URL>#g"
```

What it does: `GET /v1/models` on the runtime. It sends no model request and spends no credit.

Expected output when the runtime is online:

```text
config: MeterlessSettings(base_url='<base URL>', token='***', model_id='nvidia/nemotron-3-ultra-550b-a55b', app='indie-growth-agent')
status: online at <base URL>
models: meterless/…, …
METERLESS_MODEL nvidia/nemotron-3-ultra-550b-a55b: listed by the runtime
```

The last line can instead read `not listed by the runtime`, followed by a `note:` line. A pinned provider model may not appear in `GET /v1/models` (README, LLM provider section). In that case:

- Keep both lines on screen; do not cut them out.
- Change the M3 caption to: "Nightshift status check · no model request · Nemotron is pinned in the config; the runtime's model list can omit provider models".
- Keep the narration. It describes the configuration (`model_id` in the `config:` line), not this check's result.
- Do not run `--chat` to make the line change; that is a model request.

Masking and when not to use the take:

| What | Where it appears | Action |
|------|------------------|--------|
| Base URL | `config:` line and `status: … at` | Replaced by `sed` (`<base URL>`); check every frame |
| Runtime token | Never printed (shown as `***`) | If any other token-like string appears, discard the take |
| `status: offline` or `unauthorized`, or an error detail | Runtime not running or token mismatch | Do not use. Fix it off camera and record again |
| `hint:` line about the token | Token mismatch | Do not use |

### M5: offline checks in Cursor

Command (in Cursor's terminal panel, with `integrations/zetaris/` and `llm/factory.py` open as editor tabs):

```bash
python scripts/verify_offline.py
```

Expected: 19 `PASS  …` lines (an import check, then one per script in `OFFLINE_CHECKS`), a blank line, and `All 19 offline checks passed.` The H-MEM conformance part is skipped without Node.js. It uses local fakes only: no credentials, network, or model. Show the last lines and the open tabs; keep the agent chat and the file explorer closed. If any line says `FAIL`, do not use the take: the failure output can include local paths.

## Shot checklist

Preparation, off camera:

- [ ] `python scripts/show_sample_demo.py` lists the three Recorded Demos
- [ ] `python api_server.py` and `cd web && npm run dev` are running (these terminals are never recorded)
- [ ] A new browser profile or guest window opens `http://localhost:3000` on Sample Workspace (no saved real Analyze result or workspace choice in `localStorage`)
- [ ] UI language set to English; 1920×1080; browser zoom about 125%; bookmarks bar hidden; notifications off
- [ ] Only the `localhost:3000` tab is open; developer tools closed
- [ ] Cursor: file explorer, agent chat, and search panel closed; no `.env`, `products/`, or `tmp/` tab open
- [ ] Recording terminal set up as in [Terminal shots](#terminal-shots-zetaris-and-nightshift)

Shots:

| Done | ID | Scene | What to record | Source | Length to capture |
|------|----|-------|----------------|--------|-------------------|
| [ ] | C1 | 1 | Title card | Still image | 10 s |
| [ ] | R1 | 2 | Sample Workspace: header, notice, Key metrics, 14-day trend | Browser `/` | 20 s |
| [ ] | R2a | 3 | `/demo` top: headline, tags, flow, note, context row | Browser `/demo` (`base`) | 15 s |
| [ ] | R2b | 4 | How the AI's proposals changed; open the v3 change reasons | Browser `/demo` (`base`) | 20 s |
| [ ] | R2c | 5 | Critic 1 tally and the five findings with answers | Browser `/demo` (`base`) | 25 s |
| [ ] | R2d | 6a | Critic 2 tally; SQL evidence opened on one claim | Browser `/demo` (`base`) | 12 s |
| [ ] | R3 | 6b | Enlarged trace JSON, lines 2046–2054, plus a still of 2051–2053 | Cursor | 12 s + still |
| [ ] | R2e | 7 | Switch to `competitor-variant`; C1 value mismatch; one Known misjudgment | Browser `/demo` | 20 s |
| [ ] | R2f | 8 | Switch back to `base`; Outcome; Known limitations (3) opened | Browser `/demo` | 18 s |
| [ ] | M1 | 9 | Evidence loop diagram | Cursor Markdown preview of `docs/architecture.md` | 8 s |
| [ ] | M2 | 9 | Zetaris live check | Recording terminal | Full run |
| [ ] | M3 | 9 | Nightshift status check | Recording terminal | Full run |
| [ ] | M4 | 9 | Close-up of the Model field | Crop from R2a | — |
| [ ] | M5 | 9 | `verify_offline.py` result with the integration tabs open | Cursor | 10 s |
| [ ] | R2g | 10 | Final Top 3 Actions — v3 with Known limitation notes | Browser `/demo` (`base`) | 15 s |
| [ ] | C2 | 10 | End card with the closing line | Still image | 7 s |
| [ ] | VO | all | Narration, recorded separately, scene by scene | Microphone | — |
| [ ] | SUB | all | English subtitles matching the narration | Editor | — |

Capture each browser shot a few seconds longer than its slot, so the edit can trim.

## Checks before export

- [ ] Length is 3:00 or less (target 2:55)
- [ ] No model call was made while recording (no Analyze, evidence run, Live Sample, or `--chat`)
- [ ] No real app metrics, no My Workspace, no Portfolio
- [ ] No `.env`, base URL, JDBC URL, host, port, user, token, key, or home-directory path in any frame (check M2 and M3 frame by frame)
- [ ] In 6b, `"matched": false` and the `error` text are readable at 1080p
- [ ] Cursor's agent chat, file explorer, and `tmp/` are not visible
- [ ] Zetaris, Meterless, NVIDIA, and Cursor are each named and shown (scene 9 and the end card)
- [ ] The video says the demo ran on SQLite and that the trace records the model id but not the endpoint
- [ ] "Converged" is never presented as "correct" or "verified"
- [ ] `base` and `competitor-variant` are not compared as cause and effect
- [ ] Subtitles match the narration
