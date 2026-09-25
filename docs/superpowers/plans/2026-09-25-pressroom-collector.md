# Press-room Collector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A weekly `pressroom` collector over a config list of vendor newsrooms, registered like every other collector, run once for the current week, with its first yield measured and recorded.

**Architecture:** `observatory/collectors/pressroom.py` follows the `BaseCollector` contract (`fetch_raw` touches the network and yields `RawPage`s; `parse` is pure). Each `RawPage` is a JSON envelope for one newsroom: `{"vendor", "kind", "url", "fetched_week", "listing": <text>, "pages": {url: html}, "notes": [..]}`. `parse` extracts items from the listing by kind, dates them, takes opening text from the item page when present (else the RSS description), and yields `Document`s. Newsrooms live in `pressrooms.yaml`. Registration adds the source to `run.COLLECTORS`, an `Aggregation("press_releases", "pressroom", "count")`, the `press` family and `deployment` stage maps.

**Tech Stack:** Python 3.13, stdlib (`re`, `json`, `datetime`, `urllib.robotparser`, `urllib.parse`), PyYAML, requests via `observatory.http`; pytest.

## Global Constraints

- Raw before parse: `parse(text)` reads only the envelope text. Tests exercise `parse` against fixtures only.
- No `anthropic`, no model call, no import of `observatory.claims` or `observatory.trl` anywhere in the collector (`tests/test_claims_isolation.py` enforces the first two).
- Obey `robots.txt`; never evade a 403, captcha or JavaScript shell. One request per 2 s. At most 15 item pages per newsroom per run.
- A failed newsroom marks the source degraded for the week; never zero.
- Never `git add -A`; nothing under `data/` committed. Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Do NOT run `--rebuild` or `--backfill`: since 2026-09-24 a rebuild drops the 485 frozen Scopus/Lens observations (STATUS §5). Task 3 runs `--only pressroom` for the current week only.
- Python: `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`.

## File structure

| Path | Responsibility |
|---|---|
| `pressrooms.yaml` | the newsroom list: `vendor`, `url`, `kind`, `chosen_for` (Task 1) |
| `observatory/collectors/pressroom.py` | parsers by kind, date parsing, text extraction, `PressroomCollector` (Tasks 1–2) |
| `tests/fixtures/pressroom_rss.json`, `pressroom_html.json`, `pressroom_sitemap.json`, `pressroom_links.json` | envelopes (Task 1) |
| `tests/test_collector_pressroom.py` | parse tests (Task 1), fetch tests with a fake session (Task 2) |
| `observatory/run.py`, `observatory/normalize.py`, `observatory/metrics.py`, `observatory/quarter.py` | registration (Task 2) |
| `docs/pressroom-first-run-2026-09-25.md`, `STATUS.md` | first run measured (Task 3) |

---

### Task 1: Config, parsers and `parse()`

**Files:**
- Create: `pressrooms.yaml`, `observatory/collectors/pressroom.py`, `tests/test_collector_pressroom.py`, four fixtures under `tests/fixtures/`.

**Interfaces:**
- Produces: `load_pressrooms(path=None) -> list[Newsroom]` (`Newsroom` frozen dataclass: `vendor, url, kind, chosen_for: tuple[str, ...]`); `parse_date(s) -> date | None`; `url_date(url) -> date | None`; `visible_text(html) -> str`; `opening_text(html) -> str` (first two `<p>` of ≥ 80 chars, joined, ≤ 1200 chars; else first 300 visible chars); `items_from_rss(xml)`, `items_from_sitemap(xml)`, `items_from_html(html, base)`, `links_under(html, base, path) -> list[str]` each returning `list[Item]` (`Item`: `title, url, date: date | None, description: str`); `PressroomCollector.parse(text) -> list[Document]`.

- [ ] **Step 1: pressrooms.yaml**

```yaml
# Vendor newsrooms the pressroom collector reads weekly. kind: rss | sitemap | html | links:<path>.
# chosen_for is provenance (why the newsroom is on the list); the matcher decides what an item evidences.
# Newsrooms that could not be read on 2026-09-25 are listed at the bottom with the reason, not fetched.
version: 1
newsrooms:
  - {vendor: aurora, url: "https://ir.aurora.tech/news-events/press-releases", kind: html, chosen_for: [autonomous_trucking]}
  - {vendor: kodiak, url: "https://kodiak.ai/news", kind: html, chosen_for: [autonomous_trucking]}
  - {vendor: plus, url: "https://plus.ai/news-and-insights", kind: html, chosen_for: [autonomous_trucking]}
  - {vendor: wing, url: "https://wing.com/news", kind: "links:/news/", chosen_for: [delivery_drones]}
  - {vendor: agility, url: "https://www.agilityrobotics.com/content", kind: html, chosen_for: [humanoid_logistics]}
  - {vendor: figure, url: "https://www.figure.ai/news", kind: html, chosen_for: [humanoid_logistics]}
  - {vendor: apptronik, url: "https://apptronik.com/company/press-releases", kind: html, chosen_for: [humanoid_logistics]}
  - {vendor: circularise, url: "https://www.circularise.com/blogs", kind: html, chosen_for: [digital_product_passport]}
  - {vendor: averydennison, url: "https://news.averydennison.com/rss", kind: html, chosen_for: [digital_product_passport, item_level_rfid]}
  - {vendor: gs1us, url: "https://www.gs1us.org/industries-and-insights/media-center/press-releases", kind: html, chosen_for: [gs1_2d]}
  - {vendor: daimlertruck, url: "https://www.daimlertruck.com/en/newsroom", kind: html, chosen_for: [electric_trucks, hydrogen_trucks]}
  - {vendor: volvotrucks_us, url: "https://www.volvotrucks.us/sitemap.xml", kind: sitemap, chosen_for: [electric_trucks]}
  - {vendor: righthand, url: "https://righthandrobotics.com/the-latest?q=news", kind: html, chosen_for: [piece_picking]}
  - {vendor: berkshiregrey, url: "https://www.berkshiregrey.com/feed/", kind: rss, chosen_for: [piece_picking, warehouse_robotics]}
  - {vendor: symbotic, url: "https://www.symbotic.com/post-sitemap.xml", kind: sitemap, chosen_for: [warehouse_robotics]}
  - {vendor: locus, url: "https://locusrobotics.com/feed", kind: rss, chosen_for: [warehouse_robotics]}
not_reachable_2026_09_25:
  - {vendor: zipline, url: "https://www.flyzipline.com/newsroom", reason: JavaScript shell}
  - {vendor: flytrex, url: "https://www.flytrex.com/news", reason: JavaScript shell}
  - {vendor: tesla, url: "https://ir.tesla.com/press", reason: 403 Akamai}
  - {vendor: gs1, url: "https://www.gs1.org/news-events/news", reason: 403}
  - {vendor: covariant, url: "https://covariant.ai/news/", reason: 404}
```

- [ ] **Step 2: Fixtures**

Build the four envelopes with a throwaway script (not committed). Each is `json.dumps({"vendor": ..., "kind": ..., "url": ..., "fetched_week": "2026-W39", "listing": <text>, "pages": {...}, "notes": []})`:
- `pressroom_rss.json`: vendor `berkshiregrey`, kind `rss`, listing = an RSS with two `<item>`s: (1) title "Berkshire Grey Deploys Robotic Picking at Acme DC", link `https://www.berkshiregrey.com/news/acme-dc/`, pubDate `Tue, 16 Sep 2026 14:00:00 +0000`, description in CDATA "Acme Logistics has gone live with robotic piece-picking at its Ohio distribution center."; (2) title "Our Q3 e-book", link `.../ebook/`, pubDate `Mon, 01 Sep 2026 10:00:00 +0000`, no description. `pages` = {link1: `<html><body><p>Berkshire Grey today announced that Acme Logistics has gone live with robotic piece-picking at its Ohio distribution center, the first of three sites planned for 2027.</p><p>Short.</p><p>The system handles 1,200 picks per hour across 40,000 SKUs in a warehouse the company opened in 2024.</p></body></html>`}.
- `pressroom_html.json`: vendor `kodiak`, kind `html`, listing = HTML with three anchors: (a) `<div class="card"><span class="date">September 24, 2026</span><a href="/news/dtl-first-deliveries">Kodiak AI and DTL Transport Complete First Autonomous Trucking Deliveries Under New California DMV Permit</a></div>`; (b) `<div class="card"><a href="/news/2026/08/14/dmv-permit"><h3>Kodiak AI Receives DMV Permit to Test Autonomous Trucks in California</h3></a></div>`; (c) `<a href="/careers">Join us</a>`. `pages` = {`https://kodiak.ai/news/dtl-first-deliveries`: an item page whose first long `<p>` reads "Kodiak AI and DTL Transport completed the first commercial autonomous trucking deliveries in California under the new DMV permit, hauling freight between Fresno and Los Angeles for a supply chain customer."}.
- `pressroom_sitemap.json`: vendor `volvotrucks_us`, kind `sitemap`, listing = a sitemap with `<url><loc>https://www.volvotrucks.us/news/press-releases/2026/september/city-harvest-vnr-electric/</loc><lastmod>2026-09-10</lastmod></url>` and `<url><loc>https://www.volvotrucks.us/about/</loc></url>`. `pages` = {first loc: `<html><body><p>City Harvest begins using Volvo VNR Electric trucks to rescue food across New York City, a first for the food-rescue organization's freight fleet.</p></body></html>`}.
- `pressroom_links.json`: vendor `wing`, kind `links:/news/`, listing = HTML with `<a href="/news/world-cup-deliveries">Delivering throughout the tournament</a>` and `<a href="/about">About</a>`; `pages` = {`https://wing.com/news/world-cup-deliveries`: `<html><head><title>Delivering throughout the tournament</title></head><body><p>Published August 7, 2026</p><p>Wing is making drone deliveries in the World Cup host cities this summer, working with the DHS and FAA on airspace access for the tournament's fan zones.</p></body></html>`}.

- [ ] **Step 3: Failing tests**

```python
# tests/test_collector_pressroom.py
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
```

- [ ] **Step 4: Run to see them fail**

Run: `python -m pytest tests/test_collector_pressroom.py -q`. Expected: `ModuleNotFoundError: observatory.collectors.pressroom`.

- [ ] **Step 5: Implement the parse side**

Move `parse_date`, `url_date`, `visible_text`, `DATE_RES`, `URL_DATE_RES`, `MONTHS`, `items_from_rss`, `items_from_sitemap`, `items_from_html` from `docs/experiments/trl/probe2.py` into `observatory/collectors/pressroom.py` (the probe script keeps its own copies; do not import the package from it). Then:

```python
# observatory/collectors/pressroom.py  (add to the moved helpers)
"""Vendor newsrooms: the free source that carries pilots, first sites, orders
and launches. One raw envelope per newsroom per week; parse is pure over it.
Spec: docs/superpowers/specs/2026-09-25-pressroom-collector-design.md."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml

from .. import config
from .base import BaseCollector, Document

PRESSROOMS_PATH = config.ROOT / "pressrooms.yaml"
MAX_ITEM_PAGES = 15


@dataclass(frozen=True)
class Newsroom:
    vendor: str
    url: str
    kind: str
    chosen_for: tuple[str, ...] = ()


@dataclass(frozen=True)
class Item:
    title: str
    url: str
    date: "dt.date | None"
    description: str = ""


def load_pressrooms(path: Path | None = None) -> list[Newsroom]:
    raw = yaml.safe_load((path or PRESSROOMS_PATH).read_text())
    return [Newsroom(r["vendor"], r["url"], r["kind"], tuple(r.get("chosen_for", ()))) for r in raw["newsrooms"]]


def opening_text(html: str) -> str:
    paras = [visible_text(p) for p in re.findall(r"<p\b[^>]*>(.*?)</p>", html, re.S | re.I)]
    long = [p for p in paras if len(p) >= 80][:2]
    return " ".join(long)[:1200] if long else visible_text(html)[:300]


def links_under(html: str, base: str, path: str) -> list[str]:
    out = []
    for href in re.findall(r'href="([^"#]+)"', html):
        u = urljoin(base, href)
        if path in u and u.rstrip("/") != base.rstrip("/") and u not in out:
            out.append(u)
    return out[:MAX_ITEM_PAGES]


def items_for(kind: str, listing: str, base: str, pages: dict) -> list[Item]:
    if kind == "rss":
        return items_from_rss(listing)
    if kind == "sitemap":
        return items_from_sitemap(listing)
    if kind.startswith("links:"):
        items = []
        for u in links_under(listing, base, kind.split(":", 1)[1]):
            page = pages.get(u, "")
            t = re.search(r"<title>(.*?)</title>", page, re.S)
            items.append(Item(visible_text(t[1]) if t else u, u, parse_date(visible_text(page)[:3000])))
        return items
    return items_from_html(listing, base)


def _doc_id(url: str) -> str:
    return "pressroom:" + hashlib.sha1(url.encode("utf8")).hexdigest()[:16]


class PressroomCollector(BaseCollector):
    name = "pressroom"
    rate_limit_seconds = 2.0

    def parse(self, text: str) -> list[Document]:
        env = json.loads(text)
        if not env.get("listing"):
            return []
        pages = env.get("pages") or {}
        docs = []
        for item in items_for(env["kind"], env["listing"], env["url"], pages):
            if item.date is None or not item.url:
                continue
            page = pages.get(item.url)
            body = opening_text(page) if page else (item.description or "")
            docs.append(Document(doc_id=_doc_id(item.url), date=item.date.isoformat(), title=item.title,
                                 text=body, url=item.url, entity=env["vendor"]))
        return docs
```

Adjust the moved `items_from_*` functions to return `Item`s (they returned dicts in the probe). `items_from_html` must fall back to `url_date` before the nearest-date search, as the probe does, and skip items without a date. Sitemap: the probe's `url_date` gives month granularity for `/2026/september/` URLs (first of the month), which the fixture test expects (`2026-09-01`).

- [ ] **Step 6: Run tests, lint, commit**

Run: `python -m pytest tests/test_collector_pressroom.py tests/test_claims_isolation.py -q` then `python -m pytest -q` and `ruff check observatory tests`. Expected: green.

```bash
git add pressrooms.yaml observatory/collectors/pressroom.py tests/test_collector_pressroom.py tests/fixtures/pressroom_rss.json tests/fixtures/pressroom_html.json tests/fixtures/pressroom_sitemap.json tests/fixtures/pressroom_links.json
git commit -m "Pressroom collector: newsroom list, parsers by kind, pure parse over a raw envelope"
```

---

### Task 2: `fetch_raw`, robots, and registration

**Files:**
- Modify: `observatory/collectors/pressroom.py` (fetch side), `observatory/run.py` (COLLECTORS), `observatory/normalize.py` (AGGREGATIONS), `observatory/metrics.py` (SIGNALS_BY_STAGE deployment, QUARTERLY_SIGNALS, QUARTERLY_STAGES), `observatory/quarter.py` (EVIDENCE_FAMILIES `pressroom: press`, FAMILY_STAGE/STAGE_FAMILIES `press` → deployment), `tests/test_collector_pressroom.py`, and whichever registry tests pin these maps (`tests/test_run.py`, `tests/test_quarter.py`, `tests/test_metrics_*.py`: read them first; extend expectations rather than weaken them).

**Interfaces:**
- Produces: `PressroomCollector.fetch_raw(session, week) -> Iterator[RawPage]`, one `RawPage(url=newsroom.url, status, text=<envelope json>, extension="json")` per newsroom, always yielded (a failed newsroom yields an envelope with empty `listing` and a note, so the raw record says the attempt happened). `robots_allows(session, url, cache) -> bool` using `urllib.robotparser` on `<scheme>://<host>/robots.txt`, fetched once per host, treated as allow-all on fetch failure. Item pages fetched only for items dated within `[monday - LOOKBACK_DAYS, sunday]` of `week`, or for all `links:` candidates (≤ 15).

- [ ] **Step 1: Failing fetch tests with a fake session**

```python
class FakeResponse:
    def __init__(self, status, text): self.status_code, self.text, self.url, self.headers = status, text, "", {}
    def raise_for_status(self): pass


class FakeSession:
    """Answers by URL; records requests. robots.txt disallows /private/."""
    def __init__(self, answers): self.answers, self.calls, self.headers = answers, [], {}
    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            return FakeResponse(200, "User-agent: *\nDisallow: /private/\n")
        status, text = self.answers.get(url, (404, ""))
        return FakeResponse(status, text)


def test_fetch_raw_yields_one_envelope_per_newsroom_and_fetches_only_in_window_pages(tmp_path, monkeypatch):
    rooms = tmp_path / "rooms.yaml"
    rooms.write_text('version: 1\nnewsrooms:\n  - {vendor: k, url: "https://k.test/news", kind: html, chosen_for: [x]}\n')
    monkeypatch.setattr(pressroom, "PRESSROOMS_PATH", rooms)
    listing = ('<span>September 24, 2026</span><a href="/news/new-item">A long enough title for the new item here</a>'
               '<span>January 5, 2020</span><a href="/news/old-item">A long enough title for the old item here</a>')
    session = FakeSession({"https://k.test/news": (200, listing),
                           "https://k.test/news/new-item": (200, "<p>" + "x" * 100 + "</p>")})
    pages = list(PressroomCollector().fetch_raw(session, "2026-W39"))
    assert len(pages) == 1
    env = json.loads(pages[0].text)
    assert set(env["pages"]) == {"https://k.test/news/new-item"}      # the 2020 item is out of window, not fetched
    assert "https://k.test/news/old-item" not in session.calls


def test_fetch_raw_obeys_robots_and_records_a_note_instead_of_fetching(tmp_path, monkeypatch):
    rooms = tmp_path / "rooms.yaml"
    rooms.write_text('version: 1\nnewsrooms:\n  - {vendor: p, url: "https://p.test/private/news", kind: rss, chosen_for: [x]}\n')
    monkeypatch.setattr(pressroom, "PRESSROOMS_PATH", rooms)
    session = FakeSession({"https://p.test/private/news": (200, "<rss></rss>")})
    env = json.loads(next(PressroomCollector().fetch_raw(session, "2026-W39")).text)
    assert env["listing"] == "" and any("robots" in n for n in env["notes"])
    assert "https://p.test/private/news" not in session.calls


def test_a_failed_newsroom_still_yields_an_envelope_with_the_status(tmp_path, monkeypatch):
    rooms = tmp_path / "rooms.yaml"
    rooms.write_text('version: 1\nnewsrooms:\n  - {vendor: t, url: "https://t.test/press", kind: html, chosen_for: [x]}\n')
    monkeypatch.setattr(pressroom, "PRESSROOMS_PATH", rooms)
    env = json.loads(next(PressroomCollector().fetch_raw(FakeSession({"https://t.test/press": (403, "blocked")}), "2026-W39")).text)
    assert env["listing"] == "" and any("403" in n for n in env["notes"])
```

Check how `observatory.http.fetch` wraps `session.get` (it expects `.status_code`, `.text`, `.url`, `.headers`; read `_with_retries` and `Response`) and shape `FakeResponse` to it; `http.fetch` raises `HttpError` on non-2xx — catch it in `fetch_raw` and note the status.

- [ ] **Step 2: Implement fetch_raw**

```python
import urllib.robotparser

from .. import http
from .base import RawPage


def robots_allows(session, url: str, cache: dict, limiter) -> bool:
    host = "{0.scheme}://{0.netloc}".format(urlparse(url))
    if host not in cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = http.fetch(session, host + "/robots.txt", limiter=limiter)
            rp.parse(r.text.splitlines())
        except http.HttpError:
            rp.parse([])            # no robots file: allow
        cache[host] = rp
    return cache[host].can_fetch(config.user_agent(), url)


class PressroomCollector(BaseCollector):
    ...
    def fetch_raw(self, session, week: str):
        limiter = http.RateLimiter(self.rate_limit_seconds)
        robots: dict = {}
        monday, sunday = config.week_bounds(week)
        start = monday - dt.timedelta(days=config.LOOKBACK_DAYS)
        for room in load_pressrooms():
            env = {"vendor": room.vendor, "kind": room.kind, "url": room.url, "fetched_week": week,
                   "listing": "", "pages": {}, "notes": []}
            status = 0
            if not robots_allows(session, room.url, robots, limiter):
                env["notes"].append("robots.txt disallows the listing; not fetched")
                yield RawPage(room.url, status, json.dumps(env), "json"); continue
            try:
                r = http.fetch(session, room.url, limiter=limiter)
                status, env["listing"] = r.status, r.text
            except http.HttpError as e:
                env["notes"].append(f"listing: {e}")
                yield RawPage(room.url, status, json.dumps(env), "json"); continue
            wanted = []
            if room.kind.startswith("links:"):
                wanted = links_under(env["listing"], room.url, room.kind.split(":", 1)[1])
            else:
                for it in items_for(room.kind, env["listing"], room.url, {}):
                    if it.url and it.date and start <= it.date <= sunday:
                        wanted.append(it.url)
            for u in wanted[:MAX_ITEM_PAGES]:
                if not robots_allows(session, u, robots, limiter):
                    env["notes"].append(f"robots.txt disallows {u}"); continue
                try:
                    env["pages"][u] = http.fetch(session, u, limiter=limiter).text
                except http.HttpError as e:
                    env["notes"].append(f"page {u}: {e}")
            yield RawPage(room.url, status, json.dumps(env, ensure_ascii=False), "json")
```

`HttpError`'s message must carry the status; check `observatory/http.py:18-33` and format the note so the test's `"403" in n` holds.

- [ ] **Step 3: Register**

- `run.py`: import `PressroomCollector` and append `PressroomCollector()` to `COLLECTORS`.
- `normalize.py`: `Aggregation("press_releases", "pressroom", "count")`.
- `metrics.py`: `"deployment": ("fed_awards", "fedreg_docs", "media_deploy", "press_releases")`; `QUARTERLY_SIGNALS["press_releases"] = ("pressroom",)`; `QUARTERLY_STAGES["deployment"] = ("regulation_docs", "trade_articles", "press_releases")` and add `press_releases` to the `diffusion` tuple too if `trade_articles` is there (mirror `trade_articles`).
- `quarter.py`: `EVIDENCE_FAMILIES["pressroom"] = "press"`, `FAMILY_STAGE["press"] = "deployment"`, `STAGE_FAMILIES["deployment"] += ("press",)`, and the `diffusion` tuple gets `"press"` if it has `"trade"`.
- Read `tests/test_run.py`, `tests/test_quarter.py`, `tests/test_metrics_*.py`, `tests/test_failures_durable.py`, `tests/test_supplemental.py` for assertions that enumerate collectors, families or signals; extend them to include the new source. If a test asserts an exact count (e.g. "10 sources"), update the number and the reason.
- Also check `observatory/status.py` (family count in STATUS §2 is generated) and `tests/test_status_table.py`: the generated rows will change on the next `--write-status`; Task 3 handles it.

- [ ] **Step 4: Run everything**

Run: `python -m pytest -q` and `ruff check observatory tests`. Expected: green.

- [ ] **Step 5: Commit**

```bash
git add observatory/collectors/pressroom.py observatory/run.py observatory/normalize.py observatory/metrics.py observatory/quarter.py tests/test_collector_pressroom.py <any registry tests touched>
git commit -m "Pressroom collector: fetch with robots and a window, registered as the press family at the deployment stage"
```

---

### Task 3: First run, measured, and STATUS

**Files:**
- Create: `docs/pressroom-first-run-2026-09-25.md`
- Modify: `STATUS.md` (§2 via `--write-status`; §3 command list; §5 a paragraph on the source; §7 the sources list; the by-source row will show `pressroom`)

- [ ] **Step 1: Run the collector for the current week only**

Run: `python -m observatory.run --only pressroom --week 2026-W39` (check `--week` semantics in `run.py` `main()`; if `--only` with the default week is the weekly path, use that). Do NOT pass `--rebuild` or `--backfill`. Expected: one raw envelope per newsroom under `data/raw/2026-W39/pressroom/`, observations inserted, filed by each document's own date (`_document_week`), so items from August land in August weeks.

- [ ] **Step 2: Measure**

With sqlite3 or a short Python snippet, count: envelopes written; newsrooms with a non-empty listing; item pages fetched; documents parsed (from `corpus` for source `pressroom`); observations by technology; observations by vendor (`entity`); notes recorded (403s, robots). Read every observation's title and matched pattern (there will be a few dozen at most) and say which look like false positives.

- [ ] **Step 3: Write the note and STATUS**

`docs/pressroom-first-run-2026-09-25.md`: what ran, the counts above in a table, the per-vendor table (status, items, pages, observations), the false positives seen, and two sentences on what the weekly yield will be (RSS carries ~10 items; HTML listings carry more but only in-window pages are fetched). STATUS: `--write-status`, then §3 adds nothing new (the weekly run includes it) but names `pressrooms.yaml`; §5 gets a short paragraph (what the source is, licence, robots, the first-run numbers, the reversal condition: retire the source if two consecutive quarters yield under 10 matched observations); §7's "sources" item is updated; `tests/test_status_table.py` passes.

- [ ] **Step 4: Full suite, commit**

```bash
python -m pytest -q && ruff check observatory tests
git add docs/pressroom-first-run-2026-09-25.md STATUS.md
git commit -m "Pressroom collector: first run measured; STATUS"
```

---

## Self-review against the spec

- §2 raw before parse → envelope design, Task 1 parse tests over fixtures only. No LLM → stdlib only; isolation test still runs. Robots and rate → Task 2 `robots_allows`, limiter 2 s, `MAX_ITEM_PAGES` 15. Licence → sources note in STATUS §5 (Task 3). Config not code → `pressrooms.yaml`. Missing is not zero → a failed newsroom yields an envelope with a note; the source's week status follows the existing collector isolation in `run.py` (a raised exception marks the source failed; a 403 on one newsroom does not, by design, since the other newsrooms answered; the note is in the raw).
- §3 family/stage/signal → Task 2 registration.
- §4 four kinds → Task 1.
- Placeholder scan: Task 2 Step 3 says "read the registry tests and extend" rather than listing exact edits, because the assertions must be read first; the instruction is concrete about what to look for. Task 3 Step 1 names the command to check. No TBDs.
- Types: `Item`, `Newsroom`, `items_for`, `links_under`, `opening_text` used consistently across Tasks 1–2; `Document` fields as in `collectors/base.py`.
