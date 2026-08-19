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

## Momentum

Momentum is the second difference of the last three quarters, not of weekly
slopes. Three guards keep it from reporting noise as a trend:

- **All three quarters present.** Bridging a missing quarter invents a trend
  across the gap.
- **Two of the three non-zero, summing to at least 12.** 95% of `weekly_signals`
  is observed zeros, so a technology seen once still has a full, mostly-flat
  series; normalising that divides by a near-zero spread and hands the single
  document a large z-score. Three documents in a year is how manufacturing
  execution systems came to rank first. A fall *to* zero still qualifies — the
  guard is against absence, not against bad news.
- **Stocks are not summed.** `edgar_filers` counts distinct companies over a
  trailing window, so the same companies reappear every week. Adding thirteen
  weeks of it turned two filers into twenty-six. Signals with a `trailing_weeks`
  aggregation fold to their latest value instead.

On the first year of data 17 of 50 technologies clear all three; the smallest
corpus among them holds 16 documents.

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

## GitHub coverage

The GitHub collector needs a token in `.env` as `GITHUB_TOKEN`. A fine-grained
token with **no repository grants** is sufficient — we only read public data —
and it lifts the *search* rate limit from 10 requests a minute to 30. The
familiar 60-an-hour-to-5,000 figure is the core API's; the search endpoint this
collector uses is the tighter one, which is why `rate_limit_seconds` is 2.5.

GitHub is the only source here whose search accepts an explicit `created:` date
range, so unlike the others it backfills historically. A 52-week backfill of 51
pending weeks completed with **zero failures**, which no other source has managed:
GDELT and arXiv both throttled under the same treatment.

**The match rate is low and that is a property of the source, not a bug.** A
repository's entire searchable text is its description plus its language — a
sentence, against an arXiv abstract's paragraph. The first live run matched 57 of
2,337 distinct repositories, about 2.4%. Matches cluster on terms that appear
verbatim in short descriptions (`ERP`, `control tower`, `demand forecasting`)
while generic descriptions like "logistics API" match nothing.

**A repository needs at least one star to be counted.** `MIN_STARS = 1` in
`observatory/collectors/github.py` and `GithubCollector.parse` drops any item
whose `stargazers_count` falls below it (a missing or null count is treated as
zero, not skipped). This is a parse-time rule, applied to whatever raw JSON is
already on disk, so it is deterministic regardless of how a page happened to be
fetched — the existing year of raw, pulled down with no star filter at all,
re-derives the new numbers under an offline `--rebuild` with no new fetching.
The search query also carries a `stars:>=1` qualifier, but that is only an
optimization that shrinks what a *future* fetch pulls down against the page
cap (see below); it is not what decides whether an item counts. Across the 52-week
backfill this drops matched GitHub observations from 1,606 to 669 (42%) and
fetched repo-instances from 108,652 to 25,862 (24%). The owner's rationale: a
copied class project rarely gets starred, a real one usually does.

That is a lexicon question rather than a collector one. The Rising Terms block now
has 52 weeks of GitHub vocabulary in it. Discovery reads a repository's
description rather than its `owner/repo` slug, so what surfaces is language a
developer wrote — but read it knowing that a phrase repeated across a clone
cohort counts once per repository, so the loudest GitHub entries in a week are
often one boilerplate description duplicated forty times rather than forty
people converging on a word.

**The page cap truncates most anchor queries, every week.** `MAX_PAGES = 5`
fetches at most 500 results per anchor, and across the 52-week backfill 895 of
1,166 pages belong to a query whose `total_count` exceeded that, in 52 of 52
weeks. For 2026-W33 the six anchors reported 2,183 / 2,140 / 39 / 658 / 3,107 /
838 results and only one of them completed. So `gh_repos_new` is really
"matching repositories among the top 500 per anchor by stars", not "matching
repositories created in the week". Worse, coverage is falling as the repository
population grows — 54.6% in 2025-W35 against 28.3% in 2026-W33 — which puts a
trend inside the bias, across exactly the series z-scores and acceleration are
computed over. A truncated anchor now prints a `! github truncated …` line on
stderr during a fetch; raising the cap or narrowing the anchors would change
what the signal counts and is an open decision.

**About a fifth of matched repositories were clone cohorts, before the star
filter.** 294 of the 1,566 distinct matched repositories shared an exact name
with at least one other, and the families were larger than that once suffixed
variants were counted. The largest week in the series, 2026-W23, was 42
VendorBridge variants — one team project from the Odoo x KSV Hackathon 2026,
forked across an entire cohort of entrants, that alone suppressed `erp`'s
current z-score by 44%. **The star filter reduces this substantially but
does not eliminate it** — a copied class project can still pick up a stray
star, and forks within a large-enough cohort will too. After the filter, 43 of
651 distinct matched repositories still share an exact name with another
(down from 294 of 1,566), and 13 of the 46 VendorBridge copies survive.
Whether `gh_repos_new` should collapse exact-name families is still an open
signal-definition question; today it counts every one that clears the star
threshold.

**GitHub raw is about 12 MB a week — 621 MB of the 799 MB `data/raw` tree.**
Design rule 3 (raw before parse) is what makes `--rebuild` possible, so the
tree cannot be pruned without giving up the ability to replay history under a
changed parser or lexicon.
