# Press rooms widened, 2026-09-29

The owner's instruction was "widen pressrooms.yaml". The press-room collector
(`observatory/collectors/pressroom.py`) read 16 newsrooms and now reads **52**:
the original 16, unchanged and first, plus 36 new ones.

The rule for staying on the list, set by the controller at review: **a
newsroom stays only if its listing is mostly the company's own releases on its
own site.** Site-wide blogs, SEO or marketing feeds, and listings dominated by
third-party coverage are out. Every number below was observed. Where a
decision was made by hand, the note says so.

## First pass, and what the review changed

The first pass, committed as 0b4a59b, accepted 44 candidates (60 newsrooms in
all) and ran `--only pressroom --week 2026-W40`. It produced 91 documents and
10 observations, none of them pilot-stage. Six of the ten were false
positives, all from Jaggaer's `/feed`, which turned out to be its blog of
vendor-comparison articles.

The review (fix round 1) changed the following:

- **Membership rule applied (R1).** Eight newsrooms moved to `not_reachable`:
  jaggaer, brightpick, checkpoint, pactum, ambi, vimaan, nfi and amazon.
  Ivalua was re-pointed from its blog feed to its html newsroom.
- **Off-site items are not documents (R2).** `parse` drops any item whose URL
  is not on the newsroom's own site. That is the same rule the fetch uses:
  press coverage under a vendor's name is not the vendor's release.
- **Item redirects stay on site (R3).** An item page whose redirect leaves the
  newsroom's site stops with the note "redirect leaves the newsroom's site:
  <url>". The listing itself may still redirect across hosts; that is how
  `resolved_url` is set.
- **Corrected reasons (R4).** Five rejections recorded as "captcha" were
  wrong: the script had read a form's reCAPTCHA settings as a challenge page.
  - Peterbilt, Stratasys, Ryder: JavaScript-rendered listings with no dated
    items in the HTML.
  - Matternet: `/news` redirects to the homepage.
  - Hyundai: a JavaScript shell, 7 visible characters.

  The script's test now needs a challenge marker ("Just a moment", "Enable
  JavaScript and cookies", `cf-chl`, "Attention Required") *and* under 400
  visible characters. Four redirect reasons were also made specific:
  rcsglobal, kiwibot, gatik and dexterity.
- **Cron protection (R5).**
  - A server asking for more than two minutes (`Retry-After` over 120 s)
    ends that request for the week: `http` raises at once, keeping the status,
    without sleeping or asking again. A wait of 120 s or less is honoured in
    full, as before. (Fix round 2; fix round 1 had capped the wait at 120 s and
    retried, which would have contacted the server before its stated time.)
  - The listing fetch gets one retry, like robots.txt and item pages.
  - `PressroomCollector.max_seconds = 2700` (45 min) is measured on the
    injected clock. A newsroom not reached in time gets an envelope with an
    empty listing and the note "time budget exhausted; not fetched this run".
    The source still fails only if no newsroom produced a listing. The same
    check runs inside a newsroom's item-page loop (fix round 2): past the
    budget, the remaining pages are skipped with the note "time budget
    exhausted; N item pages not fetched".
- **Production data re-derived without fetching (below).**

## Discovery, permission first

Script: `docs/experiments/trl/widen_pressrooms.py`. Raw responses and one
decision file per candidate are kept in `data/trl/widen/` (gitignored). The
hand calls are recorded in the script as `HAND_REJECT` and `HAND_REPOINT`, and
`--report` prints the table below from them.

**Candidates.** 124 in all:

- the brief's list, plus seven warehouse-automation vendors added by hand
  (Ambi, Brightpick, Geek+, Dematic, KNAPP, Swisslog, Hai Robotics);
- they cover all 24 tracked technologies and 16 user firms and logistics
  operators;
- Boston Dynamics and Einride appear once each, under all the technologies
  they were chosen for.

**Fetch path.** Every request goes through the collector's own
`PressroomCollector._get`:

- redirects are followed by hand, and robots.txt is checked for every hop;
- each host gets its own limiter, with requests at least 2 s apart;
- there is one retry;
- a subclass honours Crawl-delay in full rather than capping it at 30 s.

Eleven hosts set a Crawl-delay:

- 10 s: Amazon, Ivalua, KNAPP, Outrider, NFI, Ryder, Kroger, Cognex and
  Lineage;
- 5 s: GXO;
- 1 s: o9, where the 2 s floor applies.

None was over 30 s.

**Order per candidate.**

1. robots.txt.
2. The known newsroom URL. The next known URL is tried only after a 404.
3. A feed that the listing advertises.
4. `/feed`, `/rss`, `/news/rss`, then `/sitemap.xml`. From a sitemap index,
   only a news, press or post child is followed.
5. `links:<path>`, last, with at most 3 item pages.

**Automatic acceptance.** A candidate passed if the collector's own
`items_for` found at least 3 dated items, at least one of them dated after
2025-09-29.

**Budget.** At most 6 requests per candidate, counting robots.txt, retries
and redirect hops. A 7th request raises.

**What was spent.** 509 requests: 1,811 s for the full run, plus about 20 s
for a three-candidate trial run first. One candidate went over budget: Symbio
used 7, because a redirect hop that `requests` followed itself was counted
after the budget check.

**What was not done.**

- No 403, captcha or JavaScript shell was retried or evaded.
- No terms pages were fetched.
- No listing showed a notice against automated access. The script searches
  each listing's visible text for one, and found none to read by hand.

### Hand calls under the membership rule

Automatic acceptance was necessary but not sufficient. I read the items of
every accepted listing. Thirteen candidates were rejected by hand.

**Third-party coverage, not releases:**

| Candidate | Dated items | Of those on its own site |
|---|---:|---:|
| Boston Dynamics | 3 | 0 |
| Bright Machines | 5 | 0 |
| Windrose (`/news` redirects to `/about-us`) | 5 | 0 |
| Zeem | 49 | 2 |
| Brightpick (items in the last 12 months) | 23 | 3 |

**Site blogs or marketing feeds (6):**

- Jaggaer: the newsroom is a 404, and `/feed` is vendor-comparison posts.
- Checkpoint: the advertised feed is `/blog/`.
- Pactum: `/news/` redirects to a blog tag.
- Ambi: 35 of 37 items are under `/blog/`.
- Vimaan: the feed is its resources section, including reposted trade
  coverage.
- NFI: the feed is about-page insight posts.

**Relevance (1):** Amazon's feed is a corporate news feed across all of Amazon
(entertainment, sellers, devices, climate). Its 10 items roll over in under a
week, and none matched. This is a hand call on relevance, not a blog finding.
Reversal condition: an operations-only feed.

**Another firm's page:** DB Schenker's press page redirects to the DSV
homepage. `dsv` is kept.

**Re-pointed:** Ivalua's advertised feed is its site blog. Its html newsroom
at `/company/newsroom/` (the redirect target of the known URL) passed on its
own: 13 dated items, the newest dated 2026-09-25.

**Watch.** These were kept, but their listings mix releases with other
material:

- NVIDIA: the blog feed, the only source for supply_chain_digital_twin beyond
  Kinaxis and o9.
- Toyota: the corporate latest-news feed, which includes motorsport.
- Maersk: carrier advisories mixed in with releases.
- Ericsson: investor notices.
- FedEx: a partial feed.
- o9: one off-site link.
- Outrider: newest item 2025-11-20.
- DSV: 3 dated items.
- WattEV: WattEV's listing on its parent's site, `wattsystems.com`.
- Circulor: its `/resources` listing, which mixes releases with blog posts.
- Minespider: its `/blog`.

NVIDIA, Circulor and Minespider are blog-type feeds kept under watch. **All
four new observations this week came from them** (below).

### The collector's same-site rule

A listing that links coverage on other sites made the weekly run fetch those
sites' pages when they fell in the window: WSJ, CNBC, Forbes, and
FreightWaves, which probe 3 rated amber. **The item host's robots.txt was
always checked, per hop. Its terms were not, and third-party coverage is not
the vendor's release in any case.** Plus's listing already linked
FreightWaves before this widening.

The collector now does three things:

- It fetches item pages only on the newsroom's own site.
- It drops off-site items from `parse`, so they are neither documents nor
  counted in the window.
- It stops an item's redirect chain when a hop leaves the site.

"Own site" means the last two host labels, or the last three under a
`co.uk`-style suffix, so `ir.aurora.tech` counts as `aurora.tech`. When
off-site item pages are skipped, the envelope notes "N item pages on other
sites not fetched". For a `links:` kind those are linked pages, not
necessarily in-window ones.

## Counts

| | |
|---|---|
| Candidates | 124 |
| Accepted | 36 (22 html, 14 rss) |
| Rejected | 88 |
| Known page 404, then no feed and no news sitemap | 22 |
| Listing loads but yields no dated items | 14 |
| JavaScript-rendered listing, no dated items in the HTML (Peterbilt, Stratasys, Ryder) | 3 |
| No listing within 6 requests (redirect chains; Dexterity, Kiwibot and Gatik among them) | 13 |
| 403 (PACCAR, Kenworth, Coupa, Oracle, Markforged, Nokia, UPS, XPO) | 8 |
| robots.txt unavailable, network error (Serve, Voltera, Manhattan, Identiv, Divergent, DHL) | 6 |
| Nothing dated in the last 12 months (ISEE, EON, Zebra) | 3 |
| JavaScript shell (Verity 6, Hyundai 7 visible characters) | 2 |
| robots.txt disallows (SAP News: `User-agent: *` / `Disallow: /`) | 1 |
| `/news` redirects to the homepage (Matternet) | 1 |
| Parked domain (Haddy) | 1 |
| Redirects to another firm (RCS Global to SLR Consulting; DB Schenker to DSV) | 2 |
| Third-party coverage (by hand) | 5 |
| Site blog or marketing feed (by hand) | 6 |
| Not relevant: corporate news across all of Amazon (by hand) | 1 |
| **Newsrooms now** | **52** |

A 404 at a guessed URL is a weak rejection. Dexterity, Waabi, Einride, Wiliot,
Dexory, Keelvar and others almost certainly have a newsroom somewhere else on
their site. They are listed as not reachable at the URL tried, not as having
no newsroom.

### Coverage of the 24 tracked technologies (by `chosen_for`)

- **No newsroom:** battery_free_iot, cv_inspection, microfactories and
  smart_labels.
- **One newsroom:** additive_spares (SPEE3D), autonomous_yard (Outrider),
  gs1_2d (GS1 US) and private_5g_warehouse (Ericsson).
- **Two or more:** the other 16.
- **User firms (5):** GXO, FedEx, Maersk, Penske Logistics and DSV.

## First yield, 2026-W40

### How the first pass ran

`main` does not consult `collectors_needing_fetch`, so a `--week` run always
fetches and does not refuse. `fetch_week` writes envelopes numbered from
`000.json`, so the 16 files from Monday's cron were overwritten in the same
order, and the new newsrooms' envelopes followed them. The 16 originals had
been copied first to `data/backups/raw-2026-W40-pressroom-before-widen/`, and
the database to `data/backups/observatory-before-widen-2026-09-29.db`.

The first pass fetched 60 newsrooms in 9 min 16 s (raw files 18:10:32 to
18:19:48 UTC); the 16-newsroom run took under 2 minutes. The 52-newsroom list
has not been timed on its own.

### Fix round: production data, in order, with counts

1. **Database backed up** to
   `data/backups/observatory-before-widen-fix-2026-09-29.db` (integrity ok,
   2,419 observations).
2. **Envelopes moved.** The W40 envelopes of the eight dropped vendors and
   the old ivalua (rss) envelope were identified by their `vendor` field (016
   ambi, 017 brightpick, 025 amazon, 033 jaggaer, 034 ivalua, 036 pactum, 043
   checkpoint, 047 vimaan, 058 nfi). They were moved to
   `data/backups/raw-2026-W40-pressroom-dropped/`, taking the directory from
   60 files to 51.
3. **Ivalua rebuilt without a network call.** Its html newsroom envelope was
   built from the discovery response saved at 2026-09-29T17:48:57Z. It uses
   the collector's envelope format with `pages: {}`, decoded through
   `http._settle_encoding` as the collector would. It is written as `060.json`
   with a note saying where the listing came from. It has no `raw_fetch` row,
   so any observation from it would carry a NULL `raw_ref`; this week it
   matched nothing.
4. **Deletes.**
   - observations `source='pressroom' AND id >= 2410`: 10 rows;
   - corpus `pressroom` 2026-W40: 8 rows, 91 documents;
   - `weekly_signals` `press_releases` for W39 and W40: 96 rows.

   The three original W39 observations (2383, 2384, 2385) remain, and the
   observations table went from 2,419 to 2,409.
5. **Dangling raw paths.** `raw_fetch` rows under `/.worktrees/widen/` (60)
   and `/.worktrees/pressroom/` (16) were rewritten to the main checkout's
   path, leaving 0 under `.worktrees`. Of the pressroom rows' distinct paths,
   67 exist on disk. The 9 that do not are the envelopes moved in step 2.
6. **Re-parse.** `--only pressroom --week 2026-W40 --skip-fetch` was run
   through a wrapper that sets `config.RAW_DIR` to its resolved path, so that
   `_raw_ref` finds the rewritten `raw_fetch` rows. The new observations carry
   `raw_ref` 3692 to 3694. Run from the worktree unchanged, the lookup would
   have used worktree paths and found none. It took 2 s.

### Re-measured

Window: 2026-09-21 to 2026-10-04.

| | |
|---|---|
| Envelopes | 52 (51 fetched on the first pass, plus ivalua's from discovery) |
| Notes | 0 on the fetched envelopes (ivalua's carries its provenance note) |
| Item pages held | 77 |
| Documents (`corpus`, pressroom, 2026-W40) | **68**: 18 from the original 16, 50 from the new 36 |
| Newsrooms with an in-window document | 23 of 52 (16 of the 36 new) |
| In-window items dropped as off-site | 0 this week |
| Observations | **4** new: 3 filed under 2026-W39, 1 under 2026-W40, by document date |
| `press_releases` signal rows | 48 for W39, 48 for W40 |
| Source status, pressroom 2026-W40 | `ok` |
| Observations table | 2,409 → 2,413 |

In-window documents per newsroom:

- **New newsrooms:** nvidia 10, maersk 9, ericsson 5, ionq 5, gxo 4, toyota
  3, pasqal 3, fedex 2, ivalua 2, gep 1, o9 1, circulor 1, minespider 1,
  dwave 1, knapp 1, hairobotics 1.
- **Original 16:** daimlertruck 5, berkshiregrey 5, kodiak 4, aurora 1,
  agility 1, circularise 1, gs1us 1.

### Every observation, read by hand

| id | Week | Date | Vendor | Title | Tech | Reading |
|---|---|---|---|---|---|---|
| 2410 | W39 | 09-21 | nvidia | Why Deploying Physical AI at Scale Demands Safety at Every Layer | humanoid_logistics | passing mention: an essay, no deployment |
| 2411 | W39 | 09-21 | nvidia | (same) | robotic_manufacturing | passing mention |
| 2412 | W39 | 09-23 | circulor | The EU Digital Product Passport (DPP) registry is live: what to do now | digital_product_passport | passing mention: a regulatory explainer |
| 2413 | W40 | 09-29 | minespider | AI and the Digital Battery Passport: Where It Can Reduce Manual Work | minerals_traceability | passing mention: an explainer |

**Pilot-stage: 0. Passing mentions: 4. False positives: 0.** The six false
positives of the first pass all came from Jaggaer's blog feed, which is now
off the list.

Some in-window documents matched nothing but are the kind of item the tracker
wants:

- KNAPP will supply automation for Kesko's new logistics centre, an order.
- GXO deployed a labour-management system and signed Columbia Sportswear.
- Maersk opened a 72,000 m² warehouse and extended its PUMA partnership.
- IonQ's Superion was selected by FIU.

None of them is about a tracked technology in the lexicon's terms. What an
item evidences is the matcher's decision, not the collector's.

### Fix round 2: what the `--only` runs broke, and the repair

**The defect.** `--only pressroom` overwrote `candidate_terms` for 2026-W39
and 2026-W40. `detect_rising` saw only one collector, and `upsert_candidates`
replaces a week's rows, so the stored `total` fell from 228 to 73 (W39) and
from 230 to 118 (W40). The same runs also re-rendered those weeks' pages from
one source, in the worktree's `output/`.

**The repair.**

1. The database was backed up to
   `data/backups/observatory-before-candidates-restore-2026-09-29.db`.
2. Both weeks' rows were restored from
   `data/backups/observatory-before-widen-2026-09-29.db`:
   - before: W39 25 rows, total 73; W40 25 rows, total 118;
   - after: W39 25 rows, total 228; W40 25 rows, total 230;
   - 50 rows deleted and 50 inserted, and an `EXCEPT` in both directions
     against the backup returns 0 rows.

**Rule until this is fixed.** A single-source replay must not be run on a
week the cron has already scored. The main checkout's W39 page predates
observations 2410–2412, and the cron will not re-render W39.

**raw_fetch paths now point at where the bytes are.** Each file was matched
by the `vendor` and `url` inside it before its row was updated, and every
updated path exists on disk:

- ids 3636–3651 (Monday's cron fetch of the 16 originals, whose files the
  first pass overwrote) now point to
  `data/backups/raw-2026-W40-pressroom-before-widen/000–015.json`;
- ids 3668, 3669, 3677, 3685, 3686, 3688, 3695, 3699 and 3710 (ambi,
  brightpick, amazon, jaggaer, the old ivalua feed, pactum, checkpoint,
  vimaan and nfi) now point to
  `data/backups/raw-2026-W40-pressroom-dropped/`.

That is 25 rows in all.

## What the wider list costs, and what it yields

- **Time.** Probably around 8 minutes a week. That is an estimate, not a
  measurement: the first pass took 9 min 16 s for 60 newsrooms, and the
  dropped nine are a small share of the requests. Monday's cron (2026-10-05)
  is the first measured 52-newsroom run. The 45-minute budget bounds when
  the run starts a new newsroom or item page; the last request begun inside
  it can still take up to two 60 s timeouts, plus a wait of up to 120 s. A
  longer `Retry-After` ends that request rather than being waited out.
- **Yield.** One week, on-site releases only: 68 documents and 4
  observations, all passing mentions. This does not move the STATUS §5 (c)
  reversal condition, which is under 10 matched observations a quarter for
  two quarters. At four a week, the source clears that on count, but the
  question the tracker cares about is pilot-band quality, and a quarter of
  weekly runs will answer it better than one week can.

## Candidate table

"Requests" counts every request made for the candidate, including robots.txt,
retries and redirect hops. "Dated items" and "Newest" describe the accepted
listing as `items_for` reads it.

| Vendor | Chosen for | Outcome | Kind | Dated items | Newest | Requests | Reason if rejected |
|---|---|---|---|---:|---|---:|---|
| Dexterity (`dexterity`) | piece_picking | rejected |  |  |  | 6 | 404 after the www-to-apex redirect; no listing within 6 requests |
| Plus One Robotics (`plusone`) | piece_picking | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Mujin (`mujin`) | piece_picking | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Nimble Robotics (`nimble`) | piece_picking | rejected |  |  |  | 6 | no listing found within 6 requests |
| OSARO (`osaro`) | piece_picking | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Pickle Robot (`pickle`) | piece_picking | rejected |  |  |  | 5 | listing loads but yields no dated items |
| Boston Dynamics (`bostondynamics`) | piece_picking, humanoid_logistics | rejected (hand) |  |  |  | 2 | listing is third-party coverage (3 dated items, 0 on its own site) |
| Ambi Robotics (`ambi`) | piece_picking | rejected (hand) |  |  |  | 4 | newsroom 404; /feed is the site blog (35 of 37 items under /blog/) |
| Brightpick (`brightpick`) | piece_picking, microfulfillment | rejected (hand) |  |  |  | 2 | listing is mostly third-party coverage (20 of 23 items in the last 12 months on other sites) |
| 1X (`1x`) | humanoid_logistics | rejected |  |  |  | 6 | listing loads but yields no dated items |
| Sanctuary AI (`sanctuary`) | humanoid_logistics | accepted | rss | 10 | 2026-06-17 | 6 |  |
| Unitree (`unitree`) | humanoid_logistics | accepted | html | 11 | 2026-08-05 | 3 |  |
| Outrider (`outrider`) | autonomous_yard | accepted | rss | 10 | 2025-11-20 | 4 |  |
| Fernride (`fernride`) | autonomous_yard | rejected |  |  |  | 6 | listing loads but yields no dated items |
| ISEE (`isee`) | autonomous_yard | rejected |  |  |  | 5 | no item in the last 12 months (16 dated, newest 2025-04-29) |
| Starship Technologies (`starship`) | sidewalk_delivery_robots | accepted | html | 9 | 2026-04-28 | 2 |  |
| Serve Robotics (`serve`) | sidewalk_delivery_robots | rejected |  |  |  | 2 | robots unavailable (network error) |
| Coco (`coco`) | sidewalk_delivery_robots | accepted | html | 6 | 2026-04-28 | 2 |  |
| Kiwibot (`kiwibot`) | sidewalk_delivery_robots | rejected |  |  |  | 6 | redirects to robot.com, where /blog is 404; no listing within 6 requests |
| Matternet (`matternet`) | delivery_drones | rejected |  |  |  | 5 | /news redirects to the homepage |
| DroneUp (`droneup`) | delivery_drones | accepted | rss | 20 | 2026-07-28 | 3 |  |
| Manna (`manna`) | delivery_drones | accepted | html | 17 | 2026-07-08 | 2 |  |
| Amazon (`amazon`) | delivery_drones, user_firm | rejected (hand) |  |  |  | 3 | corporate news feed across all of Amazon (entertainment, sellers, devices, climate); 10 items roll over in under a week, 0 matches; reversal: an operations-only feed |
| Walmart (`walmart`) | delivery_drones, user_firm | rejected |  |  |  | 3 | listing loads but yields no dated items |
| Waabi (`waabi`) | autonomous_trucking | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Torc Robotics (`torc`) | autonomous_trucking | accepted | rss | 10 | 2026-09-03 | 4 |  |
| Gatik (`gatik`) | autonomous_trucking | rejected |  |  |  | 6 | /news redirects (via www) to archive.gatik.ai; no listing within 6 requests |
| Bot Auto (`botauto`) | autonomous_trucking | accepted | html | 50 | 2026-09-18 | 2 |  |
| Volvo Autonomous Solutions (`volvoautonomous`) | autonomous_trucking | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Einride (`einride`) | autonomous_trucking, electric_trucks | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| PACCAR (`paccar`) | electric_trucks | rejected |  |  |  | 2 | 403 |
| Kenworth (`kenworth`) | electric_trucks | rejected |  |  |  | 2 | 403 |
| Peterbilt (`peterbilt`) | electric_trucks | rejected |  |  |  | 3 | JavaScript-rendered listing (no dated items in the HTML) |
| Freightliner / Daimler Truck North America (`freightliner`) | electric_trucks | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Windrose (`windrose`) | electric_trucks | rejected (hand) |  |  |  | 3 | /news redirects to /about-us, a list of third-party coverage (5 dated, 0 on its own site) |
| Harbinger (`harbinger`) | electric_trucks | accepted | rss | 10 | 2026-07-31 | 6 |  |
| Hyundai Motor America (`hyundai`) | hydrogen_trucks | rejected |  |  |  | 2 | JavaScript shell (7 visible characters) |
| Hyundai HTWO (`htwo`) | hydrogen_trucks | rejected |  |  |  | 6 | no listing found within 6 requests |
| Toyota (US pressroom) (`toyota`) | hydrogen_trucks | accepted | rss | 20 | 2026-09-28 | 4 |  |
| Symbio (`symbio`) | hydrogen_trucks | rejected |  |  |  | 7 | no listing found within 6 requests |
| WattEV (`wattev`) | freight_charging | accepted | html | 6 | 2026-06-30 | 4 |  |
| Greenlane (`greenlane`) | freight_charging | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| TeraWatt Infrastructure (`terawatt`) | freight_charging | accepted | html | 8 | 2026-04-09 | 5 |  |
| Voltera (`voltera`) | freight_charging | rejected |  |  |  | 2 | robots unavailable (network error) |
| Forum Mobility (`forummobility`) | freight_charging | accepted | rss | 10 | 2026-09-11 | 6 |  |
| Zeem Solutions (`zeem`) | freight_charging | rejected (hand) |  |  |  | 3 | listing is third-party coverage (49 dated items, 2 on its own site) |
| Coupa (`coupa`) | agentic_procurement | rejected |  |  |  | 2 | 403 |
| Zip (`zip`) | agentic_procurement | rejected |  |  |  | 6 | no listing found within 6 requests |
| Jaggaer (`jaggaer`) | agentic_procurement | rejected (hand) |  |  |  | 3 | newsroom 404; /feed is the site blog (10 of 10 items vendor-comparison and how-to posts) |
| Ivalua (`ivalua`) | agentic_procurement | accepted | html | 13 | 2026-09-25 | 4 |  |
| GEP (`gep`) | agentic_procurement | accepted | html | 15 | 2026-09-24 | 3 |  |
| Keelvar (`keelvar`) | agentic_procurement | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Pactum (`pactum`) | agentic_procurement | rejected (hand) |  |  |  | 4 | /news/ redirects to a blog tag; the feed is the site blog (48 of 48 items under /blog/) |
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
| RCS Global (`rcsglobal`) | minerals_traceability | rejected |  |  |  | 6 | /news/ redirects to slrconsulting.com (RCS Global is now part of SLR Consulting) |
| Minespider (`minespider`) | minerals_traceability, digital_product_passport | accepted | html | 24 | 2026-09-29 | 2 |  |
| Everledger (`everledger`) | minerals_traceability | rejected |  |  |  | 4 | listing loads but yields no dated items |
| Digimarc (`digimarc`) | gs1_2d | rejected |  |  |  | 3 | listing loads but yields no dated items |
| Zebra Technologies (`zebra`) | gs1_2d | rejected |  |  |  | 3 | no item in the last 12 months (1 dated, newest 2023-12-31) |
| Wiliot (`wiliot`) | battery_free_iot, smart_labels | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Everactive (`everactive`) | battery_free_iot | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Atmosic (`atmosic`) | battery_free_iot | rejected |  |  |  | 4 | listing loads but yields no dated items |
| Identiv (`identiv`) | smart_labels, battery_free_iot | rejected |  |  |  | 2 | robots unavailable (network error) |
| Checkpoint Systems (`checkpoint`) | smart_labels | rejected (hand) |  |  |  | 3 | advertised feed is the site blog (10 of 10 items under /blog/) |
| Wurth Additive Group (`wurthadditive`) | additive_spares | rejected |  |  |  | 6 | no listing found within 6 requests |
| Markforged (`markforged`) | additive_spares | rejected |  |  |  | 2 | 403 |
| Stratasys (`stratasys`) | additive_spares | rejected |  |  |  | 2 | JavaScript-rendered listing (no dated items in the HTML) |
| EOS (`eos`) | additive_spares | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| SPEE3D (`spee3d`) | additive_spares | accepted | rss | 12 | 2026-09-08 | 4 |  |
| Haddy (`haddy`) | microfactories | rejected |  |  |  | 3 | domain parked (redirects to ww16.haddy.com, robots disallows) |
| Divergent (`divergent`) | microfactories | rejected |  |  |  | 2 | robots unavailable (network error) |
| Bright Machines (`brightmachines`) | microfactories | rejected (hand) |  |  |  | 3 | listing is third-party coverage (5 dated items, 0 on its own site) |
| AutoStore (`autostore`) | microfulfillment | accepted | rss | 10 | 2026-09-07 | 3 |  |
| Ocado Group (`ocado`) | microfulfillment | accepted | html | 11 | 2026-08-25 | 3 |  |
| Fabric (`fabric`) | microfulfillment | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Exotec (`exotec`) | microfulfillment | rejected |  |  |  | 4 | listing loads but yields no dated items |
| Attabotics (`attabotics`) | microfulfillment | rejected |  |  |  | 6 | listing loads but yields no dated items |
| Cognex (`cognex`) | cv_inspection | rejected |  |  |  | 6 | no listing found within 6 requests |
| Kargo (`kargo`) | cv_inspection | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Gather AI (`gatherai`) | cv_inspection | rejected |  |  |  | 6 | no listing found within 6 requests |
| Vimaan (`vimaan`) | cv_inspection | rejected (hand) |  |  |  | 4 | newsroom 404; /feed is the resources section (blog, application notes, reposted trade coverage) |
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
| Ryder (`ryder`) | user_firm | rejected |  |  |  | 3 | JavaScript-rendered listing (no dated items in the HTML) |
| Penske Logistics (`penske`) | user_firm | accepted | rss | 30 | 2026-06-16 | 5 |  |
| J.B. Hunt (`jbhunt`) | user_firm | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| Schneider (`schneider`) | user_firm | rejected |  |  |  | 6 | no listing found (known page 404, no feed, no news sitemap) |
| NFI (`nfi`) | user_firm | rejected (hand) |  |  |  | 4 | newsroom 404; /feed is about-page insight posts (10 of 10 under /about-nfi/insights/) |
| Kroger (`kroger`) | user_firm | rejected |  |  |  | 4 | listing loads but yields no dated items |
| DB Schenker (`dbschenker`) | user_firm | rejected (hand) |  |  |  | 4 | press page redirects to the DSV homepage (Schenker is part of DSV); covered by dsv |
| DSV (`dsv`) | user_firm | accepted | html | 3 | 2026-09-01 | 1 |  |
| XPO (`xpo`) | user_firm | rejected |  |  |  | 2 | 403 |
| Werner (`werner`) | user_firm | rejected |  |  |  | 5 | listing loads but yields no dated items |
| Lineage (`lineage`) | user_firm | rejected |  |  |  | 6 | no listing found within 6 requests |
