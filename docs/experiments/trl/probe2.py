"""Probe 2: do free, mineable sources closer to pilots, approvals, purchases and
launches than papers reach the pilot band (TRL 5-8) for pre-practice
technologies? Seven candidate sources, seven technologies. Raw kept under
data/trl/probe2/. No model calls.

  regulations_gov   API v4 documents search (DEMO_KEY, ~25 requests/hour/IP): one request
                    per technology, newest first, 12 months back; the 8-week count is read
                    off the dates. Cached: a saved response is reused unless --refresh.
  faa               FAA UAS program pages (Part 135 delivery, BEYOND, BVLOS, waivers, 44807).
  dot               NHTSA AV TEST, USDOT SMART, FMCSA AV pages; plus the Federal Register
                    API (FAA/FMCSA/NHTSA notices) as the machine-readable route to the
                    same agencies.
  sbir              SBIR.gov awards API; if refused, the public awards search page (HTML).
  cordis            CORDIS Horizon Europe projects bulk CSV (data.europa.eu distribution);
                    the EU Funding & Tenders portal page status.
  press             Vendor newsrooms: RSS where one exists, else the newsroom HTML, else the
                    published sitemap; the in-window item pages (at most 10 per vendor) are
                    fetched for their first paragraph.
  shows             Trade-show exhibitor directories (ProMat 2027, MODEX 2026, Automate, CES).

Windows: fast sources (press, regulations.gov, SBIR, Federal Register) trailing 8 weeks;
slow sources (FAA pages, DOT award lists, CORDIS, exhibitor directories) trailing 12 months.

A 403, a JavaScript shell (under 500 characters of visible text) or a challenge page is
recorded as the finding and not retried with other headers.

Usage: SEC_CONTACT_EMAIL=<contact> probe2.py [--refresh] [--only SOURCE ...]
"""

import argparse
import csv
import datetime as dt
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import urljoin

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from observatory import http  # noqa: E402

OUT = ROOT / "data" / "trl" / "probe2"
TODAY = dt.date(2026, 9, 25)
FAST_START = TODAY - dt.timedelta(weeks=8)          # 2026-07-31
SLOW_START = TODAY - dt.timedelta(days=365)         # 2025-09-25

TECH_IDS = ["autonomous_trucking", "delivery_drones", "digital_product_passport",
            "humanoid_logistics", "gs1_2d", "electric_trucks", "piece_picking"]
# One plain phrase per technology for sources that take a single search term, taken
# from the watchlist's first include pattern with the regex removed.
PHRASE = {
    "autonomous_trucking": "autonomous truck",
    "delivery_drones": "drone delivery",
    "digital_product_passport": "digital product passport",
    "humanoid_logistics": "humanoid robot",
    "gs1_2d": "2D barcode",
    "electric_trucks": "electric truck",
    "piece_picking": "piece picking",
}
# Every plain-word form of the watchlist include patterns, for sources that search one
# phrase at a time (neither regulations.gov nor the Federal Register stems a quoted phrase).
VARIANTS = {
    "autonomous_trucking": ["autonomous truck", "autonomous trucks", "autonomous trucking", "driverless truck",
                            "driverless trucks", "self-driving truck", "self-driving trucks"],
    "delivery_drones": ["drone delivery", "delivery drone", "delivery drones", "BVLOS"],
    "digital_product_passport": ["digital product passport", "digital product passports"],
    "humanoid_logistics": ["humanoid robot", "humanoid robots", "general-purpose robot", "general-purpose robots"],
    "gs1_2d": ["2D barcode", "2D barcodes", "GS1 Digital Link", "Sunrise 2027"],
    "electric_trucks": ["electric truck", "electric trucks", "battery-electric truck", "battery-electric trucks",
                        "zero-emission truck", "zero-emission trucks", "electric semi", "electric tractor"],
    "piece_picking": ["piece picking", "piece-picking", "robotic picking", "bin picking"],
}
# regulations.gov's DEMO_KEY answered with x-ratelimit-limit: 10 per hour on 2026-09-25, so it
# gets the first phrase for every technology plus the most likely other forms, in this order,
# until the limit refuses; the refusal is recorded.
REGS_ORDER = [(t, VARIANTS[t][0]) for t in VARIANTS] + [
    ("delivery_drones", "BVLOS"), ("autonomous_trucking", "autonomous trucks"),
    ("autonomous_trucking", "autonomous trucking"), ("electric_trucks", "electric trucks"),
    ("electric_trucks", "zero-emission trucks"), ("humanoid_logistics", "humanoid robots"),
    ("delivery_drones", "delivery drones"), ("digital_product_passport", "digital product passports"),
    ("gs1_2d", "2D barcodes"), ("piece_picking", "robotic picking"), ("autonomous_trucking", "driverless trucks"),
    ("gs1_2d", "GS1 Digital Link"), ("electric_trucks", "battery-electric trucks"),
]

# Vendor newsrooms, chosen from the brief's list. kind: rss | html | sitemap | links:<path>
# (an undated listing: the first 10 links under <path> are fetched and dated from their page).
# URLs are the ones that answered during discovery; the ones that did not are listed in
# the report with their status.
VENDORS = [
    ("autonomous_trucking", "aurora", "html", "https://ir.aurora.tech/news-events/press-releases"),
    ("autonomous_trucking", "kodiak", "html", "https://kodiak.ai/news"),
    ("autonomous_trucking", "plus", "html", "https://plus.ai/news-and-insights"),
    ("delivery_drones", "zipline", "html", "https://www.flyzipline.com/newsroom"),
    ("delivery_drones", "wing", "links:/news/", "https://wing.com/news"),
    ("delivery_drones", "flytrex", "html", "https://www.flytrex.com/news"),
    ("humanoid_logistics", "agility", "html", "https://www.agilityrobotics.com/content"),
    ("humanoid_logistics", "figure", "html", "https://www.figure.ai/news"),
    ("humanoid_logistics", "apptronik", "html", "https://apptronik.com/company/press-releases"),
    ("digital_product_passport", "circularise", "html", "https://www.circularise.com/blogs"),
    ("digital_product_passport", "averydennison", "html", "https://news.averydennison.com/rss"),
    ("digital_product_passport", "gs1", "html", "https://www.gs1.org/news-events/news"),
    ("gs1_2d", "gs1us", "html", "https://www.gs1us.org/industries-and-insights/media-center/press-releases"),
    ("gs1_2d", "gs1", "html", "https://www.gs1.org/news-events/news"),
    ("electric_trucks", "daimlertruck", "html", "https://www.daimlertruck.com/en/newsroom"),
    ("electric_trucks", "volvotrucks_us", "sitemap", "https://www.volvotrucks.us/sitemap.xml"),
    ("electric_trucks", "tesla", "html", "https://ir.tesla.com/press"),
    ("piece_picking", "righthand", "html", "https://righthandrobotics.com/the-latest?q=news"),
    ("piece_picking", "covariant", "html", "https://covariant.ai/news/"),
    ("piece_picking", "berkshiregrey", "rss", "https://www.berkshiregrey.com/feed/"),
    # The brief's "warehouse" pair: not one of the seven technologies; reported as its own row.
    ("warehouse", "symbotic", "sitemap", "https://www.symbotic.com/post-sitemap.xml"),
    ("warehouse", "locus", "rss", "https://locusrobotics.com/feed"),
]

FAA_PAGES = {
    "part135_delivery": "https://www.faa.gov/uas/advanced_operations/package_delivery_drone",
    "beyond": "https://www.faa.gov/uas/programs_partnerships/beyond",
    "bvlos": "https://www.faa.gov/uas/advanced_operations/beyond_visual_line_of_sight",
    "part107_waivers_issued": "https://www.faa.gov/uas/commercial_operators/part_107_waivers/waivers_issued",
    "section_44807": "https://www.faa.gov/uas/advanced_operations/section_44807",
}
DOT_PAGES = {
    "nhtsa_av_test": "https://www.nhtsa.gov/automated-vehicle-safety/av-test",
    "usdot_smart": "https://www.transportation.gov/grants/SMART",
    "fmcsa_av": "https://www.fmcsa.dot.gov/regulations/automated-driving-systems",
    "fhwa_grants": "https://highways.dot.gov/newsroom",
}
SHOW_PAGES = {
    "promat2027_floorplan": "https://pm2027.mapyourshow.com/8_0/exhview/index.cfm",
    "promat2027_alphalist": "https://pm2027.mapyourshow.com/8_0/explore/exhibitor-alphalist.cfm?alpha=A",
    "promat_site": "https://www.promatshow.com/exhibitors",
    "modex_site": "https://www.modexshow.com/exhibitors",
    "automate": "https://www.automateshow.com/exhibitors",
    "automate_prior": "https://www.automateshow.com/prior-exhibitors",
    "automate_prior_detail_agility": "https://www.automateshow.com/prior-exhibitors/agility-robotics",
    "automate_exhibitor_news": "https://www.automateshow.com/exhibitor-news",
    "ces_alphalist": "https://exhibitors.ces.tech/8_0/explore/exhibitor-alphalist.cfm?alpha=A",
}
FT_PORTAL = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/projects-results"
CORDIS_ZIP = "https://cordis.europa.eu/data/cordis-HORIZONprojects-csv.zip"

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DATE_RES = [
    (re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2}),? (20\d\d)\b"), "mdy"),
    (re.compile(r"\b(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (20\d\d)\b"), "dmy"),
    (re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)"), "iso"),
    (re.compile(r"\b(\d{2})\.(\d{2})\.(20\d\d)\b"), "dotted"),
]
URL_DATE_RES = [
    re.compile(r"/(20\d\d)-(\d\d)-(\d\d)"),
    re.compile(r"/(20\d\d)/(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*/", re.I),
]


def parse_date(s):
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


def url_date(url):
    m = URL_DATE_RES[0].search(url)
    if m:
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    m = URL_DATE_RES[1].search(url)
    if m:  # month granularity: first of the month
        return dt.date(int(m[1]), MONTHS[m[2][:3].lower()], 1)
    return None


def visible_text(html):
    t = re.sub(r"<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&nbsp;|&#160;", " ", t)
    t = re.sub(r"&amp;", "&", t)
    return re.sub(r"\s+", " ", t).strip()


def classify(status, text):
    """What kind of answer a page gave: ok, blocked, challenge, js_shell, missing."""
    vt = visible_text(text or "")
    if status == 403 and ("Just a moment" in vt or "Enable JavaScript and cookies" in vt):
        return "challenge"
    if status in (401, 403):
        return "blocked"
    if status in (404, 410):
        return "missing"
    if status != 200:
        return f"status_{status}"
    if "captcha" in vt.lower() and "protected by recaptcha" not in vt.lower():
        return "captcha"
    if len(vt) < 500:
        return "js_shell"
    return "ok"


def get(session, url, limiter, params=None, retries=1):
    """(status, text). A refusal is data here, not an exception."""
    try:
        r = http.fetch(session, url, params=params, limiter=limiter, retries=retries)
        return r.status, r.text
    except http.HttpError as e:
        body = ""
        if e.status is not None and e.status != 429:  # one plain re-read of the refusal body, same headers
            try:
                body = session.get(url, params=params, timeout=http.TIMEOUT_SECONDS).text
            except Exception:  # noqa: BLE001
                body = ""
        return e.status, body


def save(name, text):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(text)


def page_status(session, prefix, pages, limiter):
    rows = []
    for key, url in pages.items():
        status, text = get(session, url, limiter)
        save(f"{prefix}-{key}.html", f"<!-- {url} status={status} -->\n{text}")
        rows.append({"page": key, "url": url, "status": status, "finding": classify(status, text),
                     "visible_chars": len(visible_text(text))})
    return rows


def watch_patterns():
    w = yaml.safe_load((ROOT / "watchlist.yaml").read_text())
    return {t["id"]: re.compile("|".join(t["include"]), re.I) for t in w["technologies"] if t["id"] in TECH_IDS}


# ---------------------------------------------------------------- regulations.gov

def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def regulations_gov(session, refresh):
    """One request per (technology, phrase) in REGS_ORDER until the key's limit refuses."""
    out = {t: {"docs": {}, "phrases": {}} for t in TECH_IDS}
    limited = False
    lim = http.RateLimiter(4.0)
    for tech, phrase in REGS_ORDER:
        path = OUT / f"regulations_gov-{tech}-{slug(phrase)}.json"
        if path.exists() and not refresh:
            raw = path.read_text()
        elif limited:
            out[tech]["phrases"][phrase] = "not run: rate limit"
            continue
        else:
            params = {"filter[searchTerm]": f'"{phrase}"', "filter[postedDate][ge]": SLOW_START.isoformat(),
                      "sort": "-postedDate", "page[size]": "250", "api_key": "DEMO_KEY"}
            status, raw = get(session, "https://api.regulations.gov/v4/documents", lim, params, retries=0)
            if status != 200:
                save(f"regulations_gov-{tech}-{slug(phrase)}.error.txt", f"status={status}\n{raw}")
                out[tech]["phrases"][phrase] = f"refused {status}"
                limited = limited or status == 429
                continue
            save(path.name, raw)
        d = json.loads(raw)
        out[tech]["phrases"][phrase] = d["meta"]["totalElements"]
        for x in d["data"]:
            a = x["attributes"]
            out[tech]["docs"][x["id"]] = {"date": a["postedDate"][:10], "title": a["title"], "id": x["id"],
                                          "agency": a["agencyId"], "type": a["documentType"], "phrase": phrase,
                                          "url": f"https://www.regulations.gov/document/{x['id']}"}
    for t in out:
        out[t]["docs"] = sorted(out[t]["docs"].values(), key=lambda d: d["date"], reverse=True)
    return out


def federal_register(session, refresh):
    out = {t: {"docs": {}, "phrases": {}} for t in TECH_IDS}
    lim = http.RateLimiter(2.0)
    for tech in TECH_IDS:
        for phrase in VARIANTS[tech]:
            path = OUT / f"federal_register-{tech}-{slug(phrase)}.json"
            if path.exists() and not refresh:
                raw = path.read_text()
            else:
                params = {"conditions[term]": f'"{phrase}"',
                          "conditions[publication_date][gte]": SLOW_START.isoformat(),
                          "order": "newest", "per_page": "100",
                          "fields[]": ["title", "publication_date", "agency_names", "type", "abstract", "html_url",
                                       "document_number"]}
                status, raw = get(session, "https://www.federalregister.gov/api/v1/documents.json", lim, params)
                if status != 200:
                    out[tech]["phrases"][phrase] = f"refused {status}"
                    continue
                save(path.name, raw)
            d = json.loads(raw)
            out[tech]["phrases"][phrase] = d.get("count", 0)
            for x in d.get("results", []):
                out[tech]["docs"][x["html_url"]] = {
                    "date": x["publication_date"], "title": x["title"], "type": x["type"], "phrase": phrase,
                    "agency": ", ".join(x.get("agency_names") or []),
                    "abstract": (x.get("abstract") or "")[:400], "url": x["html_url"]}
    for t in out:
        out[t]["docs"] = sorted(out[t]["docs"].values(), key=lambda d: d["date"], reverse=True)
    return out


# ---------------------------------------------------------------- SBIR

def sbir(session, tech, refresh):
    lim = http.RateLimiter(3.0)
    api_status = None
    api_path = OUT / f"sbir_api-{tech}.txt"
    if not api_path.exists() or refresh:
        api_status, text = get(session, "https://api.www.sbir.gov/public/api/awards", lim,
                               {"keyword": PHRASE[tech], "rows": "50"})
        save(api_path.name, f"status={api_status}\n{text[:5000]}")
    else:
        api_status = int(api_path.read_text().split("\n", 1)[0].split("=")[1] or 0)
    path = OUT / f"sbir_html-{tech}.html"
    if path.exists() and not refresh:
        html = path.read_text()
    else:
        params = {"keywords": f'"{PHRASE[tech]}"', "year[2026]": "2026", "year[2025]": "2025"}
        status, html = get(session, "https://www.sbir.gov/awards", lim, params)
        if status != 200:
            return {"api_status": api_status, "error": status}
        save(path.name, html)
    m = re.search(r"Showing [\d-]+ of ([\d,]+) results", html)
    facet = visible_text(html)
    y = re.search(r"Select a Year (.*?) Apply", facet)
    docs = []
    for block in re.findall(r'<h4[^>]*><a href="(/awards/\d+)">(.*?)</a></h4>(.*?)</td>', html, re.S):
        tags = re.findall(r'text-no-uppercase margin-top-1">([^<]+)<', block[2])
        sbc = re.search(r"<b>SBC:</b>\s*([^<]+)<", block[2])
        para = re.findall(r"<p>([^<]{40,})</p>", block[2])
        docs.append({"title": visible_text(block[1]), "company": sbc[1].strip() if sbc else "",
                     "tags": tags, "abstract": para[0][:300] if para else "",
                     "url": "https://www.sbir.gov" + block[0]})
    return {"api_status": api_status, "total_2025_2026": int(m[1].replace(",", "")) if m else 0,
            "year_facet": y[1][:200] if y else "", "docs": docs}


# ---------------------------------------------------------------- CORDIS

def cordis(session, pats, refresh):
    zpath = OUT / "cordis-HORIZONprojects-csv.zip"
    if not zpath.exists() or refresh:
        http.RateLimiter(1.0).wait()
        r = session.get(CORDIS_ZIP, timeout=600)
        if r.status_code != 200:
            return {"error": r.status_code}
        zpath.write_bytes(r.content)
    zf = zipfile.ZipFile(zpath)
    name = next(n for n in zf.namelist() if n.endswith("project.csv"))
    rows = list(csv.DictReader(io.TextIOWrapper(zf.open(name), encoding="utf-8"), delimiter=";"))
    out = {}
    for tech, rx in pats.items():
        hits = []
        for r in rows:
            text = f"{r.get('title', '')} {r.get('objective', '')}"
            if not rx.search(text):
                continue
            sig = r.get("ecSignatureDate") or ""
            start = r.get("startDate") or ""
            d = max(sig, start)[:10]
            hits.append({"id": r["id"], "acronym": r.get("acronym"), "title": r.get("title"),
                         "signed": sig[:10], "start": start[:10], "date": d, "scheme": r.get("fundingScheme"),
                         "objective": re.sub(r"\s+", " ", r.get("objective", ""))[:600],
                         "url": f"https://cordis.europa.eu/project/id/{r['id']}"})
        hits.sort(key=lambda h: h["date"], reverse=True)
        out[tech] = hits
        save(f"cordis-{tech}.json", json.dumps(hits, indent=1))
    return {"projects_in_file": len(rows), "by_tech": out}


# ---------------------------------------------------------------- press rooms

def items_from_rss(xml):
    items = []
    for it in re.findall(r"<item[ >].*?</item>", xml, re.S):
        title = re.search(r"<title>(.*?)</title>", it, re.S)
        link = re.search(r"<link>(.*?)</link>", it, re.S)
        pub = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
        desc = re.search(r"<description>(.*?)</description>", it, re.S)
        items.append({"title": visible_text(re.sub(r"<!\[CDATA\[|\]\]>", "", title[1])) if title else "",
                      "url": link[1].strip() if link else "", "date": parse_date(pub[1]) if pub else None,
                      "first_para": visible_text(re.sub(r"<!\[CDATA\[|\]\]>", "", desc[1]))[:400] if desc else ""})
    return items


def items_from_sitemap(xml):
    items = []
    for u in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>(.*?)</loc>", u)
        if not loc:
            continue
        lm = re.search(r"<lastmod>(.*?)</lastmod>", u)
        d = url_date(loc[1]) or (parse_date(lm[1]) if lm else None)
        items.append({"title": loc[1].rstrip("/").rsplit("/", 1)[-1].replace("-", " "), "url": loc[1], "date": d,
                      "date_basis": "url" if url_date(loc[1]) else "lastmod"})
    return items


def items_from_html(html, base):
    """Anchors with a title-length text, dated by the nearest date string in the markup
    around them, or by a date in their URL."""
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
        items.append({"title": title, "url": url, "date": d})
    return items


def undated_links(session, html, base, path, vendor, lim, refresh):
    urls = []
    for href in re.findall(r'href="([^"#]+)"', html):
        u = urljoin(base, href)
        if path in u and u.rstrip("/") != base.rstrip("/") and u not in urls:
            urls.append(u)
    items = []
    for u in urls[:10]:
        ipath = OUT / "pages" / f"{vendor}-{re.sub(r'[^a-z0-9]+', '-', u.lower())[-80:]}.html"
        if ipath.exists() and not refresh:
            page = ipath.read_text()
        else:
            _, page = get(session, u, lim)
            ipath.parent.mkdir(parents=True, exist_ok=True)
            ipath.write_text(page)
        t = re.search(r"<title>(.*?)</title>", page, re.S)
        items.append({"title": visible_text(t[1]) if t else u, "url": u, "date": parse_date(visible_text(page)[:3000]),
                      "first_para": first_paragraph(page)})
    return items


def first_paragraph(html):
    for p in re.findall(r"<p\b[^>]*>(.*?)</p>", html, re.S | re.I):
        t = visible_text(p)
        if len(t) >= 120:
            return t[:500]
    return visible_text(html)[:300]


def press(session, refresh):
    rows = []
    for tech, vendor, kind, url in VENDORS:
        lim = http.RateLimiter(2.0)
        ext = "xml" if kind in ("rss", "sitemap") else "html"
        path = OUT / f"press-{tech}-{vendor}.{ext}"
        if path.exists() and not refresh:
            status, text = 200, path.read_text()
            meta = OUT / f"press-{tech}-{vendor}.status"
            if meta.exists():
                status = int(meta.read_text())
        else:
            status, text = get(session, url, lim)
            save(path.name, text)
            save(f"press-{tech}-{vendor}.status", str(status))
        finding = classify(status, text) if kind == "html" or kind.startswith("links:") else ("ok" if status == 200 else classify(status, text))
        items = []
        if finding == "ok" and kind.startswith("links:"):
            items = undated_links(session, text, url, kind.split(":", 1)[1], vendor, lim, refresh)
        elif finding == "ok":
            items = (items_from_rss(text) if kind == "rss" else items_from_sitemap(text) if kind == "sitemap"
                     else items_from_html(text, url))
        dated = [i for i in items if i["date"]]
        window = sorted([i for i in dated if FAST_START <= i["date"] <= TODAY], key=lambda i: i["date"], reverse=True)
        for it in window[:10]:
            if it.get("first_para"):
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", it["url"].lower())[-80:]
            ipath = OUT / "pages" / f"{vendor}-{slug}.html"
            if ipath.exists() and not refresh:
                html = ipath.read_text()
            else:
                st, html = get(session, it["url"], lim)
                ipath.parent.mkdir(parents=True, exist_ok=True)
                ipath.write_text(html)
            it["first_para"] = first_paragraph(html)
        rows.append({"tech": tech, "vendor": vendor, "kind": kind, "url": url, "status": status, "finding": finding,
                     "items": len(items), "dated": len(dated),
                     "oldest": min((i["date"] for i in dated), default=None),
                     "window": window})
    return rows


# ---------------------------------------------------------------- main

def in_fast(d):
    return FAST_START.isoformat() <= d <= TODAY.isoformat()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--refresh", action="store_true", help="refetch even where a raw file is saved")
    p.add_argument("--only", nargs="*", default=["regulations_gov", "federal_register", "faa", "dot", "sbir",
                                                 "cordis", "press", "shows"])
    args = p.parse_args()
    session = http.make_session()
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {"today": TODAY.isoformat(), "fast_start": FAST_START.isoformat(), "slow_start": SLOW_START.isoformat()}
    pats = watch_patterns()

    if "regulations_gov" in args.only:
        summary["regulations_gov"] = regulations_gov(session, args.refresh)
    if "federal_register" in args.only:
        summary["federal_register"] = federal_register(session, args.refresh)
    if "faa" in args.only:
        summary["faa"] = page_status(session, "faa", FAA_PAGES, http.RateLimiter(3.0))
    if "dot" in args.only:
        summary["dot"] = page_status(session, "dot", DOT_PAGES, http.RateLimiter(3.0))
    if "sbir" in args.only:
        summary["sbir"] = {t: sbir(session, t, args.refresh) for t in TECH_IDS}
    if "cordis" in args.only:
        summary["cordis"] = cordis(session, pats, args.refresh)
        summary["ft_portal"] = page_status(session, "ft_portal", {"projects_results": FT_PORTAL}, http.RateLimiter(2.0))
    if "press" in args.only:
        summary["press"] = press(session, args.refresh)
    if "shows" in args.only:
        summary["shows"] = page_status(session, "shows", SHOW_PAGES, http.RateLimiter(3.0))

    save("summary.json", json.dumps(summary, indent=1, default=str))
    print_tables(summary)


def print_tables(s):
    print(f"windows: fast {s['fast_start']}..{s['today']}; slow {s['slow_start']}..{s['today']}\n")
    for src in ("regulations_gov", "federal_register"):
        if src not in s:
            continue
        print(f"## {src}\n| technology | hits per phrase, 12 months | distinct documents | in 8 weeks |\n|---|---|---|---|")
        for t, r in s[src].items():
            per = "; ".join(f"{k}: {v}" for k, v in r["phrases"].items())
            print(f"| {t} | {per} | {len(r['docs'])} | {sum(in_fast(d['date']) for d in r['docs'])} |")
        print()
    for src in ("faa", "dot", "shows", "ft_portal"):
        if src in s:
            print(f"## {src}\n| page | status | finding | visible chars |\n|---|---|---|---|")
            for r in s[src]:
                print(f"| {r['page']} | {r['status']} | {r['finding']} | {r['visible_chars']} |")
            print()
    if "sbir" in s:
        print("## sbir\n| technology | API status | HTML 2025-26 total | 2026 on page 1 | year facet |\n|---|---|---|---|---|")
        for t, r in s["sbir"].items():
            n26 = sum("2026" in d["tags"] for d in r.get("docs", []))
            print(f"| {t} | {r['api_status']} | {r.get('total_2025_2026', r.get('error'))} | {n26} | {r.get('year_facet', '')[:60]} |")
        print()
    if "cordis" in s and "by_tech" in s["cordis"]:
        c = s["cordis"]
        print(f"## cordis ({c['projects_in_file']} Horizon Europe projects in file)\n"
              "| technology | matches, all years | signed or started in 12 months |\n|---|---|---|")
        for t, hits in c["by_tech"].items():
            print(f"| {t} | {len(hits)} | {sum(h['date'] >= s['slow_start'] for h in hits)} |")
        print()
    if "press" in s:
        print("## press\n| technology | vendor | kind | status | finding | items | dated | in 8 weeks |\n|---|---|---|---|---|---|---|---|")
        for r in s["press"]:
            print(f"| {r['tech']} | {r['vendor']} | {r['kind']} | {r['status']} | {r['finding']} | {r['items']} | "
                  f"{r['dated']} | {len(r['window'])} |")


if __name__ == "__main__":
    main()
