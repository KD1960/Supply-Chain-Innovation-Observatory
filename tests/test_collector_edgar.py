import json
from pathlib import Path

import pytest

from observatory import matcher
from observatory.collectors.edgar import QUERY_TERMS, EdgarCollector

FIXTURE = Path(__file__).parent / "fixtures" / "edgar_page.json"


def response(hits, term="autonomous trucking"):
    """A synthetic response shaped like a real one.

    EDGAR echoes the submitted query back on every response, hits or no hits,
    and the echo is the only thing that says which technology a filing belongs
    to — so a synthetic payload without it is not a response this collector
    should ever accept.
    """
    return json.dumps({
        "query": {"query": {"bool": {"must": [{"match_phrase": {"doc_text": term}}]}}},
        "hits": {"hits": hits},
    })


def test_parse_returns_a_document_per_hit():
    documents = EdgarCollector().parse(FIXTURE.read_text())
    assert documents
    assert all(doc.doc_id.startswith("edgar:") for doc in documents)


def test_cik_becomes_entity_id_zero_padded_to_ten_digits():
    for doc in EdgarCollector().parse(FIXTURE.read_text()):
        assert doc.entity_id is not None
        assert len(doc.entity_id) == 10
        assert doc.entity_id.isdigit()


def test_display_name_becomes_the_entity():
    assert all(doc.entity for doc in EdgarCollector().parse(FIXTURE.read_text()))


def test_file_date_becomes_an_iso_date():
    for doc in EdgarCollector().parse(FIXTURE.read_text()):
        assert doc.date is None or (len(doc.date) == 10 and doc.date[4] == "-")


def test_url_points_at_the_filing_on_sec_gov():
    for doc in EdgarCollector().parse(FIXTURE.read_text()):
        assert doc.url.startswith("https://www.sec.gov/")


def test_two_filings_from_one_company_share_an_entity_id():
    ids = [doc.entity_id for doc in EdgarCollector().parse(FIXTURE.read_text())]
    assert len(ids) > len(set(ids)), "fixture should contain a repeated filer"


def test_hits_without_a_cik_are_skipped():
    payload = response([
        {"_id": "x:doc.htm", "_source": {"display_names": ["Nobody"], "file_date": "2026-08-12"}},
    ])
    assert EdgarCollector().parse(payload) == []


def test_hits_with_an_empty_cik_are_skipped():
    payload = response([
        {"_id": "x:doc.htm", "_source": {"ciks": [""], "display_names": ["Nobody"], "file_date": "2026-08-12"}},
    ])
    assert EdgarCollector().parse(payload) == []


def test_a_non_numeric_cik_falls_back_to_the_browse_edgar_url_instead_of_raising():
    payload = response([
        {"_id": "a:doc.htm", "_source": {"ciks": ["ABCDE12345"], "display_names": ["Weird"], "file_date": "2026-08-12"}},
    ])
    documents = EdgarCollector().parse(payload)
    assert len(documents) == 1
    assert documents[0].url == (
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=ABCDE12345"
    )


def test_a_short_cik_is_zero_padded_to_ten_digits():
    payload = response([
        {"_id": "a:doc.htm", "_source": {"ciks": ["320193"], "display_names": ["Apple Inc."], "file_date": "2026-08-12"}},
    ])
    documents = EdgarCollector().parse(payload)
    assert documents[0].entity_id == "0000320193"


def test_the_query_term_becomes_the_text_the_matcher_sees():
    documents = EdgarCollector().parse(response([
        {"_id": "a:doc.htm", "_source": {"ciks": ["320193"],
                                         "display_names": ["Apple Inc."],
                                         "file_date": "2026-08-12"}},
    ], term="warehouse robotics"))
    assert documents[0].text == "warehouse robotics"


def test_parse_handles_an_empty_result_set():
    assert EdgarCollector().parse(response([])) == []


def test_a_response_without_the_query_echo_raises_rather_than_matching_nothing():
    """Degrading to an empty term would leave every haystack as the filer name,
    match no technology at all, and still report the source `ok`. run.py
    isolates a raising source and marks it failed, so an honest hole appears
    where a silent zero used to."""
    payload = json.dumps({"hits": {"hits": [
        {"_id": "a:doc.htm", "_source": {"ciks": ["320193"],
                                         "display_names": ["Apple Inc."],
                                         "file_date": "2026-08-12"}},
    ]}})
    with pytest.raises(ValueError, match="echo"):
        EdgarCollector().parse(payload)


def test_an_empty_body_raises_rather_than_parsing_to_nothing():
    with pytest.raises(ValueError, match="echo"):
        EdgarCollector().parse("")


# The submitted term is what attributes a filing to a technology, so drift
# between this list and the watchlist moves an adoption count to the wrong row.
# Asserting only that a term matches *something* would not catch that.
INTENDED_TECHNOLOGY = {
    "autonomous trucking": "autonomous_trucking",
    "warehouse robotics": "warehouse_robotics",
    "supply chain risk intelligence": "risk_intelligence",
    "digital freight matching": "digital_freight",
    "cold chain monitoring": "cold_chain_iot",
    "nearshoring supply chain": "nearshoring_analytics",
    "warehouse management system": "wms",
    "enterprise resource planning supply chain": "erp",
}


def test_every_query_term_matches_its_intended_technology():
    assert set(INTENDED_TECHNOLOGY) == set(QUERY_TERMS), (
        "QUERY_TERMS changed; state which technology each new term is meant for"
    )
    watchlist = matcher.load_watchlist()
    for term, tech_id in INTENDED_TECHNOLOGY.items():
        matched = {matched_id for matched_id, _ in watchlist.match(term)}
        assert matched == {tech_id}, f"{term!r} now matches {matched or 'nothing'}"
