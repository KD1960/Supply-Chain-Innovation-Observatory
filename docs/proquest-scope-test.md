# Which ProQuest scope to search

**Status:** settled 2026-08-29. Recorded because the conclusion reversed two earlier changes.

## The answer

Supply Chain Dive, 2026-Q3, the term "digital twin":

| Query | Articles |
|---|---|
| `PUB.EXACT(...) AND "digital twin"` | **22** |
| `PUB.EXACT(...) AND FT("digital twin")` | **22** |
| `PUB.EXACT(...) AND ("digital twin" OR FT("digital twin"))` | **22** |
| `PUB.EXACT(...) AND ALL("digital twin")` | 1 |
| `PUB.EXACT(...)` — no term filter | **4,706** |

Unfielded and `FT()` are the same search here, so the plain phrase stands and
`FT()` was reverted. `ALL()` is not "anywhere" and must never be used.

**The scope was never the problem.** One term returns 22 on its own, so the
fifty-term query could not have returned 19. Those readings came from
ProQuest's marked-items list accumulating across searches while signed in --
each export carried the previous selections rather than that query's own
results. Clearing the selections between exports is the fix, and
`manual._refuse_overlapping` now refuses the files if it is forgotten.

A term filter is still needed: 4,706 articles in one publication in one quarter
is far past the 1,000-record export limit. Fifty terms at roughly this hit rate
should land in the high hundreds, which fits.

## Two guesses that were wrong

Worth keeping, because both were plausible and both cost a round trip.

- **"ProQuest's default excludes the article body, so wrap terms in FT()."**
  It does exclude it, and wrapping changed nothing.
- **"3,460 articles with only 19 matches means the filter is broken."** The
  3,460 was measured under `PUB(...)`, which matched partially. The real
  denominator is 4,706, and 22 of it for one niche term is unremarkable.

---

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
