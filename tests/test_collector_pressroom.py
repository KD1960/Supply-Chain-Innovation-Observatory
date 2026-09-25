import datetime as dt
import json
from pathlib import Path

import pytest

from observatory import http
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


# --- fetch_raw ---------------------------------------------------------------
#
# The fake mirrors what observatory.http.fetch reads from a response:
# status_code, text, url and headers (for Content-Type and Retry-After).


class FakeResponse:
    def __init__(self, status, text):
        self.status_code, self.text, self.url, self.headers = status, text, "", {}


class FakeSession:
    """Answers by URL; records requests. robots.txt disallows /private/."""

    def __init__(self, answers):
        self.answers, self.calls, self.headers = answers, [], {}

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            return FakeResponse(200, "User-agent: *\nDisallow: /private/\n")
        status, text = self.answers.get(url, (404, ""))
        return FakeResponse(status, text)


class _NoWait:
    """RateLimiter's shape without its sleeping."""

    def __init__(self, *_args, **_kwargs):
        pass

    def wait(self):
        pass


@pytest.fixture()
def no_wait(monkeypatch):
    monkeypatch.setattr(http, "RateLimiter", _NoWait)


def test_fetch_raw_yields_one_envelope_per_newsroom_and_fetches_only_in_window_pages(tmp_path, monkeypatch, no_wait):
    rooms = tmp_path / "rooms.yaml"
    rooms.write_text('version: 1\nnewsrooms:\n  - {vendor: k, url: "https://k.test/news", kind: html, chosen_for: [x]}\n')
    monkeypatch.setattr(pressroom, "PRESSROOMS_PATH", rooms)
    # Each date follows its anchor: items_from_html takes the nearest date either
    # side, so a date placed before the next anchor would sit at distance 0 from
    # the previous anchor's end and be claimed by it.
    listing = ('<li><a href="/news/new-item">A long enough title for the new item here</a>'
               '<span>September 24, 2026</span></li>'
               '<li><a href="/news/old-item">A long enough title for the old item here</a>'
               '<span>January 5, 2020</span></li>')
    session = FakeSession({"https://k.test/news": (200, listing),
                           "https://k.test/news/new-item": (200, "<p>" + "x" * 100 + "</p>")})
    pages = list(PressroomCollector().fetch_raw(session, "2026-W39"))
    assert len(pages) == 1
    env = json.loads(pages[0].text)
    assert set(env["pages"]) == {"https://k.test/news/new-item"}      # the 2020 item is out of window, not fetched
    assert "https://k.test/news/old-item" not in session.calls
    assert session.calls.count("https://k.test/robots.txt") == 1     # robots read once per host


def test_fetch_raw_obeys_robots_and_records_a_note_instead_of_fetching(tmp_path, monkeypatch, no_wait):
    rooms = tmp_path / "rooms.yaml"
    rooms.write_text('version: 1\nnewsrooms:\n  - {vendor: p, url: "https://p.test/private/news", kind: rss, chosen_for: [x]}\n')
    monkeypatch.setattr(pressroom, "PRESSROOMS_PATH", rooms)
    session = FakeSession({"https://p.test/private/news": (200, "<rss></rss>")})
    env = json.loads(next(PressroomCollector().fetch_raw(session, "2026-W39")).text)
    assert env["listing"] == "" and any("robots" in n for n in env["notes"])
    assert "https://p.test/private/news" not in session.calls


def test_a_failed_newsroom_still_yields_an_envelope_with_the_status(tmp_path, monkeypatch, no_wait):
    rooms = tmp_path / "rooms.yaml"
    rooms.write_text('version: 1\nnewsrooms:\n  - {vendor: t, url: "https://t.test/press", kind: html, chosen_for: [x]}\n')
    monkeypatch.setattr(pressroom, "PRESSROOMS_PATH", rooms)
    env = json.loads(next(PressroomCollector().fetch_raw(FakeSession({"https://t.test/press": (403, "blocked")}), "2026-W39")).text)
    assert env["listing"] == "" and any("403" in n for n in env["notes"])


def test_a_robots_txt_that_cannot_be_fetched_means_allow(monkeypatch, no_wait):
    class NoRobots(FakeSession):
        def get(self, url, params=None, headers=None, timeout=None):
            if url.endswith("/robots.txt"):
                self.calls.append(url)
                return FakeResponse(404, "")
            return super().get(url, params, headers, timeout)

    assert pressroom.robots_allows(NoRobots({}), "https://n.test/private/x", {}, _NoWait())
