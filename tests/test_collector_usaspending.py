import datetime as dt
import json
from pathlib import Path

from observatory import config, run
from observatory.collectors.usaspending import UsaspendingCollector

FIXTURE = Path(__file__).parent / "fixtures" / "usaspending_page.json"
# The week whose query produced the committed fixture, captured live.
FIXTURE_WEEK = "2026-W33"


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
        "Last Modified Date": "2026-08-12 09:00:00",
    }]})
    doc = UsaspendingCollector().parse(payload)[0]
    assert doc.lat is None and doc.lon is None


def test_amount_survives_a_string_valued_award_amount():
    payload = json.dumps({"results": [{
        "Award ID": "X2", "Recipient Name": "R", "Award Amount": "1234.50",
        "Description": "d", "Place of Performance State Code": "AZ",
        "Last Modified Date": "2026-08-12 09:00:00",
    }]})
    assert UsaspendingCollector().parse(payload)[0].amount == 1234.50


def test_payload_window_includes_the_lookback():
    payload = UsaspendingCollector().payload_for("2026-W33", "port infrastructure", 1)
    period = payload["filters"]["time_period"][0]
    assert period["start_date"] == "2026-08-03"
    assert period["end_date"] == "2026-08-16"
    assert payload["filters"]["keywords"] == ["port infrastructure"]
    assert payload["page"] == 1


def test_the_requested_date_field_is_the_one_the_filter_uses():
    """Filtering on one date and reporting another is what put every award in a
    week the query never asked about."""
    payload = UsaspendingCollector().payload_for(FIXTURE_WEEK, "port infrastructure", 1)
    assert payload["filters"]["time_period"][0]["date_type"] == "last_modified_date"
    assert "Last Modified Date" in payload["fields"]


def test_every_documents_week_falls_inside_the_window_that_retrieved_it():
    """The assertion whose absence let a fabricated zero through: the real
    fixture's own dates, put through the same `_document_week` the pipeline
    uses, must land in the weeks the fixture's query actually asked for."""
    period = UsaspendingCollector().payload_for(
        FIXTURE_WEEK, "port infrastructure", 1
    )["filters"]["time_period"][0]
    window = set(config.week_range(
        config.iso_week(dt.date.fromisoformat(period["start_date"])),
        config.iso_week(dt.date.fromisoformat(period["end_date"])),
    ))

    documents = UsaspendingCollector().parse(FIXTURE.read_text())
    assert documents
    for document in documents:
        assert run._document_week(document, "never-asked-for") in window, document


def test_parse_handles_an_empty_result_set():
    assert UsaspendingCollector().parse(json.dumps({"results": []})) == []
