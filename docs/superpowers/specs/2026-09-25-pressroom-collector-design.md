# Press-room collector: design

Date: 2026-09-25. Owner's instruction: "build the press-room collector", after
probe 2 (`docs/trl-probe2-2026-09-25.md`) ranked it first among free sources by
evidence per unit of effort. Status: approved by the instruction; the owner
reviews the artifact, not the mechanism.

## 1. What it is

A weekly collector, `pressroom`, that reads a fixed list of vendor newsrooms
(`pressrooms.yaml` at the repo root), keeps each item's title, date, URL and
opening text, and hands the documents to the same matcher every other source
uses. It is the first free source that carries pilots, first sites, orders and
product launches, the TRL 5–8 band that papers and grants never reach. Probe 2
measured it: 16 of 22 newsrooms answered with dated items; 14 in-window items
for autonomous trucking, 3 of them pilot-band, all from Kodiak.

## 2. Constraints

- **Raw before parse.** One raw file per newsroom per week: a JSON envelope
  holding the listing page as fetched and every item page fetched for it.
  `parse()` is a pure function over that envelope.
- **No LLM in the weekly run** (C5). The collector is regex and stdlib only.
- **Robots and rate.** `robots.txt` is read once per host per run and obeyed;
  a disallowed path is skipped and logged as a source note, never fetched.
  One request every 2 seconds per collector; at most 15 item pages per
  newsroom per run.
- **Licence.** Press releases are issued for redistribution. The report quotes
  with attribution and links the release. Newsroom pages that return 403 or a
  JavaScript shell are recorded, not evaded.
- **The list is config, not code.** Adding a newsroom is a `pressrooms.yaml`
  edit. The matcher decides which technologies an item evidences; the yaml's
  `chosen_for` field is provenance only.
- **A missing newsroom is not a zero.** A newsroom that fails leaves its items
  absent; the source is marked degraded for the week, not ok.

## 3. Evidence semantics

Family `press`, stage `deployment` in the count instrument's maps; signal
`press_releases` (count). For the TRL tracker the source type is
`press_release`, actor type usually `incumbent_vendor` or `startup`; user
firms appear as the named customer in the text.

## 4. Kinds of newsroom

`rss` (title, link, pubDate, description), `sitemap` (loc, lastmod, or a date
in the URL), `html` (anchors with title-length text, dated by a date in the
URL or the nearest date string within 900 characters), `links:<path>` (an
undated listing: the first 15 links under `<path>` are fetched and dated from
their own page). All four exist in `docs/experiments/trl/probe2.py` and are
moved into the package with tests.

## 5. Out of scope

Per-site CSS selectors (a maintenance trap), full-text extraction beyond the
first substantial paragraphs, and any newsroom that needs JavaScript. The
count instrument's z-scores are not re-tuned for the new signal.
