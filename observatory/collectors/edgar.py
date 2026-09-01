"""SEC EDGAR full-text search — which public companies name a technology.

The signal that matters here is breadth, not volume: `edgar_filers` counts
distinct CIKs over a trailing year, so one company mentioning a technology in
every quarterly filing counts once, and ten companies mentioning it once each
counts ten. That is the difference between one enthusiast and an industry
adopting something.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Iterator

from .. import config, http
from .base import BaseCollector, Document, RawPage

API_URL = "https://efts.sec.gov/LATEST/search-index"
FORMS = ("10-K", "10-Q", "8-K", "S-1")

# The query term retrieves the hits; the watchlist regex then re-checks it (see
# `parse`). Keep this list aligned with the watchlist by hand when either
# changes -- there is no automated link between the two.
QUERY_TERMS = (
    "autonomous trucking",
    "warehouse robotics",
    "digital freight matching",
    "cold chain monitoring",
    "nearshoring supply chain",
    "warehouse management system",
)

# Removed 2026-09-01 after measuring them live, and recorded rather than
# deleted so the next person does not re-add them and re-measure zero. The
# same shape as USAspending's named exclusions.
#
# Both were caught in a bind with no move inside it. `parse` sets a document's
# text to the query term itself -- filing bodies are megabytes and are never
# fetched -- so the context gate only ever sees the term, and a term that does
# not carry a domain word fails the gate for every filing it will ever
# retrieve. Phrasing a term to carry one makes it long, and EDGAR matches
# phrases exactly. Broad enough to retrieve, and nothing survives the gate;
# gated, and nothing is retrieved.
#
# Reversing this needs the SIC container filter or the filing bodies, not a
# better phrase: every phrase was tried. See docs/edgar-depth-2026-09-01.md.
EXCLUDED_TERMS = {
    "supply chain risk intelligence": (
        "zero observations in the life of the project. `risk intelligence` "
        "retrieves 7 filings a quarter and fails the gate; `supplier risk "
        "platform` passes the gate and retrieves none"
    ),
    "enterprise resource planning supply chain": (
        "zero observations in the life of the project. `enterprise resource "
        "planning` retrieves 537 filings a quarter and produces 0 "
        "observations; every gated phrasing retrieves none"
    ),
}


class EdgarCollector(BaseCollector):
    name = "edgar"
    rate_limit_seconds = 1.0  # SEC asks for no more than 10 requests/second

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        limiter = http.RateLimiter(self.rate_limit_seconds)
        start, end = config.week_bounds(week)
        start -= dt.timedelta(days=config.LOOKBACK_DAYS)
        for term in QUERY_TERMS:
            params = {
                "q": f'"{term}"',
                "forms": ",".join(FORMS),
                "startdt": start.isoformat(),
                "enddt": end.isoformat(),
            }
            response = http.fetch(session, API_URL, params=params, limiter=limiter)
            yield RawPage(response.url, response.status, response.text, "json")

    def parse(self, text: str) -> list[Document]:
        payload = json.loads(text or "{}")
        # Filing bodies are megabytes each and are never fetched, so the
        # matcher can't see them -- it only sees `document.title` and
        # `document.text`. EDGAR's full-text search has already done the
        # matching by the time a hit comes back, so `text` is set to the
        # query term that retrieved this page, echoed back verbatim in the
        # response's own `query` block. A filing therefore matches a
        # technology because the term that found it does, not because its
        # body was checked.
        term = _query_term(payload)
        hits = ((payload.get("hits") or {}).get("hits")) or []
        documents = []
        for hit in hits:
            source = hit.get("_source") or {}
            ciks = source.get("ciks") or []
            if not ciks or not str(ciks[0]).strip():
                continue
            cik = str(ciks[0]).strip().zfill(10)
            names = source.get("display_names") or []
            name = names[0] if names else cik
            documents.append(
                Document(
                    doc_id=f"edgar:{hit.get('_id')}",
                    date=(source.get("file_date") or None),
                    title=name,
                    text=term,
                    url=_filing_url(hit.get("_id"), cik),
                    entity=name,
                    entity_id=cik,
                )
            )
        return documents


def _query_term(payload: dict) -> str:
    """The echoed query term, or an exception — never a degraded empty string.

    Technology attribution rests entirely on this echo. Swallowing a missing
    one would leave `text` empty, collapse every haystack to the filer name,
    and match nothing: edgar_filings and edgar_filers would fall to zero for
    every technology while the source still reported `ok`. `fetch_week` and
    `ingest_week` isolate a raising source and mark it failed, so raising
    turns that silent zero into an honest hole.
    """
    try:
        clauses = payload["query"]["query"]["bool"]["must"]
        return clauses[0]["match_phrase"]["doc_text"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(
            "EDGAR response did not echo the query term back; "
            "without it no filing can be attributed to a technology"
        ) from error


def _filing_url(hit_id: str | None, cik: str) -> str:
    """EDGAR ids look like 0000320193-26-000001:aapl-20260630.htm."""
    if not hit_id or ":" not in hit_id:
        return f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"
    accession, _, document = hit_id.partition(":")
    try:
        numeric_cik = int(cik)
    except ValueError:
        return f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"
    return (
        f"https://www.sec.gov/Archives/edgar/data/{numeric_cik}/"
        f"{accession.replace('-', '')}/{document}"
    )
