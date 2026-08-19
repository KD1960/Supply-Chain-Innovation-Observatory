# Supply Chain Innovation Observatory

A weekly dashboard that tracks supply chain technologies moving from idea to
experimentation, investment, deployment, and diffusion — built entirely from
public data.

## Setup

    python -m pip install -e ".[dev]"
    cp .env.example .env      # then fill in SEC_CONTACT_EMAIL

## Run a week

    python -m observatory.run

Other forms:

    python -m observatory.run --week 2026-W33   # a specific week
    python -m observatory.run --skip-fetch      # recompute from saved raw files
    python -m observatory.run --rebuild         # recompute all weeks from raw
    python -m observatory.run --only arxiv      # a single collector
    python -m observatory.run --backfill 52     # fetch 52 trailing weeks, then rebuild

## Backfill

Most of the dashboard needs history to say anything: a z-score wants 12 weeks,
so a cold database renders "warming up" and no scores at all. `--backfill N` fetches the trailing `N` weeks, oldest first, and then runs
the same full rebuild as `--rebuild`.

It takes a while, because the collectors are deliberately polite. A week costs
about a dozen requests at the floor and about forty-five when every source
runs into its page cap, with arXiv paced at one request every three seconds.
For 52 weeks that is roughly half an hour at the floor and around three hours
at the ceiling.

Interrupting it is safe. Every collector's outcome is recorded per week, so a
restart refetches only the weeks and the individual collectors that have not
recorded a success — a week where four sources worked and one failed costs one
source's requests on the next attempt, not five. Run it again until it reports
that every week is already fetched.

Because it ends in a full rebuild, which replays every source, it cannot be
combined with `--only`.

Output lands in `output/latest.html` — one self-contained file, no server needed.
Every count on it links to `output/evidence.html`, which lists each observation
behind the week's numbers alongside the document and the regex pattern that
matched it, so any number can be traced back to its evidence.

## Growing the lexicon

The pipeline never edits `watchlist.yaml` itself — deciding whether "dark
factory" names a real technology is a human judgement, not a pattern match.
The loop for adding a new term:

    python -m observatory.run                       # run the week as usual
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
It exits non-zero if anything fails, and prints nothing further to paste. On
success it prints a paste-ready YAML block: copy that into the `technologies`
list in `watchlist.yaml`, then by hand:

- bump `lexicon_version` at the top of the file
- set `added_week` on each new entry — `watchlist.yaml` requires it and the
  proposal never carries it
- set `patterns_changed_week` on each entry you added or changed

`patterns_changed_week` no longer gates a metric — momentum, the only thing it
suppressed, has been dropped — but it still records when a technology stopped
meaning the same thing, which any comparison across that date has to respect.
Finally, recompute history under the new patterns:

    python -m observatory.run --rebuild

## Design rules

1. **No LLM in the weekly run.** Scoring and matching are deterministic, so any
   week recomputes identically. A test enforces this.
2. **No paid data sources.**
3. **Raw before parse.** Responses are written to `data/raw/` before parsing, so
   a parser fix never costs a re-fetch.
4. **A missing week is not a zero week.** Failed sources carry forward.

Full design: `docs/superpowers/specs/2026-08-16-supply-chain-innovation-observatory-design.md`

## Weekly cron

Installed 2026-08-17, Monday 07:00 local:

    0 7 * * MON cd '/Users/kevindooley/Claude/Projects/Supply chain innovation' && /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m observatory.run >> data/cron.log 2>&1

The interpreter path matters. `/usr/bin/python3` is macOS's system Python 3.9 and
has none of this project's dependencies, so the obvious-looking entry fails every
week and only shows up in the log. Use the absolute path to the Python that has
them; `which python3` names it.

Monday is deliberate. Each collector's window reaches seven days back, so the
Monday run also sweeps the week that just ended, and the pipeline rescores every
week it writes observations into.

Check it worked with `tail data/cron.log`. If the log is empty on a Monday
afternoon, cron did not run: on macOS `/usr/sbin/cron` may need Full Disk Access
under System Settings → Privacy & Security to reach files under your home
directory.

## Quarterly report

Collection stays weekly; reporting does not.

    python3 -m observatory.run --quarter 2026-Q2

Across this corpus two thirds of technology-weeks hold zero observations and the
median is zero, so a weekly ranking mostly reports which week a collector caught
something. Thirteen weeks is the first interval at which a typical technology has
anything in it: zero cells fall from 68% to 34%, and the median from 0 to 2.

The report reads stored observations only and never fetches. It writes
`output/report-<quarter>.html`.

A quarter still filling up says so on its own face and withholds its share
movement — eight weeks of share against a full thirteen looks exactly like a
decline. The count of weeks actually run comes from `source_runs`, because a week
that ran and found nothing is observed while a week that never ran is not.

### Why collection stays weekly

A wider fetch window would silently truncate four of the six sources. Per 13-week
quarter the volumes run past their caps: arXiv ~15,800 against 2,000 per sweep,
GitHub ~6,460 against a hard 1,000-result API limit, the Federal Register ~3,400
against 2,000, Hacker News ~2,200 against 1,000. Three of those caps could be
raised; GitHub's cannot — the Search API refuses to page past 1,000 results for
any single query. The weekly window is what keeps every query under its cap.

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

With the annual report the deliverable, nothing else wanted a weekly slope.
Adoption breadth, source concentration, pipeline position, SAI and LFI are all
cross-sectional. The weekly dashboard now ranks by substance rather than
momentum.
