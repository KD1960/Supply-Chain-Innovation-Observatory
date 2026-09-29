"""Probe 3: do the supply chain trade titles' own public feeds carry pilot-stage news
often enough to collect, and do their owners permit reading them? Sixteen titles.
Permission first, content second. Raw kept under data/trl/probe3/. No model calls.

  permission   per title: /robots.txt, /.well-known/tdmrep.json, the homepage (only to
               find the footer's terms link and the <link rel="alternate"> feed), the
               terms page(s). Candidate sentences on automated access, scraping, mining,
               RSS and AI are pulled out of the terms for a hand read; the calls and quotes
               in the report are the hand read, written into CALLS below.
  content      per title not red in CALLS: every feed candidate that robots allows for a
               generic agent ('*') and for the project's own User-Agent is fetched; the
               first that parses as RSS/Atom with items is the title's feed. Feed only:
               no article page is ever fetched, for any title.

Window: trailing 8 weeks, 2026-08-04..2026-09-29. A feed carries its latest N items, so
each feed's depth (oldest item, item count) is recorded and pilot-stage counts are
normalised per week of the window the feed actually covers.

A 403, a challenge, a captcha or a JavaScript shell is recorded as the finding and not
retried with other headers. One request every 2 s per host (the limiter is per host).

Usage: SEC_CONTACT_EMAIL=<contact> probe3.py [--refresh] [--phase permission|content|all]
"""

import argparse
import datetime as dt
import json
import re
import sys
import urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from observatory import config, http  # noqa: E402
from observatory.collectors.pressroom import items_from_rss, parse_date, visible_text  # noqa: E402

OUT = ROOT / "data" / "trl" / "probe3"
TODAY = dt.date(2026, 9, 29)
START = TODAY - dt.timedelta(weeks=8)          # 2026-08-04
PROBE_TECHS = ["autonomous_trucking", "delivery_drones", "humanoid_logistics", "digital_product_passport",
               "gs1_2d", "electric_trucks", "piece_picking"]
SORT_SHEET = ROOT / "docs" / "audit" / "tech-practice-sort-2026-09-23.xlsx"

# (key, title, homepage, extra feed candidates found by hand during discovery)
TITLES = [
    ("scdive", "Supply Chain Dive", "https://www.supplychaindive.com/", ["/feeds/news/"]),
    ("dcvelocity", "DC Velocity", "https://www.dcvelocity.com/", []),
    ("freightwaves", "FreightWaves", "https://www.freightwaves.com/", ["/feed"]),   # footer "RSS"
    ("logmgmt", "Logistics Management", "https://www.logisticsmgmt.com/", []),
    ("ttnews", "Transport Topics", "https://www.ttnews.com/", ["/rss.xml"]),
    ("mmh", "Modern Materials Handling", "https://www.mmh.com/", []),
    ("scmr", "Supply Chain Management Review", "https://www.scmr.com/", []),
    ("autologistics", "Automotive Logistics", "https://www.automotivelogistics.media/", []),
    ("loadstar", "The Loadstar", "https://theloadstar.com/", []),
    ("robotics247", "Robotics 24/7", "https://www.robotics247.com/", []),
    ("ccj", "Commercial Carrier Journal", "https://www.ccjdigital.com/", []),
    ("joc", "Journal of Commerce", "https://www.joc.com/", ["/api/rssfeed"]),   # "All News" on the footer's /rss page
    ("scbrain", "Supply Chain Brain", "https://www.supplychainbrain.com/", ["/rss/articles"]),  # header link
    ("mhl", "Material Handling & Logistics", "https://www.mhlnews.com/", []),
    ("robotreport", "The Robot Report", "https://www.therobotreport.com/", []),
    ("truckingdive", "Trucking Dive", "https://www.truckingdive.com/", ["/feeds/news/"]),
]
COMMON_FEED_PATHS = ["/feed", "/rss", "/feeds/news"]
# The terms pages, found by hand from each homepage's footer on 2026-09-29 (the footer's own
# "Terms", "Copyright", "Permissions", "AI policy" and "Privacy" links). Where a footer has no
# terms link, the privacy page is read (several publishers put terms there) and the common
# paths are tried; a 404 there is recorded as "no terms page found at <path>".
TERMS_PAGES = {
    "scdive": ["https://www.informatechtarget.com/terms-of-use/", "https://www.industrydive.com/takedown-policy/"],
    "dcvelocity": ["https://www.dcvelocity.com/privacy", "https://www.dcvelocity.com/terms",
                   "https://www.dcvelocity.com/terms-of-use"],
    "freightwaves": ["https://www.freightwaves.com/terms-of-use"],
    "logmgmt": ["https://www.logisticsmgmt.com/site/privacy", "https://www.logisticsmgmt.com/site/reprints",
                "https://www.logisticsmgmt.com/site/terms"],
    "ttnews": ["https://www.trucking.org/terms-use", "https://www.ttnews.com/artificial-intelligence-policy",
               "https://www.ttnews.com/permissions-request"],
    "mmh": ["https://www.mmh.com/site/privacy", "https://www.mmh.com/site/terms"],
    "scmr": ["https://www.scmr.com/site/privacy", "https://www.scmr.com/site/reprints", "https://www.scmr.com/site/terms"],
    "autologistics": ["https://www.automotivelogistics.media/terms-and-conditions",
                      "https://www.automotivelogistics.media/terms", "https://www.automotivelogistics.media/about-us",
                      # the footer's "Imprint" goes to the publisher, Ultima Media
                      "https://www.ultimamedia.com/imprint", "https://www.ultimamedia.com/terms-and-conditions",
                      "https://www.ultimamedia.com/terms-conditions"],   # the imprint footer's link
    "loadstar": ["https://theloadstar.com/licencing-and-copyright", "https://theloadstar.com/privacy-policy/"],
    "robotics247": ["https://www.robotics247.com/site/privacy", "https://www.robotics247.com/site/terms"],
    "ccj": [],   # the host answers the identified client with a Cloudflare challenge; nothing readable
    "joc": ["https://www.joc.com/terms-conditions", "https://www.joc.com/copyright-and-legal-disclaimer",
            "https://www.joc.com/rss"],   # the footer's RSS page, read for any terms of feed use
    "scbrain": ["https://www.supplychainbrain.com/privacy-policy", "https://www.supplychainbrain.com/terms-of-use",
                "https://www.supplychainbrain.com/terms", "https://www.supplychainbrain.com/rss"],
    "mhl": ["https://www.endeavorbusinessmedia.com/endeavor-terms"],
    "robotreport": ["https://www.therobotreport.com/terms-of-use/", "https://www.therobotreport.com/privacy-policy/",
                    # the footer's only legal link, and the publisher WTWH Media's own site
                    "http://www.arrowfly.com/privacy-policy/", "https://www.wtwhmedia.com/terms-of-use/",
                    "https://www.wtwhmedia.com/privacy-policy/",
                    # the Arrowfly (formerly WTWH) footer's own links
                    "http://www.arrowfly.com/terms/", "http://www.arrowfly.com/ai-policy"],
    "truckingdive": ["https://www.informatechtarget.com/terms-of-use/", "https://www.industrydive.com/takedown-policy/"],
}

# Hand calls after reading the saved terms, robots and tdmrep files: key -> "green" | "amber"
# | "red". Filled after the permission phase; the content phase skips red and uncalled titles.
CALLS = {
    # green: robots allows, no terms of use found or terms silent on automated access, feed public
    "dcvelocity": "green", "logmgmt": "green", "mmh": "green", "scmr": "green",
    "scbrain": "green", "robotreport": "green",
    # amber: terms restrict robots, mining or use in general words; a feed is offered to readers
    "scdive": "amber", "truckingdive": "amber", "freightwaves": "amber", "ttnews": "amber",
    "joc": "amber", "mhl": "amber",
    # red: terms exclude text and data mining and limit RSS to linking (Loadstar); host
    # answers the identified client with a challenge, terms unreadable (CCJ)
    "loadstar": "red", "ccj": "red",
    # red, no feed: the terms reading would be green (Robotics 24/7) and amber (Automotive
    # Logistics), but no feed exists at the homepage's links or the common paths; recorded from
    # the first content run, whose saved candidates are reused
    "robotics247": "red", "autologistics": "red",
}
NO_FEED = {"robotics247", "autologistics"}   # candidates still re-read from the saved files

TERMS_WORDS = re.compile(
    r"automat|scrap|crawl|spider|\brobot|\bbots?\b|harvest|text and data mining|data mining|\bTDM\b|"
    r"machine learning|artificial intelligence|\bAI\b|large language|\bLLM|\bRSS\b|\bfeeds?\b|"
    r"systematic(ally)? (download|retriev|collect)|extract", re.I)
AI_AGENTS = re.compile(
    r"GPTBot|ChatGPT|OAI-SearchBot|CCBot|ClaudeBot|Claude-|anthropic|Google-Extended|PerplexityBot|"
    r"Bytespider|Amazonbot|Applebot-Extended|cohere|Meta-External|FacebookBot|Diffbot|omgili|"
    r"ImagesiftBot|Timpibot|AI2Bot|YouBot|img2dataset|\bai\b|text.?and.?data|\btdm", re.I)


# ---------------------------------------------------------------- plumbing

_limiters = {}


def limiter(url):
    host = urlparse(url).netloc
    if host not in _limiters:
        _limiters[host] = http.RateLimiter(2.0)
    return _limiters[host]


def classify(status, text):
    vt = visible_text(text or "")
    if status in (403, 503) and ("Just a moment" in vt or "Enable JavaScript and cookies" in vt
                                  or "challenge" in (text or "")[:5000].lower()):
        return "challenge"
    if status in (401, 403):
        return "blocked"
    if status in (404, 410):
        return "missing"
    if status is None:
        return "network_error"
    if status != 200:
        return f"status_{status}"
    if "captcha" in vt.lower() and "recaptcha" not in vt.lower():
        return "captcha"
    return "ok"


def get(session, url, retries=1):
    """(status, final_url, text). A refusal is data, not an exception, and is recorded from
    the first response: http.HttpError carries the status but not the body, so the body is
    left empty rather than asked for a second time. (Until 2026-09-29 a refusal was re-read
    once for its body; that doubled every 404 and sent CCJ's challenged host 6 requests.)"""
    try:
        r = http.fetch(session, url, limiter=limiter(url), retries=retries)
        return r.status, r.url, r.text
    except http.HttpError as e:
        return e.status, url, ""


def cached(session, name, url, refresh, retries=1):
    """Fetch once and keep the envelope; a re-run reads the saved file."""
    path = OUT / name
    if path.exists() and not refresh:
        env = json.loads(path.read_text())
        return env["status"], env["final_url"], env["text"]
    status, final, text = get(session, url, retries)
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"url": url, "final_url": final, "status": status,
                                "fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                                "text": text}))
    return status, final, text


def host_of(url):
    return "{0.scheme}://{0.netloc}".format(urlparse(url))


def robots_for(session, key, url, refresh, cache):
    """A RobotFileParser for url's host, read from a saved robots.txt. As in the
    press-room collector: 404/403/network error means allow, 5xx means disallow all."""
    host = host_of(url)
    if host in cache:
        return cache[host]
    name = f"{key}-robots-{urlparse(url).netloc}.json"
    status, _, text = cached(session, name, host + "/robots.txt", refresh)
    rp = urllib.robotparser.RobotFileParser()
    if status == 200:
        rp.parse(text.splitlines())
    elif status is not None and status >= 500:
        rp.parse(["User-agent: *", "Disallow: /"])
    else:
        rp.parse([])
    cache[host] = (rp, status, text if status == 200 else "")
    delay = rp.crawl_delay("*") or crawl_delay_anywhere(text if status == 200 else "")
    if delay:
        limiter(url).min_interval = max(2.0, float(delay))
    return cache[host]


def crawl_delay_anywhere(text):
    """A Crawl-delay written outside any group (The Robot Report puts it above the first
    User-agent line), which robotparser ignores; honoured anyway."""
    m = re.search(r"^\s*crawl-delay:\s*(\d+)", text, re.I | re.M)
    return int(m[1]) if m else None


def allowed(rp, url, robots_text=""):
    """robotparser for both agents, and RFC 9309 longest-match over every '*' group.

    robotparser alone is not enough: it takes the first matching line, and reads an empty
    "Disallow:" as "Allow: (everything)", so on The Loadstar's file (an empty Disallow, then
    "Disallow: /tag/") it allows /tag/. RFC 9309 (and Google) take the longest match, under
    which /tag/ is disallowed. Found in this probe after one /tag/ page had been fetched."""
    return (rp.can_fetch("*", url) and rp.can_fetch(config.user_agent(), url)
            and rfc9309_allows(robots_text, url))


def rfc9309_allows(robots_text, url):
    path = urlparse(url).path or "/"
    if urlparse(url).query:
        path += "?" + urlparse(url).query
    rules, in_star, prev_ua = [], False, False
    for raw in robots_text.splitlines():
        line = raw.split("#", 1)[0].strip()
        k, _, v = line.partition(":")
        k, v = k.strip().lower(), v.strip()
        if k == "user-agent":
            in_star = (v == "*") or (in_star and prev_ua)
            prev_ua = True
            continue
        prev_ua = False
        if in_star and k in ("allow", "disallow") and v:
            rules.append((k == "allow", v))
    best = None
    for allow, pat in rules:
        rx = "^" + re.escape(pat).replace(r"\*", ".*")
        if rx.endswith(r"\$"):
            rx = rx[:-2] + "$"
        if re.match(rx, path):
            key = (len(pat), allow)
            if best is None or key > best[0]:
                best = (key, allow)
    return True if best is None else best[1]


def rule_for(robots_text, path):
    """The robots lines in the '*' group(s) that bear on path, quoted for the report."""
    out, in_star, prev_ua = [], False, False
    for raw in robots_text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        k, _, v = line.partition(":")
        k, v = k.strip().lower(), v.strip()
        if k == "user-agent":
            in_star = (v == "*") or (in_star and prev_ua)
            prev_ua = True
            continue
        prev_ua = False
        if in_star and k in ("allow", "disallow", "crawl-delay", "content-signal") and \
                (k == "crawl-delay" or k == "content-signal" or v == "" or path.startswith(v.rstrip("*$")) or v == "/"):
            out.append(f"{k}: {v}")
    return out


def named_agents(robots_text):
    """User-agent groups naming AI or text-mining crawlers, with their first rule; and
    any comment or directive mentioning AI, TDM or content signals."""
    groups, cur = [], None
    for raw in robots_text.splitlines():
        line = raw.strip()
        low = line.lower()
        if low.startswith("user-agent:"):
            ua = line.split(":", 1)[1].strip()
            if cur and not cur["rules"]:
                cur["agents"].append(ua)
            else:
                cur = {"agents": [ua], "rules": []}
                groups.append(cur)
        elif cur is not None and line and not line.startswith("#"):
            cur["rules"].append(line)
    hits = [f"{', '.join(g['agents'])} -> {'; '.join(g['rules'][:2])}"
            for g in groups if any(AI_AGENTS.search(a) for a in g["agents"])]
    notes = [ln.strip() for ln in robots_text.splitlines()
             if ln.strip().startswith("#") and AI_AGENTS.search(ln)][:6]
    signals = [ln.strip() for ln in robots_text.splitlines() if ln.lower().startswith("content-signal")]
    return hits, notes, signals


# ---------------------------------------------------------------- permission

def feed_links(html, base):
    out = []
    for tag in re.findall(r"<link\b[^>]*>", html, re.I):
        if re.search(r"application/(rss|atom)\+xml", tag, re.I):
            m = re.search(r'href=["\']([^"\']+)', tag)
            if m:
                u = urljoin(base, m[1].replace("&amp;", "&"))
                if u not in out:
                    out.append(u)
    return out


def terms_links(html, base):
    out = []
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', html, re.S | re.I):
        text = visible_text(m[2]).lower()
        if re.search(r"terms|conditions|legal|user agreement|copyright", text) and len(text) < 60:
            u = urljoin(base, m[1].replace("&amp;", "&"))
            if u.startswith("http") and u not in out:
                out.append(u)
    return out


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.;:])\s+(?=[A-Z(\"'])", text) if s.strip()]


def permission(session, refresh):
    rows = []
    for key, title, home, extra in TITLES:
        cache = {}
        rp, rstatus, rtext = robots_for(session, key, home, refresh, cache)
        row = {"key": key, "title": title, "home": home, "robots_status": rstatus}
        row["robots_home_allowed"] = allowed(rp, home, rtext)
        row["robots_named"], row["robots_notes"], row["content_signals"] = named_agents(rtext)
        row["robots_crawl_delay"] = rp.crawl_delay("*")
        tstatus, _, ttext = cached(session, f"{key}-tdmrep.json", host_of(home) + "/.well-known/tdmrep.json", refresh)
        row["tdmrep"] = ttext[:500] if tstatus == 200 and ttext.strip().startswith(("[", "{")) else f"status {tstatus}"
        if not row["robots_home_allowed"]:
            row["home_finding"] = "robots disallows the homepage; not fetched"
            rows.append(row)
            continue
        hstatus, hfinal, html = cached(session, f"{key}-home.json", home, refresh)
        row["home_status"], row["home_finding"] = hstatus, classify(hstatus, html)
        row["home_visible_chars"] = len(visible_text(html))
        row["feeds_on_home"] = feed_links(html, hfinal)
        row["terms_links_auto"] = terms_links(html, hfinal)
        row["terms"] = []
        for i, turl in enumerate(TERMS_PAGES.get(key, [])):
            trp, _, ttxt = robots_for(session, key, turl, refresh, cache)
            if not allowed(trp, turl, ttxt):
                row["terms"].append({"url": turl, "finding": "robots disallows; not fetched"})
                continue
            st, fu, th = cached(session, f"{key}-terms{i}.json", turl, refresh)
            vt = visible_text(th)
            cands = [s for s in sentences(vt) if TERMS_WORDS.search(s) and 30 < len(s) < 1500]
            row["terms"].append({"url": turl, "final_url": fu, "status": st, "finding": classify(st, th),
                                 "visible_chars": len(vt), "candidates": cands[:60]})
        rows.append(row)
    return rows


# ---------------------------------------------------------------- content

def items_from_atom(xml):
    out = []
    for e in re.findall(r"<entry[ >].*?</entry>", xml, re.S):
        t = re.search(r"<title[^>]*>(.*?)</title>", e, re.S)
        ln = re.search(r'<link\b[^>]*href="([^"]+)"', e)
        d = re.search(r"<(?:published|updated)>(.*?)</", e, re.S)
        s = re.search(r"<(?:summary|content)[^>]*>(.*?)</(?:summary|content)>", e, re.S)
        out.append({"title": visible_text(re.sub(r"<!\[CDATA\[|\]\]>", "", t[1])) if t else "",
                    "url": ln[1] if ln else "", "date": parse_date(d[1]) if d else None,
                    "summary": visible_text(re.sub(r"<!\[CDATA\[|\]\]>", "", s[1]))[:600] if s else ""})
    return out


def feed_items(xml):
    """Items with title, url, date, summary (description, up to 600 chars) and the length
    of any full-text body (content:encoded), to judge headline / summary / full text."""
    if "<item" in xml:
        base = items_from_rss(xml)
        raw = re.findall(r"<item[ >].*?</item>", xml, re.S)
        out = []
        for it, r in zip(base, raw):
            desc = re.search(r"<description>(.*?)</description>", r, re.S)
            body = re.search(r"<content:encoded>(.*?)</content:encoded>", r, re.S)
            # twice: Industry Dive escapes its HTML (&lt;figure&gt;...), so one pass leaves tags
            summ = visible_text(visible_text(re.sub(r"<!\[CDATA\[|\]\]>", "", desc[1]))) if desc else ""
            pub = re.search(r"<pubDate>(.*?)</pubDate>", r, re.S)
            out.append({"title": it.title, "url": it.url, "date": it.date or two_digit_year(pub[1] if pub else ""),
                        "summary": summ[:600],
                        "summary_chars": len(summ),
                        "body_chars": len(visible_text(re.sub(r"<!\[CDATA\[|\]\]>", "", body[1]))) if body else 0})
        return out
    if "<entry" in xml:
        out = items_from_atom(xml)
        for o in out:
            o["summary_chars"], o["body_chars"] = len(o["summary"]), 0
        return out
    return []


def two_digit_year(s):
    """RFC 822 allows a two-digit year ("Tue, 29 Sep 26 11:47:15 EDT", Transport Topics);
    the press-room parse_date needs four digits and returns None."""
    m = re.search(r"\b(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d\d) \d\d:", s)
    return parse_date(f"{m[1]} {m[2]} 20{m[3]}") if m else None


def feed_kind(items):
    if not items:
        return "none"
    body = sorted(i["body_chars"] for i in items)[len(items) // 2]
    summ = sorted(i["summary_chars"] for i in items)[len(items) // 2]
    if body >= 1500 or summ >= 1500:
        return "full text"
    if summ >= 40 or body >= 40:
        return "headline + summary"
    return "headline only"


def patterns(ids):
    w = yaml.safe_load((ROOT / "watchlist.yaml").read_text())
    return {t["id"]: (re.compile("|".join(t["include"]), re.I),
                      re.compile("|".join(t["exclude"]), re.I) if t.get("exclude") else None)
            for t in w["technologies"] if t["id"] in ids}


def tracked_ids():
    import openpyxl
    ws = openpyxl.load_workbook(SORT_SHEET, read_only=True)["Sort"]
    rows = list(ws.iter_rows(values_only=True))
    col = rows[0].index("assistant call")
    return [r[0] for r in rows[1:] if isinstance(r[col], str) and r[col].lower().startswith("pre-practice")]


def match(pats, text):
    hits = []
    for tid, (inc, exc) in pats.items():
        if inc.search(text) and not (exc and exc.search(text)):
            hits.append(tid)
    return hits


def content(session, refresh, perm):
    tracked = tracked_ids()
    pats = patterns(tracked)
    rows = []
    for key, title, home, extra in TITLES:
        prow = next(r for r in perm if r["key"] == key)
        call = CALLS.get(key)
        row = {"key": key, "title": title, "call": call, "candidates": []}
        if call not in ("green", "amber") and key not in NO_FEED:
            row["finding"] = f"not fetched: call is {call or 'not made'}"
            rows.append(row)
            continue
        cache = {}
        cands = prow.get("feeds_on_home", []) + [urljoin(home, p) for p in extra + COMMON_FEED_PATHS]
        cands = list(dict.fromkeys(c for c in cands if not re.search(r"comments/feed|/wp-json/|oembed", c)))
        for i, url in enumerate(cands):
            rp, _, rtext = robots_for(session, key, url, refresh, cache)
            path = urlparse(url).path or "/"
            c = {"url": url, "robots_star_rules": rule_for(rtext, path)}
            if not allowed(rp, url, rtext):
                c["finding"] = "robots disallows; not fetched"
                row["candidates"].append(c)
                continue
            st, fu, xml = cached(session, f"{key}-feed{i}.json", url, refresh)
            items = feed_items(xml) if st == 200 else []
            c.update({"final_url": fu, "status": st, "finding": classify(st, xml) if st != 200 or items else
                      "not a feed", "items": len(items)})
            row["candidates"].append(c)
            if items:
                row["feed"], row["items"] = url, items
                break
        items = row.get("items", [])
        if not items:
            row["finding"] = "no feed found"
            rows.append(row)
            continue
        dated = [i for i in items if i["date"]]
        row["n_items"], row["n_dated"] = len(items), len(dated)
        row["oldest"] = min((i["date"] for i in dated), default=None)
        row["newest"] = max((i["date"] for i in dated), default=None)
        row["kind"] = feed_kind(items)
        eff_start = max(row["oldest"], START) if row["oldest"] else TODAY
        row["covers_from"] = eff_start
        row["weeks"] = round(((TODAY - eff_start).days + 1) / 7, 2)
        win = [i for i in dated if START <= i["date"] <= TODAY]
        for i in win:
            i["techs"] = match(pats, f"{i['title']} {i['summary']}")
        row["in_window"] = win
        row["by_tech"] = {t: [i["title"] for i in win if t in i["techs"]] for t in tracked}
        rows.append(row)
    return rows


# ---------------------------------------------------------------- hand counts

# The hand read of every in-window item (title and feed summary only), 2026-09-29, same rule
# as probes 1-2: pilot-stage when the title or summary says a named actor did something real
# (pilot at a named site, first route or customer, order, contract, approval, or an operation
# at scale with a count). Plans, targets, funding, product launches, partnerships between
# vendors and market forecasts are not counted. Keyed by the start of the item's title.
# tracked: pilot-stage about one of the 24 tracked technologies -> (title start, technology)
# other: pilot-stage about any other supply chain technology
# research: would give a proposes/prototypes/demonstrates claim
HAND = {
    "dcvelocity": {
        "tracked": [("Lowe’s launches airborne drone delivery", "delivery_drones"),
                    ("Aurora says its technology will guide 200", "autonomous_trucking"),  # 500,000 driverless miles
                    ("Freight conglomerate orders 2,500 Tesla Semi", "electric_trucks")],
        "other": ["Maersk completes first U.S. ethanol bunkering", "How Sonepar Turned Three Warehouses"],
        "research": ["Boston Dynamics will train its Atlas humanoid"],
    },
    "freightwaves": {
        "tracked": [("Lowe’s test drives drone delivery", "delivery_drones"),
                    ("Tesla Marked the Start of High Volume Semi Production", "electric_trucks")],
        # not counted: "Coretura selects Vector-QNX" (a selection, no deployment)
        "other": ["Clarios takes its battery subscription",
                  "Union Pacific begins battery-electric locomotive testing",
                  "Amazon rolls out safety tech, pay bump"],
        "research": [],
    },
    "ttnews": {
        "tracked": [("Tesla launches high-volume Semi production", "electric_trucks")],
        "other": ["CBP pilot to test electronic truck export manifests"],
        "research": [],
    },
    "mmh": {
        "tracked": [],
        # not counted: "Amazon plans to deploy AutoStore" (no purchasing commitment) and
        # "Amazon Germany invests in forklift safety" (forklifts "will be outfitted")
        "other": ["Productivity Solutions: Mrs. Gerry’s automates", "System Report: GEODIS doubles picking",
                  "Netherlands terminal to deploy electric Hyster"],
        "research": [],
    },
    "scmr": {
        "tracked": [],
        "other": ["Reimagining demand forecasting at Bayer"],
        "research": ["A few good truck stops", "Trust was the consequence"],
    },
    "robotreport": {
        "tracked": [], "other": [],
        "research": ["General Robotics is betting on modular", "Agility Robotics, maker of Digit humanoid, exploring"],
    },
    "truckingdive": {
        "tracked": [("Shippers’ coalition orders 2,500 Class 8", "electric_trucks")],
        "other": [], "research": [],
    },
}
PASS_PER_WEEK = 1.0


def hand_table(rows):
    """Resolve HAND against the saved feed items (a title start that finds no item in the
    window stops the run), and apply the pass line per week of feed depth."""
    out = []
    for r in rows:
        if "in_window" not in r:
            continue
        h = HAND.get(r["key"], {"tracked": [], "other": [], "research": []})
        titles = [i["title"] for i in r["in_window"]]

        def find(start):
            hits = [t for t in titles if t.startswith(start)]
            if not hits:
                raise SystemExit(f"HAND entry not in {r['key']} window: {start!r}")
            return hits[0]
        tracked = [(find(t), tech) for t, tech in h["tracked"]]
        other = [find(t) for t in h["other"]]
        research = [find(t) for t in h["research"]]
        rate = round(len(tracked) / r["weeks"], 2)
        out.append({"key": r["key"], "title": r["title"], "call": r["call"], "weeks": r["weeks"],
                    "newest": r["newest"], "in_window": len(r["in_window"]), "tracked": tracked,
                    "any": len(tracked) + len(other), "research": research, "rate": rate,
                    "any_rate": round((len(tracked) + len(other)) / r["weeks"], 2),
                    "passes": rate >= PASS_PER_WEEK})
    return out


# ---------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--phase", default="all", choices=["permission", "content", "all"])
    args = p.parse_args()
    config.load_dotenv()
    session = http.make_session()
    OUT.mkdir(parents=True, exist_ok=True)
    perm = permission(session, args.refresh)
    (OUT / "permission.json").write_text(json.dumps(perm, indent=1, default=str))
    print_permission(perm)
    if args.phase in ("content", "all"):
        rows = content(session, args.refresh, perm)
        (OUT / "content.json").write_text(json.dumps(rows, indent=1, default=str))
        print_content(rows)
        hand = hand_table(rows)
        (OUT / "hand.json").write_text(json.dumps(hand, indent=1, default=str))
        print_hand(hand)


def print_permission(perm):
    print("| title | robots | home | feeds on home | terms pages 200 | named AI agents | tdmrep |\n|---|---|---|---|---|---|---|")
    for r in perm:
        print(f"| {r['title']} | {r['robots_status']} | {r.get('home_status')} {r.get('home_finding')} | "
              f"{len(r.get('feeds_on_home', []))} | {sum(t.get('status') == 200 for t in r.get('terms', []))}/{len(r.get('terms', []))} | {len(r['robots_named'])} | "
              f"{r['tdmrep'][:30]} |")


def print_content(rows):
    print("\n| title | call | feed | kind | items | oldest | covers from | weeks | in window |\n|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        if "feed" not in r:
            print(f"| {r['title']} | {r['call']} | {r.get('finding')} | | | | | | |")
            continue
        print(f"| {r['title']} | {r['call']} | {r['feed']} | {r['kind']} | {r['n_items']} | {r['oldest']} | "
              f"{r['covers_from']} | {r['weeks']} | {len(r['in_window'])} |")
    print("\n| title | " + " | ".join(PROBE_TECHS) + " | any tracked (regex) |")
    print("|---|" + "---|" * (len(PROBE_TECHS) + 1))
    for r in rows:
        if "feed" in r:
            anyt = sum(bool(i["techs"]) for i in r["in_window"])
            print(f"| {r['title']} | " + " | ".join(str(len(r["by_tech"].get(t, []))) for t in PROBE_TECHS)
                  + f" | {anyt} |")



def print_hand(hand):
    print("\n| title | call | weeks | newest item | in window | tracked pilot-stage | per week | passes |"
          " any-tech pilot-stage | per week | research-band |\n|---|---|---|---|---|---|---|---|---|---|---|")
    for h in hand:
        print(f"| {h['title']} | {h['call']} | {h['weeks']} | {h['newest']} | {h['in_window']} | {len(h['tracked'])} | "
              f"{h['rate']} | {'yes' if h['passes'] else 'no'} | {h['any']} | {h['any_rate']} | {len(h['research'])} |")
    for calls in (("green",), ("green", "amber")):
        n = sum(h["passes"] for h in hand if h["call"] in calls)
        print(f"titles passing, {' + '.join(calls)}: {n} (probe line: 4)")


if __name__ == "__main__":
    main()
