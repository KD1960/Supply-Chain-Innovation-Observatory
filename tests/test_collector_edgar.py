import json
from pathlib import Path

from observatory import matcher
from observatory.collectors.edgar import QUERY_TERMS, EdgarCollector

FIXTURE = Path(__file__).parent / "fixtures" / "edgar_page.json"


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
    payload = json.dumps({"hits": {"hits": [
        {"_id": "x:doc.htm", "_source": {"display_names": ["Nobody"], "file_date": "2026-08-12"}},
    ]}})
    assert EdgarCollector().parse(payload) == []


def test_hits_with_an_empty_cik_are_skipped():
    payload = json.dumps({"hits": {"hits": [
        {"_id": "x:doc.htm", "_source": {"ciks": [""], "display_names": ["Nobody"], "file_date": "2026-08-12"}},
    ]}})
    assert EdgarCollector().parse(payload) == []


def test_a_non_numeric_cik_falls_back_to_the_browse_edgar_url_instead_of_raising():
    payload = json.dumps({"hits": {"hits": [
        {"_id": "a:doc.htm", "_source": {"ciks": ["ABCDE12345"], "display_names": ["Weird"], "file_date": "2026-08-12"}},
    ]}})
    documents = EdgarCollector().parse(payload)
    assert len(documents) == 1
    assert documents[0].url == (
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=ABCDE12345"
    )


def test_a_short_cik_is_zero_padded_to_ten_digits():
    payload = json.dumps({"hits": {"hits": [
        {"_id": "a:doc.htm", "_source": {"ciks": ["320193"], "display_names": ["Apple Inc."], "file_date": "2026-08-12"}},
    ]}})
    documents = EdgarCollector().parse(payload)
    assert documents[0].entity_id == "0000320193"


def test_parse_handles_an_empty_result_set():
    assert EdgarCollector().parse(json.dumps({"hits": {"hits": []}})) == []


def test_every_query_term_matches_an_active_technology():
    watchlist = matcher.load_watchlist()
    for term in QUERY_TERMS:
        assert watchlist.match(term), f"QUERY_TERMS entry {term!r} matches no active technology"
