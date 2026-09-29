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


ORIGINAL_16 = {"aurora", "kodiak", "plus", "wing", "agility", "figure", "apptronik", "circularise",
               "averydennison", "gs1us", "daimlertruck", "volvotrucks_us", "righthand", "berkshiregrey",
               "symbotic", "locus"}


def test_pressrooms_yaml_slugs_are_unique_and_the_original_16_are_kept_first():
    rooms = pressroom.load_pressrooms()
    slugs = [r.vendor for r in rooms]
    assert len(slugs) == len(set(slugs))
    assert all(s == s.lower() and " " not in s for s in slugs)
    assert set(slugs[:16]) == ORIGINAL_16


def test_no_vendor_is_both_read_and_not_reachable_and_the_dropped_ones_are_listed():
    import yaml
    raw = yaml.safe_load(pressroom.PRESSROOMS_PATH.read_text())
    read = {r["vendor"] for r in raw["newsrooms"]}
    unreachable = {r["vendor"] for r in raw["not_reachable"]}
    assert not read & unreachable
    assert {"jaggaer", "brightpick", "checkpoint", "pactum", "ambi", "vimaan", "nfi", "amazon"} <= unreachable
    assert all(r.get("checked") and r.get("reason") for r in raw["not_reachable"])


def test_every_chosen_for_is_a_watchlist_technology_or_user_firm():
    from observatory import matcher
    ids = {t.id for t in matcher.load_watchlist().technologies} | {"user_firm"}
    rooms = pressroom.load_pressrooms()
    assert all(r.chosen_for for r in rooms)
    assert {c for r in rooms for c in r.chosen_for} <= ids


def test_rss_items_become_documents_with_page_text_and_vendor():
    docs = _docs("pressroom_rss.json")
    assert [d.date for d in docs] == ["2026-09-16", "2026-09-15"]
    first = docs[0]
    assert first.doc_id.startswith("pressroom:") and first.entity == "berkshiregrey"
    assert first.url == "https://www.berkshiregrey.com/news/acme-dc/"
    assert "first of three sites" in first.text and "1,200 picks" in first.text   # two long paragraphs, the short one skipped
    assert "Short." not in first.text
    assert docs[1].text == "" or "e-book" in docs[1].title   # no page, no description: title still a document


def test_html_items_are_dated_from_nearby_text_or_url_and_undatable_links_are_dropped():
    docs = _docs("pressroom_html.json")
    assert {d.date for d in docs} == {"2026-09-24", "2026-09-18"}
    assert all("careers" not in d.url for d in docs)
    dtl = next(d for d in docs if "DTL" in d.title)
    assert "Fresno and Los Angeles" in dtl.text and dtl.url == "https://kodiak.ai/news/dtl-first-deliveries"


def test_sitemap_items_take_the_date_from_the_url_then_lastmod_and_skip_undated():
    """The fixture's URL dates only the month (/2026/september/); its page
    carries the day, which becomes the document's date."""
    docs = _docs("pressroom_sitemap.json")
    assert len(docs) == 1 and docs[0].date == "2026-09-03" and "City Harvest" in docs[0].text


def _month_only_env(page_date):
    url = "https://v.test/news/2026/september/foo/"
    listing = f"<urlset><url><loc>{url}</loc></url></urlset>"
    page = f"<html><body><p>{page_date}</p><p>{'Volvo delivers electric trucks. ' * 4}</p></body></html>"
    return json.dumps({"vendor": "v", "kind": "sitemap", "url": "https://v.test/sitemap.xml",
                       "fetched_week": "2026-W39", "listing": listing, "pages": {url: page}, "notes": []})


def test_a_month_only_sitemap_item_is_redated_from_its_page():
    """/2026/september/ once dated every release to the 1st, so one from the
    20th fell outside every window after the month's first days."""
    docs = PressroomCollector().parse(_month_only_env("September 20, 2026"))
    assert [d.date for d in docs] == ["2026-09-20"]


def test_a_month_only_sitemap_item_whose_page_date_is_out_of_window_is_dropped():
    assert PressroomCollector().parse(_month_only_env("September 2, 2026")) == []


def test_a_month_only_item_with_no_page_or_no_page_date_is_dropped():
    env = json.loads(_month_only_env("no date"))
    assert PressroomCollector().parse(json.dumps(env)) == []
    env["pages"] = {}
    assert PressroomCollector().parse(json.dumps(env)) == []


def test_in_window_for_a_month_only_item_asks_whether_its_month_meets_the_window():
    start, end = dt.date(2026, 9, 14), dt.date(2026, 9, 27)
    sept = pressroom.Item("t", "u", dt.date(2026, 9, 1), month_only=True)
    june = pressroom.Item("t", "u", dt.date(2026, 6, 1), month_only=True)
    assert pressroom.in_window(sept, start, end) and not pressroom.in_window(june, start, end)
    assert not pressroom.in_window(pressroom.Item("t", "u", dt.date(2026, 9, 1)), start, end)


def test_visible_text_unescapes_entities():
    assert pressroom.visible_text("<p>Plus&#39;s &amp; AT&amp;T&nbsp;&rsquo;</p>") == "Plus's & AT&T \u2019"


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


def test_parse_keeps_only_items_dated_inside_the_envelopes_own_window():
    """A listing carries its whole history; only the run week and its lookback
    are collected, or every run re-parses and re-counts the same items."""
    listing = ('<rss><item><title>In window</title><link>https://r.test/new</link>'
               '<pubDate>Wed, 16 Sep 2026 10:00:00 +0000</pubDate></item>'
               '<item><title>Years old</title><link>https://r.test/old</link>'
               '<pubDate>Sun, 05 Jan 2020 10:00:00 +0000</pubDate></item></rss>')
    env = json.dumps({"vendor": "r", "kind": "rss", "url": "https://r.test/feed", "fetched_week": "2026-W39",
                      "listing": listing, "pages": {}, "notes": []})
    assert [d.date for d in PressroomCollector().parse(env)] == ["2026-09-16"]


# --- fetch_raw ---------------------------------------------------------------
#
# The fake mirrors what observatory.http.fetch reads from a response:
# status_code, text, url and headers (for Content-Type and Retry-After).


class FakeResponse:
    def __init__(self, status, text, location=None):
        self.status_code, self.text, self.url = status, text, ""
        self.headers = {"Location": location} if location else {}


class FakeSession:
    """Answers by URL with (status, text) or (status, text, location); records
    requests. robots.txt disallows /private/ unless told otherwise."""

    def __init__(self, answers, robots=(200, "User-agent: *\nDisallow: /private/\n")):
        self.answers, self.calls, self.headers, self.robots = answers, [], {}, robots

    def get(self, url, params=None, headers=None, timeout=None, **kwargs):
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            return FakeResponse(*self.robots)
        return FakeResponse(*self.answers.get(url, (404, "")))


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
    monkeypatch.setattr(http, "_backoff_seconds", lambda *a, **k: 0)
    rooms = tmp_path / "rooms.yaml"
    rooms.write_text('version: 1\nnewsrooms:\n  - {vendor: k, url: "https://k.test/news", kind: html, chosen_for: [x]}\n')
    monkeypatch.setattr(pressroom, "PRESSROOMS_PATH", rooms)
    # Each date follows its anchor: items_from_html takes the nearest date either
    # side, so a date placed before the next anchor would sit at distance 0 from
    # the previous anchor's end and be claimed by it.
    listing = ('<li><a href="/news/new-item">A long enough title for the new item here</a>'
               '<span>September 24, 2026</span></li>'
               '<li><a href="/news/old-item">A long enough title for the old item here</a>'
               '<span>January 5, 2020</span></li>'
               '<li><a href="/news/hanging-item">A long enough title for the hanging item here</a>'
               '<span>September 23, 2026</span></li>')
    session = FakeSession({"https://k.test/news": (200, listing),
                           "https://k.test/news/new-item": (200, "<p>" + "x" * 100 + "</p>"),
                           "https://k.test/news/hanging-item": (503, "")})
    pages = list(PressroomCollector().fetch_raw(session, "2026-W39"))
    assert len(pages) == 1
    env = json.loads(pages[0].text)
    assert set(env["pages"]) == {"https://k.test/news/new-item"}      # the 2020 item is out of window, not fetched
    # An item page gets one retry, not three: a hanging origin costs two timeouts.
    assert session.calls.count("https://k.test/news/hanging-item") == 2
    assert any("hanging-item" in n for n in env["notes"])
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
    page = next(PressroomCollector().fetch_raw(FakeSession({"https://t.test/press": (403, "blocked")}), "2026-W39"))
    env = json.loads(page.text)
    assert env["listing"] == "" and any("403" in n for n in env["notes"])
    assert page.status == 403


def test_a_robots_txt_that_cannot_be_fetched_means_allow(monkeypatch, no_wait):
    class NoRobots(FakeSession):
        def get(self, url, params=None, headers=None, timeout=None, **kwargs):
            if url.endswith("/robots.txt"):
                self.calls.append(url)
                return FakeResponse(404, "")
            return super().get(url, params, headers, timeout, **kwargs)

    assert pressroom.robots_allows(NoRobots({}), "https://n.test/private/x", {}, _NoWait())


def test_a_robots_txt_server_error_means_disallow(monkeypatch, no_wait):
    monkeypatch.setattr(http, "_backoff_seconds", lambda *a, **k: 0)

    class BrokenRobots(FakeSession):
        def get(self, url, params=None, headers=None, timeout=None, **kwargs):
            if url.endswith("/robots.txt"):
                self.calls.append(url)
                return FakeResponse(503, "")
            return super().get(url, params, headers, timeout, **kwargs)

    session = BrokenRobots({})
    assert not pressroom.robots_allows(session, "https://s.test/news", {}, _NoWait())
    assert session.calls.count("https://s.test/robots.txt") == 2          # one retry


def test_fetch_raw_fetches_a_month_only_sitemap_item_when_its_month_meets_the_window(tmp_path, monkeypatch, no_wait):
    rooms = tmp_path / "rooms.yaml"
    rooms.write_text('version: 1\nnewsrooms:\n  - {vendor: v, url: "https://v.test/sitemap.xml", kind: sitemap}\n')
    monkeypatch.setattr(pressroom, "PRESSROOMS_PATH", rooms)
    listing = ("<urlset><url><loc>https://v.test/news/2026/september/foo/</loc></url>"
               "<url><loc>https://v.test/news/2026/june/bar/</loc></url></urlset>")
    session = FakeSession({"https://v.test/sitemap.xml": (200, listing),
                           "https://v.test/news/2026/september/foo/": (200, "<p>September 20, 2026</p>")})
    env = json.loads(next(PressroomCollector().fetch_raw(session, "2026-W39")).text)
    assert set(env["pages"]) == {"https://v.test/news/2026/september/foo/"}
    assert [d.date for d in PressroomCollector().parse(json.dumps(env))] == ["2026-09-20"]


def test_item_hrefs_resolve_against_the_listings_final_url(tmp_path, monkeypatch, no_wait):
    """A listing that redirects to another host: relative hrefs belong to the
    host that served the listing, not the one in pressrooms.yaml, and that
    host's robots.txt is read before the listing is fetched from it."""
    rooms = tmp_path / "rooms.yaml"
    rooms.write_text('version: 1\nnewsrooms:\n  - {vendor: r, url: "https://old.test/news", kind: html}\n')
    monkeypatch.setattr(pressroom, "PRESSROOMS_PATH", rooms)
    listing = ('<li><a href="/news/item">A long enough title for the moved item here</a>'
               '<span>September 24, 2026</span></li>')
    session = FakeSession({"https://old.test/news": (301, "", "https://new.test/news"),
                           "https://new.test/news": (200, listing),
                           "https://new.test/news/item": (200, "<p>" + "y" * 100 + "</p>")})
    env = json.loads(next(PressroomCollector().fetch_raw(session, "2026-W39")).text)
    assert env["resolved_url"] == "https://new.test/news"
    assert set(env["pages"]) == {"https://new.test/news/item"}
    assert [d.url for d in PressroomCollector().parse(json.dumps(env))] == ["https://new.test/news/item"]
    assert session.calls.index("https://new.test/robots.txt") < session.calls.index("https://new.test/news")


def _two_rooms(tmp_path, monkeypatch):
    rooms = tmp_path / "rooms.yaml"
    rooms.write_text('version: 1\nnewsrooms:\n'
                     '  - {vendor: a, url: "https://a.test/news", kind: rss, chosen_for: [x]}\n'
                     '  - {vendor: b, url: "https://b.test/news", kind: rss, chosen_for: [x]}\n')
    monkeypatch.setattr(pressroom, "PRESSROOMS_PATH", rooms)


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    from observatory import run, store
    monkeypatch.setattr(run.base.config, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(run.base.config, "RUN_LOG_PATH", tmp_path / "run_log.jsonl")
    monkeypatch.setattr(run.base.config, "DB_PATH", tmp_path / "observatory.db")
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def _status(conn):
    from observatory import store
    return {row["name"]: row for row in store.source_statuses(conn)}["pressroom"]


def test_every_newsroom_failing_records_the_source_failed_not_ok(tmp_path, monkeypatch, no_wait, conn):
    """A hole, not a zero: an ok source with no listings would write
    press_releases = 0 for every technology."""
    from observatory import run
    _two_rooms(tmp_path, monkeypatch)
    session = FakeSession({"https://a.test/news": (403, "blocked")})   # b.test: 404
    assert run.fetch_week(conn, "2026-W39", [PressroomCollector()], session) == set()
    assert _status(conn)["status"] == "failed"
    assert len(list((tmp_path / "raw" / "2026-W39" / "pressroom").iterdir())) == 2   # the envelopes stay


def test_one_newsroom_failing_of_two_is_still_ok(tmp_path, monkeypatch, no_wait, conn):
    from observatory import run
    _two_rooms(tmp_path, monkeypatch)
    session = FakeSession({"https://a.test/news": (403, "blocked"), "https://b.test/news": (200, "<rss></rss>")})
    assert run.fetch_week(conn, "2026-W39", [PressroomCollector()], session) == {"pressroom"}
    assert _status(conn)["status"] == "ok"


def test_an_undated_card_does_not_borrow_its_neighbours_date():
    html = ('<ul><li><a href="/news/first">A long enough title for the first card here</a>'
            '<span>September 24, 2026</span></li>'
            '<li><a href="/news/second">A long enough title for the second card here</a></li></ul>')
    items = pressroom.items_from_html(html, "https://k.test/news")
    assert [(i.url, i.date) for i in items] == [("https://k.test/news/first", dt.date(2026, 9, 24))]


def test_parse_date_reads_a_two_digit_year_only_in_the_rfc_822_shape():
    assert pressroom.parse_date("Tue, 29 Sep 26 11:47:15 EDT") == dt.date(2026, 9, 29)
    assert pressroom.parse_date("29 Sep 26 11:47 GMT") == dt.date(2026, 9, 29)
    assert pressroom.parse_date("Fri, 01 Jan 99 00:00:00 +0000") == dt.date(1999, 1, 1)
    assert pressroom.parse_date("Thu, 31 Dec 70 23:59:59 GMT") == dt.date(1970, 12, 31)
    assert pressroom.parse_date("Tue, 01 Jan 69 12:00:00 GMT") == dt.date(2069, 1, 1)
    assert pressroom.parse_date("chapter 29 Sep 26 pages") is None
    assert pressroom.parse_date("129 Sep 261 11:47") is None
    assert pressroom.parse_date("Tue, 29 Sep 2026 11:47:15 EDT") == dt.date(2026, 9, 29)   # four digits still win


def _one_room(tmp_path, monkeypatch, kind="html"):
    rooms = tmp_path / "rooms.yaml"
    rooms.write_text(f'version: 1\nnewsrooms:\n  - {{vendor: c, url: "https://c.test/news", kind: {kind}}}\n')
    monkeypatch.setattr(pressroom, "PRESSROOMS_PATH", rooms)


def test_a_robots_server_error_skips_the_host_with_a_note_that_says_why(tmp_path, monkeypatch, no_wait):
    """Unavailable is not the same finding as disallowed: the note keeps them apart."""
    monkeypatch.setattr(http, "_backoff_seconds", lambda *a, **k: 0)
    _one_room(tmp_path, monkeypatch)
    session = FakeSession({"https://c.test/news": (200, "<p>listing</p>")}, robots=(503, ""))
    env = json.loads(next(PressroomCollector().fetch_raw(session, "2026-W39")).text)
    assert env["listing"] == "" and "https://c.test/news" not in session.calls
    assert "robots.txt unavailable (503); host skipped this run" in env["notes"]
    assert not any("disallows" in n for n in env["notes"])


def test_a_robots_network_error_means_disallow(monkeypatch, no_wait):
    """RFC 9309 2.3.1.4: unreachable is complete disallow, like a 5xx."""
    monkeypatch.setattr(http, "_backoff_seconds", lambda *a, **k: 0)
    import requests

    class Unreachable(FakeSession):
        def get(self, url, params=None, headers=None, timeout=None, **kwargs):
            if url.endswith("/robots.txt"):
                raise requests.ConnectionError("refused")
            return super().get(url, params, headers, timeout, **kwargs)

    assert not pressroom.robots_allows(Unreachable({}), "https://u.test/news", {}, _NoWait())


def test_a_robots_404_allows_the_listing(tmp_path, monkeypatch, no_wait):
    _one_room(tmp_path, monkeypatch)
    session = FakeSession({"https://c.test/news": (200, "<p>listing</p>")}, robots=(404, ""))
    env = json.loads(next(PressroomCollector().fetch_raw(session, "2026-W39")).text)
    assert env["listing"] == "<p>listing</p>" and not any("robots" in n for n in env["notes"])


_TWO_ITEMS = ('<li><a href="/news/one">A long enough title for the first item here</a>'
              '<span>September 24, 2026</span></li>'
              '<li><a href="/news/two">A long enough title for the second item here</a>'
              '<span>September 23, 2026</span></li>')


class _FakeClock:
    """A clock that only moves when slept on, and records each sleep."""

    def __init__(self):
        self.now, self.sleeps = 0.0, []

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def clock(self):
        return self.now


def test_crawl_delay_spaces_requests_to_its_host(tmp_path, monkeypatch):
    _one_room(tmp_path, monkeypatch)
    session = FakeSession({"https://c.test/news": (200, _TWO_ITEMS),
                           "https://c.test/news/one": (200, "<p>one</p>"),
                           "https://c.test/news/two": (200, "<p>two</p>")},
                          robots=(200, "User-agent: *\nCrawl-delay: 5\n"))
    fake = _FakeClock()
    env = json.loads(next(PressroomCollector(sleep_fn=fake.sleep, clock_fn=fake.clock)
                          .fetch_raw(session, "2026-W39")).text)
    assert set(env["pages"]) == {"https://c.test/news/one", "https://c.test/news/two"}
    # robots, listing, two pages: three gaps, each the crawl-delay, not the 2 s rate limit
    assert len(fake.sleeps) == 3 and all(s >= 5 for s in fake.sleeps)


def test_a_crawl_delay_over_30_s_fetches_the_listing_only(tmp_path, monkeypatch):
    _one_room(tmp_path, monkeypatch)
    session = FakeSession({"https://c.test/news": (200, _TWO_ITEMS),
                           "https://c.test/news/one": (200, "<p>one</p>")},
                          robots=(200, "User-agent: *\nCrawl-delay: 60\n"))
    fake = _FakeClock()
    env = json.loads(next(PressroomCollector(sleep_fn=fake.sleep, clock_fn=fake.clock)
                          .fetch_raw(session, "2026-W39")).text)
    assert env["listing"] == _TWO_ITEMS and env["pages"] == {}
    assert "https://c.test/news/one" not in session.calls
    assert any("crawl-delay 60" in n for n in env["notes"])
    assert fake.sleeps == [30]            # the one wait, before the listing, is capped


def test_a_listing_redirected_to_a_disallowed_path_is_not_fetched(tmp_path, monkeypatch, no_wait):
    _one_room(tmp_path, monkeypatch)
    session = FakeSession({"https://c.test/news": (301, "", "/private/news"),
                           "https://c.test/private/news": (200, "<p>listing</p>")})
    env = json.loads(next(PressroomCollector().fetch_raw(session, "2026-W39")).text)
    assert env["listing"] == "" and "https://c.test/private/news" not in session.calls
    assert "robots.txt disallows redirect target https://c.test/private/news" in env["notes"]


def test_a_redirect_loop_stops_after_five_hops(tmp_path, monkeypatch, no_wait):
    _one_room(tmp_path, monkeypatch)
    session = FakeSession({"https://c.test/news": (302, "", "https://c.test/news2"),
                           "https://c.test/news2": (302, "", "https://c.test/news")})
    env = json.loads(next(PressroomCollector().fetch_raw(session, "2026-W39")).text)
    assert env["listing"] == ""
    assert len([c for c in session.calls if not c.endswith("robots.txt")]) == 6    # the request and 5 hops
    assert any("more than 5 redirects" in n for n in env["notes"])


def test_a_robots_429_skips_the_host_like_a_server_error(tmp_path, monkeypatch, no_wait):
    monkeypatch.setattr(http, "_backoff_seconds", lambda *a, **k: 0)
    _one_room(tmp_path, monkeypatch)
    session = FakeSession({"https://c.test/news": (200, "<p>listing</p>")}, robots=(429, ""))
    env = json.loads(next(PressroomCollector().fetch_raw(session, "2026-W39")).text)
    assert "https://c.test/news" not in session.calls
    assert "robots.txt unavailable (429); host skipped this run" in env["notes"]


def test_a_robots_network_error_is_noted_as_unavailable(tmp_path, monkeypatch, no_wait):
    monkeypatch.setattr(http, "_backoff_seconds", lambda *a, **k: 0)
    _one_room(tmp_path, monkeypatch)
    import requests

    class Unreachable(FakeSession):
        def get(self, url, params=None, headers=None, timeout=None, **kwargs):
            if url.endswith("/robots.txt"):
                raise requests.ConnectionError("refused")
            return super().get(url, params, headers, timeout, **kwargs)

    session = Unreachable({"https://c.test/news": (200, "<p>listing</p>")})
    env = json.loads(next(PressroomCollector().fetch_raw(session, "2026-W39")).text)
    assert "https://c.test/news" not in session.calls
    assert "robots.txt unavailable (network error); host skipped this run" in env["notes"]


def test_item_pages_on_a_host_whose_robots_is_unavailable_are_skipped_with_one_note(tmp_path, monkeypatch,
                                                                                   no_wait):
    monkeypatch.setattr(http, "_backoff_seconds", lambda *a, **k: 0)
    _one_room(tmp_path, monkeypatch)
    listing = _TWO_ITEMS.replace('href="/news/', 'href="https://ir.c.test/news/')

    class DownRobots(FakeSession):
        def get(self, url, params=None, headers=None, timeout=None, **kwargs):
            if url == "https://ir.c.test/robots.txt":
                self.calls.append(url)
                return FakeResponse(503, "")
            return super().get(url, params, headers, timeout, **kwargs)

    session = DownRobots({"https://c.test/news": (200, listing)})
    env = json.loads(next(PressroomCollector().fetch_raw(session, "2026-W39")).text)
    assert env["pages"] == {} and not any(c.startswith("https://ir.c.test/news") for c in session.calls)
    assert env["notes"] == ["robots.txt unavailable (503); https://ir.c.test skipped this run"]


def test_a_malformed_item_url_costs_that_item_not_the_newsroom(tmp_path, monkeypatch, no_wait):
    _one_room(tmp_path, monkeypatch)
    listing = _TWO_ITEMS.replace('href="/news/one"', 'href="https://c.test:99999/news/one"')
    session = FakeSession({"https://c.test/news": (200, listing), "https://c.test/news/two": (200, "<p>two</p>")})
    env = json.loads(next(PressroomCollector().fetch_raw(session, "2026-W39")).text)
    assert set(env["pages"]) == {"https://c.test/news/two"}
    assert not any("99999" in c for c in session.calls)          # never requested
    assert any("99999" in n for n in env["notes"])


def test_the_robots_and_limiter_key_is_the_canonical_host():
    assert pressroom._host("HTTPS://WWW.X.test:443/a") == "https://www.x.test"
    assert pressroom._host("http://x.test:80/a") == "http://x.test"
    assert pressroom._host("https://x.test:8443/a") == "https://x.test:8443"


def test_item_pages_on_another_site_are_not_fetched(tmp_path, monkeypatch, no_wait):
    """A listing that links press coverage (a trade title, a wire) keeps the
    item from the listing but does not fetch the other site's page: the
    newsroom's robots.txt says nothing about that site."""
    rooms = tmp_path / "rooms.yaml"
    rooms.write_text('version: 1\nnewsrooms:\n  - {vendor: k, url: "https://www.k.test/news", kind: html}\n')
    monkeypatch.setattr(pressroom, "PRESSROOMS_PATH", rooms)
    listing = ('<li><a href="https://news.k.test/own">A long enough title for our own release here</a>'
               '<span>September 24, 2026</span></li>'
               '<li><a href="https://press.test/story">A long enough title for the coverage item here</a>'
               '<span>September 23, 2026</span></li>')
    session = FakeSession({"https://www.k.test/news": (200, listing),
                           "https://news.k.test/own": (200, "<p>" + "z" * 100 + "</p>")})
    env = json.loads(next(PressroomCollector().fetch_raw(session, "2026-W39")).text)
    assert set(env["pages"]) == {"https://news.k.test/own"}
    assert not any(c.startswith("https://press.test/") for c in session.calls)
    assert any("other sites" in n for n in env["notes"])
    # Press coverage under a vendor's name is not its release: the off-site item
    # is not a document either, only the newsroom's own.
    assert [d.url for d in PressroomCollector().parse(json.dumps(env))] == ["https://news.k.test/own"]


def test_site_is_the_registrable_domain_approximately():
    assert pressroom._site("https://ir.aurora.tech/x") == pressroom._site("https://aurora.tech/") == "aurora.tech"
    assert pressroom._site("https://www.bbc.co.uk/news") == "bbc.co.uk"
    assert pressroom._site("https://www.freightwaves.com/a") != pressroom._site("https://plus.ai/news")


def test_an_item_redirect_that_leaves_the_newsrooms_site_is_not_followed(tmp_path, monkeypatch, no_wait):
    _one_room(tmp_path, monkeypatch)
    listing = ('<li><a href="/news/moved">A long enough title for the moved item here</a>'
               '<span>September 24, 2026</span></li>')
    session = FakeSession({"https://c.test/news": (200, listing),
                           "https://c.test/news/moved": (301, "", "https://press.test/story")})
    env = json.loads(next(PressroomCollector().fetch_raw(session, "2026-W39")).text)
    assert env["pages"] == {}
    assert "https://press.test/story" not in session.calls and "https://press.test/robots.txt" not in session.calls
    assert "redirect leaves the newsroom's site: https://press.test/story" in env["notes"]


def test_the_listing_may_still_redirect_to_another_host(tmp_path, monkeypatch, no_wait):
    _one_room(tmp_path, monkeypatch)
    session = FakeSession({"https://c.test/news": (301, "", "https://d.test/news"),
                           "https://d.test/news": (200, "<rss></rss>")})
    env = json.loads(next(PressroomCollector().fetch_raw(session, "2026-W39")).text)
    assert env["resolved_url"] == "https://d.test/news" and env["listing"] == "<rss></rss>"


def test_the_listing_gets_one_retry(tmp_path, monkeypatch, no_wait):
    monkeypatch.setattr(http, "_backoff_seconds", lambda *a, **k: 0)
    _one_room(tmp_path, monkeypatch)
    session = FakeSession({"https://c.test/news": (503, "")})
    env = json.loads(next(PressroomCollector().fetch_raw(session, "2026-W39")).text)
    assert session.calls.count("https://c.test/news") == 2 and env["listing"] == ""


def test_a_run_over_its_time_budget_records_the_newsrooms_it_did_not_reach(tmp_path, monkeypatch, conn):
    """A cron run must end: past max_seconds, each newsroom not reached gets an
    envelope saying it was not fetched, and the source is still ok because one
    newsroom produced a listing."""
    from observatory import run
    rooms = tmp_path / "rooms.yaml"
    rooms.write_text('version: 1\nnewsrooms:\n'
                     '  - {vendor: a, url: "https://a.test/news", kind: rss}\n'
                     '  - {vendor: b, url: "https://b.test/news", kind: rss}\n'
                     '  - {vendor: c, url: "https://c.test/news", kind: rss}\n')
    monkeypatch.setattr(pressroom, "PRESSROOMS_PATH", rooms)
    session = FakeSession({f"https://{h}.test/news": (200, "<rss></rss>") for h in "abc"},
                          robots=(200, "User-agent: *\nCrawl-delay: 20\n"))
    fake = _FakeClock()
    collector = PressroomCollector(sleep_fn=fake.sleep, clock_fn=fake.clock)
    collector.max_seconds = 10     # robots then listing on a.test: one 20 s wait
    assert run.fetch_week(conn, "2026-W39", [collector], session) == {"pressroom"}
    envs = [json.loads(p.read_text()) for p in sorted((tmp_path / "raw" / "2026-W39" / "pressroom").iterdir())]
    assert [e["vendor"] for e in envs] == ["a", "b", "c"]
    assert envs[0]["listing"] == "<rss></rss>"
    assert [e["notes"] for e in envs[1:]] == [["time budget exhausted; not fetched this run"]] * 2
    assert not any(u.startswith(("https://b.test", "https://c.test")) for u in session.calls)
    assert _status(conn)["status"] == "ok"
