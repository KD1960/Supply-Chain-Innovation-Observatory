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
    "supply chain risk intelligence",
    "digital freight matching",
    "cold chain monitoring",
    "nearshoring supply chain",
    "warehouse management system",
    "enterprise resource planning supply chain",
)


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
            if not ciks:
                continue
            cik = str(ciks[0]).strip().zfill(10)
            names = source.get("display_names") or []
            name = names[0] if names else cik
            documents.append(
                Document(
                    doc_id=f"edgar:{hit.get('_id')}",
                    date=(source.get("file_date") or None),
                    title=name,
                    text=term or "",
                    url=_filing_url(hit.get("_id"), cik),
                    entity=name,
                    entity_id=cik,
                )
            )
        return documents


def _query_term(payload: dict) -> str | None:
    try:
        clauses = payload["query"]["query"]["bool"]["must"]
        return clauses[0]["match_phrase"]["doc_text"]
    except (KeyError, IndexError, TypeError):
        return None


def _filing_url(hit_id: str | None, cik: str) -> str:
    """EDGAR ids look like 0000320193-26-000001:aapl-20260630.htm."""
    if not hit_id or ":" not in hit_id:
        return f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"
    accession, _, document = hit_id.partition(":")
    return (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession.replace('-', '')}/{document}"
    )
