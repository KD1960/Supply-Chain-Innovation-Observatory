import json
from pathlib import Path

from observatory.collectors.usaspending import UsaspendingCollector

FIXTURE = Path(__file__).parent / "fixtures" / "usaspending_page.json"


def test_parse_returns_a_document_per_award():
    documents = UsaspendingCollector().parse(FIXTURE.read_text())
    assert documents
    assert all(doc.doc_id.startswith("usaspend:") for doc in documents)


def test_award_amount_lands_in_amount_as_a_float():
    for doc in UsaspendingCollector().parse(FIXTURE.read_text()):
        assert doc.amount is None or isinstance(doc.amount, float)


def test_recipient_becomes_the_entity():
    assert any(doc.entity for doc in UsaspendingCollector().parse(FIXTURE.read_text()))


def test_state_code_is_resolved_to_coordinates():
    documents = UsaspendingCollector().parse(FIXTURE.read_text())
    located = [doc for doc in documents if doc.lat is not None]
    assert located, "at least one award should resolve to a state centroid"
    for doc in located:
        assert 15 < doc.lat < 72
        assert -180 < doc.lon < 0


def test_unknown_state_leaves_coordinates_empty_rather_than_guessing():
    payload = json.dumps({"results": [{
        "Award ID": "X1", "Recipient Name": "R", "Award Amount": 10.0,
        "Description": "d", "Place of Performance State Code": "ZZ",
        "Start Date": "2026-08-12",
    }]})
    doc = UsaspendingCollector().parse(payload)[0]
    assert doc.lat is None and doc.lon is None


def test_amount_survives_a_string_valued_award_amount():
    payload = json.dumps({"results": [{
        "Award ID": "X2", "Recipient Name": "R", "Award Amount": "1234.50",
        "Description": "d", "Place of Performance State Code": "AZ",
        "Start Date": "2026-08-12",
    }]})
    assert UsaspendingCollector().parse(payload)[0].amount == 1234.50


def test_payload_window_includes_the_lookback():
    payload = UsaspendingCollector().payload_for("2026-W33", "port infrastructure", 1)
    period = payload["filters"]["time_period"][0]
    assert period["start_date"] == "2026-08-03"
    assert period["end_date"] == "2026-08-16"
    assert payload["filters"]["keywords"] == ["port infrastructure"]
    assert payload["page"] == 1


def test_parse_handles_an_empty_result_set():
    assert UsaspendingCollector().parse(json.dumps({"results": []})) == []
