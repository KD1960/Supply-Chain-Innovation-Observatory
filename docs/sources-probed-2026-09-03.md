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
