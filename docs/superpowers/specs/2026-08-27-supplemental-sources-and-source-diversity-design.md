# Supplemental Sources and Source Diversity — Design Spec

**Date:** 2026-08-27
**Status:** Approved for planning
**Owner:** Kevin Dooley (ASU W. P. Carey)
**Extends:** `2026-08-16-supply-chain-innovation-observatory-design.md`

---

## 1. The problem this solves

Every stage of the pipeline currently rests on one source, and in three cases
that source is known to be weak or empty.

| Stage | Sources today | Condition |
|---|---|---|
| Idea | arXiv, Hacker News | arXiv is preprints only; no peer-reviewed literature at all |
| Experiment | GitHub | 78% of matched repos have one star and gained none in 9–12 months; PatentsView has no key |
| Investment | EDGAR, USAspending | USAspending has returned **zero** usable awards in a year |
| Deployment | Federal Register | one source, US regulatory only |
| Diffusion | EDGAR filers | one source |

The measured consequence, from `STATUS.md` §5: of the 18 technologies with 19 or
more documents, seven draw over 80% of their evidence from a single source — ERP
95% GitHub, vehicle routing 92% arXiv, blockchain 99% GitHub, rail intermodal
100% Federal Register. Nine technologies are silent for the entire year.

A pipeline-position number computed from one source is not a position. It is
that source's coverage wearing a stage label.

This spec does two things about it: it adds four sources a human can supply, and
it makes the system refuse to state a position it cannot support.

## 2. Two non-goals, restated

The no-paid-data rule is unchanged. Every source below is either free or already
licensed by ASU for its own reasons; the project buys nothing.

The no-LLM-in-the-run rule is unchanged. Human-supplied exports go through the
same deterministic matcher as every API source. The human's contribution is
*fetching*, never *judging*: nobody reads an article and decides whether it
counts.

## 3. The collection principle

**A human never identifies relevant documents.** The human exports a slice of a
corpus defined by a structural filter, and the existing matcher (`matcher.py`,
via `manual.import_exports`) decides which technologies each document matches.

This is the same shape as every API collector: fetch a domain, match the
watchlist against it. It matters for three reasons beyond effort.

- **Reproducibility.** The same query re-run next quarter yields a comparable
  slice. A human deciding relevance does not.
- **A denominator.** Auto-discovery (§4 of the design spec) needs to know how
  many supply chain papers there were, not only how many matched. A
  technology-targeted search destroys that.
- **Discovery survives.** A search shaped by the watchlist can only confirm the
  watchlist. A domain slice can surface terms nobody put there.

The filter is therefore always a property of the *container* — the journal, the
patent classification, the publication — never of the technology.

The one exception is trade press (§4.2), and it is called out as an exception
with its cost stated.

## 4. The four supplemental sources

Access was confirmed by the owner on 2026-08-27: Scopus **yes**, Web of Science
**no**, ABI/INFORM **yes**, Factiva **no**, Gartner **no**.

Total human effort: roughly four hours per quarter, one person, with the two
annual items amortised.

### 4.1 Scopus — peer-reviewed journal literature

**Fixes:** Idea stage is 100% preprint. Journal publication is the slower,
higher-bar half of the research signal, and the gap between a technology's
preprint volume and its journal volume is itself informative.

**Filter:** a fixed list of ISSNs for approximately 40 supply chain, operations
management and logistics journals, plus the quarter's date range. The ISSN list
lives in the repository at `journals.yaml` and is versioned like the
lexicon — adding a journal mid-series changes the denominator and must be
visible.

Query shape:

    ( ISSN(0272-6963) OR ISSN(1478-4092) OR ... )
    AND PUBDATETXT( ... quarter range ... )

ISSNs rather than journal titles: titles are entered inconsistently and change,
ISSNs do not.

**Export:** RIS, abstracts included. `manual.parse_ris` already handles this
format.

**Volume:** estimated 400–1,500 records per quarter. Scopus caps an
abstract-inclusive export at 2,000 records and says so only in the interface,
which is exactly the silent truncation `manual.read_exports` was built to catch.
The estimate is unverified and §8 makes verifying it the first task.

**Fallback if a journal is not in Scopus:** the journal's own issue index page,
hand-entered into the CSV template of §5.3. Slower per article, works for
anything.

### 4.2 ABI/INFORM — trade press

**Fixes:** the largest coverage gap in the project. Trade press is where
deployment is announced and where the nine silent technologies would appear.
Feeds both Deployment and Diffusion, neither of which has a second source.

**Filter:** a publication list — Supply Chain Dive, DC Velocity, Modern
Materials Handling, Logistics Management, Journal of Commerce, FreightWaves, and
their neighbours — held in `publications.yaml`.

**The exception to §3.** Publication alone yields an estimated 5,000–8,000
stories per quarter, past both the export cap and any reasonable human step. So
this source, alone among the four, also carries a term filter: a **single**
disjunctive query of roughly 30 terms, generated from the watchlist by the
command in §5.1. One query, not thirty searches.

The cost is stated rather than hidden: **trade press cannot contribute to
auto-discovery**, because its slice is shaped by the terms already on the
watchlist. Candidate terms continue to come from arXiv, Hacker News, Federal
Register and Scopus, whose slices are unshaped. The quarterly report notes this
where discovery is presented.

**Export:** RIS.

### 4.3 Lens.org — granted patents

**Fixes:** Experiment rests entirely on GitHub, and GitHub was measured and found
to be counting inert student projects. Patents are the intended second source and
have never been present — PatentsView is still waiting on a key.

Lens.org is free with a registered account and needs no library access, so this
one proceeds regardless of anything else in this spec.

**Filter:** CPC classification codes plus a grant-date range. Starting set, to be
validated against a sample before adoption:

| Code | Covers |
|---|---|
| `G06Q10/08` | logistics — warehousing, loading, distribution, shipping |
| `G06Q10/087` | inventory management |
| `B65G` | transport or storage devices |
| `G05D1` | autonomous vehicle control |
| `B64U` | unmanned aerial vehicles |

Grants, not applications: a grant is a dated event, an application is a filing
whose eventual status is unknown, and mixing them double-counts.

**Export:** CSV. `manual.parse_csv` handles it; the field alias table in
`manual.CSV_FIELDS` will need Lens's column names added.

**Relation to PatentsView.** Should the key arrive, PatentsView becomes the
automated collector and Lens becomes redundant. Both express the same query
principle, so the switch changes the fetch and not the meaning. Until then Lens
is the source.

### 4.4 MHI Annual Industry Report and trade shows — benchmarks, not signals

**Fixes:** the role Gartner would have played. Not additional volume — an
*independently published placement* to correlate our computed pipeline position
against. That is what turns "does this metric mean anything" from an opinion
into a testable claim.

**MHI Annual Industry Report.** Free PDF, published annually, reporting current
and projected adoption percentages for roughly a dozen named technologies.
Hand-keyed into one CSV a year. Availability is to be confirmed by the owner.

**Trade show exhibitor and session lists.** MODEX and ProMat (alternating years)
and Manifest. Public web pages, copy-pasted. A count of exhibitors per technology
is a vendor-side deployment signal that no other source in the project sees.

**These two are deliberately not signals.** They arrive once a year. Folding an
annual value into a quarterly z-score creates a step change at one quarter
boundary and three quarters of carried-forward flatness — a fake movement that
the metric cannot distinguish from a real one. This is the same failure that
retired momentum (design spec §6, commit `5b1c4f4`), and it is not repeated here.

They live instead in an **external benchmark block** in the quarterly report:
their ranking beside ours, with the rank correlation stated. When we disagree
with MHI, that is a finding to explain, not a number to average away.

## 4.5 Sources checked and not adopted

Access to these was confirmed on 2026-08-28. They are recorded here with the
reason they were not taken up, so that finding them again does not restart the
argument.

**Nexis Uni — rejected on export format.** Its trade-press and company-news
coverage is the widest of anything available here, and on content alone it would
rank first. It delivers PDF and RTF only. That is the same unstructured
delivery that excluded Factiva in §4.2, and it would need a parser built against
a brittle layout. What decides it is redundancy rather than format alone:
ABI/INFORM already covers trade press for this project and exports clean RIS, so
the parser would buy breadth of outlet, not a new capability. **Reconsider only
if ABI/INFORM's publication list proves too narrow in the trial of §8** — at
that point the breadth is worth the parser, and not before.

**Applied Science Commons (Coherent Digital) — open, pending a format check.**
A grey-literature aggregator: technical reports, standards documents, working
papers. This is a genuine gap rather than a duplicate. Three of the nine
technologies silent for a full year — GS1 2D barcodes, digital product passport,
item-level RFID — are standards-driven, and standards work is published as
reports and specifications rather than as journal articles or code. None of the
four adopted sources sees that literature. Worth adopting if it exports
structured metadata; its export format has not been checked.

**OECD iLibrary and World Bank Publications — benchmark candidates, not
signals.** Both publish structured indicators; the World Bank's Logistics
Performance Index is an independently published capability ranking. They belong
in the external benchmark block of §4.4 beside MHI, not in `weekly_signals`, and
for the same reason: annual publication cannot feed a quarterly z-score. Their
resolution is national, so they can corroborate the Build Map's geography but
say nothing about any single technology.

**Dun & Bradstreet Hoovers — no innovation signal.** Firmographics: industry,
size, location, officers. It describes companies rather than what they are
adopting. One narrow use exists — attaching an industry to EDGAR filer CIKs
would let Corporate Adoption be read by sector — and that is a possible later
refinement, not a source.

**Barron's — subsumed.** A single investor-facing weekly, almost certainly
inside ABI/INFORM's index already. Adding it would deepen a source the project
already has rather than widen the base, which is the opposite of this spec's
purpose.

## 5. What gets built

### 5.1 `--export-queries`

    python -m observatory.run --export-queries 2026-Q4

Prints, for each supplemental source, the exact query string to paste into that
database, built from the current `watchlist.yaml`, `journals.yaml` and
`publications.yaml`, with the quarter's date range filled in.

This is the mechanism that keeps §3 honest. The human copies a string and clicks
export; no judgment enters. When the lexicon changes, the query changes with it
rather than drifting silently out of step. The printed string is also what the
sidecar records, so the query in the file and the query that ran are the same
string by construction rather than by care.

### 5.2 A source registry

`manual.py` today takes `meta["source"]` as free text, which means a typo creates
a new source silently and nothing knows which stage an export feeds. Replace it
with a registry — source id, human name, the signal it emits, the stage that
signal feeds, expected export format. An export naming a source outside the
registry raises `ExportProblem` rather than being ingested under a name nothing
reads.

`quarter.SOURCES` is likewise a hardcoded six-tuple; supplemental sources
currently fall through into a `licensed` list rendered as an afterthought. It
becomes the registry's key order so every source is a first-class column.

### 5.3 A hand-entry CSV template

For material with no export at all: journal issue index pages, the MHI table,
exhibitor lists. A fixed-column CSV with the same sidecar requirement as any
export. Documented columns, one row per document, no free-form fields.

### 5.4 New signals

| Signal | Source | Stage |
|---|---|---|
| `journal_papers` | Scopus | Idea |
| `patents` | Lens.org | Experiment (already defined, never populated) |
| `trade_deploy` | ABI/INFORM, article also matching the deployment lexicon | Deployment |
| `trade_articles` | ABI/INFORM | Diffusion |

`SIGNALS_BY_STAGE` in `metrics.py` becomes:

    idea        = (arxiv_papers, hn_points, journal_papers)
    experiment  = (patents, gh_repos_new, gh_commits, gh_stars_delta)
    investment  = (fed_obligated, edgar_filings)
    deployment  = (fed_awards, fedreg_docs, media_deploy, trade_deploy)
    diffusion   = (edgar_filers, media_articles, trade_articles)

`journal_papers` joins `HARD_SIGNALS`; `patents` is already there and has simply
never had a value. `trade_articles` joins `SOFT_SIGNALS`. Trade press is coverage, not construction, and the substance
index should read it that way.

Investment gains nothing here and stays the weakest stage in the system. Fixing
USAspending remains the separate first item of `STATUS.md` §7.

**The deployment lexicon is reused, not rewritten.** `trade_deploy` applies the
same verb list that `media_deploy` uses — opens, breaks ground, goes live,
begins operations, deploys, commissions — so the two are comparable.

### 5.5 The source diversity gate

The quarterly report already computes each technology's top source and its
percentage share (`quarter.py:153`) and prints it as a tag. It is decoration; it
becomes a gate.

**Diversity is counted across kinds of evidence, not source names**, because
two sources measuring the same thing are one piece of evidence twice. arXiv and
Scopus are both research literature: a technology at 6 preprints and 5 journal
papers would clear a two-source floor while resting entirely on academic
interest. Measured on 2026-Q2, five technologies would have cleared on a Scopus
export alone — freight decarbonisation, critical infrastructure security,
electric heavy-duty trucks, warehouse robotics and humanoid logistics.

| Family | Sources |
|---|---|
| research | arXiv, Scopus |
| code | GitHub |
| patents | Lens.org, PatentsView |
| filings | EDGAR |
| trade | ABI/INFORM |
| regulation | Federal Register |
| money | USAspending |
| community | Hacker News |

An unregistered source is its own family. Folding an unknown export in with
something else would invent corroboration nobody checked.

Per technology per period, over the observations in that period:

    concentration = max over families of ( documents from that family / total documents )
    distinct_families = count of families supplying at least FAMILY_FLOOR documents

A technology is **single-source** when `concentration >= 0.80` or
`distinct_families < 2`.

**`FAMILY_FLOOR` is 1 for now, deliberately.** One document from a second family
is not corroboration — on 2026-Q2, eleven of the eighteen technologies that
passed the gate had a second source contributing one or two documents, and
raising the floor to 3 would gate 27 of 34. But that number measures how thin
the corpus is today rather than where the threshold belongs, and Scopus,
ABI/INFORM and Lens are expected to change it substantially. Patents and trade
press are new families for exactly the hardware and deployment technologies that
are silent now. The mechanism ships at a floor of 1; the number is set against
real data after the first quarter that has the new sources in it.

**Normalisation was tested and rejected.** Raw counts are not comparable across
sources — GitHub retrieved 30,459 documents in 2026-Q2 against Hacker News's
2,304 — so expressing each technology as a share of its source's own corpus
looks like the obvious correction. It is not. Warehouse management systems is 21
GitHub repositories and 21 EDGAR filings, two families genuinely corroborating;
raw concentration reads 50% and normalised reads 87% EDGAR, because EDGAR is
small. Normalisation trades a corpus-size distortion for a small-denominator one
that is worse, and ranking by normalised share puts a three-document technology
in the top two. Corroboration asks whether each family independently produced
enough evidence, which is a question about counts, not shares.

For a single-source technology the report **withholds its inferences** and keeps
its observations. Which fields those are depends on the report:

- The **quarterly report** shows no stage scores or pipeline position. Its one
  inference is the share shift against the previous period, so that is what is
  withheld, and a gated technology is also kept out of the movers list. Counts,
  the per-source breakdown, and the source that supplied most of the evidence
  are all still shown. *(Built 2026-08-28. The spec first named position and
  stage scores here, which this report does not display; the principle is the
  same and the fields were wrong.)*
- The **weekly dashboard**, which does show stage scores, position and the
  lab-to-field index, withholds those. Not yet built.

Two reasons for withholding rather than annotating. A number printed beside a
caveat is still read as a number, and this project has already shipped one wrong
ranking that way. And a stage score whose inputs all come from one source is
arithmetically a restatement of that source's coverage — suppressing it removes
nothing that was there.

The 0.80 threshold is a judgment, not a derivation. It is a named constant, and
the quarterly report states how many technologies it gated so the choice stays
visible and arguable rather than buried.

**Measured effect on the current corpus**, once built: on 2026-Q2, **16 of 34
technologies holding 324 of 511 documents** are gated, and 19 of 34 on Q1. Four
of the five largest technologies are among them, as are both quarters' two
largest movers — ERP platforms at 97% GitHub and ML demand forecasting at 92%.
The report's headline finding was a restatement of what GitHub indexed.

If the four new sources work, most of those should clear. Whether they do is the
measurement that tells us whether this spec succeeded, and §9 records it.

### 5.6 Cadence

Quarterly is the reporting cadence, confirmed by the owner. Weekly collection is
unchanged and, per `STATUS.md` §6, is not to be widened — four of six API sources
silently truncate against a quarter-wide query.

Supplemental exports are dropped into `data/manual/<quarter>/` before the
quarterly run. Their documents are dated by the document's own date and land in
their own ISO week, exactly as every other source does, so an export arriving
late is placed correctly rather than in the week it was uploaded.

An export whose declared and parsed record counts disagree halts the run rather
than being skipped, which `manual.read_exports` already enforces.

**A quarter with no supplemental exports still runs**, and its report says which
supplemental sources were absent. A missing export is a missing week, not a zero
week — the project's oldest rule, applied to its newest source.

## 6. Data model changes

    -- observations gains nothing; supplemental documents are ordinary rows.

    manual_exports(id INTEGER PK, source TEXT, quarter TEXT, query TEXT,
                   exported_date TEXT, declared_records INT, parsed_records INT,
                   matched_documents INT, path TEXT, imported_at TEXT)

    benchmarks(source TEXT, year INT, tech_id TEXT, measure TEXT, value REAL,
               note TEXT, PRIMARY KEY(source, year, tech_id, measure))

`manual_exports` makes a hand-made fetch as auditable as `raw_fetch` makes an
API one. `benchmarks` holds MHI and trade show figures, deliberately outside
`weekly_signals` so nothing can accidentally z-score them.

## 7. Testing

Following the project's existing practice, every claim above that could silently
fail gets a test.

- Each parser against a **real** export from the actual database, not a synthetic
  file. `STATUS.md` §7 item 2 is explicit that `--import-manual` has only ever
  seen synthetic input, and a fixture written from documentation tests the
  documentation.
- A truncated export raises `ExportProblem`. This is the single most likely real
  failure and the one whose consequence is a quietly smaller number.
- An export naming an unregistered source raises rather than ingesting.
- `--export-queries` output changes when the watchlist changes.
- The gate: a technology at 79% is scored, at 80% is withheld, and the withheld
  fields are absent from the rendered report rather than rendered empty.
- A quarter with zero supplemental exports completes and names what was missing.
- Document-week placement: an export uploaded in Q4 containing a Q3-dated article
  writes into the Q3 week.

## 8. Order of work

1. **Trial Scopus export.** One quarter, real ISSN list, before anything is
   built. It settles the record count against the 2,000 cap and shows what
   Scopus's RIS fields are actually called. Every volume figure in §4 is an
   estimate until this runs.
2. **Lens.org patents.** Free, no dependency on anyone, and it repairs the
   weakest measured source in the project. Begins by pulling one quarter under
   the §4.3 codes and reading a sample by hand: a classification set that admits
   every conveyor belt ever patented is worse than no patent source, and only
   looking at the output will show that.
3. **The diversity gate.** Deliberately before ABI/INFORM: it is the piece that
   makes the current report honest, and it works on data already in hand.
4. **ABI/INFORM trade press.** The largest coverage gain and the most involved
   query.
5. **Benchmark block**, when the MHI report is confirmed available. OECD and
   World Bank indicators join it there.
6. **Applied Science Commons**, if its export format turns out to be
   structured. It is the only candidate that would see standards literature.

Items 1 and 2 are independent of each other and of everything else.

## 9. How we will know it worked

Recorded here so the answer is not decided after the fact:

- Fewer than four of the eighteen well-evidenced technologies gated as
  single-source, down from seven.
- Fewer than five technologies silent for a full year, down from nine.
- Every stage drawing on at least two sources for a majority of technologies.
- Our pipeline position rank correlating with MHI's adoption ranking on the
  technologies both cover — with **no target value**. A weak correlation is a
  finding about the metric, and setting a threshold now would only invite
  tuning the metric until it clears it.
