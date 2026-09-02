# Would CRA improve precision here?

**Status:** tested 2026-09-03 before any spec or workflow change, at the
owner's instruction. **Rejected the same day — CRA is not being added in any
form, including the stored-flag option this document recommends below.** The
recommendation is left as written because it is what the measurement supported;
the decision not to take it is the owner's, on cost against a 0.70 AUC and a
42% coverage ceiling. Reverse only if the ABI/INFORM export is fixed and the
short-text sources gain real abstracts, which is what makes the ceiling.

Crawdad classic (`~/Claude/Projects/Crawdad/app/js`), the deterministic
implementation of Centering Resonance Analysis — not Crawdad NLP, which is
LLM-first and could not go in a weekly run that has to be reproducible.

## The question

Every false positive the 2026-09-02 audit found was a **passing mention**: a
visual-mapping paper matched on "digital twin generation", a secure-coding
grant matched on "critical infrastructure", a port award matched on
"greenhouse gas emissions" appearing as a *reported metric*. Presence-matching
cannot tell centre from periphery. CRA influence is exactly that distinction,
so the question is whether it separates the audit's Y from its N.

## Method

The 132-item audit sample, its 120 coded items, and CRA run over each with
`interSentenceLinking` off, stemming on — the JHC 2002 defaults. For each item,
the influence of the highest-scoring content word inside the matched span,
looked up in that document's own CRA network.

79 items had the ≥100 words CRA needs; 67 of those had a span word that
appeared in the network. Y 47, N 20.

## Result: real signal, moderate strength

| feature | AUC |
|---|---|
| rank in document (inverted) | **0.715** |
| percentile rank | 0.704 |
| influence ÷ document max | 0.702 |
| raw influence | 0.694 |
| in the document's top 10 | 0.638 |

All within noise of each other at n=67. Take it as **AUC ≈ 0.70**: better than
chance, well short of decisive.

Correct items have median influence 0.066 against 0.029 for wrong ones — a real
gap, and heavily overlapping distributions.

## What it would cost to use as a filter

| drop below | items kept | precision | true positives lost |
|---|---|---|---|
| — | 67 | 70.1% | 0 |
| raw 0.02 | 54 | 75.9% | 6 of 47 |
| raw 0.03 | 45 | 80.0% | 11 of 47 |
| ÷max 0.10 | 45 | 80.0% | 11 of 47 |
| ÷max 0.20 | 31 | 83.9% | 21 of 47 |

**Roughly six precision points for thirteen per cent of the true positives, or
ten points for twenty-three per cent.** For comparison, retiring two
technologies and tightening two bought more precision than that and cost 5.6%
of the corpus, most of which was genuinely wrong.

## Where it works, which is the useful finding

| source | n | AUC |
|---|---|---|
| federalregister | 6 | 1.000 (one N — unreliable) |
| **nsf** | 11 | **0.867** |
| **usaspending** | 11 | **0.750** |
| arxiv | 12 | 0.625 |
| hn | 7 | 0.583 |
| **openalex** | 8 | **0.400** |
| scopus | 12 | — (all correct; nothing to separate) |

The signal is concentrated in the **long federal award texts**, NSF and
USAspending, which run 443 and 470 median words. It is weak on arXiv and
*below chance* on OpenAlex — the two largest research sources. Scopus needs no
help: it coded 12 of 12.

The cells are 6–12 items. Treat the ordering as a direction and none of the
individual figures as a rate.

## What a low score actually catches

Below raw influence 0.02, thirteen items: seven wrong, six correct. The seven
are textbook passing mentions —

- `supply_chain_digital_twin` ← "Digital Twin" at influence **0.0000, rank 165 of 179** in an NSF award about network O-RAN
- `green_logistics` ← "GREENHOUSE GAS EMISSIONS" at rank **38 of 286** in a port construction award, where it is a reported metric
- `infrastructure_security` ← "critical infrastructure" at rank 83 of 143
- `sidewalk_delivery_robots` ← "delivery robots" at rank 53 of 138

That is precisely the failure mode. But it takes six correct items with them,
which is why the recommendation is not a filter.

## Coverage ceiling

CRA needs text. By median words, three sources cannot use it at all: github
(28), abi_inform (26 — we store ProQuest subject terms, not the abstract) and
edgar (13). Those are **965 of 2,324 observations, 42% of the corpus**, and
github alone is a third of everything.

So even a perfect CRA gate would reach 58% of the corpus, and not the part with
the most volume.

## Recommendation

1. **Store it, do not gate on it.** Compute influence at ingest, store it on the
   observation, and surface low-influence matches on the evidence page. That
   keeps every observation, gives the next precision audit a ranked worklist
   instead of a random sample, and costs nothing in recall.
2. **Consider a filter on NSF and USAspending only**, where AUC is 0.87 and
   0.75. That is 82 observations, so the upside is small but the evidence for
   it is the strongest here.
3. **Do not gate arXiv or OpenAlex on it.** The measurement does not support it.
4. **Fix the ABI/INFORM export first.** Storing subject terms instead of
   abstracts costs more than CRA would gain, and it is a template change rather
   than a new subsystem.

## Limits

- 67 items with a score, 47 correct and 20 wrong. Per-source cells of 6–12.
- Coded by this model, so CRA is being validated against a labelling that has
  its own known biases and no independent coder.
- One CRA configuration, the JHC 2002 defaults. No tuning of stemming,
  inter-sentence linking, or the exclude list was attempted.
- The span-word lookup takes the highest-influence content word in the match.
  A multi-word match such as "greenhouse gas emissions" is therefore scored by
  its strongest word, which is the generous reading.
