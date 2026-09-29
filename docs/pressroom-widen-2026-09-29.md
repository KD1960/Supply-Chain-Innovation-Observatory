# Press rooms widened, 2026-09-29

The owner's instruction was "widen pressrooms.yaml". The press-room collector
(`observatory/collectors/pressroom.py`) read 16 newsrooms. It now reads **60**:
the 16 unchanged and first, plus 44 found by the discovery below. This note
covers the candidates, the permission check, one change to the collector, and
the first weekly yield measured against production data.

## Discovery, permission first

Script: `docs/experiments/trl/widen_pressrooms.py`. Raw responses and one
decision file per candidate are in `data/trl/widen/` (gitignored).

- **Candidates:** 124. These are the brief's list plus seven warehouse-automation
  vendors I added by hand (Ambi, Brightpick, Geek+, Dematic, KNAPP, Swisslog, Hai
  Robotics). The candidates cover all 24 tracked technologies and 16 user
  firms and logistics operators. Boston Dynamics and Einride each appear once,
  under all the technologies they were chosen for.
- **Fetch path:** every request goes through the collector's own
  `PressroomCollector._get`. That means redirects are followed by hand with
  robots.txt checked on every hop, each host gets its own limiter at least 2 s
  apart, and there is one retry. A subclass honours Crawl-delay in full instead
  of capping it at 30 s. Eleven hosts set a Crawl-delay: 10 s on nine of them
  (Amazon, Ivalua, KNAPP, Outrider, NFI, Ryder, Kroger, Cognex, Lineage), 5 s
  on GXO, and 1 s on o9, where the 2 s floor applies. None was over 30 s, so
  the cap would not have bound either.
- **Order per candidate:**
  1. robots.txt.
  2. The known newsroom URL (the next one is tried only after a 404).
  3. A feed the listing advertises.
  4. `/feed`, `/rss`, `/news/rss`, and `/sitemap.xml`. A sitemap index is
     followed only to a news, press or post child.
  5. `links:<path>` last, with at most 3 item pages.
- **Acceptance:** the collector's own `items_for` finds at least 3 dated items,
  at least one of them dated after 2025-09-29.
- **Budget:** 6 requests per candidate, counting robots, retries and redirect
  hops. The 7th request raises an error.
- **Restarts:** every response is saved as it arrives and replayed on a restart.
- **Totals:** 509 requests. The full run took 1,811 s, plus about 20 s for a
  three-candidate trial run first. One candidate went over budget: Symbio used
  7 requests, because a redirect hop that `requests` followed itself was
  counted after the budget check.
- **Refusals:** no 403, captcha or JavaScript shell was retried or evaded. No
  terms pages were fetched. No listing showed a notice against automated access
  (the script searches each listing's visible text; it found none to hand-read).

### Hand calls after reading the accepted listings

Five candidates passed the automatic test but were rejected after I read their
items:

- **Four listings of third-party coverage.** Boston Dynamics (3 dated items, 0
  on its own site), Bright Machines (5, 0), Windrose (`/news` redirects to
  `/about-us`: 5, 0) and Zeem (49, 2) list press coverage on other sites
  (Reuters, Forbes, FreightWaves, fleetowner.com), not their own releases.
- **DB Schenker.** Its press page redirects to the DSV homepage. `dsv` is
  kept.

Brightpick (3 of 25 dated items on its own site), Manna (8 of 17) and o9 (6 of
12) were kept. IonQ (12 of 18) and Kinaxis (5 of 7) have some off-site links
too.

### A change to the collector this made necessary

A listing that links coverage on other sites made the weekly run fetch those
sites' pages when they fell in the window: WSJ, CNBC, Forbes, and FreightWaves,
which probe 3 rated amber. Only the newsroom's own robots.txt had ever been
checked for them. This was already possible before today: Plus's listing links
FreightWaves.

`fetch_raw` now fetches item pages only on the newsroom's own site. "Own site"
means the last two host labels, or three under a `co.uk`-style suffix, so
`ir.aurora.tech` counts as the same site as `aurora.tech`. Off-site items stay
as documents built from the listing's own text, and the envelope notes how many
item pages were skipped. Tests:

- `test_item_pages_on_another_site_are_not_fetched`
- `test_site_is_the_registrable_domain_approximately`

One existing test, whose item pages sat on another host, moved them to a
subdomain of the listing's host.

## Counts

| | |
|---|---|
| Candidates | 124 |
| Accepted | 44 (22 rss, 22 html) |
| Rejected | 80 |
| Known page 404, then no feed and no news sitemap | 22 |
| No listing within 6 requests (mostly redirect chains) | 14 |
| Listing loads but yields no dated items (script-rendered or undated) | 14 |
| Nothing dated in the last 12 months (ISEE, EON, Zebra) | 3 |
| 403 (PACCAR, Kenworth, Coupa, Oracle, Markforged, Nokia, UPS, XPO) | 8 |
| robots.txt unavailable, network error (Serve, Voltera, Manhattan, Identiv, Divergent, DHL) | 6 |
| Captcha (Matternet, Peterbilt, Hyundai, Stratasys, Ryder) | 5 |
| robots.txt disallows (SAP News: `User-agent: *` / `Disallow: /`) | 1 |
| JavaScript shell (Verity, 6 visible characters) | 1 |
| Parked domain (Haddy) | 1 |
| Rejected by hand (above) | 5 |
| Newsrooms now | **60** |

A 404 at a guessed URL is a weak rejection. Dexterity, Waabi, Einride, Wiliot,
Dexory, Keelvar and others almost certainly have a newsroom somewhere else on
their site. They are listed as not reachable at the URL tried, not as having
no newsroom.

### Coverage of the 24 tracked technologies (by `chosen_for`)

- **No newsroom: battery_free_iot, microfactories.**
- **One newsroom:** additive_spares (SPEE3D), autonomous_yard (Outrider),
  cv_inspection (Vimaan), gs1_2d (GS1 US), private_5g_warehouse (Ericsson),
  smart_labels (Checkpoint).
- **Two or more:** all the other 16.
- **User firms (7):** Amazon, GXO, FedEx, Maersk, Penske Logistics, NFI, DSV.

## First yield, 2026-W40

### What a second W40 fetch does

`main` does not consult `collectors_needing_fetch`, so a `--week` run always
fetches and does not refuse. `fetch_week` writes envelopes `000.json` onwards,
so the 16 files written by Monday's cron were overwritten in the same order,
and 44 new files were added after them. Before the run, the 16 were copied to
`data/backups/raw-2026-W40-pressroom-before-widen/` (verified identical), and
the database was copied to
`data/backups/observatory-before-widen-2026-09-29.db`.

Other effects:

- Observations are `INSERT OR IGNORE`.
- `record_corpus` replaces the W40 pressroom rows.
- Only the pressroom signals are recomputed.
- The run renders to the worktree's own `output/`.

No `--rebuild` and no `--backfill` was run.

    python -m observatory.run --only pressroom --week 2026-W40

The window was 2026-09-21 to 2026-10-04. Every number below is read from
`data/raw/2026-W40/pressroom/*.json`, from `parse()` over those files, or from
the `observations`, `corpus` and `source_runs` tables.

| | |
|---|---|
| Raw envelopes | 60 |
| Newsrooms with a listing | 60 of 60 |
| Notes (robots, 403, errors, off-site pages) | 0 |
| Item pages fetched | 102 |
| Documents (`corpus`, pressroom, 2026-W40) | 91 (13 before the run), 18 from the original 16 and 73 from the new 44 |
| Newsrooms with an in-window document | 27 of 60 (20 of the 44 new) |
| New observations | 10: 6 filed under 2026-W40, 4 under 2026-W39 by their document dates |
| Observations by technology | erp 5, agentic_procurement 1, humanoid_logistics 1, robotic_manufacturing 1, digital_product_passport 1, minerals_traceability 1 |
| Observations by vendor (all new newsrooms) | jaggaer 6, nvidia 2, circulor 1, minespider 1; none from the original 16 |
| Source status, pressroom 2026-W40 | `ok` (was `empty`) |
| Observations table | 2,409 → 2,419 |
| Wall time | 9 min 23 s for the command; raw files 18:10:32 to 18:19:48 UTC, 9 min 16 s. The 16-newsroom run took under 2 min. |

### Every new observation, read by hand

| Date | Vendor | Title | Tech | Reading |
|---|---|---|---|---|
| 09-25, 09-28 (×5) | jaggaer | "GEP SMART vs Zycus (2026)…", "Basware vs Workday…", "Oracle Procurement Cloud vs Tipalti…", "Oracle… vs Workday…", "GEP SMART vs Oracle…" | erp | **false positive**: vendor-comparison articles on Jaggaer's blog feed, matched on `ERP` |
| 09-28 | jaggaer | "GEP SMART vs Tipalti (2026)…" | agentic_procurement | **false positive**: same kind of article; "agentic AI" appears in the comparison |
| 09-21 | nvidia | "Why Deploying Physical AI at Scale Demands Safety at Every Layer" | humanoid_logistics, robotic_manufacturing | passing mention ×2: an essay, no deployment |
| 09-23 | circulor | "The EU Digital Product Passport (DPP) registry is live: what to do now" | digital_product_passport | passing mention: a regulatory explainer |
| 09-29 | minespider | "AI and the Digital Battery Passport: Where It Can Reduce Manual Work" | minerals_traceability | passing mention: an explainer |

**Pilot-stage: 0 of 10. False positives: 6. Passing mentions: 4.**

Some in-window documents matched nothing but are the kind of item the tracker
wants. KNAPP will supply automation for Kesko's new logistics centre (an
order). GXO deployed a labour-management system. Maersk opened a 72,000 m²
warehouse and extended its PUMA partnership. IonQ's Superion was selected by
FIU. None of these is about a tracked technology in the lexicon's terms.
Deciding what an item evidences is the matcher's job, not the collector's.

## What the wider list costs, and what it yields

- **Time.** The weekly pressroom fetch goes from under 2 minutes to about
  9 minutes. Most of that is item pages: 102 against 26 on the first run.
- **Noise.** The new feeds are mostly corporate blogs. Amazon, Toyota, NVIDIA,
  FedEx and Ericsson publish entertainment, motorsport, consumer and
  investor-relations items. Jaggaer's feed is vendor-comparison articles, and
  it produced 6 of the 10 observations, all of them false positives.
  Replacing `jaggaer` with its press-release page, or dropping it, is the
  obvious first cut. That is the owner's decision, and it was not made here.
- **Yield.** One week is one draw. Taken literally, 0 pilot-stage in 10 does
  not move the STATUS §5 (c) reversal condition, which is under 10 matched
  observations a quarter for two quarters. On this week's flow the source now
  clears 10 a quarter on count alone, mostly on false positives. The pilot-band
  question is about quality, and a quarter of weekly runs will answer it
  better than this one run can.

## Candidate table

Requests counts every request made for the candidate: robots, retries and
redirect hops. Dated items and Newest are for the accepted kind's listing, as
`items_for` reads it.

| Vendor | Chosen for | Outcome | Kind | Dated items | Newest | Requests | Reason if rejected |
|---|---|---|---|---:|---|---:|---|
| Dexterity (`dexterity`) | piece_picking | rejected |  |  |  | 6 | no listing found within 6 requests |
| Plus One Robotics (`plusone`) | piece_picking | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Mujin (`mujin`) | piece_picking | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Nimble Robotics (`nimble`) | piece_picking | rejected |  |  |  | 6 | no listing found within 6 requests |
| OSARO (`osaro`) | piece_picking | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Pickle Robot (`pickle`) | piece_picking | rejected |  |  |  | 5 | listing loads but yields no dated items |
| Boston Dynamics (`bostondynamics`) | piece_picking, humanoid_logistics | rejected |  |  |  | 2 | listing is third-party coverage (3 dated items, 0 on its own site) |
| Ambi Robotics (`ambi`) | piece_picking | accepted | rss | 37 | 2026-09-17 | 4 |  |
| Brightpick (`brightpick`) | piece_picking, microfulfillment | accepted | html | 25 | 2026-09-16 | 2 |  |
| 1X (`1x`) | humanoid_logistics | rejected |  |  |  | 6 | listing loads but yields no dated items |
| Sanctuary AI (`sanctuary`) | humanoid_logistics | accepted | rss | 10 | 2026-06-17 | 6 |  |
| Unitree (`unitree`) | humanoid_logistics | accepted | html | 11 | 2026-08-05 | 3 |  |
| Outrider (`outrider`) | autonomous_yard | accepted | rss | 10 | 2025-11-20 | 4 |  |
| Fernride (`fernride`) | autonomous_yard | rejected |  |  |  | 6 | listing loads but yields no dated items |
| ISEE (`isee`) | autonomous_yard | rejected |  |  |  | 5 | no item in the last 12 months (16 dated, newest 2025-04-29) |
| Starship Technologies (`starship`) | sidewalk_delivery_robots | accepted | html | 9 | 2026-04-28 | 2 |  |
| Serve Robotics (`serve`) | sidewalk_delivery_robots | rejected |  |  |  | 2 | robots unavailable (network error) |
| Coco (`coco`) | sidewalk_delivery_robots | accepted | html | 6 | 2026-04-28 | 2 |  |
| Kiwibot (`kiwibot`) | sidewalk_delivery_robots | rejected |  |  |  | 6 | no listing found within 6 requests |
| Matternet (`matternet`) | delivery_drones | rejected |  |  |  | 5 | captcha |
| DroneUp (`droneup`) | delivery_drones | accepted | rss | 20 | 2026-07-28 | 3 |  |
| Manna (`manna`) | delivery_drones | accepted | html | 17 | 2026-07-08 | 2 |  |
| Amazon (`amazon`) | delivery_drones, user_firm | accepted | rss | 10 | 2026-09-29 | 3 |  |
| Walmart (`walmart`) | delivery_drones, user_firm | rejected |  |  |  | 3 | listing loads but yields no dated items |
| Waabi (`waabi`) | autonomous_trucking | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Torc Robotics (`torc`) | autonomous_trucking | accepted | rss | 10 | 2026-09-03 | 4 |  |
| Gatik (`gatik`) | autonomous_trucking | rejected |  |  |  | 6 | no listing found within 6 requests |
| Bot Auto (`botauto`) | autonomous_trucking | accepted | html | 50 | 2026-09-18 | 2 |  |
| Volvo Autonomous Solutions (`volvoautonomous`) | autonomous_trucking | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Einride (`einride`) | autonomous_trucking, electric_trucks | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| PACCAR (`paccar`) | electric_trucks | rejected |  |  |  | 2 | 403 |
| Kenworth (`kenworth`) | electric_trucks | rejected |  |  |  | 2 | 403 |
| Peterbilt (`peterbilt`) | electric_trucks | rejected |  |  |  | 3 | captcha |
| Freightliner / Daimler Truck North America (`freightliner`) | electric_trucks | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Windrose (`windrose`) | electric_trucks | rejected |  |  |  | 3 | /news redirects to /about-us, a list of third-party coverage (5 dated, 0 on its own site) |
| Harbinger (`harbinger`) | electric_trucks | accepted | rss | 10 | 2026-07-31 | 6 |  |
| Hyundai Motor America (`hyundai`) | hydrogen_trucks | rejected |  |  |  | 2 | captcha |
| Hyundai HTWO (`htwo`) | hydrogen_trucks | rejected |  |  |  | 6 | no listing found within 6 requests |
| Toyota (US pressroom) (`toyota`) | hydrogen_trucks | accepted | rss | 20 | 2026-09-28 | 4 |  |
| Symbio (`symbio`) | hydrogen_trucks | rejected |  |  |  | 7 | no listing found within 6 requests |
| WattEV (`wattev`) | freight_charging | accepted | html | 6 | 2026-06-30 | 4 |  |
| Greenlane (`greenlane`) | freight_charging | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| TeraWatt Infrastructure (`terawatt`) | freight_charging | accepted | html | 8 | 2026-04-09 | 5 |  |
| Voltera (`voltera`) | freight_charging | rejected |  |  |  | 2 | robots unavailable (network error) |
| Forum Mobility (`forummobility`) | freight_charging | accepted | rss | 10 | 2026-09-11 | 6 |  |
| Zeem Solutions (`zeem`) | freight_charging | rejected |  |  |  | 3 | listing is third-party coverage (49 dated items, 2 on its own site) |
| Coupa (`coupa`) | agentic_procurement | rejected |  |  |  | 2 | 403 |
| Zip (`zip`) | agentic_procurement | rejected |  |  |  | 6 | no listing found within 6 requests |
| Jaggaer (`jaggaer`) | agentic_procurement | accepted | rss | 10 | 2026-09-29 | 3 |  |
| Ivalua (`ivalua`) | agentic_procurement | accepted | rss | 9 | 2026-09-28 | 4 |  |
| GEP (`gep`) | agentic_procurement | accepted | html | 15 | 2026-09-24 | 3 |  |
| Keelvar (`keelvar`) | agentic_procurement | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Pactum (`pactum`) | agentic_procurement | accepted | rss | 48 | 2026-09-10 | 4 |  |
| Globality (`globality`) | agentic_procurement | accepted | rss | 10 | 2026-06-09 | 4 |  |
| Kinaxis (`kinaxis`) | supply_chain_digital_twin, genai_planning, supply_chain_llm | accepted | html | 7 | 2026-09-15 | 2 |  |
| o9 Solutions (`o9`) | supply_chain_digital_twin, genai_planning, supply_chain_llm | accepted | html | 12 | 2026-09-22 | 3 |  |
| Blue Yonder (`blueyonder`) | supply_chain_digital_twin, genai_planning, supply_chain_llm | rejected |  |  |  | 6 | no listing found within 6 requests |
| Manhattan Associates (`manhattan`) | genai_planning, supply_chain_llm | rejected |  |  |  | 2 | robots unavailable (network error) |
| SAP News (`sap`) | supply_chain_digital_twin, genai_planning, supply_chain_llm | rejected |  |  |  | 1 | robots.txt disallows / |
| Oracle (`oracle`) | genai_planning, supply_chain_llm | rejected |  |  |  | 2 | 403 |
| NVIDIA blog (`nvidia`) | supply_chain_digital_twin | accepted | rss | 18 | 2026-09-24 | 3 |  |
| Circulor (`circulor`) | digital_product_passport, minerals_traceability | accepted | html | 126 | 2026-09-23 | 6 |  |
| Kezzler (`kezzler`) | digital_product_passport | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| EON (`eon`) | digital_product_passport | rejected |  |  |  | 6 | no item in the last 12 months (55 dated, newest 2024-09-19) |
| Spherity (`spherity`) | digital_product_passport | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| RCS Global (`rcsglobal`) | minerals_traceability | rejected |  |  |  | 6 | no listing found within 6 requests |
| Minespider (`minespider`) | minerals_traceability, digital_product_passport | accepted | html | 24 | 2026-09-29 | 2 |  |
| Everledger (`everledger`) | minerals_traceability | rejected |  |  |  | 4 | listing loads but yields no dated items |
| Digimarc (`digimarc`) | gs1_2d | rejected |  |  |  | 3 | listing loads but yields no dated items |
| Zebra Technologies (`zebra`) | gs1_2d | rejected |  |  |  | 3 | no item in the last 12 months (1 dated, newest 2023-12-31) |
| Wiliot (`wiliot`) | battery_free_iot, smart_labels | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Everactive (`everactive`) | battery_free_iot | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Atmosic (`atmosic`) | battery_free_iot | rejected |  |  |  | 4 | listing loads but yields no dated items |
| Identiv (`identiv`) | smart_labels, battery_free_iot | rejected |  |  |  | 2 | robots unavailable (network error) |
| Checkpoint Systems (`checkpoint`) | smart_labels | accepted | rss | 10 | 2026-09-24 | 3 |  |
| Wurth Additive Group (`wurthadditive`) | additive_spares | rejected |  |  |  | 6 | no listing found within 6 requests |
| Markforged (`markforged`) | additive_spares | rejected |  |  |  | 2 | 403 |
| Stratasys (`stratasys`) | additive_spares | rejected |  |  |  | 2 | captcha |
| EOS (`eos`) | additive_spares | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| SPEE3D (`spee3d`) | additive_spares | accepted | rss | 12 | 2026-09-08 | 4 |  |
| Haddy (`haddy`) | microfactories | rejected |  |  |  | 3 | domain parked (redirects to ww16.haddy.com, robots disallows) |
| Divergent (`divergent`) | microfactories | rejected |  |  |  | 2 | robots unavailable (network error) |
| Bright Machines (`brightmachines`) | microfactories | rejected |  |  |  | 3 | listing is third-party coverage (5 dated items, 0 on its own site) |
| AutoStore (`autostore`) | microfulfillment | accepted | rss | 10 | 2026-09-07 | 3 |  |
| Ocado Group (`ocado`) | microfulfillment | accepted | html | 11 | 2026-08-25 | 3 |  |
| Fabric (`fabric`) | microfulfillment | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Exotec (`exotec`) | microfulfillment | rejected |  |  |  | 4 | listing loads but yields no dated items |
| Attabotics (`attabotics`) | microfulfillment | rejected |  |  |  | 6 | listing loads but yields no dated items |
| Cognex (`cognex`) | cv_inspection | rejected |  |  |  | 6 | no listing found within 6 requests |
| Kargo (`kargo`) | cv_inspection | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Gather AI (`gatherai`) | cv_inspection | rejected |  |  |  | 6 | no listing found within 6 requests |
| Vimaan (`vimaan`) | cv_inspection | accepted | rss | 10 | 2026-09-21 | 4 |  |
| Dexory (`dexory`) | cv_inspection | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Verity (`verity`) | cv_inspection | rejected |  |  |  | 5 | JavaScript shell (6 visible characters) |
| Celona (`celona`) | private_5g_warehouse | rejected |  |  |  | 6 | no listing found within 6 requests |
| Nokia (`nokia`) | private_5g_warehouse | rejected |  |  |  | 2 | 403 |
| Ericsson (`ericsson`) | private_5g_warehouse | accepted | html | 10 | 2026-09-29 | 2 |  |
| Betacom (`betacom`) | private_5g_warehouse | rejected |  |  |  | 6 | listing loads but yields no dated items |
| D-Wave (`dwave`) | quantum_logistics | accepted | html | 6 | 2026-09-21 | 2 |  |
| IonQ (`ionq`) | quantum_logistics | accepted | html | 18 | 2026-09-24 | 2 |  |
| Quantinuum (`quantinuum`) | quantum_logistics | rejected |  |  |  | 3 | listing loads but yields no dated items |
| Pasqal (`pasqal`) | quantum_logistics | accepted | html | 9 | 2026-09-28 | 3 |  |
| Q-CTRL (`qctrl`) | quantum_logistics | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Geek+ (`geekplus`) | piece_picking, microfulfillment | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Dematic (`dematic`) | microfulfillment, piece_picking | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| KNAPP (`knapp`) | microfulfillment, piece_picking | accepted | rss | 10 | 2026-09-24 | 4 |  |
| Swisslog (`swisslog`) | microfulfillment, piece_picking | rejected |  |  |  | 6 | listing loads but yields no dated items |
| Hai Robotics (`hairobotics`) | microfulfillment | accepted | html | 10 | 2026-09-23 | 2 |  |
| DHL Group (`dhl`) | user_firm | rejected |  |  |  | 2 | robots unavailable (network error) |
| GXO (`gxo`) | user_firm | accepted | html | 12 | 2026-09-29 | 3 |  |
| UPS (`ups`) | user_firm | rejected |  |  |  | 2 | 403 |
| FedEx (`fedex`) | user_firm | accepted | rss | 8 | 2026-09-27 | 3 |  |
| Maersk (`maersk`) | user_firm | accepted | html | 18 | 2026-09-29 | 2 |  |
| Ryder (`ryder`) | user_firm | rejected |  |  |  | 3 | captcha |
| Penske Logistics (`penske`) | user_firm | accepted | rss | 30 | 2026-06-16 | 5 |  |
| J.B. Hunt (`jbhunt`) | user_firm | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Schneider (`schneider`) | user_firm | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| NFI (`nfi`) | user_firm | accepted | rss | 10 | 2026-04-09 | 4 |  |
| Kroger (`kroger`) | user_firm | rejected |  |  |  | 4 | listing loads but yields no dated items |
| DB Schenker (`dbschenker`) | user_firm | rejected |  |  |  | 4 | press page redirects to the DSV homepage (Schenker is part of DSV); covered by dsv |
| DSV (`dsv`) | user_firm | accepted | html | 3 | 2026-09-01 | 1 |  |
| XPO (`xpo`) | user_firm | rejected |  |  |  | 2 | 403 |
| Werner (`werner`) | user_firm | rejected |  |  |  | 5 | listing loads but yields no dated items |
| Lineage (`lineage`) | user_firm | rejected |  |  |  | 6 | no listing found within 6 requests |
