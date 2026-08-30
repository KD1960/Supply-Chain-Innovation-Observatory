# Precision audit — lexicon v7

**Date:** 2026-08-30 · **Sample:** 105 observations, twelve per source, seed 20260830
**Coders:** two, independent · **Agreement:** 88%, Cohen's kappa 0.79
**Adjudicated precision: 51%**
**Sheet:** `output/precision-audit-sample.md`, reproducible from the seed

Loosening the lexicon at v7 added about 1,100 observations. This measures what
that cost. The question asked of each row was only: *does this document support
counting it under that technology?*

## Second coder, and a correction to the headline

A second coder worked the same sheet blind, without access to the first
coder's judgments or to this document. Codes are in `docs/audit/`.

| | judgeable | correct | precision |
|---|---|---|---|
| coder A | 93 | 55 | 59% |
| coder B | 91 | 51 | 56% |
| **adjudicated** | **91** | **47** | **51%** |

Raw agreement 88%, Cohen's kappa **0.79** across three codes and 0.75 on the
two substantive ones. That is substantial agreement, and both coders
independently marked the same twelve EDGAR rows unjudgeable — which is the
strongest evidence that "the filing text is not recoverable" is a fact about
the data rather than one coder's caution.

**Of thirteen disagreements, nine resolved against coder A and none against
coder B.** That is not noise, it is a leniency bias, and its direction is
exactly what should have been expected: coder A wrote the patterns being
judged. Examples of what it let through — a repository that *integrates with*
S/4HANA counted as ERP; a security advisory about a transportation management
product counted as AI transportation management; a paper about visual mapping
counted as a digital twin on a passing mention; a study of vessel fleet
decarbonisation counted as port electrification.

**The headline figure is 51%, not 59%.** The single-coder estimate was
optimistic by eight points. Four PTC disagreements were left standing rather
than adjudicated: coder B's reasoning — that freight railroads are in scope —
is fair, and it is precisely why the owner moved PTC to its own technology at
lexicon v8. That disagreement was about the category, not the rows.

## Result (coder A, retained for the per-source breakdown)

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

**Two coders now, but both are the same model.** The agreement statistic is
real and the leniency bias it exposed was real. What it cannot rule out is a
bias both coders share — a human reading the same sheet might find both of
them wrong in the same direction. A student coder on this sheet remains worth
an hour.

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
