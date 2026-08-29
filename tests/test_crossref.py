"""Resolving a bibliographic record's real publication date.

Scopus RIS carries a year and nothing else, and that year is the *issue* year:
across a 40-DOI sample of records Scopus stamped PY 2026, 12% were actually
published in 2025. Dating on it put all 2,607 records of one export on January
1st -- one fabricated spike in 2026-W01 and nothing in any other week.

Crossref answers the question the export cannot. It is public metadata about
documents already in hand, free and keyless.
"""

import json

import pytest

from observatory import config, crossref


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """A cache is module state. Without this, one test's DOIs answer another's."""
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    crossref.reset()
    yield tmp_path
    crossref.reset()


def test_a_full_date_is_used_as_it_stands():
    assert crossref.date_from_parts([2026, 8, 16]) == "2026-08-16"


def test_a_year_and_month_become_the_first_of_that_month():
    """A deliberate, visible approximation rather than a guess at a real day --
    the same move manual.py already makes for a bare year."""
    assert crossref.date_from_parts([2026, 8]) == "2026-08-01"


def test_a_bare_year_is_refused_rather_than_placed_in_january():
    """January 1st is where 2,607 records piled up. A year that Crossref cannot
    improve on is not a week, and saying so is better than inventing one."""
    assert crossref.date_from_parts([2026]) is None


def test_empty_date_parts_resolve_to_nothing():
    assert crossref.date_from_parts([]) is None
    assert crossref.date_from_parts(None) is None


def test_a_cached_doi_is_not_fetched_again():
    """2,607 lookups a quarter is worth caching, and a DOI's publication date
    does not change."""
    crossref.remember({"10.1000/a": "2026-05-04"})
    calls = []

    def fake_fetch(doi):
        calls.append(doi)
        return "2026-06-06"

    dates = crossref.resolve(["10.1000/a"], fetch=fake_fetch)
    assert dates == {"10.1000/a": "2026-05-04"}
    assert calls == []


def test_an_uncached_doi_is_fetched_and_then_remembered():
    calls = []

    def fake_fetch(doi):
        calls.append(doi)
        return "2026-06-06"

    crossref.resolve(["10.1000/b"], fetch=fake_fetch)
    assert calls == ["10.1000/b"]
    assert crossref.cached()["10.1000/b"] == "2026-06-06"


def test_the_cache_is_written_to_raw_and_survives_a_reload():
    crossref.remember({"10.1000/c": "2026-01-02"})
    crossref.reset()
    assert crossref.cached()["10.1000/c"] == "2026-01-02"


def test_a_doi_that_does_not_resolve_is_remembered_as_unresolved():
    """Otherwise every import re-asks Crossref about the same dead DOIs."""
    crossref.resolve(["10.1000/gone"], fetch=lambda doi: None)
    assert "10.1000/gone" in crossref.cached()
    assert crossref.cached()["10.1000/gone"] is None
    calls = []
    crossref.resolve(["10.1000/gone"], fetch=lambda doi: calls.append(doi))
    assert calls == []


def test_the_raw_log_is_append_only_json_lines():
    crossref.remember({"10.1000/d": "2026-03-03"})
    crossref.remember({"10.1000/e": "2026-04-04"})
    lines = [json.loads(line) for line in crossref.log_path().read_text().splitlines()]
    assert [entry["doi"] for entry in lines] == ["10.1000/d", "10.1000/e"]


# --- failing loudly --------------------------------------------------------
#
# The first version passed session=None into http.fetch, which raises
# AttributeError. A broad `except Exception` caught it and recorded every one of
# 2,607 DOIs as unresolved. A systematic breakage wore the costume of 2,607
# documents that simply had no date -- which is this project's oldest failure
# mode, written in by hand.


def test_a_systematic_failure_raises_rather_than_recording_nothing_found():
    def always_broken(doi):
        raise AttributeError("'NoneType' object has no attribute 'get'")

    with pytest.raises(crossref.ResolverFailed):
        crossref.resolve([f"10.1000/{n}" for n in range(50)], fetch=always_broken)


def test_a_systematic_failure_poisons_nothing_in_the_cache():
    def always_broken(doi):
        raise AttributeError("boom")

    with pytest.raises(crossref.ResolverFailed):
        crossref.resolve([f"10.1000/{n}" for n in range(50)], fetch=always_broken)
    assert crossref.cached() == {}


def test_an_isolated_failure_is_tolerated():
    """A single dead DOI among live ones is a fact about that DOI."""
    def mostly_fine(doi):
        if doi == "10.1000/bad":
            raise ValueError("no such work")
        return "2026-05-05"

    dois = [f"10.1000/{n}" for n in range(20)] + ["10.1000/bad"]
    dates = crossref.resolve(dois, fetch=mostly_fine)
    assert dates["10.1000/bad"] is None
    assert dates["10.1000/1"] == "2026-05-05"


def test_a_doi_that_resolves_to_no_date_is_not_a_failure():
    """Crossref answering "I have no date for this" is an answer, not a fault."""
    dates = crossref.resolve([f"10.1000/{n}" for n in range(50)], fetch=lambda doi: None)
    assert set(dates.values()) == {None}


def test_resolve_makes_its_own_session_when_given_none(monkeypatch):
    """The bug was a None session reaching http.fetch. Nothing may depend on the
    caller remembering to build one."""
    from observatory import http
    sentinel = object()
    monkeypatch.setattr(http, "make_session", lambda: sentinel)
    seen = {}

    def fake_fetch_one(doi, session, limiter):
        seen["session"] = session
        return "2026-01-01"

    crossref.resolve(["10.1000/z"], fetch_one=fake_fetch_one)
    assert seen["session"] is sentinel
