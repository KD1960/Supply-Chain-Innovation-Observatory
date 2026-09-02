# STATUS

Supply Chain Innovation Observatory — state of the project, written for someone
picking it up cold. Last updated 2026-09-01.

Owner: Kevin Dooley, ASU W. P. Carey.

**Read this, then `docs/process-review-2026-08-31.md`.** That is an independent
process review commissioned on 2026-08-31; it is more candid about this
project's weaknesses than this document is, and its risk register is the best
short guide to what will break next.

**Read the review's risk 1 as closed.** It reports every published z-score as
inflated by collection ramp-up, because `compute_quarter` never passed
`collected` to `quarterly_signal`. That was fixed in `cec2a0b`, and the review
was committed after it (`7359a3a`) describing the state before. Verified live
on 2026-09-01: the 2026-Q2 window drops 2025-Q3, the quarter that was collected
for 5 of its 13 weeks. Do not fix it again.

---

## 1. What this is

A quarterly report that detects the emergence and diffusion of supply chain
innovations from observable digital traces in publicly accessible data.

The central question: **what technologies are moving from idea → experimentation
→ investment → deployment → diffusion?**

Collection runs weekly and unattended. Reporting is quarterly, on calendar
quarters. The two cadences are deliberately different and neither should be
changed into the other — see §4.

## 2. Current state

| | |
|---|---|
| Tests | **681 passing** |
| Lexicon | version **10**, 48 active technologies |
| Observations | **2,324** |
| Sources | 11, across 9 evidence families |
| By source | github 799, arxiv 517, scopus 421, openalex 239, edgar 120, lens 64, hn 62, nsf 40, usaspending 29, federalregister 20, abi_inform 13 |
| Precision | **70%** at lexicon v9, one model coder, 120 of 132 judged (`docs/precision-audit-2026-09-02.md`) — not comparable with the earlier 51% |
| Deliverable | `output/report-<period>.html`, with evidence pages and standalone SVG/PDF charts |
| Weekly page | collection health only — did the collectors run, what arrived, rising terms |
| Repository | https://github.com/KD1960/Supply-Chain-Innovation-Observatory (public) |

**The 2026-Q3 report withholds its scores.** The quarter has run 10 of 13 weeks,
and a score compares a period against periods that are complete. Counts are
shown; inferences are not. 2026-Q2 is the most recent fully scored period.

**The table above is generated.** `python -m observatory.run --write-status`
rewrites its four counted rows from the database, and `tests/test_status_table.py`
fails when they drift. Do not hand-edit them. The other rows -- precision, the
deliverable, the weekly page, the repository -- are claims rather than counts
and are still written by hand.

## 3. How to run it

    python -m observatory.run --write-status         # regenerate section 2 from the database
    python -m observatory.run                        # the weekly run; this is what cron does
    python -m observatory.run --quarter 2026-Q4      # the deliverable
    python -m observatory.run --annual 2026
    python -m observatory.run --export-queries 2026-Q4 --split   # the sheet a human works from
    python -m observatory.run --import-manual        # ingest the exports that come back
    python -m observatory.run --rebuild              # replay all raw under the current lexicon
    python -m observatory.run --backfill 52          # fetch N trailing weeks, then rebuild

Installed cron, Monday 07:00 local:

    0 7 * * MON cd '/Users/kevindooley/Claude/Projects/Supply chain innovation' && /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m observatory.run >> data/cron.log 2>&1

The interpreter path matters: `/usr/bin/python3` is macOS's 3.9 and has none of
the dependencies. Keys live in `.env`; `GITHUB_TOKEN` and `SEC_CONTACT_EMAIL`
are set and working.

**A number read without a rebuild is the old lexicon's number.** Observations
insert with `INSERT OR IGNORE`, so rows written under old patterns survive until
`--rebuild` drops the derived tables. This has produced a wrong figure in a
report to the owner twice.

## 4. The rules this project runs on

These were each learned by shipping a wrong number, and they are why the code
looks the way it does.

- **A missing week is not a zero week.** A source that failed leaves its signals
  absent, not zero. Folding absence into zero invents declines.
- **Raw before parse.** Collectors write untouched response bodies to
  `data/raw/<week>/<source>/` before anything parses them. The database is a
  derived artifact and can always be rebuilt.
- **The document's own date decides its week**, not the run week. A run rescores
  every week it wrote into.
- **Context gating.** Terms that belong to every field (`ERP`, `humanoid robot`,
  `computer vision`) count only when the document also uses supply chain
  language. The gate is per technology and document-level.
- **Say it out loud when a cap bites.** Silent truncation is this project's
  oldest failure mode.
- **Standing instruction from the owner:** plain correctness bugs inherited from
  the plan get fixed without asking and reported in the summary; genuine
  judgment calls go to the owner.

## 4a. What changed recently

The full reasoning is in the commit messages, which are long on purpose. In
brief, over 2026-08-27 to 08-31:

- **USAspending fixed** — it searched six multi-word phrases against an API that
  phrase-matches, returning 36 awards in a year and matching none. It queries
  freight assistance-listing programmes now.
- **Five sources added** — Scopus, Lens.org patents, ABI/INFORM trade press
  (all human-exported), plus OpenAlex and NSF (automated, keyless). SBIR and
  CORDIS were measured and rejected; see §5.
- **Lexicon v6 → v9** — the domain word moved out of ten patterns and into the
  context gate; operations research retired as a method rather than a
  technology; Positive Train Control split into its own entry.
- **Reporting moved to calendar quarters**, selected by each document's own
  date. The ISO year had been ending on 27 December.
- **Metrics moved from a 52-week to a four-quarter window.** A trailing weekly
  z-score had been ranking technologies with no documents in the week.
- **The weekly dashboard became a collection health view**; everything
  interpretive, and the evidence pages, moved to the quarterly report.

On 2026-09-01:

- **The withholding notice was gated on the wrong condition.** A report says
  "scores are withheld" in two places, and both asked only whether the *period*
  had finished. A score also needs three collected quarters in its trailing
  window, and that fails independently: 2025-Q4 ran all 13 of its weeks and
  still could not be scored, because one quarter of its window had ever been
  collected. Neither notice fired, so the Stage Board and the movers simply
  vanished from a complete-looking page with nothing said — this project's
  oldest failure mode, wearing the clothes of the guard against it. Both places
  now name the collected count. It was silently blank on two published reports,
  2025-Q4 and 2026-Q1, not one.
- **`MIN_HISTORY_QUARTERS` had no boundary test.** Mutating it from 3 to 2 left
  all 627 tests green. The test that should have caught it rejected "a z-score
  from two quarters" in its docstring and then probed one, which passes at
  either setting. It is now pinned in both directions.
- **Reports regenerated.** 2025-Q3, 2025-Q4 and the 2025 annual were older than
  the fix, the current template and lexicon v9 — the annual was built under v8.
  All seven reports were rebuilt and swept: each now either scores or says why
  it cannot. 2026-Q2 remains the only scored period.
- **Sixteen of twenty trade-press exports were never run**, which is why
  diffusion looked thin. `--import-manual` now says what never arrived. See §5.
- **EDGAR measured and two barren terms removed.** See §5 and
  `docs/edgar-depth-2026-09-01.md`.
- **The quarterly report has a masthead** — the W. P. Carey / NASPO lockup
  embedded as a data URI, disclosure tabs for the theory, the table and each
  figure, and a credit line. `observatory/assets/` holds the lockup.
- **`ruff` runs in a pre-commit hook, in CI and in the suite**, and was
  verified against the two defects the review said a linter would have caught.
  Details in §5.
- **Collection failures are durable.** `source_attempts` appends every attempt,
  a non-200 reaches `raw_fetch`, the run log carries `failed_sources` and
  `empty_sources`, and the weekly health strip reads the week it is about
  instead of the latest state — so a re-rendered 2025-W35 now shows the five
  collectors that existed then, each stamped W35, not today's eleven. Full
  detail in §5.
- **`data/` is backed up**, which the review listed as risk 2, Critical.
  `/Volumes/BUBBA/SC-Innovation-Observatory-backup/2026-09-01/` holds the 36
  licensed exports loose, plus a 109M archive of the whole 915M directory, a
  SHA-256 manifest and a README with the restore command. Verified rather than
  assumed: 3,437 files in against 3,437 out, the database's checksum identical
  in all three places, and all 36 exports extracted and diffed byte-for-byte
  against the source. `.env` is deliberately excluded. Time Machine also covers
  the project — it is not excluded and ran 2026-08-31 — but its snapshots
  cannot be read without Full Disk Access, so that was never verified from
  here and this copy does not depend on it.

  **It is a snapshot and goes stale from the next Monday run.** Remake it after
  each quarter's export cycle, which is when the irreplaceable part changes.

## 5. What is broken or missing

**USAspending is fixed** (2026-08-27). It searched six multi-word phrases, and
the API phrase-matches them against terse award prose: `port` returns over a
hundred awards in a week where `port infrastructure` returns one. Six such
phrases retrieved 36 awards in a year and matched none of them.

Widening the keywords -- which this document used to recommend -- was measured and
rejected: broad terms retrieve defence logistics services, passenger transit and
highway resurfacing, trading a false zero for thousands of rows of false signal.

It now queries **assistance-listing programmes** instead, the same
container-filter principle as ISSNs and CPC codes in the supplemental-sources
spec. Nine freight programmes are queried and eleven named exclusions record why
they are not. Two programmes whose entire purpose is one tracked technology
(Clean Ports, MARAD Air Emissions) attribute directly, because federal award
prose describes civil works and would otherwise never match.

Measured live over four weeks: **111 awards retrieved and 8 observations, from
36 and 0.** Every observation carries coordinates, so the Build Map has points
for the first time.

**The match rate is still only 7%**, so this yields roughly 100 observations a
year. Investment remains the thinnest stage, and whether federal infrastructure
money should count as domain evidence without technology resolution is an open
question for the owner.

**Diffusion is the thinnest stage, and EDGAR is not the main reason.**
Measured 2026-09-01, `docs/edgar-depth-2026-09-01.md`. Diffusion is fed by two
signals: filings (EDGAR) and trade press (ABI/INFORM). In 2026-Q2 that is 35
documents and **1**. ABI/INFORM holds **9 documents in the whole database** —
and the reason is not that trade press is thin. **Sixteen of the twenty exports
the sheet asked for were never run** (2026-09-01).

`--export-queries 2026-Q3 --split` asks for twenty ABI/INFORM files: four
publications by five term batches. Four exist, all of them Supply Chain Dive.
**Modern Materials Handling, Supply Chain Management Review and the Journal of
Commerce were never exported at all**, and Supply Chain Dive's fifth batch was
skipped — its sidecar says so. Trade press is not a thin source; it is a fifth
of a source, and its 30% match rate is the second best in the project.

One Scopus journal is missing too: **`scopus-14784092.ris`, the Journal of
Purchasing and Supply Management**. Eleven of twelve arrived.

**Nothing noticed.** `read_exports` refuses a file it cannot parse, on the
principle that a silently ignored export is a silently missing quarter — but it
can only judge the files it can see. `supplemental.missing_exports` now compares
what arrived against what the sheet asked for, and `--import-manual` prints the
absences before ingesting anything. It is never fatal: the rows that did arrive
are real, and refusing them would trade an undercount for nothing.

**Corrected by the owner 2026-09-01, and it matters.** Supply Chain Dive's
fifth batch *was* run and returned nothing — its own sidecar always said so;
a stale note in batch 1's sidecar claimed otherwise and has been fixed. And
**all five Journal of Commerce batches were run, and all five were empty**.
They are absent from disk, so the check reports them as never run: a genuine
empty needs a zero-record file and a sidecar, or it cannot be told from a hole.

**Journal of Commerce returning nothing across ~66 terms in a quarter is
probably a title that does not resolve**, not a quiet quarter — `sources.yaml`
already records DC Velocity, FreightWaves and Material Handling & Logistics
failing the same way under `PUB.EXACT`. Two diagnostic searches settle it and
are in `docs/exports-2026-Q3-remaining.md`.

**Those eleven were run on 2026-09-01 and are in.** Modern Materials Handling
returned 36 records, Supply Chain Management Review 12, and the Journal of
Purchasing and Supply Management 41. Trade press went from **30 retrieved and 9
matched to 78 and 16**; in 2026-Q3 it is now 15 observations, ahead of EDGAR's
13, where it had been the smallest source in the project. The Scopus journal
added 41 documents to the corpus and matched none of them, which is a real
zero and is recorded as one.

**Journal of Commerce is retired, on measurement, and both first guesses were
wrong.** `PUB.EXACT` returns **133,243** records, so the title resolves — not
the DC Velocity case. 4,487 of those fall in 2020–2026, so coverage reaches
recent years either. **ABI/INFORM's holding stops at 2022-12-31.** The
publication is alive at joc.com; the aggregator stopped indexing it. Since this
corpus begins 2024-W12, it could never have contributed a single document, and
the five empty exports run against it were correct. Recorded in `sources.yaml`
beside the three not-indexed titles, with the query that would reverse it.

**2026-Q3's exports are now complete** — nothing outstanding for any source.

**The export window was three days short and is fixed.**
`supplemental.period_bounds` derived its dates from ISO weeks, which was right
when the pipeline filed documents by week; reporting moved to calendar quarters
and this did not move with it. `--export-queries 2026-Q3` asked for 2026-06-29
to 2026-09-27 while the report counted 2026-07-01 to 2026-09-30 — two days
hand-exported and never counted, three days counted with nothing in them. It is
now literally `quarter.period_bounds`, with a test that they cannot diverge
again. **Every export already on disk used the old window**, so 2026-Q3's
existing files are missing 28–30 September.

EDGAR could give roughly **4–5x more**, not the 36x raw hit counts suggest:
thirty candidate terms returned 1,273 hits over a quarter and only 96 would
become observations. The mechanism matters. `EdgarCollector.parse` sets a
document's text to *the query term itself*, because filing bodies are megabytes
and are never fetched — so **the context gate only ever sees the term**, and a
term passes or fails it identically for every filing it will ever retrieve. On
EDGAR the gate is a whitelist of query strings, not a document-level gate.

Two terms were removed as a result: `supply chain risk intelligence` and
`enterprise resource planning supply chain`, zero observations each in the life
of the project. Both were phrased to carry a domain word so they would pass the
gate, which made them too long for an API that matches phrases exactly — the
USAspending failure in a second collector. Every replacement was measured and
each one either retrieves and fails the gate, or passes the gate and retrieves
nothing. `EXCLUDED_TERMS` records both with reasons.

**Ten measured terms were added 2026-09-01**, taking EDGAR from six to
sixteen. Each was measured live over 2026-Q2 before being added and the yield
is recorded beside it in the collector; terms measuring zero were left out,
which is the standard the two exclusions failed. Verified live on 2026-W20:
**12 documents and 9 filers became 51 and 42**, across eleven technologies
rather than six — the 4–5x the measurement predicted.

**The new terms are forward-only until a backfill.** Weeks already collected
were fetched with the old six, so their EDGAR rows are unchanged. Closing that
means re-fetching every week — `--backfill 52` — which is a large operation and
would move published numbers, so it is the owner's call rather than a tidy-up.

**Latent, not fixed: EDGAR caps a page at 100 and the collector neither
paginates nor checks the total.** `enterprise resource planning` reports 537
hits and returns 100. No current term exceeds 100 so it has never bitten, but
it is silent truncation waiting for a wider term, and a total-versus-returned
check must go in before any term is widened.

**Financial news was asked about and is the wrong instrument.** Yahoo Finance
and Finviz prohibit automated access; CNBC and MarketWatch RSS are free and
legal but cannot backfill and roll silently; Finnhub company-news is the only
one that fits, being keyed, free and date-rangeable. But all four are
*attention*, not diffusion, and the report's central metric is substance minus
attention — adding them would push technologies down that axis while feeling
like added evidence.

**GitHub measures the wrong population.** Of 735 matched repositories, 78% have
exactly one star and the largest has 118. I sampled 60 repos first seen in
2025-Q4 and re-queried them live 9–12 months later: **not one had gained a single
star, and none had been deleted.** These are inert student and portfolio projects,
not an ecosystem — and GitHub is 48% of all observations.

**Sources barely overlap** — and the quarterly report now says so on its own
face. The source-diversity gate (2026-08-28) marks any technology drawing 80%+
of its evidence from one source and withholds its share movement, because a
share computed from one source measures that source's coverage. On 2026-Q2 that
is **16 of 34 technologies holding 63% of all documents**, and it removes the
report's two largest movers: ERP platforms (97% GitHub) and ML demand
forecasting (92% GitHub). "ERP is rising fastest" was really "GitHub indexed
more one-star ERP repositories". The counts stay; only the movement is withheld.

The underlying overlap problem is unchanged and is what the supplemental sources
spec exists to fix: Of the 18 technologies with 19+ documents, seven draw
over 80% of their evidence from a single source — ERP 95% GitHub, vehicle routing
92% arXiv, blockchain 99% GitHub, rail intermodal 100% Federal Register. No
technology is evenly present across research, code and filings.

**Collection failures are durable now** (2026-09-01). `source_runs` upserts on
`(source, week)`, so a retry overwrote the failure it retried; the table held
427 rows, all `ok`, and could not have held anything else. This document
reported that as reliability — "318 source runs, none has ever failed" — which
was a claim the schema made incapable of being false.

`source_attempts` is the fix: append-only, no primary key, one row per attempt.
`source_runs` keeps its upsert and its meaning, *how did this week end up*,
which is what resumability reads. Three statuses now — `ok`, `failed`, and
`empty` for a source that ran and returned nothing.

**`empty` still counts as collected**, deliberately. A real zero and a broken
API are identical in one response, and NSF's seasonal gap is a real zero, so an
empty week is surfaced on the weekly page and in the run log and left for a
human. Nothing folds it into a hole automatically. `store.COLLECTED_STATUSES`
is the one place that decides this.

`raw_fetch` now gets a row on a non-200, with a NULL path — it had 200 on all
3,114 rows because the only insert sat downstream of the raise. One caveat
written into `http.py`: only the failure that surfaces is logged, not each
retry, because logging every attempt would need a database handle inside the
HTTP layer.

**Still true and not fixed:** `collected_quarters` (`metrics.py`, `quarter.py`)
counts a week as collected if *any* `source_runs` row exists for it, whatever
its status, so a week where every source failed still counts. Tightening it
would change which quarters score and which reports show numbers, so it is left
for the owner rather than changed quietly.

**There is a linter now** (2026-09-01). `ruff`, pinned to its default rules
(`E4, E7, E9, F`) in `pyproject.toml` rather than inherited, so a version bump
cannot quietly change what the gate catches. Style rules are deliberately off:
a hook that fires on line length is a hook people learn to bypass.

It runs in three places. `hooks/pre-commit` is tracked in the repository rather
than left in `.git/hooks`, which is not version-controlled and does not survive
a clone — enable it in a fresh clone with `git config core.hooksPath hooks`.
`.github/workflows/checks.yml` runs lint and tests on push and pull request,
which is the half `--no-verify` cannot skip. And `tests/test_lint.py` runs the
same check inside the suite, so the gate travels with the repository.

**Verified by what it rejects, not by the fact that it ran.** Both defects the
review cited were reconstructed and fed to it: the `_already_covered` call
defined nowhere, and `challenge if False else [...]`. Both come back F821. A
deliberate violation was then staged and committed for real, and the hook
refused it.

Cleaning the tree took 26 fixes. Two were more than cosmetic: a dead `scored`
in `quarter.py` duplicating the filter one line above it, and import blocks
stranded mid-file in two test files by later appends.

**Reports for periods that have not happened are refused** (2026-09-01).
Scopus issue dates run months ahead, so the store holds 62 observations dated
October to December 2026 and 2,911 corpus documents in weeks that have not
occurred. `quarter.counting_bounds` stops a period's counting at today, so the
2026 annual total falls from 1,896 to **1,841** and counts what has happened;
`quarter.period_bounds` is untouched, because it is what the export sheet asks
a human for and clamping it would ask for a short window. A period that has not
begun raises `PeriodNotStarted` — `--quarter 2026-Q4` now prints a sentence and
exits 1. `run.weeks_to_render` filters weeks that have not happened, and
`dashboard-2026-W40`, `W44` and `W49` are deleted.

The document's own date still decides its period. A December paper belongs to
Q4; it just cannot be counted before December.

**Not deferred, just absent:** PatentsView (awaiting a key, gets its own plan) and
GDELT (plan 2A tasks 3 and 4; the implementation is written, it needs a clean
fixture capture and is rate-limited).

**Carry-forward items** recorded in the plan docs: clone-cohort policy beyond the
star filter, `gh_commits` / `gh_stars_delta`, `adoption_new` hardcoded to 0,
`fed_obligated` semantics, discovery baseline denominator, discovery corpus
breadth.

## 6. Decisions that reversed the spec

**Momentum was dropped entirely** (commit `5b1c4f4`), along with `acceleration`,
`cross_sectional_z`, `normalize_series`, `trailing_mean` and the quarter-folding
helpers built for it. It was the only metric needing a time series, and it kept
reporting noise as trend in three separate ways — each found by looking at what it
*ranked*, not by reading the code:

1. 95% of `weekly_signals` is observed zeros, so normalising a technology seen
   once divided by a near-zero spread and handed its single document a large
   z-score. Manufacturing execution systems, three documents in a year, ranked
   first.
2. `edgar_filers` is a stock (distinct companies over a trailing window), not a
   flow. Summing thirteen weeks of it turned two filers into twenty-six.
3. Every guard added to fix those cut the scored set further — 50 of 50 down to
   17 of 50. A metric that on inspection was mostly not measuring anything.

The weekly dashboard now ranks by substance instead.

**Reporting moved to annual; collection stayed weekly.** Two thirds of
technology-weeks hold zero observations and the median is zero, so a weekly
ranking mostly reported which week a collector caught something. Zero cells fall
from 68% weekly to 46% monthly to 34% quarterly.

Collection did **not** move, and this is the part most likely to be
well-meaningly undone. A wider fetch window silently truncates four of six
sources: per 13-week quarter arXiv would ask for ~15,800 documents against a
2,000-per-sweep cap, GitHub ~6,460 against a **hard 1,000-result API limit that
cannot be raised at all**, Federal Register ~3,400 against 2,000, Hacker News
~2,200 against 1,000. The weekly window is the only one where every query stays
under its cap. Cadence and window are separable: an annual *run* that loops over
52 weekly *queries* is fine; a single wide query is not.

**The no-LLM rule is narrower than it looks.** It was justified by repeatability
of a *recurring* process. An annual study can afford content-analysis method —
independent coders on a stratified sample, reported agreement, archived raw plus
pinned model and published prompts. The weekly run must stay deterministic.

## 7. Where to pick up

In value order. The process review's risk register (`docs/`) is more detailed.

1. **Q4 supplemental exports**, first week of January. Three databases, roughly
   four hours: `--export-queries 2026-Q4 --split` prints the sheet. **Clear
   ProQuest's marked-items list between exports** — it accumulates, and the
   importer will refuse the files.
2. **The first complete calendar year.** 2026 finishes at W53. It is the first
   annual report where neither year is truncated.
3. **Re-audit at lexicon v10.** The four weak technologies were acted on
   2026-09-02 and the 70% figure predates that, so it now describes a corpus
   that no longer exists. `infrastructure_security` and `nearshoring_analytics`
   are retired; `green_logistics` and `agentic_procurement` had their bare
   topic words replaced with proximity patterns. Rebuilt: **2,462 → 2,309
   observations, −6.2%**, and every other technology came back at exactly
   2,198 — the change was surgical. Hacker News agentic items went 10 to 0,
   which were the "every startup shipping a dashboard" matches; Scopus
   green_logistics kept 44 of 51, arXiv lost two thirds.

4. **A coder who did not write the patterns.** The 2026-09-02 pass put the
   sample at **70%** at lexicon v9, but that is one coder and it is this model
   again — the third from the same source. It is not comparable with the
   earlier 51%: the lexicon, the sample, the instrument and the coder all
   changed at once.

   **Four technologies are close to pure noise** and are 16% of the judged
   sample: `nearshoring_analytics` 0 of 4, `infrastructure_security` 0 of 4,
   `green_logistics` 1 of 6, `agentic_procurement` 1 of 5. Each matches a topic
   word rather than the technology its name promises. Fixing or retiring those
   four is the highest-value lexicon work available, and it is an owner call
   because three of them are near-misses of fields already rejected.

   **EDGAR cannot be audited at all.** Filing bodies are never fetched, so all
   twelve sampled items are `x`: 129 observations, the strongest diffusion leg,
   precision unknown and unmeasurable without fetching filings.

5. **The instrument's own history**, kept because it explains the two
   precision figures. The old sheet truncated its evidence at 600 characters
   and said nothing: 62 of 108 items ran past the cut and **24 had the matched
   pattern beyond it**, against a median evidence length of 886. Every coder
   before 2026-09-02 judged that truncated text, which is why the 51% is not
   comparable with the 70%. The owner found it by looking for "procurement" on
   an item matched as `agentic_procurement` and not seeing it — it was at
   character 1693. Fixed in `audit.Evidence.shown`; NSF and OpenAlex were also
   missing from `audit.RECOVERY`, so 24 items had reached coders as "(full text
   not recovered from raw)". `docs/audit/coder-c.csv` is that pass and must not
   be carried forward: it codes a different sample through a broken window.

6. **PatentsView**, if the key arrives — it would replace the manual Lens export
   with an automated collector on the same CPC principle.

## 8. Owner decisions already made — do not relitigate

- Real code pipeline, not ad-hoc research.
- Free sources only. No paid data.
- Fixed watchlist plus auto-discovery of rising terms.
- No LLM in the weekly run. Lexicon work is offline, routed through a Claude
  session (`lexicon prepare` → answers → `lexicon check`), never a direct API
  call. The pipeline never edits `watchlist.yaml`; a human merges.
- `raw_fetch` is an append-only log of fetch attempts.
- GitHub clone cohorts require at least 1 star.
- **GitHub stays at the 1-star floor until Lens patents are collecting**
  (decided 2026-08-28), then the floor is reconsidered. Raising it to 5 now
  would cut GitHub from 774 observations to roughly 35 and leave the Experiment
  stage with almost nothing, because patents are specified but not yet built.
  The source-diversity gate already withholds claims for the five technologies
  that are 80%+ GitHub, which is the harm the floor was meant to address. A
  fork-based filter was tested as an alternative and rejected: recent-push rates
  move only from 70% to 78%, because repos are searched in the week they are
  created and are therefore fresh by construction.
- arXiv's old-ID limitation: leave the plan's code, log it.
- Momentum dropped; annual report is the deliverable; collection stays weekly.
- Three proposed technologies were rejected as fields rather than technologies:
  software supply chain security, e-commerce, machine learning for operations.
  Together they would have more than doubled the corpus.

## 9. Published artifacts

Reports are regenerated from the database and are cheap to remake; do not treat
any published copy as current. `output/` holds the latest of each period, its
evidence page, and `output/charts/` holds standalone SVG and PDF.

## 10. A note on how this project has gone wrong

Recorded because the same shape recurs and recognising it early is worth more
than any single fix.

**Verifying the mechanism instead of the outcome.** The tests checked that a
chart's SVG was in the template context, not that it reached the page — it did
not, for two releases. OpenAlex was recommended as a Scopus replacement after
testing its retrieval and never its abstract coverage, which is what decides
whether the matcher can see anything. A guard was written for partial quarters,
documented accurately, and never connected to its caller.

**The remedy that works:** check the artifact, not the code that makes it. Read
the rendered page, count the rows in the database, compare the number against
the export file. Every wrong figure in this project was caught that way, and
none were caught by reading the code that produced them.
