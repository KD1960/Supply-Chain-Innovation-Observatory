"""USAspending — federal award dollars and where the work happens.

This is the hardest of the hard signals: money obligated against a contract, with
a place of performance. It feeds both the Investment stage and the Build Map.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Iterator

from .. import config, geo, http
from .base import BaseCollector, Document, RawPage

API_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
PAGE_SIZE = 100
MAX_PAGES = 5

# The date field has to be the one the filter uses. `time_period` filters on
# whichever `date_type` is named, and the default (action_date) has no field in
# the response at all; "Start Date" is the period-of-performance start, which
# routinely predates the query window by years. Keying an observation to that
# date files it under a week the query never asked about, so the award lands in
# `observations` and never reaches a count. last_modified_date is filterable and
# retrievable under the same name, so the two agree by construction.
DATE_TYPE = "last_modified_date"
DATE_FIELD = "Last Modified Date"

FIELDS = [
    "Award ID", "Recipient Name", "Award Amount", "Description",
    "Place of Performance State Code", DATE_FIELD,
]

KEYWORDS = (
    "port infrastructure",
    "freight rail",
    "intermodal facility",
    "warehouse automation",
    "truck charging",
    "supply chain resilience",
)


class UsaspendingCollector(BaseCollector):
    name = "usaspending"
    rate_limit_seconds = 2.0

    def payload_for(self, week: str, keyword: str, page: int) -> dict:
        start, end = config.week_bounds(week)
        start -= dt.timedelta(days=config.LOOKBACK_DAYS)
        return {
            "filters": {
                "keywords": [keyword],
                "time_period": [
                    {"start_date": start.isoformat(), "end_date": end.isoformat(),
                     "date_type": DATE_TYPE}
                ],
                "award_type_codes": ["A", "B", "C", "D"],
            },
            "fields": FIELDS,
            "page": page,
            "limit": PAGE_SIZE,
            "sort": "Award Amount",
            "order": "desc",
            "subawards": False,
        }

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        limiter = http.RateLimiter(self.rate_limit_seconds)
        for keyword in KEYWORDS:
            for page in range(1, MAX_PAGES + 1):
                payload = self.payload_for(week, keyword, page)
                response = http.fetch_post(session, API_URL, payload, limiter=limiter)
                yield RawPage(response.url, response.status, response.text, "json")
                metadata = json.loads(response.text).get("page_metadata") or {}
                if not metadata.get("hasNext"):
                    break

    def parse(self, text: str) -> list[Document]:
        payload = json.loads(text or "{}")
        documents = []
        for result in payload.get("results", []) or []:
            award_id = result.get("Award ID")
            if not award_id:
                continue
            point = geo.centroid(result.get("Place of Performance State Code"))
            documents.append(
                Document(
                    doc_id=f"usaspend:{award_id}",
                    date=_date(result.get(DATE_FIELD)),
                    title=result.get("Description") or award_id,
                    text=result.get("Description") or "",
                    url=f"https://www.usaspending.gov/award/{award_id}",
                    entity=result.get("Recipient Name"),
                    entity_id=None,
                    amount=_amount(result.get("Award Amount")),
                    lat=point[0] if point else None,
                    lon=point[1] if point else None,
                )
            )
        return documents


def _date(value) -> str | None:
    """Last Modified Date arrives as a timestamp; the week only needs the day."""
    if not value:
        return None
    return str(value)[:10]


def _amount(value) -> float | None:
    """The API has returned this as both a number and a numeric string."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
