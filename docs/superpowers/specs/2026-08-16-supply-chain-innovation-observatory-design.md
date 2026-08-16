# Supply Chain Innovation Observatory — Design Spec

**Date:** 2026-08-16
**Status:** Approved for planning
**Owner:** Kevin Dooley (ASU W. P. Carey)

---

## 1. Purpose

A weekly analytical dashboard that detects the emergence and diffusion of supply chain
innovations from observable digital traces in publicly accessible data.

The central question: **what technologies and infrastructure capabilities are moving from
idea → experimentation → investment → deployment → diffusion?**

Six tracked questions map to concrete outputs:

| Question | Dashboard block |
|---|---|
| What technologies are accelerating right now? | This Week's Movers |
| Which technologies are actually moving out of the lab? | Lab → Field Watch |
| Where is new logistics capability being constructed? | Build Map |
| Which technologies have substance versus attention? | Substance vs. Attention |
| What technologies are developers actually building? | Stage Board (Experiment axis) + Developer signal |
| What technologies are large companies beginning to adopt? | Corporate Adoption (distinct SEC filers) |

## 2. Scope

**In scope.** A reproducible Python pipeline that fetches public data weekly, stores raw
responses, computes stage scores and four headline metrics for a curated technology
watchlist, and renders a single self-contained HTML dashboard.

**Out of scope (explicit non-goals).**

- No paid data sources (Crunchbase, PitchBook, Lightcast, Bloomberg).
- No LLM inside the pipeline. Term matching and scoring are deterministic so that any
  week can be recomputed and will produce identical numbers. Interpretation stays with
  the human reader. An LLM *is* used offline to author the lexicon (§5.1) — that is a
  separate, human-approved command that never runs during a weekly run.
- No forecasting or causal claims. The system describes observed signal movement.
- No web server, database server, or hosted deployment. Local files only.
- No user accounts, auth, or multi-tenancy.

## 3. Data sources

All sources are public. Two require a free key, supplied via `.env`.

| Collector | Endpoint | Key | Stage(s) fed | Cadence |
|---|---|---|---|---|
| `arxiv` | `http://export.arxiv.org/api/query` | none | Idea | weekly |
| `hn` | `https://hn.algolia.com/api/v1/search_by_date` | none | Idea, Attention | weekly |
| `patentsview` | `https://search.patentsview.org/api/v1/patent/` | `PATENTSVIEW_API_KEY` | Experiment | weekly |
| `github` | `https://api.github.com/search/repositories`, `/repos/{r}/stats` | `GITHUB_TOKEN` | Experiment | weekly |
| `usaspending` | `https://api.usaspending.gov/api/v2/search/spending_by_award/` | none | Investment, Deployment | weekly |
| `edgar` | `https://efts.sec.gov/LATEST/search-index` (full-text search) | none (User-Agent required) | Investment, Diffusion | weekly |
| `federalregister` | `https://www.federalregister.gov/api/v1/documents.json` | none | Deployment | weekly |
| `gdelt_doc` | `https://api.gdeltproject.org/api/v2/doc/doc` (`mode=timelinevol`, `mode=artlist`) | none | Attention, Investment, Deployment | weekly |
| `gdelt_geo` | `https://api.gdeltproject.org/api/v2/geo/geo` | none | Deployment (map) | weekly |

**Politeness rules.** Every collector sets a descriptive `User-Agent` including a contact
email (required by SEC). Requests are rate-limited per source with exponential backoff on
429/5xx. GitHub search is capped at 30 requests/minute; PatentsView at 45/minute. Each
collector declares its own limit in a module-level constant.

**Query windows.** Each weekly run fetches documents dated within the ISO week being
processed, with a 7-day lookback overlap to catch late-indexed documents. Deduplication is
by source-native document ID, so overlap is safe.

## 4. Watchlist

`watchlist.yaml` holds ~32 technologies grouped into six families, under a top-level
`lexicon_version`. Each entry:

```yaml
lexicon_version: 3
technologies:
- id: autonomous_trucking
  name: Autonomous trucking
  family: vehicles
  include:
    - "autonomous truck(s|ing)?"
    - "driverless truck"
    - "self-driving (truck|freight)"
  exclude:
    - "autonomous trucking bill"   # legislative noise, not deployment
  cik_hints: [AURORA INNOVATION, KODIAK, WAYMO VIA]   # optional, EDGAR entity aid
  status: active
  added_week: 2026-W33
  patterns_changed_week: 2026-W33   # set on every merged lexicon edit
```

**Initial families and members.**

- **Automation & robotics** — warehouse robotics (AMR/ASRS), piece-picking robotics,
  humanoid robots in logistics, autonomous yard trucks, port/terminal automation,
  last-mile delivery robots, delivery drones.
- **Vehicles & energy** — autonomous trucking, electric heavy-duty trucks, hydrogen fuel
  cell trucks, freight EV charging infrastructure, port electrification / shore power.
- **Digital planning & AI** — agentic AI for procurement, supply chain digital twins,
  demand forecasting ML, control towers, generative AI for supply chain planning,
  transportation management AI, digital freight matching.
- **Data, identity & traceability** — item-level RFID, digital product passport,
  GS1 2D barcode transition, blockchain traceability, critical minerals traceability.
- **Physical & cold chain** — cold chain IoT monitoring, active cold chain packaging,
  additive manufacturing for spare parts, microfactories / distributed manufacturing,
  microfulfillment automation, computer vision for damage inspection.
- **Networks & resilience** — supply chain risk intelligence, nearshoring analytics,
  rail intermodal technology, inland ports, private 5G in warehouses,
  quantum optimization for logistics.

**Auto-discovery.** Each week the system extracts candidate noun phrases (2–4 tokens) from
arXiv titles, Hacker News titles, and Federal Register document titles in the supply chain
corpus. A candidate is surfaced when it appears ≥5 times this week, at ≥3× its trailing
12-week mean, and matches no active watchlist entry. Candidates land in the
`candidate_terms` table with status `new`. The user promotes or ignores them by editing
`watchlist.yaml`; the pipeline never edits the watchlist itself.

## 5. Term matching

Deterministic and testable. For each document, the concatenation of title + abstract/summary
is lowercased and scanned with compiled regexes built from each technology's `include`
patterns, wrapped in word boundaries. Any `exclude` pattern match vetoes the document for
that technology. A document may match multiple technologies; each match is one observation
row recording which pattern fired, so any count can be traced back to its evidence.

## 5.1 Lexicon authoring (LLM-assisted, offline)

The quality of every number in this system depends on the quality of the word lists.
Hand-writing regexes for 32 technologies produces thin, brittle coverage. So an LLM is used
as an **authoring tool**, run deliberately by the user, never during a weekly run.

```bash
python -m observatory.lexicon propose autonomous_trucking   # expand one technology
python -m observatory.lexicon propose --all                 # expand the whole watchlist
python -m observatory.lexicon triage 2026-W33               # draft patterns for rising terms
python -m observatory.lexicon diff                          # show proposals vs. current
```

**What it produces.** For each technology, the model is asked for: synonyms and spelling
variants, common abbreviations, vendor and product names in the category, adjacent terms
that should *not* match (false friends), and the terms practitioners use that researchers
do not. Output is written to `lexicon/proposals/<tech_id>-<date>.yaml` — never directly to
`watchlist.yaml`.

**What it does not do.** It does not edit the watchlist, score anything, rank technologies,
or write dashboard text. Merging a proposal is a human edit, reviewed as a normal diff.

**Triage mode.** After a weekly run, `triage` reads that week's `candidate_terms` rows plus
three example documents each, and drafts a candidate watchlist entry (id, name, family,
include/exclude patterns) for the ones that look like real technologies rather than news
noise. These land in `lexicon/proposals/candidates-<week>.yaml` for the same human review.
The Rising Terms dashboard block itself is computed by the deterministic pipeline and is
identical whether or not triage was ever run.

**Versioning.** `watchlist.yaml` carries a top-level `lexicon_version` (integer, bumped on
every merged change) and a changelog at `lexicon/CHANGELOG.md`. Every `weekly_metrics` row
stores the `lexicon_version` used to compute it. Because widening a pattern changes historic
counts, a `--rebuild` recomputes all weeks under the current lexicon so the series stays
internally consistent; the dashboard footer states the lexicon version and the date of the
last change, and the Movers block suppresses momentum for any technology whose patterns
changed within the trailing 8 weeks — an acceleration caused by a wider net is not an
acceleration in the world.

**Cost and reproducibility.** Proposal files are committed to git, so the lexicon's
provenance is auditable and the pipeline remains fully runnable by someone with no LLM
access at all.

## 6. Data model

SQLite at `data/observatory.db`. Raw JSON/XML responses live on disk at
`data/raw/<ISO-week>/<source>/<n>.json` and are the source of truth — the database is a
derived artifact and can be rebuilt from raw with `--rebuild`.

```sql
sources(name TEXT PK, last_run_week TEXT, status TEXT, note TEXT, updated_at TEXT)
raw_fetch(id INTEGER PK, source TEXT, week TEXT, url TEXT, http_status INT,
          fetched_at TEXT, path TEXT)
observations(id INTEGER PK, source TEXT, week TEXT, tech_id TEXT, doc_id TEXT,
             doc_date TEXT, title TEXT, url TEXT, entity TEXT, entity_id TEXT,
             amount REAL, lat REAL, lon REAL, matched_pattern TEXT, raw_ref INT,
             UNIQUE(source, doc_id, tech_id))
weekly_signals(tech_id TEXT, week TEXT, signal TEXT, value REAL,
               PRIMARY KEY(tech_id, week, signal))
weekly_metrics(tech_id TEXT, week TEXT, momentum REAL, sai REAL, lfi REAL,
               adoption INT, adoption_new INT,
               stage_idea REAL, stage_experiment REAL, stage_investment REAL,
               stage_deployment REAL, stage_diffusion REAL, position REAL,
               lexicon_version INT,
               PRIMARY KEY(tech_id, week))
candidate_terms(term TEXT, week TEXT, count INT, baseline REAL, ratio REAL,
                status TEXT, PRIMARY KEY(term, week))
```

## 7. Signals and metrics

### 7.1 Raw signals

Per technology per ISO week:

| Signal | Definition |
|---|---|
| `arxiv_papers` | matching preprints |
| `hn_points` | summed points of matching stories |
| `patents` | matching granted patents (grant date in week) |
| `gh_repos_new` | matching repos created in week |
| `gh_stars_delta` | stars gained across matching repos |
| `gh_commits` | commits in week across top-50 matching repos by stars |
| `fed_obligated` | USAspending obligated dollars on matching awards |
| `fed_awards` | count of matching awards |
| `edgar_filings` | matching 8-K/10-K/10-Q/S-1 filings |
| `edgar_filers` | **distinct** filer CIKs in trailing 52 weeks |
| `fedreg_docs` | matching Federal Register rules and notices |
| `media_articles` | GDELT article volume |
| `media_deploy` | GDELT articles also matching a deployment lexicon (opens, breaks ground, goes live, begins operations, deploys, commissions) |

### 7.2 Normalization

Each signal is z-scored *within technology* across its trailing 52 weeks (minimum 12 weeks;
before that, the observatory renders the block with a "warming up" badge rather than a
misleading z-score). Write `z(x)` for that value.

### 7.3 Stage scores

```
stage_idea        = mean(z arxiv_papers, z hn_points)
stage_experiment  = mean(z patents, z gh_repos_new, z gh_commits, z gh_stars_delta)
stage_investment  = mean(z fed_obligated, z edgar_filings)
stage_deployment  = mean(z fed_awards, z fedreg_docs, z media_deploy)
stage_diffusion   = mean(z edgar_filers, z media_articles)
```

**Pipeline position** is the score-weighted centroid of stage index 1–5, using softmax
weights over the five stage scores. Range 1.0–5.0. This is the x-axis of the Stage Board.

### 7.4 Headline metrics

**Momentum** — is it speeding up? Let `S(w)` be the 4-week trailing mean of the composite
signal (the mean of the five stage scores). Then

```
slope_now  = S(w)   - S(w-4)
slope_prev = S(w-4) - S(w-8)
accel      = slope_now - slope_prev
momentum   = z-score of accel across all active technologies in week w
```

Cross-sectional z-scoring makes the weekly ranking comparable. Requires 8 weeks of history.

**Substance vs. Attention Index (SAI)**

```
hard = mean(z patents, z gh_repos_new, z gh_commits, z fed_awards, z edgar_filers)
soft = mean(z media_articles, z hn_points)
sai  = hard - soft
```

Positive = more building than talking. Negative = hype.

**Lab → Field Index (LFI)**

```
lfi = mean(stage_investment, stage_deployment) - mean(stage_idea, stage_experiment)
```

A technology "crosses over" the week its 4-week trailing LFI turns positive after being
negative for at least 4 consecutive weeks. Crossovers populate the Lab → Field Watch block.

**Corporate Adoption** — `edgar_filers`, the count of distinct filer CIKs mentioning the
technology in the trailing 52 weeks, plus `adoption_new`, the CIKs appearing for the first
time this week. Breadth of adopters, not volume of mentions.

## 8. Dashboard

`dashboard.html` — one self-contained file, inlined CSS and JS, charts generated as inline
SVG in Python. No CDN, no network at view time. A dated copy is archived to
`output/dashboard-<ISO-week>.html` and `output/latest.html` is refreshed each run.

Blocks, top to bottom:

1. **Source health strip** — one chip per collector: green (fresh), amber (stale, used last
   week's cache), red (failed). Hover gives the error.
2. **This Week's Movers** — top 5 by momentum, each with the signal that contributed most to
   the acceleration and a week-over-week arrow.
3. **Stage Board** — scatter, x = pipeline position (1–5), y = momentum, dot size = total
   raw volume, color = family.
4. **Substance vs. Attention** — scatter, x = soft, y = hard, diagonal reference line.
   Quadrants labeled: *Quiet builders*, *Breaking out*, *Dormant*, *Hype*.
5. **Lab → Field Watch** — table of crossovers this week and the last 8 weeks, with the LFI
   sparkline for each.
6. **Build Map** — US map. Points from USAspending place-of-performance (sized by obligated
   dollars) and GDELT GEO deployment articles. Filterable by technology family.
   USAspending returns place of performance as city/state/ZIP, not coordinates; those are
   resolved to latitude/longitude with a bundled offline ZIP-and-state centroid table
   (`data/geo/zip_centroids.csv`, from the Census ZCTA gazetteer). Unresolvable locations
   are counted in a "location unknown" footnote rather than dropped silently.
7. **Rising Terms** — candidate terms with count, ratio, and three example document links.

**Drill-down.** Every number links to an evidence view listing the underlying
`observations` rows with title, date, entity, and source URL. Evidence pages are generated
as a second self-contained file, `evidence.html`, keyed by anchor.

**Week-over-week.** Every headline number carries its prior-week value and a delta arrow.

## 9. Error handling and reliability

- Each collector runs in isolation. An exception is caught, recorded to `sources.status =
  'failed'` with the message, and the run continues.
- On failure, metrics for that source's signals reuse the previous week's value and the
  affected technology rows are flagged `stale` in the UI rather than silently zeroed. A
  missing week is never treated as a zero-count week — that would fabricate a decline.
- HTTP: 3 retries with exponential backoff on 429 and 5xx. 4xx other than 429 fails fast.
- Raw responses are written before parsing, so a parser bug never costs a re-fetch.
- Every run appends a line to `data/run_log.jsonl` with week, per-source counts, duration,
  and failures.

## 10. Testing

`pytest`, no network in tests.

- **Collector parsers** — one saved fixture response per source in `tests/fixtures/`,
  asserting parsed observation counts and field extraction.
- **Term matcher** — table-driven cases covering include hits, exclude vetoes, word
  boundaries, and multi-technology documents.
- **Metric math** — synthetic weekly series with known acceleration, known SAI sign, and a
  constructed LFI crossover; assert exact expected values.
- **Cold start** — fewer than 12 weeks of history produces "warming up" rather than a
  z-score.
- **Degradation** — a simulated collector failure leaves prior-week values in place, marks
  the source red, and still renders a dashboard.
- **Renderer smoke test** — generated HTML contains all seven blocks and no external
  `http(s)://` resource references.
- **Determinism** — running the full pipeline twice over the same raw data produces
  byte-identical `weekly_metrics` rows. This is the test that protects the no-LLM-at-runtime
  rule; it fails loudly if anything nondeterministic creeps into the run.
- **Lexicon isolation** — the weekly run imports no LLM client. Asserted by scanning
  `run.py`'s import graph, so the rule cannot be broken by accident.
- **Momentum suppression** — a technology whose `patterns_changed_week` is within 8 weeks
  is excluded from the Movers block.

## 11. Operations

```bash
python -m observatory.run                 # fetch, normalize, score, render current week
python -m observatory.run --week 2026-W33 # a specific week
python -m observatory.run --skip-fetch    # recompute from saved raw
python -m observatory.run --rebuild       # rebuild all history from raw
python -m observatory.run --only github   # single collector
```

Dependencies: `requests`, `PyYAML`, `Jinja2`, `pytest`. Standard library `sqlite3`. No
numpy/pandas requirement — the statistics involved are small and explicit.

Secrets live in `.env` (`GITHUB_TOKEN`, `PATENTSVIEW_API_KEY`, `SEC_CONTACT_EMAIL`), which
is git-ignored. `.env.example` is committed. The pipeline refuses to start if a required
key is missing, naming which one.

Scheduling is manual for v1 — the user runs one command weekly. A cron entry is documented
in the README but not installed.

## 12. Repository layout

```
observatory/
  __init__.py
  run.py                 orchestration + CLI
  config.py              paths, env, rate limits
  http.py                shared session, retry, backoff, User-Agent
  collectors/
    base.py              Collector protocol, raw-write helper
    arxiv.py  hn.py  patentsview.py  github.py  usaspending.py
    edgar.py  federalregister.py  gdelt_doc.py  gdelt_geo.py
  matcher.py             watchlist compilation + document matching
  lexicon.py             OFFLINE LLM authoring CLI (propose / triage / diff)
  normalize.py           observations -> weekly_signals
  metrics.py             z-scores, stages, momentum, SAI, LFI, adoption
  discover.py            candidate term extraction
  store.py               schema + queries
  charts.py              inline SVG generation
  render.py              Jinja2 -> dashboard.html, evidence.html
  templates/
watchlist.yaml
lexicon/ proposals/  CHANGELOG.md
data/    raw/  observatory.db  run_log.jsonl
output/  latest.html  dashboard-<week>.html  evidence.html
tests/   fixtures/
```

Each module has one purpose and a narrow interface: collectors return lists of raw
documents, the matcher turns documents into observations, normalize turns observations into
signals, metrics turns signals into scores, render turns scores into HTML. Any stage can be
tested with fixture data from the stage above it.

## 13. Build order

1. Skeleton: config, http, store schema, CLI that does nothing but log.
2. Watchlist + matcher, fully tested. Then `lexicon propose --all` to build the real word
   lists before any collector is pointed at live data — thin patterns would poison the
   first weeks of history.
3. Three keyless collectors (arXiv, Hacker News, Federal Register) end to end to first HTML.
4. Metrics module against synthetic data.
5. Remaining collectors: GDELT doc/geo, USAspending, EDGAR, GitHub, PatentsView.
6. Full dashboard blocks, evidence drill-down, Build Map.
7. Auto-discovery of rising terms, then `lexicon triage`.
8. Backfill: run `--rebuild` across the trailing 52 weeks where sources allow it, to give
   the first live dashboard real history instead of a cold start.

Backfill availability differs by source (GDELT and EDGAR support long history; GitHub
search does not backfill stars or commits). Where backfill is impossible the signal starts
at the first live week and is excluded from z-scoring until it has 12 weeks.
