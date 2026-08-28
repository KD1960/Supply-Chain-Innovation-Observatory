# STATUS

Supply Chain Innovation Observatory — state of the project, written for someone
picking it up cold. Last updated after commit `2ebfc58`.

Owner: Kevin Dooley, ASU W. P. Carey.

---

## 1. What this is

A dashboard and report that detect the emergence and diffusion of supply chain
innovations from observable digital traces in publicly accessible data. Six
tracked questions: what is accelerating; what is moving out of the lab; where new
logistics capability is being built; what has substance rather than attention;
what developers are building; what large companies are adopting.

Design of record: `docs/superpowers/specs/2026-08-16-supply-chain-innovation-observatory-design.md`.
Where this document and the spec disagree, this document is newer — several of
the spec's decisions have since been reversed on evidence, and §6 lists them.

## 2. Current state

| | |
|---|---|
| Tests | **350 passing** |
| Lexicon | version **6**, 50 active technologies, 7 families |
| Observations | **1,606** across 54 weeks, 2025-W34 → 2026-W35 |
| By source | github 774, arxiv 611, edgar 128, hn 72, federalregister 21, usaspending **0** |
| Raw weeks on disk | 53, 2025-W35 → 2026-W35 |
| Source runs | 318 recorded, **none has ever failed** |
| Deliverable | annual report, `output/report-2026.html` |

The weekly cron fired unattended on Monday 2026-08-24 07:00 and worked: all six
sources OK, W35 fetched, and the seven-day lookback correctly added 12 more
documents back into W34. That is the first run nobody supervised.

## 3. How to run it

    python -m observatory.run                  # the weekly run (this is what cron does)
    python -m observatory.run --annual 2026    # the deliverable
    python -m observatory.run --quarter 2026-Q2
    python -m observatory.run --import-manual  # licensed database exports
    python -m observatory.run --rebuild        # replay all raw under the current lexicon
    python -m observatory.run --backfill 52    # fetch N trailing weeks, then rebuild

Installed cron, Monday 07:00 local:

    0 7 * * MON cd '/Users/kevindooley/Claude/Projects/Supply chain innovation' && /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m observatory.run >> data/cron.log 2>&1

The interpreter path matters: `/usr/bin/python3` is macOS's 3.9 and has none of
the dependencies.

Keys live in `.env`: `GITHUB_TOKEN` is set and working. `PATENTSVIEW_API_KEY` is
not — see §5.

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

## 5. What is broken or missing

**USAspending is fixed** (2026-08-27). It searched six multi-word phrases, and
the API phrase-matches them against terse award prose: `port` returns over a
hundred awards in a week where `port infrastructure` returns one. Six such
phrases retrieved 36 awards in a year and matched none of them.

Widening the keywords -- which §7 used to recommend -- was measured and
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

**The database does not have this data yet.** Raw usaspending on disk was
fetched under the old query; `--backfill 52` would refetch and rebuild.

**GitHub measures the wrong population.** Of 735 matched repositories, 78% have
exactly one star and the largest has 118. I sampled 60 repos first seen in
2025-Q4 and re-queried them live 9–12 months later: **not one had gained a single
star, and none had been deleted.** These are inert student and portfolio projects,
not an ecosystem — and GitHub is 48% of all observations.

**Nine technologies are silent for the whole year:** advanced planning and
scheduling, autonomous yard trucks, inland ports, port electrification, item-level
RFID, GS1 2D barcodes, GenAI for supply chain planning, active cold chain
packaging, smart labels. Each was probed against the corpus directly, so this is
a finding rather than a mystery: they are absent from *these six sources*, not
from the world. Trade press and patents would see them.

**Sources barely overlap.** Of the 18 technologies with 19+ documents, seven draw
over 80% of their evidence from a single source — ERP 95% GitHub, vehicle routing
92% arXiv, blockchain 99% GitHub, rail intermodal 100% Federal Register. No
technology is evenly present across research, code and filings.

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

Roughly in value order.

1. **Backfill USAspending.** The collector is fixed but the corpus is not;
   `--backfill 52` refetches under the programme query. Then decide whether the
   7% match rate is enough for the Investment stage to make claims from.
2. **First real licensed export.** `--import-manual` is built and tested but has
   only ever seen a synthetic file. When Kevin supplies a real Web of Science or
   Scopus export, check the field mapping against what that database actually
   emits rather than what its documentation claims. Factiva exports RTF/HTML and
   is not handled — that wants a real file, not a guess.
3. **Trade press via ABI/INFORM or Factiva.** The single biggest coverage gap;
   it is where deployment gets announced and where the nine silent technologies
   would appear.
4. **PatentsView**, once the key arrives.
5. **Gartner Hype Cycle, if ASU licenses it.** Not just another source — an
   independent published placement to correlate our pipeline position against,
   which turns "does this metric mean anything" into a testable claim.
6. **Reconsider the GitHub floor** once Lens patents are collecting. Decided
   and recorded in §8; not open until then.

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

- Annual report — https://claude.ai/code/artifact/0bcfa58e-9340-4a7e-9405-f2e4ff5317c6
- WMS deep dive — https://claude.ai/code/artifact/338d4dd5-8b1d-4c04-b99b-3fa69a18e6a3

Both are **second edition and now stale**: they were written at lexicon version 4
against 1,593 observations. Regenerate before sharing.

## 10. Note on the annual report

Neither calendar year in the data is complete, and both reports say so on their
own face rather than presenting a shortfall as a decline:

- **2025**: 18 of 52 weeks — collection began at W34.
- **2026**: 35 of 53 weeks — the year is not over.

Both withhold share movement for that reason. **The first complete calendar-year
report is 2026, available after the weekly run for 2026-W53.** The cron fills it
in unattended; no action is needed between now and then.
