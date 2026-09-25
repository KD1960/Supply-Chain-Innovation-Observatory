"""Vendor newsrooms: the free source that carries pilots, first sites, orders
and launches. One raw envelope per newsroom per week; parse is pure over it.
Spec: docs/superpowers/specs/2026-09-25-pressroom-collector-design.md.

The date and HTML helpers came from docs/experiments/trl/probe2.py, which keeps
its own copies.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
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


def url_date(url: str) -> dt.date | None:
    m = URL_DATE_RES[0].search(url)
    if m:
        try:
            return dt.date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = URL_DATE_RES[1].search(url)
    if m:  # month granularity: first of the month
        return dt.date(int(m[1]), MONTHS[m[2][:3].lower()], 1)
    return None


def visible_text(html: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&nbsp;|&#160;", " ", t)
    t = re.sub(r"&amp;", "&", t)
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
        d = url_date(loc[1]) or (parse_date(lm[1]) if lm else None)
        items.append(Item(loc[1].rstrip("/").rsplit("/", 1)[-1].replace("-", " "), loc[1], d))
    return items


def items_from_html(html: str, base: str) -> list[Item]:
    """Anchors with a title-length text, dated by a date in their URL, or else by
    the nearest date string in the markup around them. Undated anchors are dropped."""
    items, seen = [], set()
    for m in re.finditer(r'<a\b[^>]*href="([^"#]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
        title = visible_text(m[2])
        if len(title) < 25 or len(title) > 250:  # an image, "Read more" or whole-card link: take its heading
            h = re.search(r"<h[1-6][^>]*>(.*?)</h[1-6]>", html[m.start():m.end() + 1500], re.S)
            title = visible_text(h[1]) if h else title
        if len(title) < 25 or len(title) > 250:
            continue
        url = urljoin(base, m[1].replace("&amp;", "&"))
        if url in seen:
            continue
        d = url_date(url)
        if d is None:
            best = None
            for rx, _ in DATE_RES:
                for dm in rx.finditer(html, max(0, m.start() - 900), min(len(html), m.end() + 900)):
                    dist = min(abs(dm.start() - m.start()), abs(dm.start() - m.end()))
                    if best is None or dist < best[0]:
                        best = (dist, dm[0])
            d = parse_date(best[1]) if best else None
        if d is None:
            continue
        seen.add(url)
        items.append(Item(title, url, d))
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
    robots.txt that cannot be fetched (404, 403, network error) means allow."""
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


def _doc_id(url: str) -> str:
    return "pressroom:" + hashlib.sha1(url.encode("utf8")).hexdigest()[:16]


class PressroomCollector(BaseCollector):
    name = "pressroom"
    rate_limit_seconds = 2.0

    def fetch_raw(self, session, week: str):
        """One envelope per newsroom, always: a newsroom that is disallowed or
        fails still yields one, with an empty listing and a note, so the raw
        record says the attempt happened."""
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
                yield RawPage(room.url, status, json.dumps(env), "json")
                continue
            try:
                r = http.fetch(session, room.url, limiter=limiter)
                status, env["listing"] = r.status, r.text
            except http.HttpError as e:
                status = e.status or 0
                env["notes"].append(f"listing: {e}")
                yield RawPage(room.url, status, json.dumps(env), "json")
                continue
            wanted = []
            if room.kind.startswith("links:"):
                wanted = links_under(env["listing"], room.url, room.kind.split(":", 1)[1])
            else:
                for it in items_for(room.kind, env["listing"], room.url, {}):
                    if it.url and it.date and start <= it.date <= sunday:
                        wanted.append(it.url)
            for u in wanted[:MAX_ITEM_PAGES]:
                if not robots_allows(session, u, robots, limiter):
                    env["notes"].append(f"robots.txt disallows {u}")
                    continue
                try:
                    env["pages"][u] = http.fetch(session, u, limiter=limiter).text
                except http.HttpError as e:
                    env["notes"].append(f"page {u}: {e}")
            yield RawPage(room.url, status, json.dumps(env, ensure_ascii=False), "json")

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
