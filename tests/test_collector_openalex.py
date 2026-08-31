"""OpenAlex — the journal literature, without a human in the middle.

This replaces the Scopus workflow it was built beside. Scopus needed twelve
hand-made exports a quarter, carried only a publication *year* (and that the
issue year, wrong for 14% of records), and licensed its abstracts so they could
not be published. OpenAlex is keyless, gives a real publication date, and is
open data.
"""

import json
from pathlib import Path

from observatory.collectors.openalex import ISSNS, OpenAlexCollector

FIXTURE = Path(__file__).parent / "fixtures" / "openalex_page.json"


def test_parse_returns_a_document_per_work():
    documents = OpenAlexCollector().parse(FIXTURE.read_text())
    assert documents
    assert all(doc.doc_id.startswith("openalex:") for doc in documents)


def test_a_work_carries_its_own_publication_date():
    """The whole reason this beats the export it replaces. Scopus gave a year,
    and that year was the issue year -- wrong for 14% of a real export, and
    good enough only for an annual report."""
    for doc in OpenAlexCollector().parse(FIXTURE.read_text()):
        assert doc.date and len(doc.date) == 10
        assert doc.date[:4].isdigit()


def test_the_abstract_is_rebuilt_from_the_inverted_index():
    """OpenAlex ships abstracts as a word-to-positions map. Without
    reconstructing it the matcher sees titles only, which on patents was the
    difference between 1% and 40%."""
    documents = OpenAlexCollector().parse(FIXTURE.read_text())
    with_text = [doc for doc in documents if doc.text]
    assert with_text
    assert any(len(doc.text) > 200 for doc in with_text)


def test_the_inverted_index_is_rebuilt_in_word_order():
    index = {"Warehouse": [0], "robots": [1], "are": [2], "fast": [3]}
    assert OpenAlexCollector().abstract(index) == "Warehouse robots are fast"


def test_a_word_appearing_twice_lands_in_both_places():
    index = {"the": [0, 2], "cat": [1], "hat": [3]}
    assert OpenAlexCollector().abstract(index) == "the cat the hat"


def test_a_work_with_no_abstract_still_becomes_a_document():
    assert OpenAlexCollector().abstract(None) == ""
    payload = json.dumps({"results": [{
        "id": "https://openalex.org/W1", "title": "A paper",
        "publication_date": "2026-08-24", "abstract_inverted_index": None}]})
    assert len(OpenAlexCollector().parse(payload)) == 1


def test_the_journal_becomes_the_entity():
    documents = OpenAlexCollector().parse(FIXTURE.read_text())
    assert any(doc.entity for doc in documents)


def test_a_work_with_no_title_is_skipped():
    """A record the matcher can do nothing with, and its id would still take a
    slot in the corpus count."""
    payload = json.dumps({"results": [
        {"id": "https://openalex.org/W1", "title": None, "publication_date": "2026-08-24"},
        {"id": "https://openalex.org/W2", "title": "Real", "publication_date": "2026-08-24"}]})
    assert len(OpenAlexCollector().parse(payload)) == 1


def test_the_url_points_at_the_doi_where_there_is_one():
    """A DOI outlives an OpenAlex id and is what a reader can follow."""
    payload = json.dumps({"results": [{
        "id": "https://openalex.org/W1", "title": "A paper",
        "doi": "https://doi.org/10.1000/x", "publication_date": "2026-08-24"}]})
    assert OpenAlexCollector().parse(payload)[0].url == "https://doi.org/10.1000/x"


def test_the_query_asks_for_the_journals_we_track():
    query = OpenAlexCollector().params_for("2026-W35", cursor="*")
    assert all(issn in query["filter"] for issn in ISSNS[:3])
    assert "to_publication_date:2026-08-30" in query["filter"]


def test_the_window_is_the_week_plus_its_lookback():
    """Every collector opens its window LOOKBACK_DAYS early, so a late-indexed
    document is caught rather than missed."""
    import datetime as dt

    from observatory import config
    query = OpenAlexCollector().params_for("2026-W35", cursor="*")
    monday, _ = config.week_bounds("2026-W35")
    opens = (monday - dt.timedelta(days=config.LOOKBACK_DAYS)).isoformat()
    assert f"from_publication_date:{opens}" in query["filter"]
    assert opens < monday.isoformat(), "the window has to open before the week does"


def test_the_request_carries_a_contact_address():
    """OpenAlex asks for one and gives politer service in return."""
    query = OpenAlexCollector().params_for("2026-W35", cursor="*")
    assert "@" in query.get("mailto", "")
