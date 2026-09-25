# Press-room collector: first run, 2026-09-25

The collector built on branch `pressroom` (spec
`docs/superpowers/specs/2026-09-25-pressroom-collector-design.md`) ran once,
for the current week only, against the production database. Nothing else was
fetched and nothing was rebuilt.

    python -m observatory.run --only pressroom --week 2026-W39

Output: `2026-W39: 3 new observations, 48 signals, 48 scored, 25 of 194 rising
candidates`. The run also printed `! failed: edgar` and `~ returned nothing:
federalregister, nsf, usaspending`; those are the week's statuses recorded by
Monday's cron run, which the render reads back, not anything this run did.
The fetch took under two minutes (first raw file 19:44:52 UTC, last 19:46:44).
Before the run the database held 2,382 observations; after, 2,513.

Every number below was read from `data/raw/2026-W39/pressroom/*.json`, from
`parse()` over those files, or from the `observations`, `corpus`,
`source_runs`, `source_attempts` and `raw_fetch` tables, filtered to source
`pressroom`. The run window is 2026-09-14 to 2026-09-27 (the week plus the
seven-day lookback).

## Counts

| | |
|---|---|
| Raw envelopes written | 16, one per newsroom |
| Newsrooms with a non-empty listing | 16 of 16, every one HTTP 200 |
| Notes recorded (403, robots, page errors) | 0 |
| Item pages fetched | 26 |
| Dated documents parsed (`corpus`, source `pressroom`) | 780 |
| of which dated inside the run window | 19 |
| of which dated in 2026-Q3 | 81 |
| Observations inserted | 131, over 129 documents |
| of which dated inside the run window | 3 (all `autonomous_trucking`: Aurora 1, Kodiak 2) |
| of which dated in 2026-Q3 | 21 |
| Source status for 2026-W39 | `ok` |

**By technology:** autonomous_trucking 45, electric_trucks 33,
digital_product_passport 27, delivery_drones 6, piece_picking 4,
minerals_traceability 4, warehouse_robotics 3, blockchain_traceability 3,
hydrogen_trucks 2, microfulfillment 1, last_mile_delivery 1, gs1_2d 1,
green_logistics 1.

**Documents by year of their own date:** 2002 1, 2018 6, 2019 3, 2020 29,
2021 25, 2022 99, 2023 109, 2024 124, 2025 190, 2026 194. A listing page
carries its whole visible history, and `parse()` returns every dated item on
it, not only the ones inside the window; each is filed under its own week.
So this first run is, in effect, a backfill of whatever the listings show.

## Per newsroom

"Documents" is what `parse()` returned (dated items); "in window" is the
subset dated 2026-09-14 to 09-27; "pages" is item pages fetched.

| Newsroom | Kind | Status | Documents | In window | Pages | Observations |
|---|---|---|---:|---:|---:|---:|
| aurora | html | 200 | 10 | 1 | 1 | 6 |
| kodiak | html | 200 | 7 | 3 | 3 | 4 |
| plus | html | 200 | 98 | 0 | 0 | 36 |
| wing | links:/news/ | 200 | 7 | 0 | 7 | 7 |
| agility | html | 200 | 24 | 3 | 3 | 0 |
| figure | html | 200 | 21 | 1 | 1 | 0 |
| apptronik | html | 200 | 13 | 0 | 0 | 0 |
| circularise | html | 200 | 179 | 2 | 2 | 33 |
| averydennison | html | 200 | 48 | 1 | 1 | 0 |
| gs1us | html | 200 | 70 | 1 | 1 | 2 |
| daimlertruck | html | 200 | 9 | 6 | 6 | 0 |
| volvotrucks_us | sitemap | 200 | 200 (of 486 entries; 286 undated, dropped) | 0 | 0 | 35 |
| righthand | html | 200 | 62 | 0 | 0 | 4 |
| berkshiregrey | rss | 200 | 10 | 1 | 1 | 1 |
| symbotic | sitemap | 200 | 12 | 0 | 0 | 1 |
| locus | rss | 200 | 10 | 0 | 0 | 2 |
| **Total** | | | **780** | **19** | **26** | **131** |

Wing's seven pages are all out of window: a `links:` listing is undated, so
its first links are fetched to learn their dates.

## What matched, read by hand

All 131 titles and matched patterns were read. A **false positive** here is
an observation whose document is not about the technology it was matched to:
the pattern hit a company's self-description in a notice about something
else. Five:

| Date | Newsroom | Technology | Title | Why |
|---|---|---|---|---|
| 2026-07-29 | aurora | autonomous_trucking | Arrow McLaren Adds Autonomous Trucking Pioneer Aurora as Official Partner | a racing sponsorship; the match is Aurora's descriptor |
| 2026-09-23 | aurora | autonomous_trucking | Aurora to Host Analyst & Investor Day on September 23, 2026 | an event notice; "autonomous trucking industry" in its first paragraph |
| 2024-12-04 | plus | autonomous_trucking | Driverless Truck AI Technology Leader Plus Named to the Inc. 2024 Best in Business List | an award list; descriptor |
| 2026-09-03 | plus | autonomous_trucking | PlusAI ... to Become Publicly Listed Through Business Combination with Texas Ventures Acquisition III Corp | a SPAC listing; descriptor |
| 2026-09-04 | wing | delivery_drones | Building the future: Wing's technical leadership | an engineering hire; "global leader in residential drone delivery" |

One of the three in-window observations (the Aurora investor-day notice) is
one of these.

**On topic but not evidence of use.** A larger group is about the right
technology and says nothing about a pilot, order or deployment: 25 of
Circularise's 33 are explainer blog posts (the other 8 name a partner or a
trial: LyondellBasell, ScaleAQ, Teijin, Samsonite, Honda and three more);
12 of Plus's 36 carry the listing's own "Events", "Insights" or "In the News"
label (a state-fair weekend, a conference, a Red Bull stunt, a podcast);
Locus's 2, Symbotic's 1 and Berkshire Grey's 1 are explainers or an ebook.
The count instrument counts these; the TRL extraction should read them as
`proposes` at most, or produce no claim.

**Other defects seen while reading:**

- Volvo's sitemap gives titles as URL slugs (lower case, no punctuation) and
  month-level dates, set to the 1st of the month.
- Plus's titles carry the listing's date and category as a prefix ("August
  22, 2023 Press Releases ...") and undecoded `&#39;`. One Plus row is dated
  2026-05-07 while its title says May 26, 2026: a wrong date from the card.
- Wing's pages show mojibake (`Wingâs` for `Wing’s`): UTF-8 read as Latin-1.
- Wing and Papa Johns' drone-delivery pilot matched `last_mile_delivery`
  only; its title says "delivery by drone", which the `delivery_drones`
  patterns do not cover.
- Missed in window, for the record: Kodiak's "Dallas-Houston As Long-Haul
  Driverless Launch Lane", Agility's "Digit 5 Humanoid Robot", Daimler's
  eActros 600 expedition. None matched; the lexicon, not the collector,
  decides that.

## What a normal week will yield

This run's 131 is a one-off: listings carry years of history, and every dated
item on them was filed under its own week. From next week the same items are
already in the database (`INSERT OR IGNORE` on the URL-derived id), so the
weekly yield is what is new inside the window, which this run measured at 19
documents and 3 matched observations over fourteen days.

RSS feeds carry about 10 items (Berkshire Grey 10, Locus 10), so a feed
newsroom adds at most a handful a week; HTML listings carry more (up to 179
for Circularise), but only the pages of in-window items are fetched, so their
weekly contribution is also the handful dated in the window, matched mostly
on the title and first paragraph.

## Concerns for the owner

- **The `corpus` table will re-count the same documents every week.** It
  records every document `parse()` returns, per run week, and the listings
  return the same 780 each time. A rate that divides by the press corpus
  will be wrong until `parse()` keeps only in-window items or the corpus
  write deduplicates. Not fixed here.
- **128 of the 131 observations sit in weeks where `pressroom` has no
  `source_runs` row**, so they never reach a weekly signal (the hole rule),
  but they do count in the §2 total, and a 2026-Q3 TRL read would have the 21
  dated in Q3 to read (18 of them from before the run window).
- Five false positives in 131 (about 4%) is a hand read by the assistant,
  not an audit.
