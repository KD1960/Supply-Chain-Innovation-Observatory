import json
from pathlib import Path

from observatory.collectors.hn import HackerNewsCollector

FIXTURE = Path(__file__).parent / "fixtures" / "hn_page.json"


def test_parse_extracts_both_stories():
    assert len(HackerNewsCollector().parse(FIXTURE.read_text())) == 2


def test_points_land_in_amount_for_summing():
    documents = HackerNewsCollector().parse(FIXTURE.read_text())
    assert documents[0].amount == 214.0
    assert documents[1].amount == 38.0


def test_doc_id_is_namespaced_and_date_is_iso():
    first = HackerNewsCollector().parse(FIXTURE.read_text())[0]
    assert first.doc_id == "hn:41234567"
    assert first.date == "2026-08-12"


def test_story_without_url_falls_back_to_the_item_page():
    second = HackerNewsCollector().parse(FIXTURE.read_text())[1]
    assert second.url == "https://news.ycombinator.com/item?id=41234599"


def test_story_text_is_searchable_body():
    second = HackerNewsCollector().parse(FIXTURE.read_text())[1]
    assert "AMRs" in second.text


def test_parse_handles_an_empty_result_set():
    assert HackerNewsCollector().parse(json.dumps({"hits": []})) == []


def test_numeric_filters_bound_the_week_plus_a_seven_day_lookback():
    # 1786320000 is Monday 2026-08-10; the lower bound sits a week earlier at
    # 2026-08-03 so late-indexed stories are still caught.
    filters = HackerNewsCollector().numeric_filters("2026-W33")
    assert filters == "created_at_i>=1785715200,created_at_i<1786924800"
