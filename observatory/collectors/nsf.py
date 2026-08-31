"""NSF award search — the research half of the investment stage.

USAspending sees infrastructure grants: ports, rail corridors, freight
facilities. It sees nothing upstream of them. NSF sees the money going into the
ideas, which is the part of the investment stage this project had no view of.

Keyless, and every award carries a technical abstract of a few thousand
characters. That last part is why this source exists and SBIR does not: SBIR was
measured at 500 awards and zero matches, because a federal contract description
names the programme and the agency and never the technology. NSF describes the
work.

Measured before building, on Jun-Aug 2026: 190 awards across the keywords
below, 100% with abstracts, 20 matched.

**NSF award volume is seasonal, and October and November 2025 are empty.** A
year's backfill returned 1,184 awards spread very unevenly: 460 in August 2026,
352 in July, and nothing at all in two autumn months. That was checked against
the API directly rather than assumed to be a collector fault -- querying
October 2025 on its own returns zero, where September returns fourteen and
December two. NSF's fiscal year ends on September 30th and its award
announcements cluster around cycle deadlines.

This matters for reading a quarterly report: a quarter holding an autumn is
genuinely thinner in this source, and that is the source's calendar rather than
a change in the world.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Iterator

from .. import config, geo, http
from .base import BaseCollector, Document, RawPage

API_URL = "https://api.nsf.gov/services/v1/awards.json"
PAGE_SIZE = 25          # the API's maximum
MAX_OFFSETS = 8         # 200 awards per keyword per week, a guard not a target

# Domain words, not technology names. The same rule every other collector
# follows: fetch a domain and let the matcher decide what is in it. A query per
# technology would grow with the watchlist and would leave the rising-term
# discovery step nothing it had not already been told to look for.
# Measured on a two-week window rather than guessed. NSF's keyword search ORs
# unquoted words -- "manufacturing automation" returned 295 awards, most of them
# about neither -- and honours a quoted phrase, which returned 15 for
# "supply chain" against 75 unquoted. So multi-word terms are quoted.
#
# Yields on 2026-08-10 to 08-23, awards and matches:
#
#     "supply chain"            15    4        robotics       81    6
#     logistics                 12    7        inventory       9    3
#     "additive manufacturing"  27    1        warehouse       1    0
#     "autonomous vehicle"       1    1        freight         0    0
#
# Warehouse and freight are kept despite returning almost nothing here: they are
# the domain's own words, a quiet fortnight is not an empty year, and dropping a
# term because one window was thin is how a source stops seeing what it was
# added for.
KEYWORDS = (
    '"supply chain"',
    "logistics",
    "warehouse",
    "freight",
    "inventory",
    "robotics",
    '"additive manufacturing"',
    '"autonomous vehicle"',
)

FIELDS = ",".join((
    "id", "title", "date", "abstractText", "fundsObligatedAmt",
    "perfStateCode", "awardeeName",
))


class NsfCollector(BaseCollector):
    name = "nsf"
    rate_limit_seconds = 1.0

    def params_for(self, week: str, keyword: str, offset: int) -> dict:
        start, end = config.week_bounds(week)
        start -= dt.timedelta(days=config.LOOKBACK_DAYS)
        return {
            "keyword": keyword,
            "printFields": FIELDS,
            "rpp": PAGE_SIZE,
            "offset": offset,
            # The API wants American dates, and it filters on the award date --
            # which is the one this collector keys on.
            "dateStart": start.strftime("%m/%d/%Y"),
            "dateEnd": end.strftime("%m/%d/%Y"),
        }

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        limiter = http.RateLimiter(self.rate_limit_seconds)
        for keyword in KEYWORDS:
            for page in range(MAX_OFFSETS):
                offset = 1 + page * PAGE_SIZE
                response = http.fetch(session, API_URL,
                                      params=self.params_for(week, keyword, offset),
                                      limiter=limiter)
                yield RawPage(response.url, response.status, response.text, "json")
                awards = ((json.loads(response.text).get("response") or {})
                          .get("award") or [])
                if len(awards) < PAGE_SIZE:
                    break
            else:
                print(f"  nsf: {week} '{keyword}' filled all {MAX_OFFSETS} pages; "
                      f"the week is undercounted")

    def parse(self, text: str) -> list[Document]:
        awards = (json.loads(text or "{}").get("response") or {}).get("award") or []
        documents = []
        for award in awards:
            # `date` is when the award was made. `startDate` is when the work
            # begins and can run a year later -- one award dated August 2026
            # starts in June 2027. Keying on that would file the award in a
            # quarter the query never asked about, which is exactly what
            # period-of-performance dates did to USAspending.
            date = _iso(award.get("date"))
            if not date or not (award.get("title") or "").strip():
                continue
            point = geo.centroid(award.get("perfStateCode"))
            documents.append(
                Document(
                    doc_id=f"nsf:{award.get('id')}",
                    date=date,
                    title=award["title"].strip(),
                    text=award.get("abstractText") or "",
                    url=f"https://www.nsf.gov/awardsearch/showAward?AWD_ID={award.get('id')}",
                    entity=award.get("awardeeName"),
                    entity_id=None,
                    amount=_amount(award.get("fundsObligatedAmt")),
                    lat=point[0] if point else None,
                    lon=point[1] if point else None,
                )
            )
        return documents


def _iso(value) -> str | None:
    """MM/DD/YYYY, the only format this API emits."""
    try:
        return dt.datetime.strptime(str(value), "%m/%d/%Y").date().isoformat()
    except (TypeError, ValueError):
        return None


def _amount(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
