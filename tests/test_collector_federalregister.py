import json
from pathlib import Path

from observatory.collectors.federalregister import FederalRegisterCollector

FIXTURE = Path(__file__).parent / "fixtures" / "federalregister_page.json"


def test_parse_extracts_both_documents():
    assert len(FederalRegisterCollector().parse(FIXTURE.read_text())) == 2


def test_doc_id_uses_the_document_number():
    first = FederalRegisterCollector().parse(FIXTURE.read_text())[0]
    assert first.doc_id == "fedreg:2026-17421"
    assert first.date == "2026-08-12"


def test_agency_becomes_the_entity():
    first = FederalRegisterCollector().parse(FIXTURE.read_text())[0]
    assert first.entity == "Federal Motor Carrier Safety Administration"
    assert first.entity_id == "200"


def test_abstract_is_the_searchable_body():
    first = FederalRegisterCollector().parse(FIXTURE.read_text())[0]
    assert "driverless truck" in first.text


def test_missing_agencies_do_not_raise():
    payload = json.dumps({"results": [{
        "document_number": "2026-1", "publication_date": "2026-08-12",
        "title": "T", "abstract": None, "html_url": "https://x.test", "agencies": []
    }]})
    document = FederalRegisterCollector().parse(payload)[0]
    assert document.entity is None
    assert document.text == ""


def test_parse_handles_an_empty_result_set():
    assert FederalRegisterCollector().parse(json.dumps({"results": []})) == []


def test_date_window_opens_a_week_early_for_late_published_documents():
    # 2026-W33 runs 2026-08-10 to 2026-08-16; both bounds are inclusive here.
    assert FederalRegisterCollector().date_window("2026-W33") == ("2026-08-03", "2026-08-16")


def test_agency_with_zero_id_is_preserved():
    payload = json.dumps({"results": [{
        "document_number": "2026-2", "publication_date": "2026-08-12",
        "title": "T", "abstract": "A", "html_url": "https://x.test",
        "agencies": [{"name": "Some Agency", "id": 0}]
    }]})
    document = FederalRegisterCollector().parse(payload)[0]
    assert document.entity_id == "0"
