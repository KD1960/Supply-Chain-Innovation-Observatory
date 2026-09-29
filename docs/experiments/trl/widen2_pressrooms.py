"""Second widening of pressrooms.yaml, 2026-09-29: newsrooms for the two technologies
that have none, battery_free_iot and microfactories. Permission first, content second.
Every response is kept under data/trl/widen2/ (gitignored). No model calls.

The fetch path, the request budget and the assessment are those of
widen_pressrooms.py (docs/pressroom-widen-2026-09-29.md), imported, not copied, with
the first pass's lessons applied:

  * Redirect hops are counted BEFORE the budget check. The first pass let `requests`
    follow a robots.txt redirect itself and counted the hops afterwards, so Symbio
    used 7 requests. Here every hop is its own request, checked against the budget
    before it is sent, and paced 2 s apart.
  * The company's PRESS RELEASE listing is preferred over a site-wide feed: the html
    newsroom first, then an advertised feed only if its URL is press-specific, and a
    site-wide feed (/feed, /rss) only if its recent items sit on press or news paths.
    The first pass preferred an advertised feed, which admitted marketing blogs.
  * The membership rule (controller, fix round 1) is applied by the script, not only
    by hand: among items dated in the last 12 months, most must be on the newsroom's
    own site (else "third-party coverage") and not under /blog/ (else "blog listing").
    A site-wide feed whose recent items are neither press nor blog paths, and a press
    page whose items sit under /blog/ (Wiliot), are left for a hand read (outcome
    "review"), with their titles saved.
  * links:<path> fetches only pages on the listing's own site. The first run of this
    script lacked that filter: for InPlay it fetched averydennison.com's robots.txt
    and one of its release pages, and businesswire.com's robots.txt (403), before the
    budget stopped it.

Per candidate: robots.txt for the newsroom host (the collector's `_robots`, RFC 9309
via observatory.robots); unavailable (5xx, 429, network) or disallowed -> reject; a
403, a challenge page or a JavaScript shell -> reject, never retried or evaded; at most
6 requests including robots, retries and redirect hops; crawl-delay honoured in full.

Usage: PYTHONPATH=. python3 docs/experiments/trl/widen2_pressrooms.py [--only slug,...] [--report]
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from requests.structures import CaseInsensitiveDict

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from observatory import config, http  # noqa: E402
from observatory.collectors.pressroom import _host, _site, items_for, links_under  # noqa: E402
from widen_pressrooms import (BUDGET, MAX_LINK_PAGES, RSS_LINK_RE, TODAY, YEAR_AGO,  # noqa: E402
                              BudgetSpent, Discovery, DiskSession, assess, is_xml, looks_blocked,
                              notices)

OUT = ROOT / "data" / "trl" / "widen2"
RESP = OUT / "responses"
DEC = OUT / "decisions"
MAX_HOPS = 5
HOP_PACE = 2.0
SITE_FEEDS = ["/feed", "/rss", "/news/rss", "/sitemap.xml"]

BF, MF = "battery_free_iot", "microfactories"
# (slug, name, chosen_for, newsroom URLs, tried in order on 404). URLs were found by
# web search for the company's own press page, 2026-09-29, not guessed, except where
# marked "guess".
CANDIDATES = [
    # battery_free_iot: retries of the first pass's rejections, at a different URL
    ("wiliot", "Wiliot", [BF, "smart_labels"], ["https://www.wiliot.com/press"]),
    ("everactive", "Everactive", [BF], ["https://everactive.com/posts/category/press/"]),
    ("identiv", "Identiv", ["smart_labels", BF], ["https://ir.identiv.com/news-events/press-releases",
                                                  "https://identiv.com/press-releases/"]),
    # battery_free_iot: new
    ("epeas", "e-peas", [BF], ["https://e-peas.com/category/press-releases/"]),
    ("powercast", "Powercast", [BF], ["https://www.powercastco.com/press-releases/"]),
    ("energous", "Energous", [BF], ["https://ir.energous.com/news-events/news-releases",
                                    "https://energous.com/company/newsroom/"]),
    ("ossia", "Ossia", [BF], ["https://www.ossia.com/press"]),
    ("enocean", "EnOcean", [BF], ["https://www.enocean.com/en/news/press/"]),
    ("onio", "ONiO", [BF], ["https://www.onio.com/news"]),
    ("dracula", "Dracula Technologies", [BF], ["https://dracula-technologies.com/press-releases/"]),
    ("epishine", "Epishine", [BF], ["https://www.epishine.com/news/tag/press-release"]),
    ("exeger", "Exeger", [BF], ["https://www.exeger.com/press-releases/", "https://www.exeger.com/press/"]),  # guess
    ("inplay", "InPlay", [BF], ["https://inplay-tech.com/news"]),
    ("trameto", "Trameto", [BF], ["https://www.trameto.com/news"]),   # guess
    # Trackonomy bought Identiv's IoT assets (ID-Pixels) in 2026 and InPlay in 2025
    ("trackonomy", "Trackonomy", [BF, "smart_labels"], ["https://trackonomy.ai/newsroom/"]),
    ("nexperia", "Nexperia", [BF], ["https://www.nexperia.com/about/news-events/press-releases"]),
    ("ambientphotonics", "Ambient Photonics", [BF], ["https://ambientphotonics.com/newsroom"]),
    # microfactories: retry of the first pass's rejection, at a different URL
    ("divergent", "Divergent", [MF], ["https://www.divergent3d.com/company/news"]),
    # microfactories: new
    ("hadrian", "Hadrian", [MF], ["https://www.hadrian.co/press"]),
    ("rebuild", "Re:Build Manufacturing", [MF], ["https://rebuildmanufacturing.com/newsroom/"]),
    ("machinalabs", "Machina Labs", [MF], ["https://machinalabs.ai/resources"]),
    ("vention", "Vention", [MF], ["https://vention.io/press-release"]),
    ("formic", "Formic", [MF], ["https://formic.co/resources/press"]),
    ("orbitalcomposites", "Orbital Composites", [MF], ["https://www.orbitalcomposites.com/news"]),  # guess
    ("mightybuildings", "Mighty Buildings", [MF], ["https://www.mightybuildings.com/news"]),  # guess
    ("azure", "Azure Printed Homes", [MF], ["https://www.azureprintedhomes.com/press"]),  # guess
    ("cuby", "Cuby Technologies", [MF], ["https://cubytechnologies.com/press"]),
    ("xometry", "Xometry", [MF], ["https://investors.xometry.com/news-and-events/news-releases"]),
    ("protolabs", "Protolabs", [MF], ["https://investors.protolabs.com/news-events/news-releases"]),
    ("fictiv", "Fictiv", [MF], ["https://www.fictiv.com/newsroom"]),
    ("sybridge", "SyBridge Technologies", [MF], ["https://www.sybridge.com/news"]),  # guess
    # added after the first 30 left microfactories with no newsroom
    ("reframe", "Reframe Systems", [MF], ["https://www.reframe.systems/news"]),  # guess
    ("fathom", "Fathom Manufacturing", [MF], ["https://fathommfg.com/company/news-press/"]),
    ("isembard", "Isembard", [MF], ["https://isembard.com/us/newsroom/"]),
]
# Not tried (recorded in the report): atmosic (same URL as the first pass; no other own
# press page known), haddy (domain parked), brightmachines (its /news is third-party
# coverage; no own-site press page known), stratasys (JavaScript-rendered, first pass);
# Arrival and Canoo (bankrupt), Local Motors (closed 2022), Firestorm Labs (its domain
# now names another business), Sensata (not a battery-free vendor).

# Hand calls after reading saved listings (2026-09-29): slug -> reason.
HAND_REJECT: dict[str, str] = {
    "identiv": ("Identiv sold its IoT business to Trackonomy and renamed itself INVE Technologies "
                "(2026-08-12); the press page redirects to invetechnologies.com, 9 of 9 recent items "
                "earnings and corporate notices"),
    "rebuild": ("on-site items are blog posts (8 of 8 recent on-site under /newsroom/blogs/); "
                "its releases are on businesswire.com (6 off-site items)"),
    "azure": "/press/ lists SEO guide posts (8 of 8 recent, e.g. 'Do Modular Homes Depreciate?'), not releases",
    # Fix round 1 (review), on the relevance standard that dropped Amazon in the first pass.
    "nexperia": ("general corporate press feed (power semiconductors, results, legal); 0 of 10 releases "
                 "in the last 12 months on energy harvesting; reversal: a product-line feed"),
    "enocean": ("press releases are building automation; 0 of 3 in the last 12 months on supply chain "
                "or logistics use; reversal: a logistics or asset-tracking release"),
}
# Hand acceptances of listings left for review: slug -> note.
HAND_ACCEPT: dict[str, str] = {
    "wiliot": ("the /press page; its releases sit under /blog/ URLs (10 of 13 recent items, all "
               "release-style titles); the other 3 are coverage links, which parse drops"),
}
# Pilot-type titles among an accepted newsroom's items of the last 12 months, counted
# by hand from the saved listing (conservative: a named deployment, pilot, customer,
# order or site): slug -> (count, the titles counted). Unlisted accepted slugs: 0.
PILOT_TITLES: dict[str, tuple[int, list[str]]] = {
    "wiliot": (1, ["Wiliot Collaborates with Walmart to Transform Retail Supply Chain with Ambient IoT and AI"]),
    "epishine": (1, ["Google TV's New G32 Remote Control is Powered by Swedish Indoor Solar Innovation "
                     "from Epishine"]),
    "dracula": (1, ["Paragon ID and Dracula Technologies Strengthen Partnership to Scale Light-powered "
                    "Bluetooth® Tags Globally for Sustainable Traceability"]),
}

PRESS_PATH = re.compile(r"/(?:news|press|newsroom|media|releases?|press-releases?|news-releases?|"
                        r"announcements?|press-release)(?:/|-|$)", re.I)
BLOG_PATH = re.compile(r"/blogs?(?:/|$)", re.I)
PRESS_URL = re.compile(r"press|news|release", re.I)


class HopCountingSession(DiskSession):
    """widen_pressrooms.DiskSession, saving under data/trl/widen2/, with every redirect
    hop its own request, counted against the budget before it is sent."""

    def _paths(self, url: str, n: int):
        h = hashlib.sha1(url.encode()).hexdigest()[:20]
        return RESP / f"{h}.{n}.json", RESP / f"{h}.{n}.body"

    def _one(self, url, params, headers, timeout):
        if self.used + 1 > BUDGET:
            raise BudgetSpent(f"request budget of {BUDGET} spent before {url}")
        n = self.calls.get(url, 0)
        self.calls[url] = n + 1
        meta_p, body_p = self._paths(url, n)
        replayed = meta_p.exists()
        if replayed:
            meta = json.loads(meta_p.read_text())
        else:
            meta = {"url": url, "n": n, "fetched_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds")}
            try:
                r = self.real.get(url, params=params, headers=headers, timeout=timeout, allow_redirects=False)
                body_p.write_bytes(r.content)
                meta.update(status=r.status_code, final_url=r.url, hops=0,
                            headers={k: v for k, v in r.headers.items()
                                     if k.lower() in ("content-type", "location", "retry-after")})
            except requests.RequestException as e:
                meta.update(error=f"{type(e).__name__}: {e}"[:300])
            meta_p.write_text(json.dumps(meta))
        self.used += 1
        self.log.append({"url": url, "status": meta.get("status"), "error": meta.get("error"),
                         "replayed": replayed})
        if "error" in meta:
            raise requests.ConnectionError(meta["error"])
        resp = requests.models.Response()
        resp._content = body_p.read_bytes()
        resp.status_code = meta["status"]
        resp.headers = CaseInsensitiveDict(meta["headers"])
        resp.url = meta["final_url"]
        resp.encoding = requests.utils.get_encoding_from_headers(resp.headers)
        return resp, replayed

    def get(self, url, params=None, headers=None, timeout=None, allow_redirects=True, **_kw):
        resp, replayed = self._one(url, params, headers, timeout)
        if not allow_redirects:
            return resp
        # robots.txt: http.fetch lets requests follow redirects; follow them here, one
        # counted and paced request per hop (RFC 9309 asks for at least five).
        history = []
        for _ in range(MAX_HOPS):
            if not (300 <= resp.status_code < 400 and resp.headers.get("Location")):
                break
            history.append(resp)
            nxt = urljoin(resp.url, resp.headers["Location"])
            if not replayed:
                time.sleep(HOP_PACE)
            resp, replayed = self._one(nxt, None, headers, timeout)
        resp.history = history
        return resp


def membership(items, base: str) -> dict:
    """The membership rule's counts over items dated in the last 12 months."""
    recent = [i for i in items if i.date and YEAR_AGO <= i.date <= TODAY + dt.timedelta(days=1)]
    on = [i for i in recent if _site(i.url) == _site(base)]
    # /blog/ wins over a press word earlier in the path: Re:Build's /newsroom/blogs/
    blog = [i for i in on if BLOG_PATH.search(urlparse(i.url).path)]
    press = [i for i in on if PRESS_PATH.search(urlparse(i.url).path) and i not in blog]
    return {"recent": len(recent), "on_site": len(on), "off_site": len(recent) - len(on),
            "press_path": len(press), "blog_path": len(blog), "other_path": len(on) - len(press) - len(blog),
            "recent_titles": [f"{i.date.isoformat()} {i.title} <{i.url}>" for i in
                              sorted(recent, key=lambda i: i.date, reverse=True)]}


def judge(kind: str, text: str, base: str, pages: dict, press_listing: bool) -> tuple[str, dict]:
    """('accept' | 'review' | 'reject: why' | 'fail', assessment). press_listing: the
    listing is a press page by its URL (the known newsroom, a press-specific feed)."""
    a = assess(kind, text, base, pages)
    if not a["ok"]:
        return "fail", a
    m = membership(items_for(kind, text, base, pages), base)
    a.update(m)
    if m["off_site"] > m["on_site"]:
        return (f"reject: listing is third-party coverage ({m['off_site']} of {m['recent']} items "
                f"in the last 12 months on other sites)"), a
    if m["blog_path"] * 2 > m["on_site"]:
        if press_listing:   # a press page whose releases sit under /blog/ (Wiliot): read by hand
            return "review", a
        return f"reject: blog listing ({m['blog_path']} of {m['on_site']} recent on-site items under /blog/)", a
    if press_listing or m["press_path"] * 2 >= m["on_site"]:
        return "accept", a
    return "review", a


def discover(col: Discovery, s: HopCountingSession, cand, cache, limiters) -> dict:
    slug, name, techs, known = cand
    s.start()
    dec = {"vendor": slug, "name": name, "chosen_for": techs, "tried": [], "checked": TODAY.isoformat()}
    held: list[dict] = []   # listings that passed assess but not the rule: reported if nothing better

    def reject(reason, **extra):
        dec.update(outcome="rejected", reason=reason, **extra)
        return dec

    def get(url, item=False):
        try:
            r, note = col._get(s, url, cache, limiters, retries=1, item=item)
        except http.HttpError as e:
            code = e.status
            if code in (403, 429):
                return None, str(code)
            return None, f"{code or 'network error'} at {url}"
        except ValueError as e:
            return None, f"bad url: {e}"
        return (r, None) if r is not None else (None, note)

    def settle(verdict, a, url, kind):
        dec["tried"][-1]["assess"] = {k: v for k, v in a.items() if k != "recent_titles"}
        if verdict == "accept":
            return {**dec, "outcome": "accepted", "url": url, **a, "kind": kind}
        if verdict == "review":
            return {**dec, "outcome": "review", "url": url, **a, "kind": kind}
        if verdict.startswith("reject"):
            held.append({"url": url, "kind": kind, "reason": verdict[8:], **a})
        return None

    first = known[0]
    try:
        rules, problem, delay, _ = col._robots(s, first, cache, limiters)
    except BudgetSpent as e:
        return reject(str(e))
    except requests.RequestException as e:
        return reject(f"robots unavailable ({type(e).__name__})")
    dec["crawl_delay"] = delay
    if problem:
        return reject(f"robots unavailable ({problem})")
    if not rules.allows(config.user_agent(), first):
        return reject(f"robots.txt disallows {urlparse(first).path}")

    try:
        listing, listing_url = None, None
        for url in known:
            r, why = get(url)
            dec["tried"].append({"url": url, "result": why or r.status})
            if r is not None:
                listing, listing_url = r, r.url
                break
            if not why.startswith(("404", "410")):
                return reject(why)

        if listing is not None and is_xml(listing):
            kind = "sitemap" if "<urlset" in listing.text[:2000] else "rss"
            done = settle(*judge(kind, listing.text, listing.url, {}, True), listing.url, kind)
            if done:
                return done
        elif listing is not None:
            blocked = looks_blocked(listing)
            if blocked:
                return reject(blocked)
            found = notices(listing.text)
            if found:
                dec["notice_candidates"] = found
                return reject("notice found; awaiting hand read", pending=True)
            # 1. the html press listing itself
            done = settle(*judge("html", listing.text, listing_url, {}, True), listing_url, "html")
            if done:
                return done
            # 2. an advertised feed, only if press-specific by its URL
            for tag in RSS_LINK_RE.findall(listing.text):
                href = re.search(r"href=[\"']([^\"']+)", tag)
                if not href:
                    continue
                feed_url = urljoin(listing_url, href[1].replace("&amp;", "&"))
                if "comments" in feed_url or not PRESS_URL.search(urlparse(feed_url).path):
                    continue
                r, why = get(feed_url)
                dec["tried"].append({"url": feed_url, "result": why or r.status})
                if r is not None:
                    done = settle(*judge("rss", r.text, r.url, {}, True), r.url, "rss")
                    if done:
                        return done
                elif why in ("403", "429"):
                    return reject(f"{why} on advertised feed")
                break

        # 3. site-wide feeds and a news sitemap, only if their items are press releases
        host = _host(listing_url or first)
        for path in SITE_FEEDS:
            if s.used >= BUDGET:
                break
            if listing is not None and path != "/sitemap.xml" and s.used + 1 + MAX_LINK_PAGES > BUDGET:
                break   # keep room for links: on a listing that loaded
            url = host + path
            r, why = get(url)
            dec["tried"].append({"url": url, "result": why or r.status})
            if r is None:
                if why in ("403", "429"):
                    return reject(f"{why} on {path}")
                continue
            if path == "/sitemap.xml":
                if "<sitemapindex" in r.text[:3000]:
                    kids = re.findall(r"<loc>\s*(.*?)\s*</loc>", r.text)
                    pick = [k for k in kids if re.search(r"news|press", k, re.I)]
                    if pick and s.used < BUDGET:
                        r, why = get(pick[0])
                        dec["tried"].append({"url": pick[0], "result": why or r.status})
                        if r is not None and "<urlset" in r.text[:3000]:
                            done = settle(*judge("sitemap", r.text, r.url, {}, False), r.url, "sitemap")
                            if done:
                                return done
                continue
            if is_xml(r) and "<item" in r.text:
                done = settle(*judge("rss", r.text, r.url, {}, False), r.url, "rss")
                if done:
                    return done

        # 4. links:<path> on a press listing that loaded, dated from at most 3 item pages
        if listing is not None and not is_xml(listing):
            path = urlparse(listing_url).path.rstrip("/") + "/"
            # own site only: InPlay's first run fetched Avery Dennison's robots.txt and a
            # page of its site, and businesswire.com's robots.txt, before this filter
            links = [u for u in links_under(listing.text, listing_url, path) if _site(u) == _site(listing_url)]
            if len(links) >= 3 and s.used + MAX_LINK_PAGES <= BUDGET:
                pages = {}
                for u in links[:MAX_LINK_PAGES]:
                    r, why = get(u, item=True)
                    dec["tried"].append({"url": u, "result": why or r.status})
                    if r is not None:
                        pages[u] = r.text
                kind = f"links:{path}"
                done = settle(*judge(kind, listing.text, listing_url, pages, True), listing_url, kind)
                if done:
                    return done
        if held:
            h = held[0]
            return reject(h["reason"], held=h)
        if listing is None:
            return reject("no listing: " + "; ".join(str(t["result"]) for t in dec["tried"]))
        html = next((t.get("assess") for t in dec["tried"] if t["url"] in known and t.get("assess")), None)
        return reject(f"no dated listing (html: {html['dated'] if html else 0} dated, "
                      f"newest {html['newest'] if html else None})")
    except BudgetSpent as e:
        if held:
            return reject(held[0]["reason"], held=held[0])
        return reject(str(e))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--report", action="store_true", help="print the decisions table, fetch nothing")
    args = ap.parse_args(argv)
    config.load_dotenv()
    RESP.mkdir(parents=True, exist_ok=True)
    DEC.mkdir(parents=True, exist_ok=True)
    slugs = [c[0] for c in CANDIDATES]
    assert len(slugs) == len(set(slugs)), "duplicate slug"
    if args.report:
        return report()
    only = set(filter(None, args.only.split(",")))
    col, s = Discovery(), HopCountingSession()
    cache, limiters = {}, {}
    t0 = time.monotonic()
    for cand in CANDIDATES:
        if only and cand[0] not in only:
            continue
        path = DEC / f"{cand[0]}.json"
        if path.exists() and not json.loads(path.read_text()).get("pending"):
            continue
        dec = discover(col, s, cand, cache, limiters)
        dec["requests"] = s.used
        dec["log"] = s.log
        path.write_text(json.dumps(dec, indent=1, default=str))
        print(f"{time.monotonic() - t0:7.0f}s {cand[0]:18s} {dec['outcome']:9s} "
              f"{dec.get('kind', '')!s:10s} req={s.used} {dec.get('reason', '')}"
              f"{' items=%s newest=%s on/off=%s/%s press/blog/other=%s/%s/%s' % (dec.get('dated'), dec.get('newest'), dec.get('on_site'), dec.get('off_site'), dec.get('press_path'), dec.get('blog_path'), dec.get('other_path')) if dec['outcome'] != 'rejected' else ''}",
              flush=True)
    return 0


def report() -> int:
    """One tab-separated row per candidate, hand calls applied."""
    for slug, name, techs, _ in CANDIDATES:
        p = DEC / f"{slug}.json"
        if not p.exists():
            print(f"{slug}\t(not run)")
            continue
        d = json.loads(p.read_text())
        src = d if d["outcome"] != "rejected" else d.get("held", {})
        if slug in HAND_REJECT:
            d.update(outcome="rejected (hand)" if d["outcome"] != "rejected" else "rejected",
                     reason=HAND_REJECT[slug])
        elif slug in HAND_ACCEPT:
            d.update(outcome="accepted (hand)")
        pilot = PILOT_TITLES.get(slug, (0, []))[0] if d["outcome"].startswith("accepted") else ""
        print("\t".join(str(x) for x in (
            slug, name, ",".join(techs), d["outcome"], src.get("kind", ""), src.get("dated", ""),
            src.get("newest", ""), src.get("on_site", ""), src.get("off_site", ""), src.get("press_path", ""),
            src.get("blog_path", ""), src.get("other_path", ""), pilot, d.get("url", ""),
            d.get("reason", ""), d.get("requests", ""))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
