# How much more EDGAR could give us

**Status:** measured 2026-09-01, live against `efts.sec.gov`. Commissioned
because the owner judged the diffusion evidence low on face validity, and asked
whether financial news sources would help before asking what EDGAR itself had
left.

Raw responses for every query below are in the session scratchpad; the numbers
are all from one window, **2026-Q2 (2026-04-01 to 2026-06-30)**, forms
`10-K, 10-Q, 8-K, S-1`.

## The answer in one line

**Roughly 4–5x, not 36x.** The raw hits look enormous and 92% of them never
become an observation, because the context gate discards them — correctly.

## Why this was asked

Diffusion is fed by exactly two signals, `filings` (EDGAR) and `trade_articles`
(ABI/INFORM). In 2026-Q2 that is **35 documents and 1 document**. ABI/INFORM
holds **9 documents in the entire database**, because it is a hand-made
quarterly export. Half the diffusion signal is a manual process that has
produced nine rows.

So the thin diffusion evidence is real, and EDGAR — free, keyless, federal, and
the strongest available evidence that companies actually *use* a technology —
was the first place to look.

## What the current collector gets

Eight query terms, against a fifty-technology watchlist. Over 2026-Q2:

| Term | Hits | Returned | Filers |
|---|---|---|---|
| warehouse management system | 19 | 19 | 13 |
| autonomous trucking | 8 | 8 | 6 |
| nearshoring supply chain | 6 | 6 | 2 |
| cold chain monitoring | 1 | 1 | 1 |
| warehouse robotics | 1 | 1 | 1 |
| supply chain risk intelligence | **0** | 0 | 0 |
| digital freight matching | **0** | 0 | 0 |
| enterprise resource planning supply chain | **0** | 0 | 0 |
| **Total** | **35** | 35 | 23 |

Two facts worth separating, because the first reading of this table was wrong.

**Three terms returned zero this quarter; only two have never worked.**
`digital freight matching` has produced 4 observations, dated 2025-08-18 to
2026-02-25. It is rare, not broken, and it stays. `supply chain risk
intelligence` and `enterprise resource planning supply chain` have produced
**zero observations in the life of the project**.

**Nothing is being truncated today.** Hits equal returned for all eight terms,
so the collector is retrieving everything its terms can find. That hypothesis
was checked and eliminated rather than assumed.

## The ceiling, and why it is not the ceiling

Thirty candidate terms over the same quarter returned **1,273 hits**. Only
**96** would become observations. The gate discards **1,177**.

| Candidate term | Hits | Becomes observations? |
|---|---|---|
| enterprise resource planning | 537 | no |
| agentic AI | 334 | no |
| supply chain risk | 83 | no |
| last mile delivery | 66 | **yes — 66** |
| digital twin | 53 | no |
| additive manufacturing | 52 | no |
| demand forecasting | 35 | no |
| route optimization | 33 | no |
| nearshoring | 20 | no |
| transportation management system | 14 | no |
| critical minerals supply chain | 10 | **yes — 10** |
| freight brokerage | 9 | no |
| micro-fulfillment | 7 | **yes — 7** |
| electric truck | 5 | **yes — 5** |
| manufacturing execution system | 4 | no |
| private 5G network | 3 | no |
| shore power, positive train control, digital product passport | 2 each | **yes — 6** |
| delivery drone, sales and operations planning | 1 each | **yes — 2** |

## The mechanism, which is the real finding

`EdgarCollector.parse` sets a document's `text` to **the query term itself**.
Filing bodies are megabytes and are never fetched, so the matcher never sees
the filing — it sees the phrase that retrieved it. Its own docstring says so.

The consequence had not been drawn out: **the context gate only ever sees the
term.** A term therefore either always passes the gate or always fails it, for
every filing it will ever retrieve. On EDGAR the gate is not a document-level
gate at all. It is a whitelist of query strings.

That produces a bind with no move inside it:

- Broad enough for EDGAR to find hits, and the gate drops all of them.
  `enterprise resource planning` returns **537 hits and 0 observations**.
- Carrying a domain word so the gate passes, and EDGAR finds nothing.
  `enterprise resource planning supply chain` returns **0 hits**.

The two never-productive terms are phrased the way they are *because of* the
gate, and are too long for phrase matching *because of* that phrasing. This is
the USAspending failure in a second collector: long multi-word phrases against
an API that matches phrases exactly.

Measured directly, for the two:

| Replacement tried | Hits | Gate |
|---|---|---|
| `risk intelligence` | 7 | dropped — no domain word in the term |
| `supply chain risk management` | 7 | dropped — matches no include pattern |
| `supplier risk platform` | **0** | passes |
| `enterprise resource planning system` | 179 | dropped — no domain word |
| `SAP S/4HANA` | 4 | dropped — no domain word |
| `ERP inventory`, `ERP and warehouse management` | **0** | passes |

Every candidate either gets hits and fails the gate, or passes the gate and
gets nothing. **There is no phrase that does both**, for either technology.

## What was done

The two never-productive terms are removed, with the reason recorded beside
them in `collectors/edgar.py` — the same shape as USAspending's eleven named
exclusions. A query that has never matched anything is not coverage; it is one
HTTP request a week and the appearance of coverage.

`digital freight matching` stays. It has produced.

## Two things found on the way, neither fixed here

**EDGAR caps a page at 100 and the collector neither paginates nor checks the
total.** `enterprise resource planning` reports 537 hits and returns 100 of
them. No current term exceeds 100, so it has never bitten — but it is silent
truncation waiting for a broader term, and silent truncation is the failure
this project names first. A total-versus-returned check costs nothing and
should go in before any term is widened.

**Every hit carries the filer's SIC code.** That is a container filter, the
same principle as ISSNs, CPC codes and USAspending's assistance-listing
programmes — and it is the only route to using the broad terms, since the API
returns no highlight or snippet and a real document gate would need the filing
bodies. It cuts hard, and unevenly:

| Term | Sampled | In-scope SIC (40xx–47xx, 50xx–51xx) |
|---|---|---|
| supply chain risk | 83 | **0** |
| additive manufacturing | 52 | **0** |
| agentic AI | 100 of 334 | 1 |
| digital twin | 53 | 1 |
| enterprise resource planning | 100 of 537 | 3 |
| demand forecasting | 35 | 5 |
| manufacturing execution system | 14 | 6 |
| route optimization | 33 | 7 |

A trucking company saying "enterprise resource planning" is plausible evidence
of supply chain ERP. A prepackaged-software vendor saying "agentic AI" — SIC
7372, the single commonest code in that result — is not. The filter is
defensible in principle and needs its own measurement before it is trusted,
because a SIC code describes the filer and not the sentence.

## What this would be worth

| | Filings/quarter | Filers |
|---|---|---|
| Today | 35 | 23 |
| Add the measured productive terms | ~131 | ~85 |
| Plus SIC-gated broad terms | ~170 | not estimated |

Filers is the number that matters: `edgar_filers` counts distinct CIKs, and
diffusion is breadth. Ten companies naming a technology once each is the
signal; one company naming it ten times is not.

## Limits of this measurement

- **One quarter.** 2026-Q2 only. Filing volume is seasonal — 10-K season is not
  April to June — and the annual picture will differ.
- **Thirty terms, chosen by hand by the assistant.** Not an exhaustive sweep of
  the forty-two technologies with no EDGAR term, and not reviewed by the owner.
- **The in-scope SIC counts for `enterprise resource planning` and `agentic AI`
  are from a 100-hit page, not the full result set**, so those two rates are
  estimates from a sample and the rest are complete.
- **No precision check.** Whether a filing that mentions "last mile delivery"
  is evidence that the filer *uses* it is exactly the question the precision
  audit exists for, and none of these 96 have been coded.
- **The 4–5x figure counts documents that would be created, not documents that
  would be correct.**

## The thing this measurement does not fix

EDGAR is the stronger of the two diffusion legs and it is being improved here.
The weaker leg is trade press: **9 documents, ever, from a manual quarterly
export.** No amount of EDGAR depth addresses that, and it is the larger half of
why diffusion reads thin.

`adoption_new` is also still hardcoded to `0` at `metrics.py:123` — a diffusion
measure that was specified and never built.
