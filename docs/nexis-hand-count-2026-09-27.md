# Nexis Uni hand count: is the trade-press content worth a mining licence?

Date: 2026-09-27. For the owner to run in Nexis Uni (ASU Library access, reading
by hand, which the licence allows). Purpose: measure the content behind Nexis
Data Lab before paying for it. Same pass line as probes 1 and 2
(`docs/trl-probe-2026-09-24.md`, `docs/trl-probe2-2026-09-25.md`). Takes about
half a day. Tally goes in `docs/audit/nexis-hand-count-2026-09-27.csv`.

## The pass line, fixed before looking

A technology **passes** when the search returns at least **3 pilot-stage
documents** in the trailing **8 weeks** (2026-08-02 to 2026-09-27). The content
**passes** when at least **3 of the 5** technologies pass. Anything less: do not
buy on this evidence; try Factiva's equivalent or wait.

Also record the **research-stage** count per technology (documents that would
only give "proposes" or "prototype" claims), because the tracker is thin there
too. It does not count toward the pass line.

## What counts as a pilot-stage document

One document = one article. Count it as pilot-stage only if the text names a
**specific actor doing something with the technology in the real world**: a
pilot at a named site, a first commercial route or customer, an order or
contract, a regulatory approval or permit, or an operation at scale with a
count. Be strict:

| counts | does not count |
|---|---|
| "Kodiak and DTL Transport complete first deliveries under California permit" | "Autonomous trucks could transform freight by 2030" |
| "Walmart expands drone delivery to 34 stores" | "Analyst says drone delivery market to reach $9B" |
| "Agility's Digit begins tote handling at GXO's Spanish Fork DC" | "Humanoid robots: hype or hope?" |
| "EU battery passport rules take effect; Northvolt issues first passports" | "What is a digital product passport? An explainer" |
| "Kroger begins 2D barcode rollout at 200 stores" | "GS1 US publishes 2D barcode guidance" |

A wire story syndicated to five outlets is **one** document. A company's own
press release reprinted by an outlet counts, but note it, because we already
collect press rooms for free.

## Setup in Nexis Uni

1. Advanced Search. Content type: **News**. Date: **2026-08-02 to 2026-09-27**.
2. Language: English. Leave sources at "All" for the first pass; note the
   outlet of every pilot-stage hit so we learn which titles matter.
3. Sort by relevance, read the first **40** results per query. Use the
   headline plus the first paragraph; open the article only when those do not
   decide it. Do not read past 40; the count is per 40, and that is the rule
   for every technology.
4. Group duplicates: same headline or same event on the same day = one.

## The five queries

Paste exactly. Nexis Uni Boolean: quotes for phrases, OR between them, W/5 for
proximity. These are the tracker's own lexicon terms in Nexis syntax.

| technology | query |
|---|---|
| autonomous_trucking | `("autonomous truck" OR "autonomous trucks" OR "autonomous trucking" OR "driverless truck" OR "driverless trucks" OR "driverless trucking")` |
| delivery_drones | `("delivery drone" OR "delivery drones" OR "drone delivery" OR BVLOS)` |
| humanoid_logistics | `("humanoid robot" OR "humanoid robots" OR "general-purpose robot" OR "general purpose robots") AND (warehouse OR logistics OR "distribution center" OR factory)` |
| digital_product_passport | `("digital product passport" OR "digital product passports")` |
| gs1_2d | `("2D barcode" OR "2D barcodes" OR "GS1 Digital Link" OR "Sunrise 2027")` |

The humanoid query carries the supply chain context words because the
watchlist marks that entry `needs_context`; the others do not need it.

## The source check (10 minutes, separate from the count)

In Nexis Uni's source browser, search each title and tick whether it is
included, and whether full text or abstract only:

Supply Chain Dive · DC Velocity · FreightWaves · Logistics Management ·
Transport Topics · Modern Materials Handling · Supply Chain Management Review ·
Automotive Logistics · The Loadstar · Robotics 24/7 · Commercial Carrier Journal
· Journal of Commerce

Fewer than 6 of 12 with full text is a fail on its own, whatever the counts say:
the licence would buy the wrong newspapers.

## Recording

`docs/audit/nexis-hand-count-2026-09-27.csv` has one row per query, columns:
`tech_id, results_total, read, pilot_stage, research_stage, duplicates_folded,
press_release_reprints, top_outlets, example_pilot_headlines, note`. Fill
`results_total` from the result count Nexis shows; `read` is 40 or fewer.
The source check goes in `docs/audit/nexis-source-check-2026-09-27.csv`:
`title, included, full_text, note`.

## Decision

| result | action |
|---|---|
| ≥ 3 of 5 pass and ≥ 6 of 12 titles full text | Ask Nexis for a 500-document sample export and run the extractor on it (about $5); buy one year with a termination clause if the sample yields ≥ 10 verified pilot-band claims |
| content passes, sources fail | Ask which product carries the trade titles; repeat the check there (Factiva) |
| content fails | Do not buy. Record the counts in STATUS §5 as the reversal condition's measurement |

Whatever the result, the counts go into STATUS §5 next to the probe verdicts,
so the decision is a number, not a memory.
