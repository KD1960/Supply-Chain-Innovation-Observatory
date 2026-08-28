"""USAspending — federal award dollars and where the work happens.

This is the hardest of the hard signals: money obligated against an award, with
a place of performance. It feeds both the Investment stage and the Build Map.

**Why this queries programmes rather than keywords.** The first version searched
six multi-word phrases and returned 36 awards in a year, none of which matched
anything. The API phrase-matches a multi-word keyword against award prose that
is terse, abbreviated and written by a contracting officer: `port` returns over
a hundred awards in a week where `port infrastructure` returns one.

Widening those keywords is worse, not better. Broad terms retrieve the federal
government's dominant spending -- military logistics services, passenger transit,
highway resurfacing -- so a wider net trades a false zero for thousands of rows
of false signal. That was measured before it was rejected.

What retrieves supply chain money precisely is the assistance listing: the
programme an award was made under. `PROGRAMS` is that list, and every number in
it was pulled live, read, and kept or discarded on what its awards actually say.
It is the same principle as filtering journals by ISSN -- a property of the
container, never of the technology.
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
# whichever `date_type` is named, and under `action_date` the retrievable date
# fields are period-of-performance dates that routinely predate the query window
# by years -- an award last modified in August 2026 reports a Start Date of
# August 2023. Keying an observation to that files it under a week the query
# never asked about. `last_modified_date` is filterable and retrievable under the
# same name, so the two agree by construction.
DATE_TYPE = "last_modified_date"
DATE_FIELD = "Last Modified Date"

FIELDS = [
    "Award ID", "Recipient Name", "Award Amount", "Description",
    "Place of Performance State Code", "CFDA Number", DATE_FIELD,
]
SORT_FIELD = "Award Amount"

# Assistance awards only. `award_type_codes` is rejected outright when it mixes
# groups -- "award_type_codes must only contain types from one group" -- so
# contracts cannot simply be appended here; they would need a second query.
# They do not get one: the contract space that these programmes cover is
# dominated by defence logistics services, which is a different subject wearing
# similar words.
GRANT_TYPE_CODES = ["02", "03", "04", "05"]

# Programmes that fund the movement of goods. Each was queried live on
# 2026-08-27, its title resolved, and a sample of its awards read.
PROGRAMS: dict[str, str] = {
    "20.823": "Port Infrastructure Development Program",
    "20.816": "United States Marine Highway Grants",
    "20.817": "Air Emissions and Energy Initiative",
    "66.051": "Clean Ports Program",
    "20.325": "Consolidated Rail Infrastructure and Safety Improvements",
    "20.337": "Consolidated Rail Infrastructure and Safety Improvements",
    "20.327": "Railroad Crossing Elimination",
    "20.934": "Nationally Significant Freight and Highway Projects",
    # Mixed: RAISE funds freight rail corridors alongside pedestrian bridges and
    # culverts. Kept because the freight share is real, and left to the text
    # matcher rather than given any direct attribution below.
    "20.933": "National Infrastructure Investments",
}

# Rejected, with the reason, so that a later reader does not re-add one on the
# strength of its name. Intercity passenger rail alone moved $16.8B against the
# Port Infrastructure Development Program's $1.4B; admitting it would drown the
# thing it was added to find.
EXCLUDED_PROGRAMS: dict[str, str] = {
    "20.326": "Federal-State Partnership for Intercity Passenger Rail — moves people, not goods",
    "20.315": "National Railroad Passenger Corporation Grants — Amtrak operations",
    "20.314": "Railroad Development — passenger corridor development",
    "20.205": "Highway Planning and Construction — every road in the country, not freight",
    "20.500": "Federal Transit Capital Investment Grants — passenger transit",
    "20.507": "Federal Transit Formula Grants — passenger transit vehicles",
    "20.525": "Federal Transit State of Good Repair — passenger transit",
    "66.045": "Clean School Bus Program — school buses, despite the clean-vehicle wording",
    "20.814": "Assistance to Small Shipyards — shipbuilding capacity, not goods movement",
    "20.807": "Merchant Marine Academy programmes — education",
    "81.086": "DOE Conservation Research and Development — too broad to attribute",
}

# The one place the query itself is evidence. A programme appears here only when
# its entire purpose is a tracked technology, because federal award prose
# describes civil works rather than technologies and would otherwise never
# match. Ports are dredged far more often than they are automated, so 20.823 is
# deliberately absent: it funds port capability in general and has to earn its
# match from the text like anything else.
PROGRAM_EVIDENCES: dict[str, tuple[str, ...]] = {
    "66.051": ("port_electrification",),   # zero-emission port equipment and shore power
    "20.817": ("port_electrification",),   # MARAD Air Emissions and Energy Initiative
}


class UsaspendingCollector(BaseCollector):
    name = "usaspending"
    rate_limit_seconds = 2.0

    def payload_for(self, week: str, page: int) -> dict:
        start, end = config.week_bounds(week)
        start -= dt.timedelta(days=config.LOOKBACK_DAYS)
        return {
            "filters": {
                "time_period": [
                    {"start_date": start.isoformat(), "end_date": end.isoformat(),
                     "date_type": DATE_TYPE}
                ],
                "award_type_codes": GRANT_TYPE_CODES,
                "program_numbers": list(PROGRAMS),
            },
            "fields": FIELDS,
            "page": page,
            "limit": PAGE_SIZE,
            "sort": SORT_FIELD,
            "order": "desc",
            "subawards": False,
        }

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        limiter = http.RateLimiter(self.rate_limit_seconds)
        for page in range(1, MAX_PAGES + 1):
            payload = self.payload_for(week, page)
            response = http.fetch_post(session, API_URL, payload, limiter=limiter)
            yield RawPage(response.url, response.status, response.text, "json")
            metadata = json.loads(response.text).get("page_metadata") or {}
            if not metadata.get("hasNext"):
                break
        else:
            # MAX_PAGES exhausted with more waiting. Silent truncation is this
            # project's oldest failure mode, so it gets said out loud.
            print(f"  usaspending: {week} hit the {MAX_PAGES}-page cap with more "
                  f"awards available; the week is undercounted")

    def parse(self, text: str) -> list[Document]:
        payload = json.loads(text or "{}")
        documents = []
        for result in payload.get("results", []) or []:
            award_id = result.get("Award ID")
            if not award_id:
                continue
            point = geo.centroid(result.get("Place of Performance State Code"))
            program = (result.get("CFDA Number") or "").strip()
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
                    evidences=PROGRAM_EVIDENCES.get(program, ()),
                    evidence_note=f"cfda:{program}" if program else None,
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
