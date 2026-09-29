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
import time
from html import unescape
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml

from .. import config, http, robots
from .base import BaseCollector, Document, RawPage

PRESSROOMS_PATH = config.ROOT / "pressrooms.yaml"
MAX_ITEM_PAGES = 15
MAX_CRAWL_DELAY = 30.0   # seconds; a host asking for more gets its listing only
MAX_REDIRECTS = 5        # RFC 9309 2.3.1.2 asks crawlers to follow at least five

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DATE_RES = [
    (re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2}),? (20\d\d)\b"), "mdy"),
    (re.compile(r"\b(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (20\d\d)\b"), "dmy"),
    (re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)"), "iso"),
    (re.compile(r"\b(\d{2})\.(\d{2})\.(20\d\d)\b"), "dotted"),
    # RFC 822's two-digit year ("Tue, 29 Sep 26 11:47:15 EDT"), only with the
    # time after it: "29 Sep 26" alone is as likely a page count as a date.
    (re.compile(r"\b(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (\d\d) "
                r"(?:[01]\d|2[0-3]):[0-5]\d\b"), "dmy2"),
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
            if kind == "dmy2":   # 00-69 is 20xx, 70-99 19xx, as email.utils and POSIX %y read it
                y = int(m[3])
                return dt.date(y + (2000 if y < 70 else 1900), MONTHS[m[2][:3].lower()], int(m[1]))
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


def _host(url: str) -> str:
    """scheme://host[:port], lower-cased and without a default port: one
    robots file and one pacing clock per origin. A bad port raises ValueError."""
    p = urlparse(url)
    scheme, host, port = p.scheme.lower(), p.hostname or "", p.port
    if ":" in host:   # IPv6
        host = f"[{host}]"
    if port is not None and port != {"http": 80, "https": 443}.get(scheme):
        host += f":{port}"
    return f"{scheme}://{host}"


def _site(url: str) -> str:
    """The registrable domain, near enough: the last two host labels, or three
    under a two-letter country code's co/com/org/net/ac/gov. No public suffix
    list; a newsroom and its IR subdomain share one site, a trade title does not."""
    labels = (urlparse(url).hostname or "").split(".")
    n = 3 if len(labels) > 2 and len(labels[-1]) == 2 and labels[-2] in ("co", "com", "org", "net", "ac", "gov") else 2
    return ".".join(labels[-n:])


def host_robots(session, url: str, cache: dict, limiter) -> tuple[robots.Robots, str | None]:
    """Read <scheme>://<host>/robots.txt once per host per run (RFC 9309).
    A 4xx means no robots file: allow all. A 5xx, a 429 or a network error
    means disallow all, and the second value says why ("503", "network error"), so
    the envelope can tell an unavailable file from a real disallow. One retry:
    a hanging origin costs two timeouts, not four."""
    host = _host(url)
    if host not in cache:
        try:
            r = http.fetch(session, host + "/robots.txt", limiter=limiter, retries=1)
            cache[host] = (robots.parse(r.text), None)
        except http.HttpError as e:
            if e.status is not None and e.status < 500 and e.status != 429:
                cache[host] = (robots.Robots.allow_all(), None)
            else:
                cache[host] = (robots.Robots.disallow_all(), str(e.status) if e.status else "network error")
    return cache[host]


def robots_allows(session, url: str, cache: dict, limiter) -> bool:
    return host_robots(session, url, cache, limiter)[0].allows(config.user_agent(), url)


def _doc_id(url: str) -> str:
    return "pressroom:" + hashlib.sha1(url.encode("utf8")).hexdigest()[:16]


class PressroomCollector(BaseCollector):
    name = "pressroom"
    rate_limit_seconds = 2.0

    def __init__(self, sleep_fn=time.sleep, clock_fn=time.monotonic):
        self.sleep_fn, self.clock_fn = sleep_fn, clock_fn

    def _robots(self, session, url: str, cache: dict, limiters: dict):
        """The host's robots, why it was unavailable if it was, its crawl-delay,
        and its limiter: requests to one host are at least max(rate limit,
        crawl-delay) apart, the delay capped at MAX_CRAWL_DELAY."""
        host = _host(url)
        if host not in limiters:
            limiters[host] = http.RateLimiter(self.rate_limit_seconds, sleep_fn=self.sleep_fn,
                                              clock_fn=self.clock_fn)
        limiter = limiters[host]
        rules, problem = host_robots(session, url, cache, limiter)
        delay = rules.crawl_delay(config.user_agent()) or 0.0
        limiter.min_interval = max(self.rate_limit_seconds, min(delay, MAX_CRAWL_DELAY))
        return rules, problem, delay, limiter

    def _get(self, session, url: str, cache: dict, limiters: dict, *, retries: int = 3, item: bool = False):
        """Fetch url, following up to MAX_REDIRECTS redirects by hand so that
        robots.txt and the host's pacing are checked for every hop, not only
        the first (requests would follow them unasked). Returns the final
        response and None, or None and the note saying why nothing was fetched.
        An item page is also skipped on a host whose crawl-delay is over
        MAX_CRAWL_DELAY."""
        agent, start = config.user_agent(), url
        for hop in range(MAX_REDIRECTS + 1):
            rules, problem, delay, limiter = self._robots(session, url, cache, limiters)
            if problem:
                where = "host" if hop == 0 and not item else _host(url)
                return None, f"robots.txt unavailable ({problem}); {where} skipped this run"
            if item and delay > MAX_CRAWL_DELAY:
                return None, (f"robots.txt crawl-delay {delay:g} s is over {MAX_CRAWL_DELAY:g} s; "
                              f"item pages on {_host(url)} skipped this run")
            if not rules.allows(agent, url):
                if hop:
                    return None, f"robots.txt disallows redirect target {url}"
                return None, f"robots.txt disallows {url}" if item else "robots.txt disallows the listing; not fetched"
            r = http.fetch(session, url, limiter=limiter, retries=retries, allow_redirects=False)
            if not 300 <= r.status < 400:
                return replace(r, url=r.url or url), None
            url = urljoin(url, r.location)
        return None, f"{start}: more than {MAX_REDIRECTS} redirects; stopped"

    def fetch_raw(self, session, week: str):
        """One envelope per newsroom, always: a newsroom that is disallowed or
        fails still yields one, with an empty listing and a note, so the raw
        record says the attempt happened.

        If no newsroom produced a listing, raise after the last envelope, so
        run.fetch_week records the source failed for the week (a hole) rather
        than ok, which would write press_releases = 0 for every technology.
        Some but not all failing is ok, with the failures in the notes."""
        limiters: dict = {}
        robots_cache: dict = {}
        monday, sunday = config.week_bounds(week)
        start = monday - dt.timedelta(days=config.LOOKBACK_DAYS)
        rooms = load_pressrooms()
        listed = 0
        for room in rooms:
            env = {"vendor": room.vendor, "kind": room.kind, "url": room.url, "fetched_week": week,
                   "listing": "", "pages": {}, "notes": []}
            status = 0
            try:
                r, note = self._get(session, room.url, robots_cache, limiters)
            except (http.HttpError, ValueError) as e:
                r, note = None, f"listing: {e}"
                status = getattr(e, "status", None) or 0
            if r is None:
                env["notes"].append(note)
                yield RawPage(room.url, status, json.dumps(env, ensure_ascii=False), "json")
                continue
            status, env["listing"] = r.status, r.text
            env["resolved_url"] = r.url   # after redirects: the base for item hrefs
            listed += bool(r.text)
            base = env["resolved_url"]
            wanted = []
            if room.kind.startswith("links:"):
                wanted = links_under(env["listing"], base, room.kind.split(":", 1)[1])
            else:
                for it in items_for(room.kind, env["listing"], base, {}):
                    if it.url and in_window(it, start, sunday):
                        wanted.append(it.url)
            # Item pages only on the newsroom's own site: a listing that links press
            # coverage (a trade title, a wire) keeps the item, from the listing's own
            # text, but the other site's robots and terms were never checked.
            elsewhere = [u for u in wanted if _site(u) != _site(base)]
            if elsewhere:
                env["notes"].append(f"{len(elsewhere)} in-window item pages on other sites not fetched")
                wanted = [u for u in wanted if u not in elsewhere]
            for u in wanted[:MAX_ITEM_PAGES]:
                try:   # one retry: a hanging page costs two timeouts, not four
                    r, note = self._get(session, u, robots_cache, limiters, retries=1, item=True)
                except (http.HttpError, ValueError) as e:
                    r, note = None, f"page {u}: {e}"
                if r is not None:
                    env["pages"][u] = r.text
                elif note not in env["notes"]:   # one note per host, not one per item
                    env["notes"].append(note)
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
