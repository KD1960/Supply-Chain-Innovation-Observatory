# ABI/INFORM retired, 2026-09-03

**Decision: ProQuest ABI/INFORM is no longer collected.** Thirteen observations
across twelve documents were removed from the database, the fifteen export
files were moved out of the import path, and every published report was
regenerated without them.

## Why

ASU Library's business librarian, answering a question about text and data
mining of licensed resources, with the electronic-resources and licensing
librarians copied:

> Clarivate, the owner of ProQuest > ABI/INFORM, does not allow text & data
> mining, and the language, in my view, applies to metadata as well: "Unless
> expressly permitted elsewhere in the Agreement, you may use the Products for
> your internal use only and shall not ... perform any text or data mining or
> indexing of the Products or any underlying data."

The librarian also states that TDM Studio, a separate ProQuest subscription ASU
holds, is the only route ProQuest sanctions for this, and that ABI/INFORM is
included in it — with exceptions, most notably the Financial Times.

What this project was doing is squarely inside that prohibition: a person ran
generated queries, exported RIS, and the pipeline matched patterns against the
records and published counts derived from them. That the export was manual does
not help — the librarian's reading covers the metadata, and the matching and
counting is the mining.

## What was removed

| | Before | After |
|---|---|---|
| Observations | 2,324 | 2,311 |
| ABI/INFORM observations | 13 | 0 |
| Sources | 11 | 10 |
| Evidence families | 9 | 8 (no trade press) |

Trade press was the thinnest leg in the corpus — 2026-Q2 held one trade article
against 328 research documents — so the corpus loses 0.6% of its observations
and one evidence family. The family mattered more than the count: `trade` was
the only non-government, non-academic voice, and the diffusion stage is now
carried by SEC filings and Hacker News alone.

## How it is enforced

- `sources.yaml` carries a `retired:` field on the entry, holding the reason
  and the conditions that reverse it. The entry, its query and its batching
  are kept, not deleted: the machinery has to work the day the answer changes.
- `--export-queries` does not offer a retired source, and says on the sheet
  that it exists and why it is not offered. Silence would have someone
  re-adding it next year.
- `--import-manual` refuses an export from a retired source by name, so a file
  left in `data/manual/` cannot be ingested by the next rebuild.
- Appendix B of the report no longer lists it as a source for any stage. A
  table of which sources feed which stage is a coverage claim.
- The files sit in `data/withdrawn/abi_inform-2026-09-03/`, which nothing
  reads. They were lawfully exported for internal use and are the record of
  what had been collected.

## What reverses this

Either of:

1. **TDM Studio.** The same content, drawn through the route ProQuest
   sanctions. The open question is cadence: this project collects weekly and
   TDM Studio is a project-based analytical environment, so the shape of a
   weekly or quarterly pull needs to be established before the source returns.
   Financial Times is not in it.
2. **A written answer from the licensing librarian** that a human-run export,
   counted locally and reported as aggregate counts, is not text or data mining
   under the agreement.

## Not resolved by this

**Scopus is the same question with a different answer.** Elsevier provides free
API keys to academic researchers and treats the API as the sanctioned route;
the librarian quotes the terms forbidding robots, spiders and crawlers for
continuous automated retrieval, and says "any other text & data mining activity
would violate the Elsevier terms". This project currently reaches Scopus by
hand-exported RIS — 421 observations from 349 records, its largest supplemental
source. Moving to the API removes the ambiguity and the hand work. That is the
next piece of work.

## Closed by the same answer

- **Web of Science** — ASU terminated the subscription on 2020-12-31. No access.
- **Factiva** — ASU does not subscribe.
- **NexisUni** — programmatic access prohibited without written permission, and
  ASU holds no LexisNexis API subscription. Excessive manual downloading can
  have ASU cut off.
- **Lightcast** — not a library resource; ask career services.
