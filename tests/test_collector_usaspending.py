import datetime as dt
import json
from pathlib import Path

from observatory import config, matcher, run
from observatory.collectors.usaspending import (
    EXCLUDED_PROGRAMS, GRANT_TYPE_CODES, PROGRAM_EVIDENCES, PROGRAMS,
    UsaspendingCollector,
)

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
        "CFDA Number": "20.823", "Last Modified Date": "2026-08-12 09:00:00",
    }]})
    doc = UsaspendingCollector().parse(payload)[0]
    assert doc.lat is None and doc.lon is None


def test_amount_survives_a_string_valued_award_amount():
    payload = json.dumps({"results": [{
        "Award ID": "X2", "Recipient Name": "R", "Award Amount": "1234.50",
        "Description": "d", "Place of Performance State Code": "AZ",
        "CFDA Number": "20.823", "Last Modified Date": "2026-08-12 09:00:00",
    }]})
    assert UsaspendingCollector().parse(payload)[0].amount == 1234.50


def test_parse_handles_an_empty_result_set():
    assert UsaspendingCollector().parse(json.dumps({"results": []})) == []


# --- the query -------------------------------------------------------------

def test_payload_window_includes_the_lookback():
    payload = UsaspendingCollector().payload_for("2026-W33", 1)
    period = payload["filters"]["time_period"][0]
    assert period["start_date"] == "2026-08-03"
    assert period["end_date"] == "2026-08-16"
    assert payload["page"] == 1


def test_the_query_filters_by_programme_and_not_by_keyword():
    """Multi-word keywords are phrase-matched against terse award prose:
    'port' returned over a hundred awards where 'port infrastructure' returned
    one. Six such phrases retrieved 36 awards in a year, none of which matched."""
    filters = UsaspendingCollector().payload_for(FIXTURE_WEEK, 1)["filters"]
    assert "keywords" not in filters
    assert filters["program_numbers"] == list(PROGRAMS)


def test_award_type_codes_all_come_from_one_group():
    """Mixing contract and assistance codes is rejected outright:
    'award_type_codes must only contain types from one group' (HTTP 422)."""
    codes = UsaspendingCollector().payload_for(FIXTURE_WEEK, 1)["filters"]["award_type_codes"]
    assert codes == GRANT_TYPE_CODES
    assert all(code.isdigit() for code in codes), "contract codes are letters"


def test_the_sort_field_is_among_the_requested_fields():
    """Sorting on a field that was not requested is a 422, and one that returns
    an empty body reads exactly like a quarter with no awards in it."""
    payload = UsaspendingCollector().payload_for(FIXTURE_WEEK, 1)
    assert payload["sort"] in payload["fields"]


def test_the_requested_date_field_is_the_one_the_filter_uses():
    """Filtering on one date and reporting another is what put every award in a
    week the query never asked about. Under an action_date filter the retrievable
    dates are period-of-performance dates that predate the window by years."""
    payload = UsaspendingCollector().payload_for(FIXTURE_WEEK, 1)
    assert payload["filters"]["time_period"][0]["date_type"] == "last_modified_date"
    assert "Last Modified Date" in payload["fields"]


def test_every_documents_week_falls_inside_the_window_that_retrieved_it():
    """The assertion whose absence let a fabricated zero through: the real
    fixture's own dates, put through the same `_document_week` the pipeline
    uses, must land in the weeks the fixture's query actually asked for."""
    period = UsaspendingCollector().payload_for(FIXTURE_WEEK, 1)["filters"]["time_period"][0]
    window = set(config.week_range(
        config.iso_week(dt.date.fromisoformat(period["start_date"])),
        config.iso_week(dt.date.fromisoformat(period["end_date"])),
    ))
    documents = UsaspendingCollector().parse(FIXTURE.read_text())
    assert documents
    for document in documents:
        assert run._document_week(document, "never-asked-for") in window, document


# --- which programmes ------------------------------------------------------

def test_passenger_and_general_purpose_programmes_stay_excluded():
    """Each of these was pulled live and read. They dwarf the freight
    programmes -- intercity passenger rail alone is $16.8B against the Port
    Infrastructure Development Program's $1.4B -- so admitting one drowns the
    signal it was added to find."""
    for number in ("20.326", "20.315", "20.205", "66.045", "20.500", "20.507"):
        assert number not in PROGRAMS
        assert number in EXCLUDED_PROGRAMS, f"{number} should be excluded, with a reason"


def test_no_programme_is_both_included_and_excluded():
    assert not set(PROGRAMS) & set(EXCLUDED_PROGRAMS)


def test_every_excluded_programme_records_why():
    for number, reason in EXCLUDED_PROGRAMS.items():
        assert reason and len(reason) > 20, f"{number} needs a reason, not a label"


def test_the_core_freight_programmes_are_present():
    for number in ("20.823", "20.325", "20.934", "66.051"):
        assert number in PROGRAMS


# --- the query as evidence -------------------------------------------------

def test_a_clean_ports_award_counts_without_using_the_words():
    """The Clean Ports Program funds nothing but zero-emission port equipment,
    so an award under it is evidence whether or not its description says so.
    Federal award prose describes civil works, not technologies."""
    payload = json.dumps({"results": [{
        "Award ID": "CP1", "Recipient Name": "PORT OF SOMEWHERE",
        "Award Amount": 5_000_000.0, "Description": "RECONFIGURE THE NORTH BERTH",
        "Place of Performance State Code": "CA", "CFDA Number": "66.051",
        "Last Modified Date": "2026-08-12 09:00:00",
    }]})
    document = UsaspendingCollector().parse(payload)[0]
    assert "port_electrification" in document.evidences

    observations = matcher.observations_for_document(
        matcher.load_watchlist(), document, "usaspending", "2026-W33", None
    )
    assert "port_electrification" in {obs.tech_id for obs in observations}


def test_a_port_construction_grant_is_not_attributed_to_a_technology():
    """Ports are dredged far more often than they are automated. The Port
    Infrastructure Development Program funds port capability in general, so it
    earns no direct attribution and has to pass the text matcher like anything
    else."""
    payload = json.dumps({"results": [{
        "Award ID": "P1", "Recipient Name": "PORT OF ELSEWHERE",
        "Award Amount": 9_000_000.0, "Description": "RECONSTRUCT THE DOCK FACE",
        "Place of Performance State Code": "TX", "CFDA Number": "20.823",
        "Last Modified Date": "2026-08-12 09:00:00",
    }]})
    document = UsaspendingCollector().parse(payload)[0]
    assert document.evidences == ()

    observations = matcher.observations_for_document(
        matcher.load_watchlist(), document, "usaspending", "2026-W33", None
    )
    assert observations == []


def test_declared_evidence_names_a_real_technology():
    known = {tech.id for tech in matcher.load_watchlist().active}
    for number, tech_ids in PROGRAM_EVIDENCES.items():
        assert number in PROGRAMS, f"{number} attributes evidence but is not queried"
        for tech_id in tech_ids:
            assert tech_id in known, f"{number} attributes to unknown {tech_id}"


def test_direct_attribution_records_the_programme_as_the_pattern():
    """A count has to be traceable to what produced it. For these rows that is
    a programme number, not a regex."""
    payload = json.dumps({"results": [{
        "Award ID": "CP2", "Recipient Name": "R", "Award Amount": 1.0,
        "Description": "NO TECHNOLOGY WORDS HERE",
        "Place of Performance State Code": "WA", "CFDA Number": "66.051",
        "Last Modified Date": "2026-08-12 09:00:00",
    }]})
    document = UsaspendingCollector().parse(payload)[0]
    observations = matcher.observations_for_document(
        matcher.load_watchlist(), document, "usaspending", "2026-W33", None
    )
    assert [obs.matched_pattern for obs in observations] == ["cfda:66.051"]


def test_text_and_programme_evidence_do_not_double_count():
    """An award that both matches the text and is declared by its programme is
    still one observation for that technology."""
    payload = json.dumps({"results": [{
        "Award ID": "CP3", "Recipient Name": "R", "Award Amount": 1.0,
        "Description": "SHORE POWER AND PORT ELECTRIFICATION AT THE TERMINAL",
        "Place of Performance State Code": "OR", "CFDA Number": "66.051",
        "Last Modified Date": "2026-08-12 09:00:00",
    }]})
    document = UsaspendingCollector().parse(payload)[0]
    observations = matcher.observations_for_document(
        matcher.load_watchlist(), document, "usaspending", "2026-W33", None
    )
    tech_ids = [obs.tech_id for obs in observations]
    assert tech_ids.count("port_electrification") == 1


# --- the regression this whole module exists to prevent --------------------

def test_the_fixture_holds_more_awards_than_the_old_query_found_in_a_year():
    """Six phrase keywords over 52 weeks returned 36 awards and zero matches.
    This fixture is a single week."""
    assert len(UsaspendingCollector().parse(FIXTURE.read_text())) > 36
