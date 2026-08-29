# Which ProQuest scope to search

**Status:** open. Two guesses have been wrong; this settles it by measurement.

## What is known

For Supply Chain Dive, 2026-Q3, with the same ~50 trade terms:

| Term form | Articles returned |
|---|---|
| unfielded — `"digital twin"` | **19** |
| `FT("digital twin")` | **13** |

So the two are different, partly overlapping sets. ProQuest's default scope
excludes the article body; `FT()` searches only the article body. Neither is
"everywhere", and the union of the two is probably larger than either.

## The test

One publication, one common term, five queries. Record the count each returns.

    1.  PUB.EXACT("Supply Chain Dive") AND "digital twin"
    2.  PUB.EXACT("Supply Chain Dive") AND FT("digital twin")
    3.  PUB.EXACT("Supply Chain Dive") AND ALL("digital twin")
    4.  PUB.EXACT("Supply Chain Dive") AND ("digital twin" OR FT("digital twin"))
    5.  PUB.EXACT("Supply Chain Dive")

Query 5 is the denominator: every article the publication published in the
period, with no term filter at all. It matters as much as the others, because
it says whether a low count means a narrow filter or a small corpus.

## What the answers decide

- Whichever of 1–4 is largest becomes `lists.trade_terms.each` in
  `sources.yaml`. If 4 wins, the wrapper becomes `("{}" OR FT("{}"))`.
- If 3 or 4 returns a great deal more than 1, the current exports are
  substantially undercollected and the quarter should be re-run.
- **The denominator needs re-measuring.** The 3,460 figure that made 19 look
  impossibly low was taken under `PUB(...)`, which matched partially and pulled
  in other publications -- including an academic journal already covered by
  Scopus. Under `PUB.EXACT` the true figure may be far smaller, and 19 of it
  may be reasonable.

## If the counts stay low after all this

Then the finding is about the corpus rather than the query: Supply Chain Dive
covers tariffs, labour, earnings and M&A alongside technology, and technology
may simply be a small share of it. That is worth knowing and worth reporting,
but it is a conclusion to reach after the scope question is settled, not
before.
