import json
from pathlib import Path

from observatory.collectors.edgar import EdgarCollector

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


def test_parse_handles_an_empty_result_set():
    assert EdgarCollector().parse(json.dumps({"hits": {"hits": []}})) == []
