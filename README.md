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

Most of the dashboard needs history to say anything: a z-score wants 12 weeks
and momentum wants 8, so a cold database renders "warming up" and no scores at
all. `--backfill N` fetches the trailing `N` weeks, oldest first, and then runs
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

Momentum is suppressed for the eight weeks following `patterns_changed_week`,
because a pattern that suddenly matches more documents looks exactly like real
acceleration otherwise. Finally, recompute history under the new patterns:

    python -m observatory.run --rebuild

## Design rules

1. **No LLM in the weekly run.** Scoring and matching are deterministic, so any
   week recomputes identically. A test enforces this.
2. **No paid data sources.**
3. **Raw before parse.** Responses are written to `data/raw/` before parsing, so
   a parser fix never costs a re-fetch.
4. **A missing week is not a zero week.** Failed sources carry forward.

Full design: `docs/superpowers/specs/2026-08-16-supply-chain-innovation-observatory-design.md`

## Weekly cron (optional, not installed)

    0 7 * * MON cd /path/to/repo && /usr/bin/python3 -m observatory.run >> data/cron.log 2>&1

## Tests

    python -m pytest

## arXiv coverage

arXiv tolerates the weekly cadence but throttles a bulk backfill: a 52-week run
succeeded for three weeks, then returned `429` for four consecutive weeks. The
owner's decision (2026-08-17) is to let the ordinary weekly runs fill the Idea
stage in over time rather than push a backfill into an IP-level cooldown.

Weeks that failed keep a `failed` status in `source_runs`, so any later run
fetches exactly the ones still missing — no bookkeeping required. The other four
collectors have the full 52 weeks.
