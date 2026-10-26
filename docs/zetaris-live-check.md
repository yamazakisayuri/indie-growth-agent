# Zetaris live check

Output of one run of `scripts/verify_zetaris_live.py` against the local Zetaris platform (Docker), recorded on 2026-10-26 at 21:16 JST for the M2 shot of the [demo video](demo-video.md). The code was `6c349dc`.

```bash
EVIDENCE_STORE=zetaris python scripts/verify_zetaris_live.py
```

What it shows: the evidence store connects to Zetaris over JDBC, writes and re-reads the probe table `zetaris_live_check` on the same connection, and after reconnecting still lists the evidence tables with their column schemas (read from the store's `evidence_tables` metadata).

What it does not show: any evidence run (Analyst, Critic, or code checks) on Zetaris. No data rows of the evidence tables are printed, and the evidence runs on real data are not committed (see [the README](../README.md#meterless-and-zetaris-what-this-repository-can-show)).

The output is unedited except that URLs are replaced with `<url>`. It contains no JDBC URL, host, port, user, password, or local path. The SLF4J lines are a warning from the JDBC driver's logging and do not affect the check.

```text
SLF4J: Failed to load class "org.slf4j.impl.StaticLoggerBinder".
SLF4J: Defaulting to no-operation (NOP) logger implementation
SLF4J: See <url> for further details.
OK connected (zetaris (Spark SQL)) in 1.5s
OK replace_table round trip; a replaced table is re-read on the same connection
OK table specs survive reconnect: asc_daily, asc_daily_by_source, competitor_listing, known_events, zetaris_live_check
SQL dialect: zetaris (Spark SQL) (write ANSI SQL; SELECT only).
- asc_daily: App Store Connect Analytics daily totals for our own app. A day with no report row is absent (not zero). impressions / page views can be 0 on a day that only appears in the downloads report.
    date date
    app_id text
    territory text -- ALL = every territory
    impressions integer
    product_page_views integer
    first_time_downloads integer
    source text -- asc_analytics
- asc_daily_by_source: App Store Connect daily impressions and first-time downloads split by how users found the app. Page views have no source split. Sources outside these buckets are not listed, so buckets may not add up to asc_daily.
    date date
    app_id text
    territory text
    source_bucket text -- search | browse | referrer
    impressions integer
    first_time_downloads integer
    source text -- asc_analytics
- competitor_listing: Public App Store listing data (iTunes Lookup API) for our app and a fixed list of competitors, one row per app per fetch date. External observation: a different source and population from asc_daily.
    fetched_on date
    country text -- App Store storefront, e.g. jp
    app_id text
    is_self integer -- 1 = our app, 0 = competitor
    name text
    seller text
    primary_genre text
    rating_avg real -- NULL when there are no ratings
    rating_count integer
    version text
    current_version_released_on date
    first_released_on date
    price real
    screenshot_count integer -- iPhone screenshots on the listing
    description_head text -- First 300 characters
    url text
    source text -- itunes_lookup
- known_events: Developer-written context (releases, store changes, unusual usage). Context only: an event near a change does not prove it caused the change.
    date date
    end_date date -- NULL for a single-day event
    type text
    product text
    description text
- zetaris_live_check: Round-trip check written by scripts/verify_zetaris_live.py
    day date
    label text
    value integer

Zetaris live check passed.
```
