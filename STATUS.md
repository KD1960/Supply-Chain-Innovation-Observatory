# STATUS

Supply Chain Innovation Observatory — state of the project, written for someone
picking it up cold. Last updated 2026-09-04.

Owner: Kevin Dooley, ASU W. P. Carey.

**Read this, then `docs/process-review-2026-09-04.md`, then
`docs/process-review-2026-08-31.md`.** The 09-04 review covers the most recent
11 commits, rechecks the register again, and adds five new risks. Like the
09-03 review before it, it is a self-assessment by the assistant that wrote the
work it assesses, and says so at the top.

**The 08-31 review is the only independent one** — commissioned from a reviewer
with no prior contact with the project — and it is still the sharper document.
It is more candid about this project's weaknesses than this file is, and its
risk register remains the best short guide to what will break next.

**Do not re-fix the closed risks.** Six of the original twelve were closed by
2026-09-03 and a seventh (the 256 hole) on 2026-09-03; each was rechecked by
behaviour rather than by grep.

**The single most important open question is not technical.** Whether 421
Scopus observations, gathered by hand export, may stay in a published report is
waiting on ASU Library. See §4a and the drafted reply in `correspondence/`.

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
| Tests | **746 passing** |
| Lexicon | version **10**, 48 active technologies |
| Observations | **2,311** |
| Sources | 10, across 8 evidence families |
| By source | github 799, arxiv 517, scopus 421, openalex 239, edgar 120, lens 64, hn 62, nsf 40, usaspending 29, federalregister 20 |
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
- **Stage what you mean to commit. Never `git add -A`.** Name the paths you
  changed. On 2026-09-03 `git add -A` published the owner's marketing and
  distribution plan to the public repository because it happened to be
  untracked, and on 2026-09-04 it did the same to a `.docx` assessment saved
  into `docs/` that morning — in the commit that wrote the review describing the
  first incident. The owner elected to leave both up and set this rule. The
  repository is public: a commit is a publication, and staging everything is not
  the same as choosing what to publish. An untracked file you notice gets
  mentioned to the owner, not committed.

## 4a. What the library can and cannot license (2026-09-03)

ASU Library answered a set of questions about text and data mining of licensed
resources; the business librarian replied with the electronic-resources and
licensing librarians copied. **Read this before adding any source that sits
behind a subscription.** The full record, including the exact clauses, is in
`docs/abi-inform-retired-2026-09-03.md`; the reply and the open questions are in
`correspondence/` (gitignored — email is not method).

The general answer: **ASU's business database licences forbid text and data
mining.** The Economist Intelligence Unit is the only business-related exception
the librarian knew of, and avoiding this restriction is a large part of why ASU
subscribes to TDM Studio at all. Most licences forbid automated retrieval even
of metadata alone.

| Source | Answer | What it meant here |
|---|---|---|
| **ProQuest / ABI/INFORM** | No TDM, and the librarian reads the clause as covering metadata. TDM Studio is the only sanctioned route, and ABI/INFORM is in it (not the Financial Times) | **Retired.** 13 observations removed, trade press gone as a family |
| **Scopus** | Elsevier gives academic researchers free API keys; the library is not involved. Quotas and throttling at dev.elsevier.com. Anything outside the API violates the terms | Move to the API. Key not yet requested; measured as worth building, `docs/scopus-vs-openalex-2026-09-03.md` |
| **Web of Science** | ASU terminated the subscription 2020-12-31. No access at all | Closed |
| **Factiva** | ASU does not subscribe | Closed. The earlier rejection stands for a second reason |
| **NexisUni** | Programmatic access prohibited without written permission; no API subscription. Even manual downloading can get ASU cut off if the vendor deems it excessive | Closed |
| **Lightcast** | Not a library resource — ask career services | Open, and not a library question |

**Still open with the library**, in the reply draft:

1. Whether a human-run Scopus export, matched locally, is acceptable until the
   API key is in place — or whether that should stop now too.
2. Whether the API key covers what this project does: retrieve, match locally,
   publish counts plus titles and links.
3. Whether TDM Studio can serve a recurring quarterly pull, or is built for
   one-off projects.
4. Whether publishing aggregate counts with titles and links is acceptable for
   a licensed source generally.

**The standing rule this produces:** a subscription source is not added until
its licence has been checked, and the answer is written down with the condition
that would change it — the same discipline this project already applies to
sources it rejects on measurement. What this project publishes helps its case
and does not settle it: observations store title, url and matched pattern, and
the evidence pages publish a title and a link. No abstract or full text is ever
published.

## 4b. What changed recently

Full reasoning is in the commit messages, which are long on purpose, in `docs/`,
and in `docs/process-review-2026-09-04.md`.

**2026-09-04** — the README was rewritten. It had described a weekly dashboard
built from six sources with an annual report, and walked a reader through
exporting from Web of Science and ABI/INFORM: the first is gone since 2020 and
the second is prohibited. Four paths in it did not exist. The `--export-queries`
help text named ABI/INFORM too, and a test now fails if the CLI's own help names
a retired source. Third process review written the same day.

**2026-09-03 (licence)** — **ABI/INFORM is retired.** ASU Library's licensing
answer: Clarivate forbids text and data mining of ProQuest products "or any
underlying data", and the licensing librarian reads that as covering metadata.
TDM Studio is the only sanctioned route. Thirteen observations were removed,
the exports moved to `data/withdrawn/`, and every published report regenerated.
2,324 → 2,311 observations; eleven sources → ten; trade press is gone as an
evidence family. `sources.yaml` carries the retirement and what reverses it;
`--export-queries` says out loud that the source exists and is not offered;
`--import-manual` refuses its files. Full record and the closed questions —
Web of Science, Factiva, NexisUni, Lightcast — in
`docs/abi-inform-retired-2026-09-03.md`.

**Scopus is the same question with a different answer**: Elsevier gives
academic researchers a free API key and treats the API as the sanctioned route,
while this project reaches Scopus by hand export — 421 observations, its
largest supplemental source. The API collector is the next piece of work.

**2026-09-03 (latest)** — the two deliverables that hang off the findings:

**Post cards.** `observatory/cards.py` draws one PNG per finding at 1200×627
(LinkedIn) and 1080×1350 (carousel): the stat in large type, the sentence, the
source line with its n, and the lockup. Drawn with **Pillow**, which is now a
declared dependency. That reverses `export.py`'s refusal of PNG on the recorded
condition: the refusal was about native libraries, and Pillow needs none.
Converting the SVG still cannot be done here — reportlab's own `renderPM` wants
cairo. A missing font raises `FontsMissing` rather than falling back to Pillow's
bitmap default, because CI runs on Ubuntu, which has no Arial.

**Tracked-technologies sheet.** `observatory/sheet.py`, one page: all 48 active
technologies in two columns with the terms each one matches, and the lexicon
version it was made from. The terms are expanded from the patterns rather than
kept beside them — `warehouse robot(s|ics)?` reads as "warehouse robots,
warehouse robotics" — so a definition cannot drift from what the entry matches.
128 of 145 patterns expand; the proximity ones do not, and a technology with
nothing expandable shows its pattern as written rather than a guess. One of the
48 does. Raises `SheetOverflow` rather than spilling onto a second page.

**Quarterly brief.** `observatory/brief.py`, two pages of reportlab from the
same `build_context`: findings on page one, the table, what is withheld, the
limitations and the provenance line on page two. reportlab draws past the bottom
edge without complaint, so the brief raises `BriefOverflow` instead of shipping
a sentence that is in the file and not on the paper.

All three are written by `--quarter`, into `output/cards/`,
`output/brief-<period>.pdf` and `output/technologies-<period>.pdf`. All three
fail soft: the report still ships and says what did not.

**§4 of the marketing plan is now built end to end** — findings layer, post
cards, brief, technologies sheet.

**2026-09-03 (later)** — the report gained a **findings layer**, §4 of
`docs/marketing-plan-2026-09-03.md` and the largest gap that plan names. Seven
rules in `observatory/findings.py` read the rows `build_context` already makes
and write a sentence with its own sample size in it; five ship, above everything
that describes the instrument. The four count rules fire in a period whose
scores are withheld, so 2026-Q3 still opens with four findings and no inferences.
The instrument tiles moved into "How to read this document"; every technology
row now carries `id="tech-<id>"` so a post can link to one row.

A rule may not name a technology on fewer than three documents. 2026-Q2 holds
cold chain IoT monitoring at diffusion on one SEC filing, which is what makes
the marketing plan's own example sentence — autonomous trucking is the only
technology at diffusion — false as written. The page says "1 further technology
appeared there on fewer than 3 documents, too few to name" instead.

`findings/<period>.yaml` is the owner's override: replace any sentence, drop any
finding, set the order. Absent means the drafted sentences ship. An id in the
file that no rule owns raises rather than sitting there looking applied. The
findings are asserted against the rendered HTML, not the template context.
Spec: `docs/superpowers/specs/2026-09-03-findings-layer-design.md`.

**2026-09-03 (earlier)** — two fixes to the overlapping-export guard, both verified
against `data/manual` and not only against tests.

The guard now enforces the 5% tolerance its own comment documented: a set is
refused when its largest file holds 95% or more of the distinct records. The old
comparison, `len(union) <= len(largest) / 0.95 * 0.95`, was both redundant with
the clause beside it and wrong at 256 and 512, where the float round-trip lands
below `n` -- an exactly-duplicated 256-record export was accepted. The owner
chose the tolerance over the narrower fix, so a duplicated set carrying a stray
extra record is caught too.

The second was found by running the guard over the real export directory rather
than reading it. **It had never once applied to Scopus.** Identity was the raw
`identifier` field; ProQuest writes an accession number and Scopus does not, so
all twelve Scopus exports -- 2,648 records, the largest manual source -- carried
a blank one, `if ids` was false every time, and twelve files were skipped in
silence. Identity is now `document_id`, the same function the rest of the
pipeline uses. Scopus measures 0.255 today and abi_inform 0.241, so neither is
near the limit.

**2026-09-01 to 09-03** — 29 commits, assessed in
`docs/process-review-2026-09-03.md`. Six of the previous review's twelve risks
closed. Headlines:

- **Withholding, failures and future periods** — a score is withheld when the
  *window* is short, not just the period; `source_attempts` makes a failure
  outlive its retry; a period that has not begun is refused, and counting stops
  at today.
- **A quality gate exists** — `ruff` in a pre-commit hook (`git config
  core.hooksPath hooks`), in CI, and in the suite.
- **STATUS §2 is generated** — `--write-status`, with a test that fails on drift.
- **Lexicon v9 → v10** — `infrastructure_security` and `nearshoring_analytics`
  retired, `green_logistics` and `agentic_procurement` tightened, on audit
  evidence. 2,462 → 2,324 observations, every other technology unchanged.
- **The precision instrument was broken and is fixed** — the sheet truncated its
  own evidence at 600 characters, hiding the matched pattern on 24 of 108 items.
  See §5.
- **The report gained a masthead**, disclosure tabs and a credit line.

**2026-08-27 to 08-31** — USAspending fixed (it phrase-matched six multi-word
strings against an API that phrase-matches, and matched none of 36 awards in a
year; it queries freight assistance-listing programmes now). Five sources added:
Scopus, Lens, ABI/INFORM by hand, OpenAlex and NSF automated. Lexicon v6 → v9.
Reporting moved to calendar quarters. Metrics moved from a 52-week to a
four-quarter window. The weekly page became a collection-health view.

## 5. What is broken or missing

### Measurement of the instrument itself

**Precision is unsettled, and further from settled than it was.** The last
figure, **70%**, was measured at lexicon v9 against a corpus that no longer
exists — the four worst technologies were retired or tightened the next day, and
ABI/INFORM was removed entirely on 2026-09-03. Two corpus changes now separate
the measurement from what is published. Nothing currently states the precision of what is
published. `docs/precision-audit-2026-09-02.md` carries both audits and the
re-audit; the sheet is `docs/audit/sample-20260902.md`, rebuilt with
`--audit-sheet`.

**Every coder so far is the same model.** Coders A, B and D, and the CRA
validation. The owner's pass (`coder-c.csv`) was against the broken sheet. A
coder who did not write or approve the patterns is the only thing that settles
this.

**EDGAR cannot be audited at all.** Filing bodies are megabytes and are never
fetched, so an observation is attributed by the query term and the stored
evidence is the filer's name. All twelve sampled items code `x`. That is 129
observations and the strongest diffusion leg, precision unknown.

### Sources

**Scopus is the open licence question, and it is the biggest thing in this
file.** ABI/INFORM was retired because ProQuest forbids mining. The same library
answer says the Elsevier API is the sanctioned route for Scopus and that "any
other text & data mining activity would violate the Elsevier terms" — and 421
Scopus observations, from hand-run exports, are in the corpus and in published
reports. The distinction being relied on (a person clicks export; the clause
quoted names robots and crawlers) is a reading, not an answer. It is question 1
in the drafted reply, and it should be settled before the next report is
published. If the answer goes the other way, the corpus loses a further 421
observations and its largest supplemental source.

**There is no trade press.** ABI/INFORM was retired on 2026-09-03 for licence
reasons (`docs/abi-inform-retired-2026-09-03.md`), taking the `trade` evidence
family with it. The abstract problem that used to sit here — ProQuest's RIS
export defaults to citation-only, so every export lacked `AB` — is moot unless
the source returns through TDM Studio. `docs/reexport-2026-Q3-abstracts.md` is
superseded: **do not run it.**

**GitHub measures the wrong population.** 78% of matched repositories have
exactly one star and the largest has 118; 60 sampled repos gained no stars in
9–12 months. It is a third of the corpus.

**Sources barely overlap.** The source-diversity gate marks any technology
drawing 80%+ of its evidence from one source and withholds its share movement.

**Diffusion is the thinnest stage, and thinner since 2026-09-03.** With trade
press gone it rests on SEC filings and Hacker News alone, which is uncomfortable
for a project whose central question is about diffusion. 2026-Q2 was 328
research and 275 code against 29 filings and 1 trade article. 14 of 48 technologies have fewer than
five observations ever. `docs/edgar-depth-2026-09-01.md` measured EDGAR's
ceiling at 4–5×; `docs/sources-probed-2026-09-03.md` probed Reddit, vendors,
GDELT, PatentsView and Semantic Scholar.

**Not built:** PatentsView (awaiting a key; `search.patentsview.org` has no DNS
record as of 2026-09-03, so check the endpoint before trusting the plan). GDELT
(reachable and keyless, but the owner has run it before and a query took hours,
so it cannot be a weekly collector). Semantic Scholar (429s unauthenticated;
the test it must pass is overlap with OpenAlex, not availability).

### Known defects, unfixed

**`collected_quarters` counts a week as collected if any `source_runs` row
exists** — the owner ruled on the all-failed case (`store.COLLECTED_STATUSES`),
but the quarter-level count still does not use it.

**`adoption_new` is hardcoded to 0** (`metrics.py`). **`media_articles` and
`media_deploy`** are declared in `normalize.py` for a GDELT collector that has
never existed.

**`missing_exports` detects absence, not staleness.** A file present but
generated under an older lexicon is invisible to it.

**`patentsview` is declared and has never existed.** It sits in
`EVIDENCE_FAMILIES` and was printed in Appendix B as a source feeding the
experiment stage until 2026-09-03. Either build it or delete the declaration.

**Two findings can name the same technology.** 2026-Q2 publishes autonomous
trucking in finding 1 and again in finding 4. Nothing tests for it.

**Post cards need a font the CI box does not have.** `cards.load_fonts` raises
`FontsMissing` rather than falling back to Pillow's bitmap default, which is
right, but `render_quarter` catches it and prints a line — so a quarter can ship
with no cards and one line of output saying why.

**Carry-forward items** in the plan docs: clone-cohort policy beyond the star
filter, `gh_commits` / `gh_stars_delta`, `fed_obligated` semantics, discovery
baseline denominator, discovery corpus breadth.

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

In value order. `docs/process-review-2026-09-04.md` has the reasoning and the
current risk register.

1. **Send the reply to the library.** Drafted at
   `correspondence/2026-09-03-library-reply-draft.md`, waiting on Kevin.
   Question 1 — whether hand-run Scopus exports may continue, and whether what
   is published from them is acceptable — decides whether 421 observations stay
   in the corpus. Nothing else in this file is worth more than that answer.
2. **The Scopus API collector — waiting on the key.** Elsevier gives academic
   researchers a free key (dev.elsevier.com); the library is not involved.
   Worth building: measured 2026-09-03, Scopus carries **159 matched documents
   OpenAlex does not**, 46% of its own matched set
   (`docs/scopus-vs-openalex-2026-09-03.md`), so it is not the duplicate the
   OpenAlex docstring implies. Deliberately not written against a guessed
   response shape — when the key lands, capture one real response as the
   fixture and **measure abstract coverage before adopting**, which is the check
   OpenAlex never got.
3. **A coder who did not write the patterns.** Four passes, one model, and the
   figure is now two corpus changes stale. The only thing that settles what
   precision is. Sheet: `docs/audit/sample-20260902.md`.
4. **The think-aloud sessions**, October, per §5 of
   `docs/marketing-plan-2026-09-03.md`. The findings layer was built ahead of
   them rather than after, so the Q2 report is the stimulus and the override
   file (`findings/<period>.yaml`) is what absorbs what they say.
5. **Split `quarter.build_context`.** Risk 12 has been open across three reviews
   and grew in every one; `quarter.py` is 826 lines.
6. **Q4 supplemental exports**, first week of January. `--export-queries 2026-Q4
   --split`, now Scopus and Lens only. Scopus caps an export at 2,000 records
   and says so only in the interface.
7. **The first complete calendar year.** 2026 finishes at W53 — the first annual
   report where neither year is truncated.
8. **Decide `patentsview`:** build it if the key arrives and the endpoint
   resolves, or delete the declaration. It has been named as a source since
   before it existed.
9. **Retire `discover.py` or justify it.** The rising-terms loop has contributed
   none of the 48 watchlist entries, and a second discovery instrument is now
   specced beside it (`docs/superpowers/specs/2026-09-03-source-discovery-design.md`).

**Waiting on the owner:** the library reply (above), an Elsevier API key for
Scopus, Reddit app credentials, and the PatentsView key. The library has already
answered on ABI/INFORM (retired), Factiva (no subscription), Web of Science
(terminated 2020), NexisUni (prohibited) and Lightcast (not a library resource).

**Specced, not built:** source discovery (above), and a PDF of the *full*
quarterly report — agreed to use reportlab, report plus evidence in one file,
rendering from the same `build_context()` the HTML uses. The two-page brief
built on 2026-09-03 is a different artifact and does not replace it.

**Built this session, and unexercised in anger:** the findings layer, the post
cards, the brief and the technologies sheet have been generated for 2026-Q2 and
2026-Q3 and looked at, but no reader outside this project has seen any of them.

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
- **CRA is not being added** (2026-09-03). Centering Resonance Analysis was
  tested against the 120 coded audit items before any change, because it
  measures whether a matched term is central or peripheral and every false
  positive found was a passing mention. It works — AUC 0.70, and the canonical
  SAVMap false positive scores its match at influence 0.000, rank 23 of 28 —
  but not well enough: roughly six precision points for thirteen per cent of
  the true positives, concentrated in NSF (0.87) and USAspending (0.75) and at
  or below chance on arXiv and OpenAlex. It also cannot reach 42% of the corpus,
  github included, for want of text. Full measurement in
  `docs/cra-feasibility-2026-09-03.md`; harness in `docs/experiments/`.
- Three proposed technologies were rejected as fields rather than technologies:
  software supply chain security, e-commerce, machine learning for operations.
  Together they would have more than doubled the corpus.

**Decided 2026-09-03 and 09-04:**

- **ABI/INFORM is retired**, and the 13 observations it had produced were
  removed rather than left in published reports. Reversal conditions in
  `docs/abi-inform-retired-2026-09-03.md`.
- **The overlap guard enforces the 5% tolerance its comment documented**,
  rather than the narrower fix of refusing only exact duplicates. A duplicated
  set carrying a stray extra record is caught.
- **Post cards carry the finding, not the figure.** A scatter with fifteen
  labelled dots is unreadable in a social crop, and a post is one click from a
  report most readers will not open.
- **Pillow is an accepted dependency.** `export.py` refused PNG because
  rasterisers need native libraries; that is still true of converting the SVG,
  and was never true of drawing.
- **The technologies sheet expands patterns into readable terms** rather than
  printing them raw or dropping definitions. What cannot be expanded cleanly is
  shown as written.
- **The Scopus collector waits for a real API response** rather than being
  written against the documented schema.
- **The marketing plan stays public.** It was pushed to the public repository by
  a `git add -A` that swept up an untracked file; the owner elected to leave it
  rather than rewrite history. Correspondence is now gitignored.

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

**Assuming the scope of an action instead of checking it.** `git add -A`
published the owner's marketing plan to a public repository, because the command
was chosen for convenience and nobody looked at what it was staging. This is the
same shape as verifying the mechanism rather than the outcome, moved outside the
pipeline: the action was believed rather than observed.

**The remedy that works:** check the artifact, not the code that makes it. Read
the rendered page, count the rows in the database, compare the number against
the export file. Every wrong figure in this project was caught that way, and
none were caught by reading the code that produced them.
