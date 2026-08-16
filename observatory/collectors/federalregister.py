"""Federal Register documents API.

Filtered by transport and trade agencies rather than by keyword, so the corpus
is bounded and every document is plausibly about physical logistics capability.
This is the regulatory half of the deployment signal.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Iterator

from .. import config, http
from .base import BaseCollector, Document, RawPage

API_URL = "https://www.federalregister.gov/api/v1/documents.json"
PAGE_SIZE = 100
MAX_PAGES = 20

AGENCY_SLUGS = (
    "transportation-department",
    "federal-motor-carrier-safety-administration",
    "federal-aviation-administration",
    "federal-railroad-administration",
    "maritime-administration",
    "national-highway-traffic-safety-administration",
    "u-s-customs-and-border-protection",
    "federal-highway-administration",
    "energy-department",
    "commerce-department",
)


class FederalRegisterCollector(BaseCollector):
    name = "federalregister"
    rate_limit_seconds = 1.0

    def date_window(self, week: str) -> tuple[str, str]:
        """Inclusive publication-date bounds, opened a week early so documents
        posted after the last run are still picked up."""
        start, end = config.week_bounds(week)
        return (start - dt.timedelta(days=config.LOOKBACK_DAYS)).isoformat(), end.isoformat()

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        limiter = http.RateLimiter(self.rate_limit_seconds)
        gte, lte = self.date_window(week)
        for page in range(1, MAX_PAGES + 1):
            params = [
                ("per_page", PAGE_SIZE),
                ("page", page),
                ("order", "oldest"),
                ("conditions[publication_date][gte]", gte),
                ("conditions[publication_date][lte]", lte),
                ("fields[]", "document_number"),
                ("fields[]", "publication_date"),
                ("fields[]", "title"),
                ("fields[]", "abstract"),
                ("fields[]", "html_url"),
                ("fields[]", "type"),
                ("fields[]", "agencies"),
            ]
            params += [("conditions[agencies][]", slug) for slug in AGENCY_SLUGS]
            response = http.fetch(session, API_URL, params=params, limiter=limiter)
            yield RawPage(response.url, response.status, response.text, "json")
            payload = json.loads(response.text)
            if page >= int(payload.get("total_pages") or 1):
                break

    def parse(self, text: str) -> list[Document]:
        payload = json.loads(text)
        documents = []
        for result in payload.get("results", []) or []:
            number = result.get("document_number")
            if not number:
                continue
            agencies = result.get("agencies") or []
            first_agency = agencies[0] if agencies else {}
            documents.append(
                Document(
                    doc_id=f"fedreg:{number}",
                    date=result.get("publication_date"),
                    title=result.get("title"),
                    text=result.get("abstract") or "",
                    url=result.get("html_url"),
                    entity=first_agency.get("name"),
                    entity_id=str(first_agency["id"]) if "id" in first_agency else None,
                )
            )
        return documents
