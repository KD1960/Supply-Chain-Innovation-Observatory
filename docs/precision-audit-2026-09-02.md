# Precision audit — lexicon v9

**Date:** 2026-09-02 · **Sample:** 132 observations, twelve per source, seed 20260902
**Sheet:** `docs/audit/sample-20260902.md`, rebuild with `--audit-sheet`
**Coder:** one, this model (`docs/audit/coder-d.csv`)
**Judged 120, correct 84 — precision 70%**

## Read this before the number

**It is not comparable with the 51% of 2026-08-30.** Four things changed at
once: the lexicon (v7 → v9), the sample (a fresh draw against a corpus that
grew from ~2,130 to 2,462), the instrument (the old sheet truncated its
evidence at 600 characters, hiding the matched pattern on 24 of 108 items), and
the coder. Nothing here says the lexicon improved. It says this sample, coded
this way, came out at 70%.

**One coder, and not an independent one.** Coders A and B were this model, and
so is this. The owner's pass (`coder-c.csv`) was against the broken sheet and
must not be carried forward. A coder who did not write or approve the patterns
is still the thing this estimate needs.

## By source

| source | judged | correct | precision |
|---|---|---|---|
| scopus | 12 | 12 | **100%** |
| federalregister | 12 | 11 | 92% |
| github | 12 | 10 | 83% |
| openalex | 12 | 9 | 75% |
| arxiv | 12 | 8 | 67% |
| usaspending | 12 | 8 | 67% |
| abi_inform | 12 | 7 | 58% |
| lens | 12 | 7 | 58% |
| hn | 12 | 6 | 50% |
| nsf | 12 | 6 | 50% |
| **edgar** | **0** | — | **not judgeable** |

**EDGAR cannot be audited at all**, and that is structural rather than an
oversight. Filing bodies are megabytes and are never fetched, so an observation
is attributed by the query term that retrieved it and the stored evidence is
the filer's name and the form type. All twelve are coded `x`. EDGAR is 129
observations and the strongest diffusion leg in the project, and its precision
is currently unknown and unmeasurable without fetching filings.

## What is actually wrong: four technologies, not the corpus

| technology | correct | judged |
|---|---|---|
| nearshoring_analytics | **0** | 4 |
| infrastructure_security | **0** | 4 |
| green_logistics | 1 | 6 |
| agentic_procurement | 1 | 5 |

Two of nineteen. These four are close to pure noise and they are 16% of the
judged sample. The rest of the corpus codes well.

Each fails in a recognisable way:

- **nearshoring_analytics** matches the bare words `nearshoring` and
  `reshoring`, which appear in trade-policy stories, factory-automation
  features and robotics grant abstracts. None is an analytics tool. The
  technology's name promises analytics; its patterns ask only for the topic.
- **infrastructure_security** matches `critical infrastructure`, which is
  background phrasing in secure-coding education grants, bridge-inspection
  research and drone roadmaps. It is also the field the owner rejected in
  `6bf0700` as a field rather than a technology, arriving through the back door.
- **green_logistics** matches `greenhouse gas emission(s)?` and
  `decarboni[sz]ation`, which appear as reported *metrics* on federal freight
  awards and as generic framing in energy papers. A port project that measures
  its GHG emissions is not a decarbonisation technology.
- **agentic_procurement** matches `agentic (ai|procurement|sourcing)`, so any
  paper about agentic AI qualifies if the context gate finds a domain word
  anywhere. Two Hacker News items passed on the word *shipping* — in "every
  startup **shipping** a dashboard".

That last one is worth its own line: **the context gate can be opened by a
domain word used in a non-domain sense**, and nothing downstream can tell.

## The other recurring failure: container codes without content

Lens patents are matched by CPC code rather than by text, and five of the
twelve are wrong in a way no text pattern would produce: `cpc:G06V20` retrieved
**a heated seat with a draining element**, and `cpc:G06K7` retrieved event
ticketing access rights over NFC. The container-filter principle works for
ISSNs, where the container is a journal about the subject. A CPC class is
broader than the technology it is standing in for.

## What this does not measure

- One sample, one coder, twelve per source. A stratum of twelve gives a
  precision estimate with a very wide interval; the per-source column is a
  direction, not a figure to quote.
- EDGAR is absent entirely, so the headline covers ten of eleven sources.
- The four failing technologies are diagnosed from four to six items each. The
  pattern in each is clear, but the rate is not.
- No inter-coder agreement, because there is one coder. The 0.79 kappa of the
  previous audit is not inherited by this one.
