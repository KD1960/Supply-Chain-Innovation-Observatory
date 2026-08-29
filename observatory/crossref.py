"""Publication dates for records whose export did not carry one.

A Scopus RIS record has `PY` and nothing else, and `PY` is the *issue* year
rather than the publication date: across a 40-DOI sample of records Scopus
stamped 2026, 12% were published in 2025. Dating on it put all 2,607 records of
one export on January 1st -- a single fabricated spike in 2026-W01 with every
other week left empty.

Crossref answers what the export cannot. It is public metadata about documents
already in hand rather than a licensed source, it needs no key, and it resolved
40 of 40 on the sample.

The results are cached because a DOI's publication date does not change and
2,607 lookups a quarter is worth not repeating. The cache lives under `raw/` as
an append-only log, so it survives a database rebuild -- the same reason every
collector writes its response bodies there before anything parses them.
"""

from __future__ import annotations

import json
import urllib.parse

from . import config, http

API = "https://api.crossref.org/works/"
# Crossref asks for a contact address and gives politer service in return.
RATE_LIMIT_SECONDS = 0.05

# How many consecutive failures mean the resolver is broken rather than the
# identifiers. The first version tolerated every exception, so passing a None
# session -- an AttributeError on the first call and every one after it --
# recorded all 2,607 DOIs as having no date. A systematic breakage must not be
# able to wear the costume of a corpus that simply has no dates.
FAILURE_STREAK = 25

_CACHE: dict[str, str | None] = {}
_LOADED = False


class ResolverFailed(Exception):
    """The resolver is broken, rather than the identifiers being unknown."""


def reset() -> None:
    """Forget everything held in memory, so the next read comes off disk.

    The cache is module state, which two tests in the same process would
    otherwise share.
    """
    global _LOADED
    _CACHE.clear()
    _LOADED = False


def log_path():
    return config.RAW_DIR / "crossref" / "dates.jsonl"


def date_from_parts(parts) -> str | None:
    """Crossref's date-parts as an ISO date, or nothing.

    A year and a month become the first of that month: a deliberate, visible
    approximation, and the same move manual.py already makes for a bare year.

    A bare year returns nothing rather than January 1st. January 1st is where
    2,607 records piled up, and a year Crossref cannot improve on is genuinely
    not a week; saying so beats inventing one.
    """
    if not parts:
        return None
    year = parts[0]
    if len(parts) >= 3:
        return f"{year:04d}-{parts[1]:02d}-{parts[2]:02d}"
    if len(parts) == 2:
        return f"{year:04d}-{parts[1]:02d}-01"
    return None


def cached() -> dict[str, str | None]:
    global _LOADED
    if not _LOADED:
        path = log_path()
        if path.exists():
            for line in path.read_text().splitlines():
                if line.strip():
                    entry = json.loads(line)
                    _CACHE[entry["doi"]] = entry["date"]
        _LOADED = True
    return _CACHE


def remember(dates: dict[str, str | None]) -> None:
    cached()
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        for doi, date in dates.items():
            handle.write(json.dumps({"doi": doi, "date": date}) + "\n")
            _CACHE[doi] = date


def fetch_one(doi: str, session=None, limiter=None) -> str | None:
    url = API + urllib.parse.quote(doi)
    response = http.fetch(session, url, limiter=limiter)
    if response.status != 200:
        return None
    message = json.loads(response.text).get("message") or {}
    published = message.get("published") or message.get("issued") or {}
    return date_from_parts((published.get("date-parts") or [[]])[0])


def resolve(dois, fetch=None, session=None, progress=None, fetch_one=None):
    """Every DOI's publication date, fetching only the ones not seen before.

    A DOI Crossref has no date for is remembered as unresolved, so the next
    import does not re-ask about the same dead identifiers. A *run* of failures
    is treated as the resolver being broken and raises, because the alternative
    is writing thousands of fabricated absences into the cache and never being
    able to tell them from real ones.
    """
    known = cached()
    wanted = [doi for doi in dict.fromkeys(dois) if doi and doi not in known]
    if wanted:
        limiter = http.RateLimiter(RATE_LIMIT_SECONDS)
        if fetch is None:
            # Built here rather than asked of the caller: a None session
            # reaching http.fetch is exactly what broke this the first time.
            session = session or http.make_session()
            one = fetch_one or globals()["fetch_one"]
            fetch = lambda doi: one(doi, session, limiter)
        found: dict[str, str | None] = {}
        streak = 0
        for index, doi in enumerate(wanted, start=1):
            try:
                found[doi] = fetch(doi)
                streak = 0
            except Exception as error:
                # One unknown identifier is a fact about that identifier. A run
                # of them is a fact about us.
                streak += 1
                if streak >= FAILURE_STREAK:
                    raise ResolverFailed(
                        f"{streak} consecutive lookups failed, most recently "
                        f"{doi}: {type(error).__name__}: {error}. Nothing has "
                        f"been cached; fix the cause and run again."
                    ) from error
                found[doi] = None
            if progress and index % 250 == 0:
                progress(index, len(wanted))
            if len(found) >= 250:
                remember(found)
                found = {}
        if found:
            remember(found)
    return {doi: known.get(doi) for doi in dict.fromkeys(dois) if doi}
