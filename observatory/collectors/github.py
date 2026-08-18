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
from typing import Iterator

from .. import config, http
from .base import BaseCollector, Document, RawPage

API_URL = "https://api.github.com/search/repositories"
PAGE_SIZE = 100
MAX_PAGES = 5

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
                    "q": f"{query} {window}",
                    "per_page": PAGE_SIZE,
                    "page": page,
                    "sort": "stars",
                    "order": "desc",
                }
                response = http.fetch(session, API_URL, params=params,
                                      headers=headers, limiter=limiter)
                yield RawPage(response.url, response.status, response.text, "json")
                if len(self.parse(response.text)) < PAGE_SIZE:
                    break

    def parse(self, text: str) -> list[Document]:
        payload = json.loads(text or "{}")
        documents = []
        for item in payload.get("items", []) or []:
            full_name = item.get("full_name")
            if not full_name:
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
