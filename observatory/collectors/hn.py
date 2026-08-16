"""Hacker News via the Algolia search API.

Anchor queries rather than per-technology queries: seven broad supply chain
terms give a corpus that the matcher then narrows. This is the "attention" side
of the substance-versus-attention comparison.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Iterator

from .. import config, http
from .base import BaseCollector, Document, RawPage

API_URL = "https://hn.algolia.com/api/v1/search_by_date"
PAGE_SIZE = 100
MAX_PAGES = 10

ANCHOR_QUERIES = (
    "supply chain",
    "logistics",
    "freight",
    "warehouse",
    "robotics",
    "procurement",
    "shipping",
)


class HackerNewsCollector(BaseCollector):
    name = "hn"
    rate_limit_seconds = 1.0

    def numeric_filters(self, week: str) -> str:
        """A week-long lookback catches stories indexed after the last run."""
        start, end = config.week_bounds(week)
        start = start - dt.timedelta(days=config.LOOKBACK_DAYS)
        start_epoch = int(
            dt.datetime.combine(start, dt.time.min, tzinfo=dt.timezone.utc).timestamp()
        )
        end_epoch = int(
            dt.datetime.combine(
                end + dt.timedelta(days=1), dt.time.min, tzinfo=dt.timezone.utc
            ).timestamp()
        )
        return f"created_at_i>={start_epoch},created_at_i<{end_epoch}"

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        limiter = http.RateLimiter(self.rate_limit_seconds)
        filters = self.numeric_filters(week)
        for query in ANCHOR_QUERIES:
            for page in range(MAX_PAGES):
                params = {
                    "query": query,
                    "tags": "story",
                    "numericFilters": filters,
                    "hitsPerPage": PAGE_SIZE,
                    "page": page,
                }
                response = http.fetch(session, API_URL, params=params, limiter=limiter)
                yield RawPage(response.url, response.status, response.text, "json")
                payload = json.loads(response.text)
                if page + 1 >= payload.get("nbPages", 1):
                    break

    def parse(self, text: str) -> list[Document]:
        payload = json.loads(text)
        documents = []
        for hit in payload.get("hits", []):
            object_id = hit.get("objectID")
            if not object_id:
                continue
            documents.append(
                Document(
                    doc_id=f"hn:{object_id}",
                    date=(hit.get("created_at") or "")[:10] or None,
                    title=hit.get("title"),
                    text=hit.get("story_text") or "",
                    url=hit.get("url")
                    or f"https://news.ycombinator.com/item?id={object_id}",
                    amount=float(hit.get("points") or 0),
                )
            )
        return documents
