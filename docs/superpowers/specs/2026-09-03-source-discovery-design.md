# Source discovery — design

**Date:** 2026-09-03 · **Status:** approved in conversation, not yet built

A quarterly, human-in-the-loop sweep that proposes **new sources to collect
from**. It never produces observations, never edits `sources.yaml`, and never
runs inside the weekly job.

## Why this, and why it is not the loop that failed

`discover.py` already does discovery: it surfaces rising n-grams from the
corpus each week. The process review's verdict was blunt — of 51 watchlist
entries, **not one came from it**, and it recommended killing it.

This is a different search space, and that is the whole argument for building
it. The rising-terms loop can only find vocabulary **already inside documents
we collect**. It cannot tell you that Blue Yonder publishes dated product
announcements, because we have no collector that would ever see one. An
agentic sweep looks *outside* the corpus, which is exactly where the evidence
we lack lives.

If it produces nothing over two cycles, it should be retired the same way.

## The gap it is aimed at

2026-Q2 by evidence family:

| family | observations |
|---|---|
| research | 328 |
| code | 275 |
| filings | 29 |
| community | 15 |
| regulation | 6 |
| patents | 5 |
| research funding | 5 |
| money | 5 |
| **trade** | **1** |

Research and code are 90% of the quarter. Everything that speaks to
**deployment and diffusion** is in single digits. **14 of 48 technologies have
fewer than five observations in the life of the project.**

Vendor announcements, conference programmes and pilot press releases are
deployment evidence with no API anywhere, which is precisely why no automated
collector reaches them and why a human-in-the-loop sweep is the only instrument
that can.

## Shape

Mirrors `observatory.lexicon`, which already works here and for the same
reason: the pipeline packages evidence, a person makes the judgement.

```
--discovery-request 2026-Q4   →  discovery/requests/2026-Q4.md
        ↓  a Claude session with browser access works the request
                                 discovery/proposals/2026-Q4.md
--discovery-check 2026-Q4     →  validates; the owner merges by hand
```

**The pipeline never adds a source.** `sources.yaml` is edited by a person,
exactly as `watchlist.yaml` is.

## The request

Generated from the database, so it cannot go stale. It carries:

1. **Every current source** — family, stage, observations all-time and this
   quarter, and audited precision where known.
2. **The exclusion list, with reasons.** SBIR (500 awards, zero matches),
   CORDIS, DC Velocity / FreightWaves / Material Handling & Logistics (not
   indexed under `PUB.EXACT`), Journal of Commerce (ABI coverage stops
   2022-12-31), Yahoo Finance and Finviz (terms of service prohibit automated
   access), Google Books Ngrams (corpus ends 2019). Without this the sweep
   spends a quarter re-proposing what was already measured and refused.
3. **The gaps** — families in single digits, technologies below five
   observations, and any technology drawing 80%+ of its evidence from one
   source.
4. **The watchlist terms**, so a candidate can be tested rather than admired.
5. **The rules a source must satisfy**: free or already licensed to ASU;
   documents carry their own date; retrievable without breaching terms.

## The proposal, and the bar it must clear

**A proposal carries a measurement, not a recommendation.** This is the
project's own standing rule: SBIR was rejected after collecting 500 awards and
matching zero; OpenAlex survived because its abstract coverage was measured at
99% against Scopus's on the same twelve journals. A candidate that has not been
sampled is a wish.

Each candidate must state:

| field | why it decides something |
|---|---|
| URL and fetch method | API, RSS or HTML-only changes the cost by an order of magnitude |
| **Does each item carry its own date?** | No date means no week. The pipeline files every document by its own date; an undated source is unusable, not merely awkward |
| Estimated volume per quarter | Tells you whether it is worth a collector at all |
| **Sample of ~20 items, and how many match the current watchlist** | The number that decides it. This is the SBIR test |
| Licence / terms position | A source we may not fetch is not a source |
| Which gap it fills | Family and stage, against the request's gap list |

`check` refuses a proposal that omits the match count, or that names a source
on the exclusion list.

## Testing

- **The request generator is deterministic and tested**: given a database, it
  names the right gaps, the right exclusions, and the right current sources.
- **`check` is tested** against a good proposal, one missing its match count,
  and one re-proposing an excluded source.
- **The sweep itself is not tested.** It is human-in-the-loop, like the manual
  exports, and the spec says so rather than implying coverage that does not
  exist. This is the project's least-tested path and the one where all three
  errors that reached the owner have occurred, so `check` carries the weight.

## Explicitly not building

- Automatic adoption of a proposed source.
- Any path from a proposal to an observation.
- Scheduling. It is quarterly and run by hand, like the supplemental exports.
- Term discovery. Terms already have `lexicon prepare → check`, and term
  discovery is the thing that failed.

## How it earns its place, or does not

Two cycles. If by 2027-Q2 no proposal has become a collector, retire it and
record why — the same standard the rising-terms loop is being held to.
