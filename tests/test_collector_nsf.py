"""NSF award search.

The research half of the investment stage. USAspending sees infrastructure
grants -- ports, rail, freight corridors -- and nothing upstream of them; NSF
sees the money going into the ideas. It is keyless, every award carries a
technical abstract of a few thousand characters, and the award has a date.

Measured before building, on Jun-Aug 2026: 190 awards across five domain
keywords, 100% with abstracts, 20 matched. SBIR was measured the same way and
rejected -- 500 awards, 0 matched, because a contract description names the
programme and the agency and never the technology.
"""

import json
from pathlib import Path

from observatory.collectors.nsf import KEYWORDS, NsfCollector

FIXTURE = Path(__file__).parent / "fixtures" / "nsf_page.json"


def test_parse_returns_a_document_per_award():
    documents = NsfCollector().parse(FIXTURE.read_text())
    assert documents
    assert all(doc.doc_id.startswith("nsf:") for doc in documents)


def test_an_award_is_dated_by_when_it_was_made():
    """`startDate` is when the work begins and runs months or years later --
    one award in the fixture is dated August 2026 and starts in June 2027.
    Keying on it would file the award in a quarter the query never asked about,
    which is what USAspending did with period-of-performance dates."""
    documents = NsfCollector().parse(FIXTURE.read_text())
    assert all(doc.date and doc.date.startswith("2026-08") for doc in documents)


def test_the_american_date_format_is_converted():
    payload = json.dumps({"response": {"award": [
        {"id": "1", "title": "A", "date": "08/05/2026", "abstractText": "x"}]}})
    assert NsfCollector().parse(payload)[0].date == "2026-08-05"


def test_an_award_with_an_unreadable_date_is_dropped():
    """Undated, it would be counted in no period and would still take a slot in
    the corpus that is the denominator of every rate."""
    payload = json.dumps({"response": {"award": [
        {"id": "1", "title": "A", "date": "not a date", "abstractText": "x"},
        {"id": "2", "title": "B", "date": "08/05/2026", "abstractText": "x"}]}})
    assert len(NsfCollector().parse(payload)) == 1


def test_the_abstract_reaches_the_matcher():
    """The whole reason this source is worth having and SBIR was not."""
    documents = NsfCollector().parse(FIXTURE.read_text())
    assert all(doc.text for doc in documents)
    assert max(len(doc.text) for doc in documents) > 1000


def test_the_awardee_becomes_the_entity():
    assert any(doc.entity for doc in NsfCollector().parse(FIXTURE.read_text()))


def test_the_obligated_amount_is_carried_as_a_number():
    for doc in NsfCollector().parse(FIXTURE.read_text()):
        assert doc.amount is None or isinstance(doc.amount, float)


def test_an_award_is_placed_on_the_map_where_the_work_happens():
    payload = json.dumps({"response": {"award": [
        {"id": "1", "title": "A", "date": "08/05/2026", "abstractText": "x",
         "perfStateCode": "AZ"}]}})
    doc = NsfCollector().parse(payload)[0]
    assert doc.lat and doc.lon


def test_an_unknown_state_leaves_the_map_alone():
    payload = json.dumps({"response": {"award": [
        {"id": "1", "title": "A", "date": "08/05/2026", "abstractText": "x",
         "perfStateCode": "ZZ"}]}})
    assert NsfCollector().parse(payload)[0].lat is None


def test_the_sweep_is_by_domain_rather_than_by_technology():
    """The same rule every other collector follows: fetch a domain and let the
    matcher decide. One query per technology would grow with the watchlist and
    would leave auto-discovery nothing to find."""
    assert '"supply chain"' in KEYWORDS
    assert len(KEYWORDS) <= 10


def test_multi_word_keywords_are_quoted():
    """NSF ORs unquoted words: "manufacturing automation" returned 295 awards
    in a fortnight, most about neither, where a quoted phrase returns what it
    says. Single words need no quoting and get none."""
    for keyword in KEYWORDS:
        if " " in keyword.strip('"'):
            assert keyword.startswith('"') and keyword.endswith('"'), keyword


def test_the_query_window_is_the_week_plus_its_lookback():
    import datetime as dt

    from observatory import config
    params = NsfCollector().params_for("2026-W35", "logistics", offset=1)
    monday, sunday = config.week_bounds("2026-W35")
    opens = monday - dt.timedelta(days=config.LOOKBACK_DAYS)
    assert params["dateStart"] == opens.strftime("%m/%d/%Y")
    assert params["dateEnd"] == sunday.strftime("%m/%d/%Y")


def test_the_query_asks_for_the_abstract():
    params = NsfCollector().params_for("2026-W35", "logistics", offset=1)
    assert "abstractText" in params["printFields"]
