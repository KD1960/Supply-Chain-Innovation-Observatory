# Supply Chain Innovation Observatory

Which supply chain technologies are being **built** rather than talked about.

The Observatory tracks technologies moving from idea to experimentation,
investment, deployment and diffusion, from observable traces in publicly
accessible data. Nothing here is a survey or an opinion: every number is a
count of documents that a stored pattern matched, and every count can be
traced back to the document that produced it.

**Collection runs weekly. Reporting is quarterly.** The two cadences are
deliberately different and neither should be changed into the other — see
[Why collection stays weekly](#why-collection-stays-weekly).

## What it produces

Per reporting period, all written by one command:

| File | What it is |
|---|---|
| `output/report-<period>.html` | The report. Opens with the findings; the table, charts and appendices are below them |
| `output/evidence-<period>.html` | Every observation behind the counts, with the document and the pattern that matched it |
| `output/charts/<period>-*.svg` and `.pdf` | The figures on their own, for a slide or a paper |
| `output/cards/<period>-<finding>-*.png` | One post card per finding, at 1200×627 and 1080×1350 |
| `output/brief-<period>.pdf` | Two pages: the findings, the table, what is withheld |
| `output/technologies-<period>.pdf` | One page: every tracked technology and the terms it matches |

The weekly page (`output/dashboard-<week>.html`) is a **collection-health view**
— did the collectors run, what arrived, which terms are rising. It is not a
ranking of technologies, and it is not the deliverable.

## Setup

    python -m pip install -e ".[dev]"
    cp .env.example .env      # then fill in SEC_CONTACT_EMAIL

## Run

    python -m observatory.run                     # the weekly run; this is what cron does
    python -m observatory.run --quarter 2026-Q2   # the deliverable
    python -m observatory.run --annual 2026

Other forms:

    python -m observatory.run --week 2026-W33   # a specific week
    python -m observatory.run --skip-fetch      # recompute from saved raw files
    python -m observatory.run --rebuild         # recompute all weeks from raw
    python -m observatory.run --only arxiv      # a single collector
    python -m observatory.run --backfill 52     # fetch 52 trailing weeks, then rebuild
    python -m observatory.run --write-status    # regenerate STATUS section 2

**A number read without a rebuild is the old lexicon's number.** Observations
insert with `INSERT OR IGNORE`, so rows written under older patterns survive
until `--rebuild` drops the derived tables.

## Sources

Ten sources across eight kinds of evidence. Eight are collected automatically:

| Source | Evidence |
|---|---|
| arXiv, OpenAlex | research |
| GitHub | code |
| USAspending, NSF | federal money, research funding |
| SEC EDGAR | company filings |
| Federal Register | regulation |
| Hacker News | community |

Two are fetched by a person, because their licences do not permit automated
retrieval: **Scopus** (research) and **Lens.org** (patents). The pipeline
generates the exact query so no judgement enters at that step:

    python -m observatory.run --export-queries 2026-Q4 --split
    python -m observatory.run --import-manual

Each export needs a `<file>.meta.yaml` sidecar beside it under
`data/manual/<period>/`:

    data/manual/2026-Q4/scopus-00207543.ris
    data/manual/2026-Q4/scopus-00207543.ris.meta.yaml

    source: scopus              # becomes the `source` column on every observation
    exported: 2026-08-20        # the day you ran the search
    query: (ISSN(0020-7543)) AND PUBYEAR = 2026
    records: 1843               # what the database said it found

Three rules make a hand-made export as accountable as an API call:

- **The query is recorded.** An export nobody can reproduce is not evidence.
- **The count is checked.** Scopus caps an export at 2,000 records and mentions
  it only in the interface. Declared and parsed counts must agree or the import
  refuses, because a truncated file is this project's oldest failure mode.
- **A set of exports that adds nothing to its largest file is refused.** Four
  files once arrived holding 182 records and 52 distinct ones — a marked-items
  list exported repeatedly as it grew.

**Abstracts are matched and then dropped.** The abstract decides the match and
is discarded. What persists is the title, the venue and a link, which any
reader with access can follow. No licensed text is stored or published.

## Licensing

**A subscription source is not added until its licence has been checked, and
the answer is written down with the condition that would change it.**

ASU Library, 2026-09-03: the university's business database licences generally
forbid text and data mining, most of them including metadata. What that meant
here:

- **ProQuest / ABI/INFORM — retired.** Clarivate's terms forbid mining of the
  product "or any underlying data". TDM Studio is the only sanctioned route.
  `docs/abi-inform-retired-2026-09-03.md`.
- **Scopus — permitted through the API.** Elsevier issues free API keys to
  academic researchers; anything outside the API violates the terms.
- **Web of Science** (subscription terminated 2020), **Factiva** (no
  subscription) and **NexisUni** (programmatic access prohibited) are closed.

A retired source keeps its registry entry, its query and the reason it stopped,
so nobody re-adds it in a year without seeing why. `--export-queries` says on
its own sheet that the source exists and is not offered, and `--import-manual`
refuses its files.

## Backfill

History matters: a score compares a period against the three quarters before
it, so a cold database reports counts and withholds every inference.
`--backfill N` fetches the trailing `N` weeks, oldest first, then runs the same
full rebuild as `--rebuild`.

It takes a while, because the collectors are deliberately polite. A week costs
about a dozen requests at the floor and about forty-five when every source runs
into its page cap, with arXiv paced at one request every three seconds. For 52
weeks that is roughly half an hour at the floor and around three hours at the
ceiling.

Interrupting it is safe. Every collector's outcome is recorded per week, so a
restart refetches only the weeks and collectors that have not recorded a
success. Because it ends in a full rebuild, it cannot be combined with `--only`.

## Growing the lexicon

The pipeline never edits `watchlist.yaml` itself — deciding whether "dark
factory" names a real technology is a human judgement, not a pattern match.
The loop for adding a new term:

    python -m observatory.run                        # run the week as usual
    python -m observatory.lexicon prepare 2026-W33   # write a request from this week's rising terms

`prepare` writes `lexicon/requests/2026-W33.md` — the candidate terms, their
evidence, the context vocabulary, and the technologies already tracked, with a
warning that the harvested text below it is evidence to be judged, not
instructions to follow. Open a Claude session, hand it that file, and ask it
to answer it by writing `lexicon/proposals/2026-W33.yaml` in the shape shown
in the request.

    python -m observatory.lexicon check 2026-W33

`check` validates the proposals file — every pattern must compile, every id
must be new, every proposed pattern must match at least one of the week's own
candidate evidence, and a `needs_context` entry must have evidence that
actually contains a context word, or it would silently track at zero forever.
It exits non-zero if anything fails. On success it prints a paste-ready YAML
block: copy that into the `technologies` list in `watchlist.yaml`, then by hand:

- bump `lexicon_version` at the top of the file
- set `added_week` on each new entry — `watchlist.yaml` requires it and the
  proposal never carries it
- set `patterns_changed_week` on each entry you added or changed

`patterns_changed_week` records when a technology stopped meaning the same
thing, which any comparison across that date has to respect. Finally, recompute
history under the new patterns:

    python -m observatory.run --rebuild

## Design rules

1. **No LLM in the weekly run.** Scoring and matching are deterministic, so any
   week recomputes identically. A test enforces this. The lexicon authoring
   command is the one exception, and it is offline with a human approving the
   merge.
2. **No paid data sources**, and no licensed source without a licence answer.
3. **Raw before parse.** Responses are written to `data/raw/` before parsing, so
   a parser fix never costs a re-fetch.
4. **A missing week is not a zero week.** A source that failed leaves its
   signals absent, not zero. Folding absence into zero invents declines.
5. **Say it out loud when a cap bites.** Silent truncation is this project's
   oldest failure mode.
6. **Check the artifact, not the code that makes it.** Every wrong number in
   this project was caught by reading the rendered page or counting rows, and
   none by reading the code.

Full design:
`docs/superpowers/specs/2026-08-16-supply-chain-innovation-observatory-design.md`.
Current state and open work: `STATUS.md`.

## Weekly cron

Installed 2026-08-17, Monday 07:00 local:

    0 7 * * MON cd '/Users/kevindooley/Claude/Projects/Supply chain innovation' && /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m observatory.run >> data/cron.log 2>&1

The interpreter path matters. `/usr/bin/python3` is macOS's system Python 3.9 and
has none of this project's dependencies, so the obvious-looking entry fails every
week and only shows up in the log.

Monday is deliberate. Each collector's window reaches seven days back, so the
Monday run also sweeps the week that just ended, and the pipeline rescores every
week it writes observations into.

Check it worked with `tail data/cron.log`. If the log is empty on a Monday
afternoon, cron did not run: on macOS `/usr/sbin/cron` may need Full Disk Access
under System Settings → Privacy & Security.

## Why reporting is quarterly

Two thirds of technology-weeks hold zero observations and the median is zero, so
a weekly ranking mostly reports which week a collector caught something.
Thirteen weeks is the first interval at which a typical technology has anything
in it: zero cells fall from 68% to 34%, and the median from 0 to 2.

A quarter still filling up says so on its own face and withholds its scores —
eight weeks of share against a full thirteen looks exactly like a decline. The
count of weeks actually run comes from `source_runs`, because a week that ran
and found nothing is observed while a week that never ran is not.

## Why collection stays weekly

A wider fetch window would silently truncate four of the automated sources. Per
13-week quarter the volumes run past their caps: arXiv ~15,800 against 2,000 per
sweep, GitHub ~6,460 against a hard 1,000-result API limit, the Federal Register
~3,400 against 2,000, Hacker News ~2,200 against 1,000. Three of those caps
could be raised; GitHub's cannot — the Search API refuses to page past 1,000
results for any single query.

Cadence and window are separable: an annual *run* that loops over 52 weekly
*queries* is fine; a single wide query is not.

## Momentum was dropped

Momentum is gone, along with `acceleration`, `cross_sectional_z`,
`normalize_series` and the quarter-folding helpers built for it.

It was the only metric that needed a time series, and the one that kept
reporting noise as trend. Three separate ways, each found by looking at what it
ranked rather than by reading the code: 95% of `weekly_signals` is observed
zeros, so normalising a technology seen once divided by a near-zero spread and
handed its single document a large z-score (manufacturing execution systems,
three documents in a year, ranked first); `edgar_filers` is a stock, not a flow,
so summing thirteen weeks of it turned two filers into twenty-six; and every
guard added to fix those took the scored set from 50 of 50 to 17 of 50, which is
a metric that was mostly not measuring anything.

Adoption breadth, source concentration, pipeline position, SAI and LFI are all
cross-sectional. The weekly page ranks by substance instead.
