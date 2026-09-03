# Reddit and vendor announcements — probed 2026-09-03

Both were approved in principle by the owner. Neither is built, because the
project's rule is that a candidate carries a measurement, and the measurements
say wait.

## Reddit — viable, but needs credentials before it can be measured

Every unauthenticated route is closed:

| route | result |
|---|---|
| `www.reddit.com/r/supplychain/new.json` | **403 Blocked** |
| `www.reddit.com/r/supplychain/new.rss` | **429 Too Many Requests** |
| `old.reddit.com/…/new.json` | 200, but an HTML interstitial — **0 entries** |
| `old.reddit.com/…/new.rss` | 200, HTML again — **0 entries** |
| `oauth.reddit.com` without a token | 403 |

Hacker News, the existing collector, answered 200 with real content from the
same machine at the same moment, so this is Reddit's policy and not the
network.

**The two 200s are the interesting part.** `old.reddit.com` returns HTTP 200
with 352KB of "Welcome to Reddit" HTML and zero entries. A collector written
against it would report a healthy fetch and an observed zero every week —
exactly the empty-but-valid-200 failure the `empty` status was added for on
2026-09-01. It was nearly reported here as a working route.

**What it needs:** a registered Reddit app at `reddit.com/prefs/apps`
(script type), giving a client id and secret for `.env` alongside
`GITHUB_TOKEN`, and an OAuth token exchange in the collector. Reddit's Data API
free tier is 100 queries per minute and is for non-commercial use; this is
academic research published from a public repository, which should qualify, but
the clause is worth reading before committing.

**Not measurable until then.** Volume and match rate are unknown. HN's match
rate is 0.8%, and the expectation was that Reddit would roughly double the
community leg — but that is an expectation, not a measurement.

## Vendor announcements — do not build yet, and the probe shows why

Eight vendor feed URLs were guessed. One answered with a real feed:

| vendor | result |
|---|---|
| **Kinaxis** | HTTP 200, `application/rss+xml`, 10 items, all dated |
| Manhattan | read timeout |
| Descartes | DNS failure |
| Blue Yonder, project44, FourKites, Körber | 404 |
| o9 | 200, HTML, no items |

**The 404s prove nothing.** The URLs were guesses; a 404 says the guess was
wrong, not that the vendor publishes nothing. Concluding otherwise would be the
same error as reading a 200 as success.

**The one feed that worked is the wrong content.** Kinaxis's RSS is their
*blog*, not their newsroom: "Why AI adoption is the wrong thing to celebrate",
"Building a winning team", "Work-life balance". **0 of 10 matched the
watchlist**, against github 3.1% and EDGAR 50.6%. It also carried an item dated
April 2019 among nine from August 2026, so the feed is not a reliable recency
window either.

Product announcements and customer go-lives — the deployment evidence this was
meant to reach — are not in that feed. They are in newsrooms and investor
relations pages whose URLs are not guessable from outside.

## What this means

**This is the first real job for the source-discovery sweep**, specified the
same day in `docs/superpowers/specs/2026-09-03-source-discovery-design.md`.
Finding the right URL for eight vendors, checking whether items carry their own
dates, and sampling twenty each against the watchlist is precisely the proposal
bar that spec sets — and it is not something URL guessing can do.

Reddit is the smaller job and is blocked on one action by the owner.

## Reversing this

- **Reddit:** register the app, add the credentials, and the match rate can be
  measured in an hour.
- **Vendors:** run the discovery sweep once it exists, or hand-collect the eight
  real newsroom URLs. Either way the decision needs the twenty-item sample, not
  a list of homepages.

---

# The three free-and-unbuilt sources, probed the same day

## GDELT — works, is free, and STATUS is wrong about it

`api.gdeltproject.org/api/v2/doc/doc` answered **HTTP 200 with 9,894 bytes of
real JSON, no key**. It is genuinely available.

**STATUS's claim that "the implementation is written" is false.** There is no
`observatory/collectors/gdelt_doc.py` and no `gdelt_geo.py`. Plan 2A specifies
both; neither was ever created, and nothing in git history has ever contained
one. What *does* exist is the downstream plumbing that would consume them:
`normalize.py` declares `media_articles` and `media_deploy` aggregations keyed
on a `gdelt_doc` source, and the tests reference it as a string.

That also explains the process review's §2.4 finding — `media_articles` is
declared in `HARD_SIGNALS` and never written to `weekly_signals`. It is not a
bug in the index; it is a collector that does not exist.

**It is aggressively rate-limited**, which STATUS did get right. Roughly one
request per five seconds; this probe exhausted the budget in under a dozen
calls and started receiving 429s. One earlier call returned **HTTP 200 with a
non-JSON body** — the same empty-but-valid-200 shape as Reddit's, and a third
instance of it in one afternoon.

**Match rate not measured.** The rate limit stopped the sweep before a sample
was complete. That is the one number that decides it, and it is still missing.

**The owner has run GDELT before, on another dashboard, and a query took many
hours to complete.** That is direct operating experience and it outranks this
probe, which measured only whether one call returns in one second. It does not.
A weekly sweep is fifty-odd queries under a rate limit that starts refusing
after a dozen, and the cron job runs Monday at 07:00.

**So GDELT cannot go in the weekly run.** If it is built at all it belongs where
the manual exports are: an occasional, separately-invoked job whose output is
imported, not a collector the Monday job waits on.

## Semantic Scholar — needs a free key

`api.semanticscholar.org/graph/v1/paper/search` returns **429** unauthenticated.
Semantic Scholar issues free API keys on request for higher limits.

The question it must answer is not whether it works but whether it **adds
anything OpenAlex does not**. That is the OpenAlex-versus-Scopus precedent
exactly: OpenAlex survived because its abstract coverage was measured at 99%
against Scopus's 49% on the same twelve journals. Semantic Scholar overlaps
arXiv, OpenAlex and Scopus heavily, and the test is overlap, not availability.

## PatentsView — the endpoint in the plan no longer exists

`search.patentsview.org` has **no DNS record at all**. `api.patentsview.org`
resolves. So beyond the key STATUS is waiting for, the API's shape needs
re-checking before any plan written against it is trusted.

## Ranking, on what is now known

1. **PatentsView.** Would replace the hand-made Lens export, the second-most
   expensive manual step after ABI/INFORM, and patents are a family currently
   resting on 5 observations a quarter. Blocked on a key, and now also on an
   endpoint question, but neither is a design problem.
2. **GDELT.** Free, keyless, and it fills the media gap `render.py` already
   apologises for — but the owner has run it before and a query took hours.
   That rules it out of the weekly run entirely. It would have to be built as
   an occasional job beside the manual exports, which is a bigger change than
   "one collector", and the match rate is still unmeasured.
3. **Semantic Scholar.** Last, because it probably duplicates sources already
   held. Worth a measured overlap test, not a build.

The ranking changed while this document was being written: GDELT led on the
probe and lost on the owner's experience of running it. A single successful
call is not a measurement of a sweep.
