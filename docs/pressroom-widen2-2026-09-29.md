# Press rooms for battery-free IoT and microfactories, 2026-09-29

After the first widening (`docs/pressroom-widen-2026-09-29.md`), two tracked
technologies still had no newsroom: `battery_free_iot` and `microfactories`.
This pass looked for vendor newsrooms for those two. It used the same method
and the same membership rule, with the first pass's lessons applied.

The collector now reads **62 newsrooms**: the 52 it already read, plus 10 new
ones. **battery_free_iot now has 9. microfactories has 1**, Fathom, and that
one is weak (below). Nothing was fetched through the collector, and no
`observatory.run` or database statement was run. Monday's cron (2026-10-05)
is the first run that will read the new newsrooms.

## Method

Script: `docs/experiments/trl/widen2_pressrooms.py`. It imports the first
pass's fetch path, budget and assessment from `widen_pressrooms.py` rather
than copying them. Raw responses and one decision file per candidate are in
`data/trl/widen2/` (gitignored). `--report` prints the table below.

**Newsroom URLs.** Most were found by web search for the company's own press
page, not guessed. Seven are guesses, marked in the script: Exeger, Trameto,
Orbital Composites, Mighty Buildings, Azure, SyBridge and Reframe.

**Permission first.**

- robots.txt is read for the newsroom host through the collector's own
  `_robots` (RFC 9309, `observatory.robots`).
- If robots.txt is unavailable (5xx, 429 or a network error) or disallows the
  listing, the candidate is rejected.
- A 403, a challenge page or a JavaScript shell is a rejection. None was
  retried or evaded.
- At most 6 requests per candidate. Crawl-delay is honoured in full, pacing is
  per host, and `retries=1`.

**Changes from the first pass:**

- **Hops are counted before the budget check.** Every redirect hop, including
  robots.txt redirects that `requests` used to follow itself, is now its own
  request. Each is checked against the budget before it is sent and paced
  2 s apart. No candidate used more than 6 requests (the first pass's Symbio
  used 7).
- **The press listing comes first.** The script tries the html newsroom
  first. Next it tries an advertised feed, but only if the feed's URL is
  press-specific. A site-wide `/feed`, `/rss` or sitemap is accepted only if
  its recent items sit on press or news paths. The first pass preferred any
  advertised feed, which is how marketing blogs got in.
- **The membership rule is checked by the script.** It looks at items dated
  in the last 12 months:
  - off-site items outnumbering on-site ones → rejected as third-party
    coverage;
  - more than half the on-site items under `/blog/` → rejected as a blog;
  - a press page whose items sit under `/blog/` → left for a hand read.

  `/blog/` takes precedence over a press word earlier in the path, so
  Re:Build's `/newsroom/blogs/` counts as blog. The first run of this pass got
  that precedence backwards; it was fixed and the listing re-judged from the
  saved response.

**A mistake in this pass.** On its first run, the `links:` fallback did not
filter item links to the listing's own site. For InPlay it made three
off-site requests before the budget stopped it:

- Avery Dennison's robots.txt;
- one Avery Dennison press-release page;
- businesswire.com's robots.txt, which returned 403.

Robots.txt was checked before the page. The run was stopped, the filter was
added (own site only, the collector's `_site`), and InPlay was re-run from
its saved responses. The table below shows InPlay's replayed count of 3;
the first run actually made 6 requests.

**What was spent.**

- 127 requests in all, counting robots.txt files, retries and redirect hops.
- Of those, 3 were off-site (InPlay, above).
- Discovery took about 15 minutes, most of it network timeouts. Each
  unreachable robots.txt costs two 60 s timeouts.

## Candidates: 34

**Battery-free IoT (17):**

- Retried at a different URL: Wiliot, Everactive and Identiv.
- New: e-peas, Powercast, Energous, Ossia, EnOcean, ONiO, Dracula
  Technologies, Epishine, Exeger, InPlay, Trameto, Nexperia, Ambient Photonics
  and Trackonomy. Trackonomy bought InPlay in 2025 and Identiv's IoT business
  in 2026.

**Microfactories (17):**

- Retried at a different URL: Divergent.
- New: Hadrian, Re:Build, Machina Labs, Vention, Formic, Orbital Composites,
  Mighty Buildings, Azure Printed Homes, Cuby, Xometry, Protolabs, Fictiv and
  SyBridge (which bought Fast Radius's assets).
- Added once the first run of 30 left microfactories empty: Reframe Systems,
  Fathom and Isembard (and Trackonomy, above).

**Not tried:**

- Atmosic: its first-pass URL again, and no other press page is known.
- Haddy: the domain is parked.
- Bright Machines: its `/news` is third-party coverage, and no own-site press
  page is known.
- Stratasys: rejected in the first pass.
- Arrival and Canoo: bankrupt.
- Local Motors: closed in 2022.
- Firestorm Labs: its domain now names another business.
- Sensata: not a battery-free vendor.

## Candidate table

Columns:

- **Items** and **Newest**: dated items in the listing, as the collector's
  `items_for` reads it.
- **On/Off**: items dated in the last 12 months on the newsroom's own site and
  on other sites.
- **Press/Blog/Other**: the on-site items of the last 12 months, by URL path.
- **Pilot titles**: titles from the last 12 months that name a real
  deployment, pilot, customer, order or site. They were counted by hand,
  conservatively, for accepted newsrooms only.
- **Req.**: requests made for the candidate.

Blank cells: no listing passed.

| Vendor | Technology | Outcome | Kind | Items | Newest | On/Off | Press/Blog/Other | Pilot titles | Req. | Reason if rejected |
|---|---|---|---|---:|---|---|---|---:|---:|---|
| Wiliot | battery_free_iot, smart_labels | accepted (hand) | html | 89 | 2026-08-25 | 10/3 | 0/10/0 | 1 | 2 | |
| Everactive | battery_free_iot | rejected | | | | | | | 6 | no listing found (press category page 404, no feed, no news sitemap) |
| Identiv | smart_labels, battery_free_iot | rejected (hand) | html | 9 | 2026-08-12 | 9/0 | 9/0/0 | | 6 | sold its IoT business to Trackonomy, renamed INVE Technologies (2026-08-12); 9 of 9 recent items earnings and corporate notices |
| e-peas | battery_free_iot | accepted | rss | 12 | 2026-07-08 | 6/0 | 6/0/0 | 0 | 3 | |
| Powercast | battery_free_iot | accepted | html | 146 | 2026-04-28 | 6/0 | 6/0/0 | 0 | 3 | |
| Energous | battery_free_iot | rejected | | | | | | | 2 | robots unavailable (read timeout, twice) |
| Ossia | battery_free_iot | rejected | | | | | | | 5 | no item in the last 12 months (newest 2024-06-12) |
| EnOcean | battery_free_iot | accepted | html | 15 | 2026-03-04 | 3/0 | 0/0/3 | 0 | 2 | |
| ONiO | battery_free_iot | accepted | html | 6 | 2025-11-25 | 1/0 | 1/0/0 | 0 | 2 | |
| Dracula Technologies | battery_free_iot | accepted | rss | 10 | 2026-06-09 | 10/0 | 0/0/10 | 0 | 3 | |
| Epishine | battery_free_iot | accepted | html | 12 | 2026-08-04 | 3/0 | 3/0/0 | 1 | 2 | |
| Exeger | battery_free_iot | accepted | html | 15 | 2025-11-06 | 2/0 | 2/0/0 | 0 | 6 | |
| InPlay | battery_free_iot | rejected | | | | | | | 3 (6 on the first run) | listing yields 1 dated item (2025-10-08); /feed not a dated press feed |
| Trameto | battery_free_iot | rejected | | | | | | | 6 | no listing found (guessed page 404, no feed, no news sitemap) |
| Trackonomy | battery_free_iot, smart_labels | rejected | | | | | | | 4 | listing yields no dated items; /feed not a dated press feed |
| Nexperia | battery_free_iot | accepted | html | 10 | 2026-09-17 | 10/0 | 10/0/0 | 0 | 2 | |
| Ambient Photonics | battery_free_iot | rejected | | | | | | | 2 | robots unavailable (TLS handshake failure, twice) |
| Divergent | microfactories | rejected | | | | | | | 2 | robots unavailable (connect timeout, twice; also so in the first pass) |
| Hadrian | microfactories | rejected | html | 38 | 2026-03-05 | 0/9 | 0/0/0 | | 3 | listing is third-party coverage (9 of 9 recent on other sites) |
| Re:Build Manufacturing | microfactories | rejected (hand) | html | 14 | 2026-07-14 | 8/6 | 0/8/0 | | 2 | on-site items are blog posts (8 of 8); its releases are on businesswire.com |
| Machina Labs | microfactories | rejected | | | | | | | 6 | `/resources` yields no dated items; no press listing within 6 requests |
| Vention | microfactories | rejected | html | 85 | 2026-09-09 | 0/11 | 0/0/0 | | 6 | redirects to vention.com/press, third-party coverage (11 of 11 recent on other sites) |
| Formic | microfactories | rejected | | | | | | | 3 | no item in the last 12 months (12 dated, newest 2025-08-25) |
| Orbital Composites | microfactories | rejected | | | | | | | 6 | no item in the last 12 months (newest 2024-07-08) |
| Mighty Buildings | microfactories | rejected | | | | | | | 6 | no listing found (guessed page 404, no feed, no sitemap) |
| Azure Printed Homes | microfactories | rejected (hand) | html | 8 | 2026-09-01 | 8/0 | 0/0/8 | | 3 | /press/ lists SEO guide posts (8 of 8 recent), not releases |
| Cuby Technologies | microfactories | rejected | | | | | | | 3 | listing yields no dated items; /feed not a dated press feed |
| Xometry | microfactories | rejected | | | | | | | 2 | robots unavailable (read timeout, twice) |
| Protolabs | microfactories | rejected | | | | | | | 2 | robots unavailable (read timeout, twice) |
| Fictiv | microfactories | rejected | | | | | | | 3 | listing yields no dated items (/feed: 2 dated, newest 2025-04-13) |
| SyBridge Technologies | microfactories | rejected | | | | | | | 6 | www redirects to the apex, where /news is 404; no listing within 6 requests |
| Reframe Systems | microfactories | rejected | | | | | | | 6 | no listing found (guessed page 404, no feed, no news sitemap) |
| Fathom Manufacturing | microfactories | accepted | html | 3 | 2026-03-30 | 3/0 | 3/0/0 | 0 | 2 | |
| Isembard | microfactories | rejected | | | | | | | 3 | listing yields no dated items |

### Hand calls

**Accepted by hand: Wiliot.** Its `/press` page puts its releases under
`/blog/` URLs: 10 of the 13 items in the last 12 months, all with
release-style titles. The other 3 are coverage links (CNBC, Fast Company,
FT), which `parse` drops as off-site. Wiliot's previous `not_reachable` entry
is removed.

**Rejected by hand:**

- **Identiv.** Its press page redirects to `invetechnologies.com`. Identiv
  sold its IoT business, including the battery-free ID-Pixels, to Trackonomy,
  and renamed itself INVE Technologies on 2026-08-12. All 9 recent items are
  earnings and corporate notices. Trackonomy's own newsroom lists no dated
  items in its HTML.
- **Re:Build.** The on-site items are event and marketing blog posts. Its
  releases link out to Business Wire, which `parse` drops.
- **Azure Printed Homes.** `/press/` lists SEO guides such as "Do Modular
  Homes Depreciate?". Its releases go out on GlobeNewswire and Business Wire.

**Kept, but weak:**

- **Nexperia** passes the membership rule: 10 of 10 recent items are its own
  releases. But none of those 10 is about energy harvesting; they cover power
  semiconductors, results and a court dispute. It adds noise only if a
  release says "energy harvesting" along with a supply chain word.
- **ONiO** has 1 item in the last 12 months, and Exeger has 2 (newest
  2025-11-06).
- **Fathom** has 3 dated items. The newest is its own recap of coverage in
  the Rochester Business Journal.
- **EnOcean and Dracula** keep their releases on paths without a press word
  (`/enocean_pressrelease/`, and root slugs). Both are press listings by URL.

**Unreachable at robots.txt.** Energous, Xometry and Protolabs are investor
relations hosts that timed out on robots.txt, twice each. Each also has a
second address found by search: `energous.com/company/newsroom/`, and the
`gcs-web.com` IR mirrors for Xometry and Protolabs. None of these was tried.
A host that does not answer could be refusing automated clients, and going
round it would be evasion. The owner may rule otherwise.

## Totals

| | |
|---|---|
| Candidates | 34 (17 battery_free_iot, 17 microfactories) |
| Accepted | 10 (8 html, 2 rss; 1 by hand) |
| Rejected | 24 |
| robots unavailable (network error) | 5 (Energous, Ambient Photonics, Divergent, Xometry, Protolabs) |
| No listing found (404, no feed, no news sitemap) | 5 (Everactive, Trameto, Mighty Buildings, Reframe, SyBridge) |
| Listing yields no dated items, or 1 | 6 (InPlay, Trackonomy, Machina Labs, Cuby, Fictiv, Isembard) |
| Nothing dated in the last 12 months | 3 (Ossia, Formic, Orbital Composites) |
| Third-party coverage | 2 (Hadrian, Vention) |
| By hand: blog or SEO posts | 2 (Re:Build, Azure) |
| By hand: company sold the business | 1 (Identiv) |
| 403, challenge page, JavaScript shell, robots disallow | 0 |
| **Newsrooms now** | **62** (`pressrooms.yaml` version 2; `not_reachable` 113) |

**Coverage now:**

- **battery_free_iot: 9.** Wiliot, e-peas, Powercast, EnOcean, ONiO,
  Dracula, Epishine, Exeger and Nexperia.
- **microfactories: 1.** Fathom.
- **smart_labels:** Wiliot is the first newsroom chosen for it.
- **Still no newsroom:** `cv_inspection`.

## Will these newsrooms produce matches?

Honestly, few, and microfactories almost none.

**Battery-free IoT.** Both technologies are `needs_context`. A release counts
only if it says "battery-free", "batteryless", "energy harvesting" or
"backscatter" *and* a supply chain word ("supply chain", "logistics",
"inventory", "shipment" and so on).

- The battery-free vendors use the technology words constantly.
- Only Wiliot, and sometimes Powercast or Dracula (its Paragon ID
  traceability tags), write about supply chains.
- e-peas, EnOcean, ONiO, Epishine, Exeger and Nexperia write about buildings,
  consumer electronics and chips. Their releases will mostly fail the context
  gate.
- In the last 12 months, 2 of the 9 accepted newsrooms carried a
  pilot-type title: Wiliot with Walmart, and Epishine in Google's TV remote.
  Only Wiliot's is a supply chain deployment.

**Microfactories.** The vendors do not use the lexicon's words. Hadrian says
"automated factories", Divergent "adaptive production", Machina "intelligent
factory". The companies that say "on-demand manufacturing" (Xometry,
Protolabs, Fictiv) could not be read. Fathom's one recent release that fits,
Edgeworks, mentions supply chain volatility, but its listing posts about once
a quarter.

**Expectation.** On Monday's cron, one or two battery-free matches a month,
mostly from Wiliot, and microfactories at or near zero from this source. The
STATUS §5 (c) reversal condition is unchanged.
