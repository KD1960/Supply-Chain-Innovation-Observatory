# Nexis Uni hand count: verdict

Date: 2026-09-29. Counts by the owner in Nexis Uni, 2026-09-29, on the sheet
`docs/nexis-hand-count-2026-09-27.md`; tallies in
`docs/audit/nexis-hand-count-2026-09-27.csv` and
`docs/audit/nexis-source-check-2026-09-27.csv` (committed as he saved them).
The pass line was fixed before the count.

## Result

| technology | results | read | pilot-stage | passes (≥ 3) |
|---|---|---|---|---|
| autonomous_trucking | 3,341 | 40 | 4 | yes |
| delivery_drones | 5,754 | 40 | 5 | yes |
| humanoid_logistics | 3,160 | 40 | 6 | yes |
| digital_product_passport | 149 | 40 | 6 | yes |
| gs1_2d | 39 | 39 | 0 | no |

**Content: 4 of 5 pass** (line: 3 of 5).

| source check | |
|---|---|
| titles included with full text | **3 of 12**: Supply Chain Dive, Commercial Carrier Journal, Journal of Commerce |
| not included | DC Velocity, FreightWaves, Logistics Management, Transport Topics, Modern Materials Handling, Supply Chain Management Review, Automotive Logistics, The Loadstar, Robotics 24/7 |

**Sources: fail** (line: 6 of 12).

## Verdict

By the sheet's decision table: **content passes, sources fail. Do not buy
Nexis Data Lab on this evidence.** The next step the table names is to ask
which product carries the trade titles and repeat the check there.

## What the counts say beyond the pass line

- **Pilot-stage news exists in volume.** Four technologies returned 4 to 6
  pilot-stage documents in the first 40 read, from totals in the thousands.
  That is the first measurement in this project to find the pilot band
  anywhere. A yield of 10–15% in the top 40 by relevance suggests dozens per
  technology per quarter.
- **The outlets are aggregators, not trade press.** Every top outlet named is
  a wire or rewrite service: News Bites, MENAFN, Newstex Blogs, Market News
  Publishing, PR Newswire, CE Noticias Financieras, MarketLine, WebNews. The
  pilot-stage hits are therefore mostly company announcements at one remove.
  The `press_release_reprints` and `duplicates_folded` columns were left
  blank, so the share is not measured; the outlet list says it is high.
- **That overlaps with what is now free.** The press-room collector
  (`docs/pressroom-first-run-2026-09-25.md`) reads announcements at the
  source. What the licence would add over it is breadth (every company, not
  16 newsrooms), not independent reporting.
- **One example is out of window.** The autonomous-trucking example headline,
  "Aurora Opens First Commercial-Ready Route for its Planned Driverless Truck
  Launch in Late 2024", describes an event from 2023–24. Either the date
  filter did not hold for that query or an aggregator re-issued an old item
  with a new date. The count of 4 for that technology should be read as at
  most 4.
- **`research_stage` reads as "the rest".** The values (36, 35, 34, 34, 39)
  are 40 minus the pilot-stage count, so the column recorded everything that
  was not pilot-stage, not documents that would give research claims. The
  research-band yield of this content is not measured.
- **gs1_2d: 39 results, none pilot-stage.** The 2D barcode transition is
  covered by GS1's own guidance and little else; it is a lexicon and source
  problem, not a licence problem.

## What would reverse the verdict

A product whose title list holds at least 6 of the 12 trade titles in full
text, with mining and quotation rights in writing, and a sample export on
which the extractor yields at least 10 verified pilot-band claims from 500
documents.

## Options from here, in order of cost

1. **Probe the trade titles' own feeds (free).** Supply Chain Dive, DC
   Velocity, FreightWaves, Logistics Management, Transport Topics and Modern
   Materials Handling publish RSS feeds of headlines and summaries. The
   press-room collector already reads feeds of this shape. Needs a terms-of-use
   and robots check per title before anything is collected, and a probe on
   the same pass line.
2. **Widen the press-room list (free).** The count shows announcements are
   where the pilot band lives. Sixteen newsrooms is small; the aggregator
   results name the companies worth adding.
3. **Ask Factiva for its title list and a trial (no cost to ask).** ASU does
   not subscribe, so this goes through Dow Jones sales. Same sheet, same line.
4. **Ask LexisNexis whether any product carries the nine missing titles.** If
   not, Nexis is closed for this purpose.
