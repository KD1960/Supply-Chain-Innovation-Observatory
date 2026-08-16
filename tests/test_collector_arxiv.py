from pathlib import Path

from observatory.collectors.arxiv import ArxivCollector

FIXTURE = Path(__file__).parent / "fixtures" / "arxiv_page.xml"


def test_parse_extracts_both_entries():
    documents = ArxivCollector().parse(FIXTURE.read_text())
    assert len(documents) == 2


def test_parse_uses_the_versionless_id_and_published_date():
    first = ArxivCollector().parse(FIXTURE.read_text())[0]
    assert first.doc_id == "arxiv:2608.01234"
    assert first.date == "2026-08-12"


def test_parse_normalises_whitespace_in_title_and_abstract():
    first = ArxivCollector().parse(FIXTURE.read_text())[0]
    assert first.title == "Fleet Learning for Autonomous Trucking on Interstate Corridors"
    assert first.text.startswith("We study closed-loop fleet learning")
    assert "\n" not in first.text


def test_parse_keeps_the_abstract_url():
    first = ArxivCollector().parse(FIXTURE.read_text())[0]
    assert first.url == "https://arxiv.org/abs/2608.01234"


def test_parse_returns_nothing_for_an_empty_feed():
    empty = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
    assert ArxivCollector().parse(empty) == []


def test_query_window_covers_the_whole_iso_week():
    query = ArxivCollector().date_filter("2026-W33")
    assert query == "submittedDate:[202608100000+TO+202608170000]"
