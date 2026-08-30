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
| Tests | **530 passing** |
| Precision | **51%**, two coders, kappa 0.79, 91 judgeable rows |
| Lexicon | version **8**, 51 active technologies, 7 families |
| Observations | **2,676** across 54 weeks, 2025-W34 → 2026-W35 |
| By source | scopus 830, github 826, arxiv 705, edgar 128, lens 85, hn 74, usaspending 33, federalregister 21, abi_inform 9 |
| Evidence families | **all 8 populated** — research, code, patents, filings, trade, regulation, money, community |
| Evidence families | research, code, patents, filings, regulation, money, community — **7 of 8** (no trade press yet) |
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
    python -m observatory.run --export-queries 2026-Q4   # the sheet a human works from
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

## 4b. What the precision audit changed (lexicon v8, 2026-08-30)

A 105-row stratified audit, coded independently by two coders, puts precision
at **51% across 91 judgeable rows** — raw agreement 88%, Cohen's kappa 0.79
(`docs/precision-audit-2026-08-30.md`, codes in `docs/audit/`). Five faults
were acted on; the sixth was measured and left alone.

- **Positive train control is its own technology now.** Eleven of twelve
  sampled Federal Register rows for `rail_intermodal_tech` were FRA notices of
  PTC amendments, mostly for passenger railroads — that technology was
  measuring the FRA's paperwork cadence. It falls 22 → 2 and PTC keeps 20 under
  its own entry. Owner's decision: PTC is not only about intermodal.
- **`item_level_rfid` 26 → 5.** The rule underneath is the audit's most useful
  finding: **CPC-as-evidence works for a *mechanism* class and fails for an
  *enabling technology* class.** `B65G1/137` (storage with indicating means)
  was 4 of 4; `G06K7` (reading record carriers) attributed a blockchain
  shipping patent and an apartment access-control system. An enabling class now
  carries a `confirm` pattern in `sources.yaml` that the text must also match.
  Swapping to the narrower `G06K19/07` was measured and changes nothing.
- **`operations_research` 556 → 546**, excluding passenger transit.
- **`agentic_procurement` 85 → 84.** Only `software supply chain` excluded,
  which was already out of scope. Two narrower options were measured and
  rejected: adjacency dropped "Agentic AI Framework for Smart Inventory
  Replenishment"; a wider exclusion list dropped "Procurement-Agentic-App".
  **This technology has known low precision** — "agentic AI" is a general
  buzzword and a document-level gate cannot separate a supply chain agent from
  an AI-industry post. Read its counts accordingly.
- **`last_mile_delivery` 223 → 222**, excluding a "LAST MILE RAIL PROJECT".

**Left alone deliberately:** a Hacker News post using "last mile" for software
deployment is one row in 223, and every rule broad enough to catch it dropped
42 drone-delivery papers that use the word "deployment".

## 4a. The lexicon carried the domain word where the gate belonged

Ten of fifty technologies wrote the domain into the pattern itself with
`needs_context` off, so the domain word had to sit *adjacent* to the technology
word. "Target strengthens inventory management with digital twins" did not
match `(supply chain|logistics|warehouse) digital twin(s)?` -- it says
"inventory" one clause away, and the gate built for exactly this was never
consulted.

Seven were revised at lexicon v7 (2026-08-29). Last-mile delivery went 114 to
222, digital twins 10 to 89, control towers 9 to 17.

**The rule that came out of it:** the gate rescues a *distinctive* term and
cannot rescue a *generic* one. `generative ai` ungated went 2 to 77 at roughly
25% precision -- a hospital management platform, a language-teacher assistant,
printed circuit board design. It was reverted to adjacency, widened but not
gated. A document-level gate passes anything that says "supply chain" once
anywhere, which is enough for a distinctive term and nowhere near enough for a
generic one.

**Precision is 51%, and the first estimate of it was optimistic.** The obstacle
to measuring it at all was that the database does not hold the text a match was
made on — a GitHub row's title is `owner/repo-name` and the match happens on
the description. `observatory/audit.py` walks an observation back to that text,
from `raw/` for the API collectors and from `data/manual` for the hand-fetched
ones; it recovered 105 of 105.

**A single coder read 59%. Two coders adjudicated to 51%.** Of thirteen
disagreements, **nine resolved against the first coder and none against the
second** — a leniency bias whose direction was predictable, since that coder
had written the patterns being judged. It had counted a repository that merely
*integrates with* S/4HANA as ERP, a security advisory about a transport
management product as AI transportation management, and a vessel fleet
decarbonisation study as port electrification.

Both coders independently marked the same twelve EDGAR rows unjudgeable, which
is good evidence that "the filing text is not recoverable" is a fact about the
data rather than one coder's caution.

**What the statistic still cannot see:** both coders are the same model. It
catches a bias one of them holds and is blind to one they share. A human coder
on the same sheet — it is in `docs/audit/sample.md` — remains worth an hour,
and is the only thing that would settle whether 51% is itself optimistic.

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

**Backfilled 2026-08-28.** 52 weeks refetched under the programme query:
**31 observations across 28 awards, $390M, 30 of them carrying coordinates.**
The Build Map has points for the first time. The old raw is kept at
`data/raw-retired/usaspending-keyword-query/` — it is the evidence for the 36-in-
a-year claim, and backfill would have skipped every week without clearing
`source_runs`, since resumability correctly treats a recorded run as done.

**GitHub measures the wrong population.** Of 735 matched repositories, 78% have
exactly one star and the largest has 118. I sampled 60 repos first seen in
2025-Q4 and re-queried them live 9–12 months later: **not one had gained a single
star, and none had been deleted.** These are inert student and portfolio projects,
not an ecosystem — and GitHub is 48% of all observations.

**A manual export needs its own record identifier.** Identity fell back to the
first 120 characters of the title, and 185 real patents produced 183 documents:
patents carry no DOI, and a continuation shares its parent's words. Two rows
became one and nothing said so. `manual.document_id` now prefers the database's
identifier (Lens ID, EID, accession number), then a DOI, then the title.

**Patents needed classification evidence, not text.** A real 185-patent Lens
export matched **2 records** by text, and 11 even with the context gate off.
Patents describe mechanisms while the watchlist speaks trade vocabulary: an
abstract about "reconfigurable racks for standardized packages" is warehouse
automation and never says so. Attributing on the CPC code the patent was filed
under reaches **75 of 185, producing 85 observations**. Only codes naming a
mechanism are mapped — `G06Q10/087` is "inventory management" and would have
labelled 135 of 185 patents as warehouse management systems, "Material
conveying method" among them.

**Seven technologies are silent for the whole year** (was nine): advanced
planning and scheduling, autonomous yard trucks, item-level RFID, GS1 2D
barcodes, GenAI for supply chain planning, active cold chain packaging, smart
labels. **Port electrification (15 observations) and inland ports (1) broke
their silence on the USAspending fix** — federal money was the source that saw
them, which is exactly the argument for widening the base. Each was probed against the corpus directly, so this is
a finding rather than a mystery: they are absent from *these six sources*, not
from the world. Trade press and patents would see them.

**Trade press is thin, and that is a finding rather than a fault.** Supply
Chain Dive's whole 2026-Q3 slice in ABI/INFORM is 28 articles across five term
batches, of which 9 mention a tracked technology. The misses were read and are
right: rate increases, fuel surcharges, 3PL partnerships, earnings. The outlet
covers supply chain business news and technology is a minority of it. Three
outlets remain unexported (Modern Materials Handling, Supply Chain Management
Review, Journal of Commerce); one of the four originally listed publications
and three others are not indexed by ABI/INFORM at all.

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
2. **Run the first supplemental exports.** `--export-queries <quarter>` prints
   the query for Lens.org, Scopus and ABI/INFORM, where to save each file and
   what its sidecar must say. Lens is free and needs no library account, so it
   goes first. **Its CPC set and query syntax are unverified** — read the first
   result set by hand and correct `sources.yaml`, not the code. The manual
   importer still needs Lens's CSV column names added to `manual.CSV_FIELDS`,
   and those must come from a real file rather than from documentation.

3. **First real licensed export.** `--import-manual` is built and tested but has
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
