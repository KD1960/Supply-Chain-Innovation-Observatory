"""Vendor newsrooms: the free source that carries pilots, first sites, orders
and launches. One raw envelope per newsroom per week; parse is pure over it.
Spec: docs/superpowers/specs/2026-09-25-pressroom-collector-design.md.

Only items dated inside the envelope's own window (its week plus the
lookback) become documents. History on a listing is not collected: the source
starts at its first run week, like every other collector, and a weekly run does
not re-parse and re-count the same items.

The date and HTML helpers came from docs/experiments/trl/probe2.py, which keeps
its own copies.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from html import unescape
import urllib.robotparser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml

from .. import config, http
from .base import BaseCollector, Document, RawPage

PRESSROOMS_PATH = config.ROOT / "pressrooms.yaml"
MAX_ITEM_PAGES = 15

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DATE_RES = [
    (re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2}),? (20\d\d)\b"), "mdy"),
    (re.compile(r"\b(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (20\d\d)\b"), "dmy"),
    (re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)"), "iso"),
    (re.compile(r"\b(\d{2})\.(\d{2})\.(20\d\d)\b"), "dotted"),
]
URL_DATE_RES = [
    re.compile(r"/(20\d\d)[-/](\d\d)[-/](\d\d)"),
    re.compile(r"/(20\d\d)/(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*/", re.I),
]


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
    date: dt.date | None
    description: str = ""
    # The URL dates only the month (Volvo's /2026/september/): `date` is the
    # 1st, a placeholder. The item is fetched if its month meets the window and
    # re-dated from its page; with no page date it is dropped.
    month_only: bool = False


def load_pressrooms(path: Path | None = None) -> list[Newsroom]:
    raw = yaml.safe_load((path or PRESSROOMS_PATH).read_text())
    return [Newsroom(r["vendor"], r["url"], r["kind"], tuple(r.get("chosen_for", ()))) for r in raw["newsrooms"]]


def parse_date(s: str) -> dt.date | None:
    for rx, kind in DATE_RES:
        m = rx.search(s)
        if not m:
            continue
        try:
            if kind == "mdy":
                return dt.date(int(m[3]), MONTHS[m[1][:3].lower()], int(m[2]))
            if kind == "dmy":
                return dt.date(int(m[3]), MONTHS[m[2][:3].lower()], int(m[1]))
            if kind == "iso":
                return dt.date(int(m[1]), int(m[2]), int(m[3]))
            return dt.date(int(m[3]), int(m[2]), int(m[1]))
        except ValueError:
            continue
    return None


def url_date_kind(url: str) -> tuple[dt.date | None, bool]:
    """The date in a URL, and whether it is month-granular (then the 1st)."""
    m = URL_DATE_RES[0].search(url)
    if m:
        try:
            return dt.date(int(m[1]), int(m[2]), int(m[3])), False
        except ValueError:
            return None, False
    m = URL_DATE_RES[1].search(url)
    if m:  # month granularity: first of the month, a placeholder
        return dt.date(int(m[1]), MONTHS[m[2][:3].lower()], 1), True
    return None, False


def url_date(url: str) -> dt.date | None:
    return url_date_kind(url)[0]


def _month_end(d: dt.date) -> dt.date:
    nxt = dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return nxt - dt.timedelta(days=1)


def in_window(item: Item, start: dt.date, end: dt.date) -> bool:
    """A dated item inside [start, end]; a month-only item whose month meets it."""
    if item.date is None:
        return False
    if item.month_only:
        return item.date <= end and _month_end(item.date) >= start
    return start <= item.date <= end


def visible_text(html: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", " ", html, flags=re.S | re.I)
    t = unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t).strip()


def opening_text(html: str) -> str:
    paras = [visible_text(p) for p in re.findall(r"<p\b[^>]*>(.*?)</p>", html, re.S | re.I)]
    long = [p for p in paras if len(p) >= 80][:2]
    return " ".join(long)[:1200] if long else visible_text(html)[:300]


def _uncdata(s: str) -> str:
    return visible_text(re.sub(r"<!\[CDATA\[|\]\]>", "", s))


def items_from_rss(xml: str) -> list[Item]:
    items = []
    for it in re.findall(r"<item[ >].*?</item>", xml, re.S):
        title = re.search(r"<title>(.*?)</title>", it, re.S)
        link = re.search(r"<link>(.*?)</link>", it, re.S)
        pub = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
        desc = re.search(r"<description>(.*?)</description>", it, re.S)
        items.append(Item(_uncdata(title[1]) if title else "", link[1].strip() if link else "",
                          parse_date(pub[1]) if pub else None, _uncdata(desc[1])[:400] if desc else ""))
    return items


def items_from_sitemap(xml: str) -> list[Item]:
    items = []
    for u in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>(.*?)</loc>", u)
        if not loc:
            continue
        lm = re.search(r"<lastmod>(.*?)</lastmod>", u)
        d, month_only = url_date_kind(loc[1])
        if d is None and lm:
            d = parse_date(lm[1])
        items.append(Item(loc[1].rstrip("/").rsplit("/", 1)[-1].replace("-", " "), loc[1], d,
                          month_only=month_only))
    return items


CARD_START = re.compile(r"<(?:li|article|div|tr)\b", re.I)


def _nearest_date(html: str, lo: int, hi: int, a_start: int, a_end: int) -> dt.date | None:
    best = None
    for rx, _ in DATE_RES:
        for dm in rx.finditer(html, lo, hi):
            dist = min(abs(dm.start() - a_start), abs(dm.start() - a_end))
            if best is None or dist < best[0]:
                best = (dist, dm[0])
    return parse_date(best[1]) if best else None


def items_from_html(html: str, base: str) -> list[Item]:
    """Anchors with a title-length text, dated by a date in their URL, or else by
    the nearest date string in their own card. Undated anchors are dropped.

    A card is the span from the anchor's nearest <li>, <article>, <div> or <tr>
    start tag (after the previous titled anchor) to the next titled anchor's
    card start, clipped to 900 characters either side. The cards partition the
    listing, so an undated item cannot borrow a neighbouring card's date: a
    wrong plausible date is worse than a dropped item."""
    anchors = []
    for m in re.finditer(r'<a\b[^>]*href="([^"#]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
        title = visible_text(m[2])
        if len(title) < 25 or len(title) > 250:  # an image, "Read more" or whole-card link: take its heading
            h = re.search(r"<h[1-6][^>]*>(.*?)</h[1-6]>", html[m.start():m.end() + 1500], re.S)
            title = visible_text(h[1]) if h else title
        if len(title) < 25 or len(title) > 250:
            continue
        anchors.append((m, title))
    starts, prev_end = [], 0
    for m, _ in anchors:
        cards = [c.start() for c in CARD_START.finditer(html, prev_end, m.start())]
        starts.append(cards[-1] if cards else prev_end)
        prev_end = m.end()
    starts.append(len(html))
    items, seen = [], set()
    for i, (m, title) in enumerate(anchors):
        url = urljoin(base, m[1].replace("&amp;", "&"))
        if url in seen:
            continue
        d, month_only = url_date_kind(url)
        if d is None or month_only:   # a card's own day beats a month-only URL
            near = _nearest_date(html, max(starts[i], m.start() - 900),
                                 min(starts[i + 1], m.end() + 900), m.start(), m.end())
            if near is not None:
                d, month_only = near, False
        if d is None:
            continue
        seen.add(url)
        items.append(Item(title, url, d, month_only=month_only))
    return items


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


def robots_allows(session, url: str, cache: dict, limiter) -> bool:
    """Read <scheme>://<host>/robots.txt once per host per run and obey it. A
    robots.txt that cannot be fetched (404, 403, network error) means allow;
    a server error (5xx) means disallow all, as RFC 9309 asks. One retry: a
    hanging origin costs two timeouts, not four."""
    host = "{0.scheme}://{0.netloc}".format(urlparse(url))
    if host not in cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = http.fetch(session, host + "/robots.txt", limiter=limiter, retries=1)
            rp.parse(r.text.splitlines())
        except (http.HttpError, ValueError) as e:
            if isinstance(e, http.HttpError) and (e.status or 0) >= 500:
                rp.parse(["User-agent: *", "Disallow: /"])
            else:
                rp.parse([])        # no robots file: allow
        cache[host] = rp
    return cache[host].can_fetch(config.user_agent(), url)


def _doc_id(url: str) -> str:
    return "pressroom:" + hashlib.sha1(url.encode("utf8")).hexdigest()[:16]


class PressroomCollector(BaseCollector):
    name = "pressroom"
    rate_limit_seconds = 2.0

    def fetch_raw(self, session, week: str):
        """One envelope per newsroom, always: a newsroom that is disallowed or
        fails still yields one, with an empty listing and a note, so the raw
        record says the attempt happened.

        If no newsroom produced a listing, raise after the last envelope, so
        run.fetch_week records the source failed for the week (a hole) rather
        than ok, which would write press_releases = 0 for every technology.
        Some but not all failing is ok, with the failures in the notes."""
        limiter = http.RateLimiter(self.rate_limit_seconds)
        robots: dict = {}
        monday, sunday = config.week_bounds(week)
        start = monday - dt.timedelta(days=config.LOOKBACK_DAYS)
        rooms = load_pressrooms()
        listed = 0
        for room in rooms:
            env = {"vendor": room.vendor, "kind": room.kind, "url": room.url, "fetched_week": week,
                   "listing": "", "pages": {}, "notes": []}
            status = 0
            if not robots_allows(session, room.url, robots, limiter):
                env["notes"].append("robots.txt disallows the listing; not fetched")
                yield RawPage(room.url, status, json.dumps(env, ensure_ascii=False), "json")
                continue
            try:
                r = http.fetch(session, room.url, limiter=limiter)
                status, env["listing"] = r.status, r.text
                env["resolved_url"] = r.url or room.url   # after redirects: the base for item hrefs
                listed += bool(r.text)
            except http.HttpError as e:
                status = e.status or 0
                env["notes"].append(f"listing: {e}")
                yield RawPage(room.url, status, json.dumps(env, ensure_ascii=False), "json")
                continue
            base = env["resolved_url"]
            wanted = []
            if room.kind.startswith("links:"):
                wanted = links_under(env["listing"], base, room.kind.split(":", 1)[1])
            else:
                for it in items_for(room.kind, env["listing"], base, {}):
                    if it.url and in_window(it, start, sunday):
                        wanted.append(it.url)
            for u in wanted[:MAX_ITEM_PAGES]:
                if not robots_allows(session, u, robots, limiter):
                    env["notes"].append(f"robots.txt disallows {u}")
                    continue
                try:   # one retry: a hanging page costs two timeouts, not four
                    env["pages"][u] = http.fetch(session, u, limiter=limiter, retries=1).text
                except (http.HttpError, ValueError) as e:
                    env["notes"].append(f"page {u}: {e}")
            yield RawPage(room.url, status, json.dumps(env, ensure_ascii=False), "json")
        if not listed:
            raise http.HttpError(f"pressroom: none of {len(rooms)} newsrooms returned a listing for {week}")

    def parse(self, text: str) -> list[Document]:
        env = json.loads(text)
        if not env.get("listing"):
            return []
        pages = env.get("pages") or {}
        monday, sunday = config.week_bounds(env["fetched_week"])
        start = monday - dt.timedelta(days=config.LOOKBACK_DAYS)
        docs = []
        base = env.get("resolved_url") or env["url"]
        for item in items_for(env["kind"], env["listing"], base, pages):
            if not item.url or not in_window(item, start, sunday):
                continue
            page = pages.get(item.url)
            if item.month_only:   # the URL gave only the month: the page must give the day
                day = parse_date(visible_text(page)[:3000]) if page else None
                if day is None or not start <= day <= sunday:
                    continue
                item = Item(item.title, item.url, day, item.description)
            body = opening_text(page) if page else (item.description or "")
            docs.append(Document(doc_id=_doc_id(item.url), date=item.date.isoformat(), title=item.title,
                                 text=body, url=item.url, entity=env["vendor"]))
        return docs
