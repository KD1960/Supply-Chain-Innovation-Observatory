"""OpenAlex — the journal literature, fetched rather than exported by hand.

This replaces the Scopus workflow it was built beside, and the comparison is
the reason it exists:

- Scopus needed twelve hand-made exports a quarter. This needs none.
- Scopus carried a publication *year*, and that the issue year: of 2,607
  records stamped 2026, 369 were published in 2025 or 2024. Every one had to be
  re-dated through Crossref. OpenAlex gives the publication date directly.
- Scopus licenses its abstracts, so they could not appear in a published
  report. OpenAlex is open data.

The filter is the same ISSN list, for the same reason it was an ISSN list
there: a journal is a container, and filtering by container rather than by
technology keeps the slice reproducible and leaves auto-discovery something to
find. Titles are entered inconsistently and change; ISSNs do not.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Iterator

from .. import config, http
from .base import BaseCollector, Document, RawPage

API_URL = "https://api.openalex.org/works"
PAGE_SIZE = 200
# A week of twelve journals is tens of records; this is a guard against a
# pathological week rather than an expected limit, and it says so when it bites.
MAX_PAGES = 25

# The supply chain, operations management and logistics journals, by ISSN.
# Kept here rather than read from journals.yaml because that file describes what
# a person pastes into Scopus, and this collector is what makes that file
# unnecessary. When Scopus is retired the two become one list.
ISSNS = (
    "0272-6963",   # Journal of Operations Management
    "1523-2409",   # Journal of Supply Chain Management
    "0960-0035",   # International Journal of Physical Distribution & Logistics Mgmt
    "0144-3577",   # International Journal of Operations & Production Management
    "1059-1478",   # Production and Operations Management
    "1366-5545",   # Transportation Research Part E
    "0925-5273",   # International Journal of Production Economics
    "1359-8546",   # Supply Chain Management: An International Journal
    "0020-7543",   # International Journal of Production Research
    "0377-2217",   # European Journal of Operational Research
    "2158-1592",   # Journal of Business Logistics
    "1478-4092",   # Journal of Purchasing and Supply Management
)


class OpenAlexCollector(BaseCollector):
    name = "openalex"
    rate_limit_seconds = 0.15

    def params_for(self, week: str, cursor: str) -> dict:
        start, end = config.week_bounds(week)
        start -= dt.timedelta(days=config.LOOKBACK_DAYS)
        return {
            "filter": (
                f"primary_location.source.issn:{'|'.join(ISSNS)},"
                f"from_publication_date:{start.isoformat()},"
                f"to_publication_date:{end.isoformat()}"
            ),
            "per-page": PAGE_SIZE,
            "cursor": cursor,
            # OpenAlex asks for a contact address and gives politer service in
            # return; the same address every other collector sends.
            "mailto": config.contact_email(),
        }

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        limiter = http.RateLimiter(self.rate_limit_seconds)
        cursor = "*"
        for _ in range(MAX_PAGES):
            response = http.fetch(session, API_URL, params=self.params_for(week, cursor),
                                  limiter=limiter)
            yield RawPage(response.url, response.status, response.text, "json")
            cursor = (json.loads(response.text).get("meta") or {}).get("next_cursor")
            if not cursor:
                return
        print(f"  openalex: {week} hit the {MAX_PAGES}-page cap with more to fetch; "
              f"the week is undercounted")

    @staticmethod
    def abstract(inverted) -> str:
        """OpenAlex ships an abstract as a word-to-positions map.

        Rebuilding it matters more than it looks: on Lens patents, matching on
        the title alone reached 1% where the abstract reached 40%.
        """
        if not inverted:
            return ""
        positions: dict[int, str] = {}
        for word, places in inverted.items():
            for place in places:
                positions[place] = word
        return " ".join(positions[key] for key in sorted(positions))

    def parse(self, text: str) -> list[Document]:
        payload = json.loads(text or "{}")
        documents = []
        for work in payload.get("results", []) or []:
            title = (work.get("title") or "").strip()
            if not title:
                # Nothing the matcher can use, and it would still take a slot
                # in the corpus count that is the denominator of every rate.
                continue
            source = (work.get("primary_location") or {}).get("source") or {}
            doi = work.get("doi") or ""
            documents.append(
                Document(
                    doc_id=f"openalex:{work.get('id', '').rsplit('/', 1)[-1]}",
                    date=work.get("publication_date"),
                    title=title,
                    text=self.abstract(work.get("abstract_inverted_index")),
                    # The DOI outlives an OpenAlex id and is what a reader can
                    # follow without knowing what OpenAlex is.
                    url=doi or work.get("id"),
                    entity=source.get("display_name"),
                    entity_id=None,
                )
            )
        return documents
