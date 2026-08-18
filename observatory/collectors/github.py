"""GitHub repository search — the Experiment stage's developer signal.

The one source in this project that moves in days. A patent lags eighteen
months and an SEC filing a quarter; a repository appears the week someone
starts building.

Unlike every other collector here, GitHub's search accepts an explicit
`created:` range, so this one backfills a year of history as readily as it
fetches the current week.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from typing import Iterator

from .. import config, http
from .base import BaseCollector, Document, RawPage

API_URL = "https://api.github.com/search/repositories"
PAGE_SIZE = 100
MAX_PAGES = 5
MAX_RESULTS = PAGE_SIZE * MAX_PAGES

# A copied class project rarely gets starred; a real one usually does. This is
# the owner's threshold for excluding clone cohorts (e.g. the 46-copy
# VendorBridge hackathon project) from the matched signal.
#
# `parse` is the authoritative filter: it applies to whatever raw JSON is on
# disk, so the rule is deterministic regardless of how that page was fetched,
# and a year of raw fetched before this threshold existed still re-derives the
# new answer under an offline `--rebuild`. The `stars:>=MIN_STARS` query
# qualifier below is only an optimization on top of that -- it shrinks what a
# future fetch pulls down (helping with the page cap), but fetching against an
# older or different query is not what makes an item pass or fail.
MIN_STARS = 1

# Broad sweeps rather than one query per technology: the request count stays
# flat as the watchlist grows, and the matcher does the narrowing — the same
# shape as the arXiv and Hacker News collectors.
ANCHOR_QUERIES = (
    "supply chain",
    "logistics",
    "warehouse automation",
    "freight",
    "inventory management",
    "procurement",
)


class GithubCollector(BaseCollector):
    name = "github"
    rate_limit_seconds = 2.5  # authenticated search allows 30/minute

    def date_range(self, week: str) -> str:
        start, end = config.week_bounds(week)
        start -= dt.timedelta(days=config.LOOKBACK_DAYS)
        return f"created:{start.isoformat()}..{end.isoformat()}"

    def auth_headers(self) -> dict:
        """The token goes in a header, never a query parameter.

        `raw_fetch` records the resolved URL of every request, so a token in
        the query string would be written to the database and the raw tree.
        """
        return {
            "Authorization": f"Bearer {config.require_env('GITHUB_TOKEN')}",
            "Accept": "application/vnd.github+json",
        }

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        limiter = http.RateLimiter(self.rate_limit_seconds)
        headers = self.auth_headers()
        window = self.date_range(week)
        for query in ANCHOR_QUERIES:
            for page in range(1, MAX_PAGES + 1):
                params = {
                    "q": f"{query} {window} stars:>={MIN_STARS}",
                    "per_page": PAGE_SIZE,
                    "page": page,
                    "sort": "stars",
                    "order": "desc",
                }
                response = http.fetch(session, API_URL, params=params,
                                      headers=headers, limiter=limiter)
                yield RawPage(response.url, response.status, response.text, "json")
                payload = _payload(response.text)
                if page == 1:
                    notice = truncation_warning(query, week, payload)
                    if notice:
                        print(notice, file=sys.stderr)
                # Against the raw item count, not the parsed documents: an item
                # dropped for a missing `full_name` would otherwise look like a
                # short page and stop the anchor early, discarding results the
                # cap would still have allowed -- and parsing here would parse
                # every page a second time for an answer the payload already has.
                if len(payload.get("items") or []) < PAGE_SIZE:
                    break

    def parse(self, text: str) -> list[Document]:
        payload = json.loads(text or "{}")
        documents = []
        for item in payload.get("items", []) or []:
            full_name = item.get("full_name")
            if not full_name:
                continue
            # Missing/null stargazers_count is treated as zero, not skipped --
            # an absent field must not slip through as if it were starred.
            if (item.get("stargazers_count") or 0) < MIN_STARS:
                continue
            body = " ".join(
                part for part in (item.get("description"), item.get("language")) if part
            )
            documents.append(
                Document(
                    doc_id=f"github:{full_name}",
                    date=(item.get("created_at") or "")[:10] or None,
                    title=full_name,
                    text=body,
                    url=item.get("html_url"),
                    amount=float(item.get("stargazers_count") or 0),
                )
            )
        return documents


def _payload(text: str) -> dict:
    try:
        payload = json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def truncation_warning(query: str, week: str, payload: dict) -> str | None:
    """The line to print when an anchor query has more results than the cap fetches.

    `MAX_PAGES` harvests at most `MAX_RESULTS` repositories per anchor, sorted
    by stars, and on live data most anchors exceed that every week. So
    `gh_repos_new` is not "matching repos created in week" but "matching repos
    among the top MAX_RESULTS per anchor by stars" -- and the shortfall grows
    as the repository population does, which puts a trend in the bias itself,
    across exactly the series z-scores and acceleration are computed over.

    Changing the cap changes what the signal means, and that is the owner's
    call. Saying out loud that the cap bit is not, so every truncated anchor
    reports itself once, on the page where GitHub states the total.
    """
    total = payload.get("total_count")
    try:
        total = int(total)
    except (TypeError, ValueError):
        return None
    if total <= MAX_RESULTS:
        return None
    return (f"  ! github truncated {week} {query!r}: "
            f"total_count {total}, fetched at most {MAX_RESULTS}")
