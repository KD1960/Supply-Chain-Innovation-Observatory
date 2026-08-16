"""Federal Register documents API.

Filtered by transport and trade agencies rather than by keyword, so the corpus
is bounded and every document is plausibly about physical logistics capability.
This is the regulatory half of the deployment signal.
"""

from __future__ import annotations

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
    "customs-and-border-protection",
    "federal-highway-administration",
    "energy-department",
    "commerce-department",
)


class FederalRegisterCollector(BaseCollector):
    name = "federalregister"
    rate_limit_seconds = 1.0

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        limiter = http.RateLimiter(self.rate_limit_seconds)
        start, end = config.week_bounds(week)
        for page in range(1, MAX_PAGES + 1):
            params = [
                ("per_page", PAGE_SIZE),
                ("page", page),
                ("order", "oldest"),
                ("conditions[publication_date][gte]", start.isoformat()),
                ("conditions[publication_date][lte]", end.isoformat()),
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
                    entity_id=str(first_agency["id"]) if first_agency.get("id") else None,
                )
            )
        return documents
