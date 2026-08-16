"""arXiv Atom API.

Two sweeps per week rather than one query per technology: a category sweep over
the robotics/systems/optimisation categories, and a keyword sweep over supply
chain language across all categories. Fetching a corpus rather than per-term
results keeps request counts flat as the watchlist grows, and gives the rising-
term discovery step something to mine.
"""

from __future__ import annotations

import datetime as dt
import re
import xml.etree.ElementTree as ET
from typing import Iterator

from .. import config, http
from .base import BaseCollector, Document, RawPage

API_URL = "http://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
PAGE_SIZE = 200
MAX_PAGES = 10

CATEGORY_SWEEP = "cat:cs.RO OR cat:eess.SY OR cat:math.OC OR cat:cs.MA"
KEYWORD_SWEEP = (
    'all:"supply chain" OR all:logistics OR all:freight OR all:warehouse '
    'OR all:procurement OR all:"last mile"'
)
SWEEPS = (CATEGORY_SWEEP, KEYWORD_SWEEP)

_WHITESPACE = re.compile(r"\s+")


class ArxivCollector(BaseCollector):
    name = "arxiv"
    rate_limit_seconds = 3.0  # arXiv asks for one request every three seconds

    def date_filter(self, week: str) -> str:
        """arXiv wants a half-open window, so the upper bound is the Monday after."""
        start, end = config.week_bounds(week)
        end_exclusive = end + dt.timedelta(days=1)
        return (
            f"submittedDate:[{start.strftime('%Y%m%d')}0000+TO+"
            f"{end_exclusive.strftime('%Y%m%d')}0000]"
        )

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        limiter = http.RateLimiter(self.rate_limit_seconds)
        for sweep in SWEEPS:
            for page in range(MAX_PAGES):
                params = {
                    "search_query": f"({sweep}) AND {self.date_filter(week)}",
                    "start": page * PAGE_SIZE,
                    "max_results": PAGE_SIZE,
                    "sortBy": "submittedDate",
                    "sortOrder": "ascending",
                }
                response = http.fetch(session, API_URL, params=params, limiter=limiter)
                yield RawPage(
                    url=response.url, status=response.status,
                    text=response.text, extension="xml",
                )
                if len(self.parse(response.text)) < PAGE_SIZE:
                    break

    def parse(self, text: str) -> list[Document]:
        root = ET.fromstring(text)
        documents = []
        for entry in root.findall(f"{ATOM}entry"):
            raw_id = _text(entry, f"{ATOM}id")
            if not raw_id:
                continue
            bare_id = raw_id.rsplit("/", 1)[-1].split("v")[0]
            published = _text(entry, f"{ATOM}published") or ""
            documents.append(
                Document(
                    doc_id=f"arxiv:{bare_id}",
                    date=published[:10] or None,
                    title=_clean(_text(entry, f"{ATOM}title")),
                    text=_clean(_text(entry, f"{ATOM}summary")),
                    url=f"https://arxiv.org/abs/{bare_id}",
                )
            )
        return documents


def _text(element, tag: str) -> str | None:
    found = element.find(tag)
    return None if found is None or found.text is None else found.text


def _clean(value: str | None) -> str | None:
    return None if value is None else _WHITESPACE.sub(" ", value).strip()
