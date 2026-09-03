# Does Scopus still add anything over OpenAlex? Measured 2026-09-03

**Yes. 159 matched documents that OpenAlex does not have — 46% of Scopus's own
matched set.** The Scopus API collector is worth building; Scopus is not a
duplicate of OpenAlex.

## Why the question came up

`observatory/collectors/openalex.py` says in its own docstring that it
"replaces the Scopus workflow it was built beside", on three measured grounds:
no hand exports, real publication dates rather than issue years, and open
abstracts rather than licensed ones. Read on its own, that says the 421
remaining Scopus observations are the leftover of a workflow already decided
against — and that building an API collector for it would be rebuilding
something retired.

The library's licensing answer of the same day made the question live: Elsevier
gives academic researchers a free API key and treats the API as the sanctioned
route, so the collector is buildable. Whether it is *worth* building is a
different question, and this project's rule is to measure before building.

## The measurement

Every matched document from each source in the database, compared by DOI:

| | |
|---|---|
| Scopus matched documents | 349 |
| OpenAlex matched documents | 224 |
| Same DOI in both | 190 |
| **Scopus only** | **159** |
| OpenAlex only | 34 |

The Scopus-only documents are spread across the whole collected period rather
than bunched in one quarter: 18 in 2026-02, 17 in 2026-08, 15 in 2026-01, and
so on down.

**What this does not separate.** These are documents the *matcher* accepted,
not documents each source *retrieved*. A paper OpenAlex retrieved but shipped
without an abstract cannot match on its title alone and is therefore absent
here, and would be counted as "Scopus only" even though OpenAlex had the
record. Both readings — real coverage gap, or abstract availability — argue for
keeping Scopus; they differ only in what would fix OpenAlex.

## The licence position, which is better than it looked

Observations store `title`, `url` and `matched_pattern`. There is no abstract
column, and the evidence pages publish a title and a link. Elsevier abstracts
are used to match and are never published, so the exposure that made OpenAlex
attractive — "Scopus licenses its abstracts, so they could not appear in a
published report" — does not arise in what this project actually publishes.

## What happens next

The collector waits for the key rather than being written against a guessed
response shape. When it arrives:

1. Capture one real response and save it as the fixture. `parse` is written
   against that, as every other collector's is.
2. **Measure abstract coverage before adopting**, not retrieval. OpenAlex was
   adopted as a Scopus replacement on retrieval alone, and its abstract
   coverage — the thing that decides whether the matcher can see anything — was
   never checked. That mistake is the reason this file exists.
3. Compare a week fetched through the API against the same week's hand export
   before the hand exports stop.
