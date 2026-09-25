import datetime as dt
import json
from pathlib import Path

from observatory.collectors import pressroom
from observatory.collectors.pressroom import PressroomCollector

FIX = Path(__file__).parent / "fixtures"


def _docs(name):
    return PressroomCollector().parse((FIX / name).read_text())


def test_pressrooms_yaml_loads_and_every_kind_is_known():
    rooms = pressroom.load_pressrooms()
    assert len(rooms) >= 16 and all(r.kind in ("rss", "sitemap", "html") or r.kind.startswith("links:") for r in rooms)
    assert all(r.url.startswith("https://") for r in rooms)


def test_rss_items_become_documents_with_page_text_and_vendor():
    docs = _docs("pressroom_rss.json")
    assert [d.date for d in docs] == ["2026-09-16", "2026-09-01"]
    first = docs[0]
    assert first.doc_id.startswith("pressroom:") and first.entity == "berkshiregrey"
    assert first.url == "https://www.berkshiregrey.com/news/acme-dc/"
    assert "first of three sites" in first.text and "1,200 picks" in first.text   # two long paragraphs, the short one skipped
    assert "Short." not in first.text
    assert docs[1].text == "" or "e-book" in docs[1].title   # no page, no description: title still a document


def test_html_items_are_dated_from_nearby_text_or_url_and_undatable_links_are_dropped():
    docs = _docs("pressroom_html.json")
    assert {d.date for d in docs} == {"2026-09-24", "2026-08-14"}
    assert all("careers" not in d.url for d in docs)
    dtl = next(d for d in docs if "DTL" in d.title)
    assert "Fresno and Los Angeles" in dtl.text and dtl.url == "https://kodiak.ai/news/dtl-first-deliveries"


def test_sitemap_items_take_the_date_from_the_url_then_lastmod_and_skip_undated():
    docs = _docs("pressroom_sitemap.json")
    assert len(docs) == 1 and docs[0].date == "2026-09-01" and "City Harvest" in docs[0].text


def test_links_kind_dates_each_page_from_its_own_text():
    docs = _docs("pressroom_links.json")
    assert len(docs) == 1 and docs[0].date == "2026-08-07" and docs[0].title == "Delivering throughout the tournament"


def test_doc_ids_are_stable_hashes_of_the_url():
    a = _docs("pressroom_rss.json")[0].doc_id
    b = _docs("pressroom_rss.json")[0].doc_id
    assert a == b and len(a) == len("pressroom:") + 16


def test_parse_date_handles_the_three_common_shapes():
    assert pressroom.parse_date("September 24, 2026") == dt.date(2026, 9, 24)
    assert pressroom.parse_date("24 September 2026") == dt.date(2026, 9, 24)
    assert pressroom.parse_date("2026-09-24T10:00:00Z") == dt.date(2026, 9, 24)
    assert pressroom.parse_date("Tue, 16 Sep 2026 14:00:00 +0000") == dt.date(2026, 9, 16)
    assert pressroom.parse_date("no date here") is None


def test_an_envelope_with_notes_and_no_listing_yields_nothing():
    env = json.dumps({"vendor": "x", "kind": "html", "url": "https://x/", "fetched_week": "2026-W39",
                      "listing": "", "pages": {}, "notes": ["403"]})
    assert PressroomCollector().parse(env) == []
