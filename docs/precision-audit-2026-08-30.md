# Precision audit — lexicon v7

**Date:** 2026-08-30 · **Sample:** 105 observations, twelve per source, seed 20260830
**Coder:** Claude (single coder — see *Limits* below)
**Sheet:** `output/precision-audit-sample.md`, reproducible from the seed

Loosening the lexicon at v7 added about 1,100 observations. This measures what
that cost. The question asked of each row was only: *does this document support
counting it under that technology?*

## Result

| source | judged | correct | precision |
|---|---|---|---|
| abi_inform | 9 | 9 | **100%** |
| github | 12 | 12 | **100%** |
| scopus | 12 | 8 | 67% |
| lens | 12 | 7 | 58% |
| arxiv | 12 | 6 | 50% |
| hn | 12 | 6 | 50% |
| usaspending | 12 | 6 | 50% |
| federalregister | 12 | 1 | **8%** |
| edgar | 12 | — | not judgeable |
| **total** | **93** | **55** | **59%** |

Trade press and GitHub are the cleanest sources in the corpus, which is the
reverse of what the star-count evidence suggested about GitHub. A repository
description is a sentence written to say what the thing is; that turns out to
be excellent matching material even when the repository itself is inert.

## Six systematic faults, in order of damage

**1. `rail_intermodal_tech` is a Positive Train Control firehose.** Eleven of
twelve Federal Register documents are FRA notices of PTC system amendments —
Long Island Rail Road, New Jersey Transit, MBTA four times, Amtrak, PATH,
Brightline twice. PTC is train control, not intermodal technology, and most of
these railroads are passenger. The technology is measuring the FRA's paperwork
cadence. This is the whole reason it reads 100% Federal Register.

**2. `agentic_procurement` on Hacker News is 0 of 5.** `agentic (ai|...)`
matches every AI-startup post: an agentic-memory database, a "Vercel for
agents", an AI threat-modelling tool, a job advertisement. The same generic-term
failure that `generative ai` showed, in a term that was never revised.

**3. `G06K7` is too broad for `item_level_rfid`.** The class is *reading record
carriers*, which covers barcodes, optical codes and magnetic stripes as well as
RFID. It attributed a blockchain shipping patent, a GPS asset-tracking hub, an
optical-code Kanban shelf, and an apartment access-control system. Three of five
sampled were wrong.

**4. `last[- ]mile` has two false friends**, and this one is mine — v7 broadened
it from `last[- ]mile delivery`. Hacker News: *"the last mile tends to be where
things stall"*, about deploying software; the gate passed it because "shipping"
appears. USAspending: a "LAST MILE RAIL PROJECT" building a 6,100-foot spur.

**5. `critical infrastructure` matches physical infrastructure.** For
`infrastructure_security` — meant to be OT and control-system security — it
caught catenary pole foundations and a wharf reconstruction in San Juan.

**6. `operations_research` absorbs passenger rail.** Urban rail transit fleet
planning and train speed-trajectory optimisation are operations research, and
they are not supply chain.

## Limits — three, and they matter

**EDGAR cannot be judged from stored evidence.** The raw response holds a
company name and a form type; the filing text is not there. Twelve rows are
excluded rather than guessed at. EDGAR is precise *by construction* — the
collector searches for the exact phrase, so the filing provably contains it —
but "contains the phrase" is not the same as "is about the technology", and
this audit cannot tell them apart.

**One coder, and it is the same model that wrote the patterns.** The method
this project sanctions is independent coders with a reported agreement
statistic. This is one pass by one coder with an obvious stake in the answer.
Treat 59% as an order of magnitude, not a measurement. A second coder on the
same sheet would cost an hour and would make the number real.

**Twelve per source is thin.** Enough to find a fault that affects a third of a
source's rows, nowhere near enough to separate 55% from 65%.

## What it does establish

The v7 broadening was not free. It bought real recall — digital twins 10 to 89,
three of which are genuine trade-press deployment stories nothing else saw —
and it also let `last mile` into a Hacker News post about software deployment.

More usefully, the faults are **specific and mostly older than v7**. Five of the
six predate it. They are lexicon errors that no amount of new sources would
have fixed, and the audit found them in an afternoon because the evidence was
on disk the whole time.
