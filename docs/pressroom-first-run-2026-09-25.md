# Press-room collector: first run, 2026-09-25

The collector built on branch `pressroom` (spec
`docs/superpowers/specs/2026-09-25-pressroom-collector-design.md`) ran for the
current week only, against the production database. Nothing else was fetched
and nothing was rebuilt.

    python -m observatory.run --only pressroom --week 2026-W39
    # after the fix below, on the same raw files:
    python -m observatory.run --only pressroom --week 2026-W39 --skip-fetch

The run window is 2026-09-14 to 2026-09-27 (the week plus the seven-day
lookback). The fetch took under two minutes (first raw file 19:44:52 UTC,
last 19:46:44). The run also printed `! failed: edgar` and `~ returned
nothing: federalregister, nsf, usaspending`; those are the week's statuses
from Monday's cron run, which the render reads back, not anything this run
did.

## What went wrong on the first pass

The first run parsed **780 documents dated back to 2002** and wrote **131
observations**. A newsroom listing carries its whole visible history (Volvo's
sitemap, Circularise's blog index), and `parse()` returned every dated item
on it, each filed under its own week. So 128 of the 131 observations landed
in weeks with no `pressroom` run, where they never reach a signal but do
count in totals, and the `corpus` table recorded all 780 documents under
2026-W39, which every later weekly run would have recorded again. Other
collectors avoid this because their queries are date-bounded.

**The fix** (commit 67e0c2d): `parse()` computes the window from the
envelope's own `fetched_week`, exactly as `fetch_raw` does, and drops items
outside it. History on a listing is not collected; the source starts at its
first run week, like every other collector. Then the first pass was purged
(a copy of the database was taken first) and replayed from the saved raw:

    DELETE FROM observations WHERE source='pressroom';     -- 131 rows
    DELETE FROM corpus WHERE source='pressroom';           -- 473 rows, 780 documents
    DELETE FROM weekly_signals WHERE signal='press_releases';  -- 48 rows

The `source_runs` row (2026-W39 ok) was kept: `--skip-fetch` replays only
sources recorded ok, and a fresh fetch would overwrite the week's raw files.
Observations went 2,513 before the purge, 2,382 after, 2,385 after the replay.

## Counts (the clean run)

Every number below was read from `data/raw/2026-W39/pressroom/*.json`, from
`parse()` over those files, or from the `observations`, `corpus`,
`source_runs` and `weekly_signals` tables for source `pressroom`.

| | |
|---|---|
| Raw envelopes written | 16, one per newsroom |
| Newsrooms with a non-empty listing | 16 of 16, every one HTTP 200 |
| Notes recorded (403, robots, page errors) | 0 |
| Item pages fetched | 26 |
| Documents parsed (`corpus`, 2026-W39) | 19, over 8 dates (09-15 2, 09-17 3, 09-18 1, 09-21 2, 09-22 2, 09-23 5, 09-24 3, 09-25 1) |
| Newsrooms with at least one in-window document | 9 of 16 |
| Observations | 3, all 2026-W39, all `autonomous_trucking` |
| `press_releases` signal rows | 48, one per active technology |
| Source status for 2026-W39 | `ok` |

## Per newsroom

| Newsroom | Kind | Status | Pages fetched | Documents in window | Observations |
|---|---|---|---:|---:|---:|
| aurora | html | 200 | 1 | 1 | 1 |
| kodiak | html | 200 | 3 | 3 | 2 |
| plus | html | 200 | 0 | 0 | 0 |
| wing | links:/news/ | 200 | 7 | 0 | 0 |
| agility | html | 200 | 3 | 3 | 0 |
| figure | html | 200 | 1 | 1 | 0 |
| apptronik | html | 200 | 0 | 0 | 0 |
| circularise | html | 200 | 2 | 2 | 0 |
| averydennison | html | 200 | 1 | 1 | 0 |
| gs1us | html | 200 | 1 | 1 | 0 |
| daimlertruck | html | 200 | 6 | 6 | 0 |
| volvotrucks_us | sitemap | 200 | 0 | 0 | 0 |
| righthand | html | 200 | 0 | 0 | 0 |
| berkshiregrey | rss | 200 | 1 | 1 | 0 |
| symbotic | sitemap | 200 | 0 | 0 | 0 |
| locus | rss | 200 | 0 | 0 | 0 |
| **Total** | | | **26** | **19** | **3** |

Wing's `links:` listing is undated, so its first links are fetched to learn
their dates. All seven were dated correctly (09-04, 08-07, 07-29, 07-16,
06-08, 05-11, 03-23) and none falls in the window, so zero documents is the
right answer.

## What matched, read by hand

All three match `autonomous truck(s|ing)?`:

| Date | Newsroom | Title | Reading |
|---|---|---|---|
| 2026-09-24 | kodiak | Kodiak AI and DTL Transport Complete First Autonomous Trucking Deliveries Under New California DMV Permit | **pilot-band**: a named customer, first deliveries, a permit |
| 2026-09-21 | kodiak | PrePass and Kodiak AI Collaborate to Advance Safe, Scalable Driverless Trucking Nationwide | an initiative with no site: a passing mention, not pilot-band |
| 2026-09-23 | aurora | Aurora to Host Analyst & Investor Day on September 23, 2026 | **false positive**: a corporate notice; the match is "autonomous trucking industry" in the company's description of itself |

In-window items that matched nothing, for the record: Kodiak's
Dallas-Houston launch lane, Agility's Digit 5 humanoid, Daimler's eActros 600
expedition and Girteka order, Avery Dennison's Bluetooth label range. Which
technologies an item evidences is the lexicon's decision, not the
collector's.

**The first pass's hand read, for what it is worth.** Over the 131 historical
observations, five were false positives of the same kind (a sponsorship, an
event notice, an award, a SPAC listing, a hire, each matched on a company's
self-description), and a larger group was on topic but not evidence of use
(25 of Circularise's 33 were explainer blog posts). The same pattern will
recur in the weekly flow.

## Known defects, not fixed here

- **Mojibake on Wing's pages** ("Wingâs" for "Wing’s"): a UTF-8 page
  decoded as Latin-1 somewhere between the fetch and the parse. Check
  `Response.text` encoding in `observatory/http.py` and the envelope's JSON
  round-trip.
- Volvo's sitemap gives titles as URL slugs (lower case, no punctuation) and
  month-level dates, set to the 1st of the month.
- Plus's listing titles carry the card's date and category as a prefix and
  an undecoded `&#39;`; on the first pass one Plus item took a date from the
  wrong card (dated 05-07, titled May 26).

## What the weekly yield is

**This is the flow: 19 documents and 3 matched observations in a fortnight's
window, one of them pilot-band, one a passing mention, one a false positive.**
RSS feeds carry about ten items, so a feed newsroom adds a handful a week;
HTML listings carry more, but only in-window items are parsed and only their
pages fetched, so they add the same handful. The list is small (16
newsrooms, most chosen for one or two technologies), and the pilot-band
claims the tracker needs will come from these items accumulating over time.
The yield is judged over a quarter: the reversal condition in STATUS §5 (c)
retires the source if two consecutive quarters yield under 10 matched
observations.
