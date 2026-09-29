"""Widen pressrooms.yaml, 2026-09-29: find a readable, permitted newsroom listing for
each candidate vendor or user firm. Permission first, content second. Every response
is kept under data/trl/widen/ (gitignored). No model calls.

Per candidate, in order (brief .superpowers/sdd/widen/brief.md, Step 1):
  1. robots.txt for the newsroom host, through the collector's own `host_robots`.
     Unavailable (5xx, 429, network) -> reject "robots unavailable"; the listing
     path disallowed for our agent -> reject.
  2. The listing: the newsroom URL(s) known by hand (the next one only after a
     404), then an RSS feed the listing advertises (<link rel="alternate"
     type="application/rss+xml">), then /feed, /rss, /news/rss, /sitemap.xml
     (a sitemap index is followed to its post/news/press child only). A 403, a
     challenge/captcha page or a JavaScript shell (under 400 visible
     characters) -> reject with that reason; never retried with other headers.
  3. Kind, by running the collector's own `items_for` on the saved listing:
     accept if it yields at least 3 dated items, one dated within the last 12
     months. Preference: an advertised feed (rss) over the html listing it came
     from; the fallbacks only when neither works; `links:<path>` last, with at
     most 3 item pages fetched to date it.
  4. Terms pages are not crawled. The listing's own visible text is searched for a
     notice against automated access or reuse; any hit is printed for a hand read
     (HAND_NOTICE below records the call).

At most 6 requests per candidate, robots, retries and redirect hops included; the 7th
raises and the candidate is rejected "request budget spent". Every request goes
through `PressroomCollector._get` (redirects followed by hand, robots checked per hop,
one limiter per host at >= 2 s, crawl-delay honoured in full here, not capped) with
retries=1.

Restartable: each response is saved as it arrives (data/trl/widen/responses/) and
replayed, not re-requested, on a later run; a candidate with a decision file
(data/trl/widen/decisions/<slug>.json) is skipped.

Usage: PYTHONPATH=. python3 docs/experiments/trl/widen_pressrooms.py [--only slug,...] [--report]
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
from observatory import config, http  # noqa: E402
from observatory.collectors.pressroom import (PressroomCollector, _host, items_for,  # noqa: E402
                                              links_under, visible_text)

OUT = ROOT / "data" / "trl" / "widen"
RESP = OUT / "responses"
DEC = OUT / "decisions"
TODAY = dt.date(2026, 9, 29)
YEAR_AGO = TODAY - dt.timedelta(days=365)
BUDGET = 6
MAX_LINK_PAGES = 3
SHELL_CHARS = 400
FALLBACKS = ["/feed", "/rss", "/news/rss", "/sitemap.xml"]

UF = "user_firm"
# (slug, name, chosen_for, newsroom URLs known by hand, tried in order on 404)
CANDIDATES = [
    # piece_picking
    ("dexterity", "Dexterity", ["piece_picking"], ["https://www.dexterity.ai/news"]),
    ("plusone", "Plus One Robotics", ["piece_picking"], ["https://www.plusonerobotics.com/news"]),
    ("mujin", "Mujin", ["piece_picking"], ["https://mujin-corp.com/news/"]),
    ("nimble", "Nimble Robotics", ["piece_picking"], ["https://www.nimble.ai/news"]),
    ("osaro", "OSARO", ["piece_picking"], ["https://www.osaro.com/news"]),
    ("pickle", "Pickle Robot", ["piece_picking"], ["https://picklerobot.com/news"]),
    ("bostondynamics", "Boston Dynamics", ["piece_picking", "humanoid_logistics"],
     ["https://bostondynamics.com/news/"]),
    ("ambi", "Ambi Robotics", ["piece_picking"], ["https://www.ambirobotics.com/news"]),
    ("brightpick", "Brightpick", ["piece_picking", "microfulfillment"], ["https://brightpick.ai/news/"]),
    # humanoid_logistics
    ("1x", "1X", ["humanoid_logistics"], ["https://www.1x.tech/discover"]),
    ("sanctuary", "Sanctuary AI", ["humanoid_logistics"], ["https://www.sanctuary.ai/news"]),
    ("unitree", "Unitree", ["humanoid_logistics"], ["https://www.unitree.com/news"]),
    # autonomous_yard
    ("outrider", "Outrider", ["autonomous_yard"], ["https://www.outrider.ai/news"]),
    ("fernride", "Fernride", ["autonomous_yard"], ["https://www.fernride.com/news"]),
    ("isee", "ISEE", ["autonomous_yard"], ["https://isee.ai/news"]),
    # sidewalk_delivery_robots
    ("starship", "Starship Technologies", ["sidewalk_delivery_robots"], ["https://www.starship.xyz/press/"]),
    ("serve", "Serve Robotics", ["sidewalk_delivery_robots"],
     ["https://investors.serverobotics.com/news-events/press-releases"]),
    ("coco", "Coco", ["sidewalk_delivery_robots"], ["https://www.cocodelivery.com/blog"]),
    ("kiwibot", "Kiwibot", ["sidewalk_delivery_robots"], ["https://www.kiwibot.com/blog"]),
    # delivery_drones
    ("matternet", "Matternet", ["delivery_drones"], ["https://mttr.net/news"]),
    ("droneup", "DroneUp", ["delivery_drones"], ["https://www.droneup.com/news"]),
    ("manna", "Manna", ["delivery_drones"], ["https://www.manna.aero/news"]),
    ("amazon", "Amazon", ["delivery_drones", UF], ["https://www.aboutamazon.com/news"]),
    ("walmart", "Walmart", ["delivery_drones", UF], ["https://corporate.walmart.com/news"]),
    # autonomous_trucking
    ("waabi", "Waabi", ["autonomous_trucking"], ["https://waabi.ai/news/"]),
    ("torc", "Torc Robotics", ["autonomous_trucking"], ["https://torc.ai/news/"]),
    ("gatik", "Gatik", ["autonomous_trucking"], ["https://gatik.ai/news/"]),
    ("botauto", "Bot Auto", ["autonomous_trucking"], ["https://bot.auto/news"]),
    ("volvoautonomous", "Volvo Autonomous Solutions", ["autonomous_trucking"],
     ["https://www.volvoautonomoussolutions.com/en-en/news-and-media/news.html"]),
    ("einride", "Einride", ["autonomous_trucking", "electric_trucks"], ["https://www.einride.tech/news"]),
    # electric_trucks
    ("paccar", "PACCAR", ["electric_trucks"], ["https://www.paccar.com/news/"]),
    ("kenworth", "Kenworth", ["electric_trucks"], ["https://www.kenworth.com/news/"]),
    ("peterbilt", "Peterbilt", ["electric_trucks"], ["https://www.peterbilt.com/about/news-events/news-releases"]),
    ("freightliner", "Freightliner / Daimler Truck North America", ["electric_trucks"],
     ["https://northamerica.daimlertruck.com/pressreleases"]),
    ("windrose", "Windrose", ["electric_trucks"], ["https://www.windrose.tech/news"]),
    ("harbinger", "Harbinger", ["electric_trucks"], ["https://www.harbingermotors.com/news"]),
    # hydrogen_trucks
    ("hyundai", "Hyundai Motor America", ["hydrogen_trucks"], ["https://www.hyundainews.com/en-us/releases"]),
    ("htwo", "Hyundai HTWO", ["hydrogen_trucks"], ["https://www.htwo.com/newsroom"]),
    ("toyota", "Toyota (US pressroom)", ["hydrogen_trucks"], ["https://pressroom.toyota.com/releases/"]),
    ("symbio", "Symbio", ["hydrogen_trucks"], ["https://www.symbio.one/en/news"]),
    # freight_charging
    ("wattev", "WattEV", ["freight_charging"], ["https://www.wattev.com/news"]),
    ("greenlane", "Greenlane", ["freight_charging"], ["https://greenlane.com/news/"]),
    ("terawatt", "TeraWatt Infrastructure", ["freight_charging"], ["https://terawattinfrastructure.com/news"]),
    ("voltera", "Voltera", ["freight_charging"], ["https://www.voltera.com/news"]),
    ("forummobility", "Forum Mobility", ["freight_charging"], ["https://www.forummobility.com/news"]),
    ("zeem", "Zeem Solutions", ["freight_charging"], ["https://www.zeemsolutions.com/news"]),
    # agentic_procurement
    ("coupa", "Coupa", ["agentic_procurement"], ["https://www.coupa.com/newsroom/"]),
    ("zip", "Zip", ["agentic_procurement"], ["https://ziphq.com/press"]),
    ("jaggaer", "Jaggaer", ["agentic_procurement"], ["https://www.jaggaer.com/newsroom"]),
    ("ivalua", "Ivalua", ["agentic_procurement"], ["https://www.ivalua.com/newsroom/"]),
    ("gep", "GEP", ["agentic_procurement"], ["https://www.gep.com/newsroom"]),
    ("keelvar", "Keelvar", ["agentic_procurement"], ["https://www.keelvar.com/news"]),
    ("pactum", "Pactum", ["agentic_procurement"], ["https://pactum.com/news/"]),
    ("globality", "Globality", ["agentic_procurement"], ["https://www.globality.com/newsroom"]),
    # supply_chain_digital_twin / genai_planning / supply_chain_llm
    ("kinaxis", "Kinaxis", ["supply_chain_digital_twin", "genai_planning", "supply_chain_llm"],
     ["https://www.kinaxis.com/en/news"]),
    ("o9", "o9 Solutions", ["supply_chain_digital_twin", "genai_planning", "supply_chain_llm"],
     ["https://o9solutions.com/news/"]),
    ("blueyonder", "Blue Yonder", ["supply_chain_digital_twin", "genai_planning", "supply_chain_llm"],
     ["https://blueyonder.com/news"]),
    ("manhattan", "Manhattan Associates", ["genai_planning", "supply_chain_llm"],
     ["https://ir.manh.com/news-releases"]),
    ("sap", "SAP News", ["supply_chain_digital_twin", "genai_planning", "supply_chain_llm"],
     ["https://news.sap.com/"]),
    ("oracle", "Oracle", ["genai_planning", "supply_chain_llm"], ["https://www.oracle.com/news/"]),
    ("nvidia", "NVIDIA blog", ["supply_chain_digital_twin"], ["https://blogs.nvidia.com/"]),
    # digital_product_passport / minerals_traceability
    ("circulor", "Circulor", ["digital_product_passport", "minerals_traceability"],
     ["https://www.circulor.com/news"]),
    ("kezzler", "Kezzler", ["digital_product_passport"], ["https://www.kezzler.com/news"]),
    ("eon", "EON", ["digital_product_passport"], ["https://www.eon.xyz/news"]),
    ("spherity", "Spherity", ["digital_product_passport"], ["https://www.spherity.com/news"]),
    ("rcsglobal", "RCS Global", ["minerals_traceability"], ["https://www.rcsglobal.com/news/"]),
    ("minespider", "Minespider", ["minerals_traceability", "digital_product_passport"],
     ["https://www.minespider.com/blog"]),
    ("everledger", "Everledger", ["minerals_traceability"], ["https://everledger.io/news/"]),
    # gs1_2d
    ("digimarc", "Digimarc", ["gs1_2d"], ["https://www.digimarc.com/press-releases"]),
    ("zebra", "Zebra Technologies", ["gs1_2d"],
     ["https://www.zebra.com/us/en/about-zebra/newsroom/press-releases.html"]),
    # battery_free_iot / smart_labels
    ("wiliot", "Wiliot", ["battery_free_iot", "smart_labels"], ["https://www.wiliot.com/news"]),
    ("everactive", "Everactive", ["battery_free_iot"], ["https://everactive.com/news/"]),
    ("atmosic", "Atmosic", ["battery_free_iot"], ["https://atmosic.com/news/"]),
    ("identiv", "Identiv", ["smart_labels", "battery_free_iot"],
     ["https://investors.identiv.com/news-events/press-releases"]),
    ("checkpoint", "Checkpoint Systems", ["smart_labels"], ["https://checkpointsystems.com/news/"]),
    # additive_spares
    ("wurthadditive", "Wurth Additive Group", ["additive_spares"], ["https://www.wurthadditive.com/news"]),
    ("markforged", "Markforged", ["additive_spares"], ["https://markforged.com/newsroom"]),
    ("stratasys", "Stratasys", ["additive_spares"],
     ["https://investors.stratasys.com/news-events/press-releases"]),
    ("eos", "EOS", ["additive_spares"], ["https://www.eos.info/en-us/about-us/news"]),
    ("spee3d", "SPEE3D", ["additive_spares"], ["https://www.spee3d.com/news/"]),
    # microfactories
    ("haddy", "Haddy", ["microfactories"], ["https://haddy.com/news"]),
    ("divergent", "Divergent", ["microfactories"], ["https://www.divergent3d.com/news"]),
    ("brightmachines", "Bright Machines", ["microfactories"], ["https://www.brightmachines.com/news"]),
    # microfulfillment
    ("autostore", "AutoStore", ["microfulfillment"], ["https://www.autostoresystem.com/news"]),
    ("ocado", "Ocado Group", ["microfulfillment"], ["https://www.ocadogroup.com/media/news"]),
    ("fabric", "Fabric", ["microfulfillment"], ["https://getfabric.com/news/"]),
    ("exotec", "Exotec", ["microfulfillment"], ["https://www.exotec.com/news/"]),
    ("attabotics", "Attabotics", ["microfulfillment"], ["https://www.attabotics.com/news"]),
    # cv_inspection
    ("cognex", "Cognex", ["cv_inspection"], ["https://investor.cognex.com/news-releases"]),
    ("kargo", "Kargo", ["cv_inspection"], ["https://www.kargo.ai/news"]),
    ("gatherai", "Gather AI", ["cv_inspection"], ["https://www.gather.ai/news"]),
    ("vimaan", "Vimaan", ["cv_inspection"], ["https://vimaan.ai/news/"]),
    ("dexory", "Dexory", ["cv_inspection"], ["https://www.dexory.com/news"]),
    ("verity", "Verity", ["cv_inspection"], ["https://verity.net/news/"]),
    # private_5g_warehouse
    ("celona", "Celona", ["private_5g_warehouse"], ["https://www.celona.io/news"]),
    ("nokia", "Nokia", ["private_5g_warehouse"], ["https://www.nokia.com/about-us/newsroom/"]),
    ("ericsson", "Ericsson", ["private_5g_warehouse"], ["https://www.ericsson.com/en/newsroom/latest-news"]),
    ("betacom", "Betacom", ["private_5g_warehouse"], ["https://www.betacom.com/news"]),
    # quantum_logistics
    ("dwave", "D-Wave", ["quantum_logistics"], ["https://www.dwavequantum.com/company/newsroom/"]),
    ("ionq", "IonQ", ["quantum_logistics"], ["https://ionq.com/news"]),
    ("quantinuum", "Quantinuum", ["quantum_logistics"], ["https://www.quantinuum.com/news"]),
    ("pasqal", "Pasqal", ["quantum_logistics"], ["https://www.pasqal.com/news/"]),
    ("qctrl", "Q-CTRL", ["quantum_logistics"], ["https://q-ctrl.com/news"]),
    # warehouse automation vendors added by hand (piece picking, microfulfillment)
    ("geekplus", "Geek+", ["piece_picking", "microfulfillment"], ["https://www.geekplus.com/news"]),
    ("dematic", "Dematic", ["microfulfillment", "piece_picking"], ["https://www.dematic.com/en-us/about/news/"]),
    ("knapp", "KNAPP", ["microfulfillment", "piece_picking"], ["https://www.knapp.com/en/news/"]),
    ("swisslog", "Swisslog", ["microfulfillment", "piece_picking"], ["https://www.swisslog.com/en-us/newsroom"]),
    ("hairobotics", "Hai Robotics", ["microfulfillment"], ["https://www.hairobotics.com/news"]),
    # user firms and logistics operators
    ("dhl", "DHL Group", [UF], ["https://group.dhl.com/en/media-relations/press-releases.html"]),
    ("gxo", "GXO", [UF], ["https://gxo.com/news/"]),
    ("ups", "UPS", [UF], ["https://about.ups.com/us/en/newsroom.html"]),
    ("fedex", "FedEx", [UF], ["https://newsroom.fedex.com/"]),
    ("maersk", "Maersk", [UF], ["https://www.maersk.com/news"]),
    ("ryder", "Ryder", [UF], ["https://newsroom.ryder.com/"]),
    ("penske", "Penske Logistics", [UF], ["https://www.penskelogistics.com/newsroom"]),
    ("jbhunt", "J.B. Hunt", [UF], ["https://www.jbhunt.com/company/newsroom/"]),
    ("schneider", "Schneider", [UF], ["https://schneider.com/newsroom"]),
    ("nfi", "NFI", [UF], ["https://www.nfiindustries.com/news/"]),
    ("kroger", "Kroger", [UF], ["https://ir.kroger.com/news/default.aspx"]),
    ("dbschenker", "DB Schenker", [UF], ["https://www.dbschenker.com/global/about/press"]),
    ("dsv", "DSV", [UF], ["https://www.dsv.com/en/about-dsv/press"]),
    ("xpo", "XPO", [UF], ["https://news.xpo.com/"]),
    ("werner", "Werner", [UF], ["https://www.werner.com/news/"]),
    ("lineage", "Lineage", [UF], ["https://ir.onelineage.com/news-releases"]),
]

# Hand calls after reading the accepted listings' items (2026-09-29): a listing whose
# dated items are mostly press coverage on other sites is not a newsroom, and a
# redirect to another firm's homepage is not this firm's. pressrooms.yaml lists these
# under not_reachable with the reason.
HAND_REJECT = {
    "bostondynamics": "listing is third-party coverage (3 dated items, 0 on its own site)",
    "brightmachines": "listing is third-party coverage (5 dated items, 0 on its own site)",
    "windrose": "/news redirects to /about-us, a list of third-party coverage (5 dated, 0 on its own site)",
    "zeem": "listing is third-party coverage (49 dated items, 2 on its own site)",
    "dbschenker": "press page redirects to the DSV homepage (Schenker is part of DSV); covered by dsv",
    # Fix round 2026-09-29, the controller's ruling: a newsroom stays only if its listing
    # is mostly the company's own releases on its own site.
    "jaggaer": "newsroom 404; /feed is the site blog (10 of 10 items vendor-comparison and how-to posts)",
    "brightpick": "listing is mostly third-party coverage (20 of 23 items in the last 12 months on other sites)",
    "checkpoint": "advertised feed is the site blog (10 of 10 items under /blog/)",
    "pactum": "/news/ redirects to a blog tag; the feed is the site blog (48 of 48 items under /blog/)",
    "ambi": "newsroom 404; /feed is the site blog (35 of 37 items under /blog/)",
    "vimaan": "newsroom 404; /feed is the resources section (blog, application notes, reposted trade coverage)",
    "nfi": "newsroom 404; /feed is about-page insight posts (10 of 10 under /about-nfi/insights/)",
    "amazon": ("corporate news feed across all of Amazon (entertainment, sellers, devices, climate); "
               "10 items roll over in under a week, 0 matches; reversal: an operations-only feed"),
    # Rejections whose recorded reason was wrong, corrected from the saved responses.
    "peterbilt": "JavaScript-rendered listing (no dated items in the HTML)",
    "stratasys": "JavaScript-rendered listing (no dated items in the HTML)",
    "ryder": "JavaScript-rendered listing (no dated items in the HTML)",
    "matternet": "/news redirects to the homepage",
    "hyundai": "JavaScript shell (7 visible characters)",
    "rcsglobal": "/news/ redirects to slrconsulting.com (RCS Global is now part of SLR Consulting)",
    "kiwibot": "redirects to robot.com, where /blog is 404; no listing within 6 requests",
    "gatik": "/news redirects (via www) to archive.gatik.ai; no listing within 6 requests",
    "dexterity": "404 after the www-to-apex redirect; no listing within 6 requests",
}
# Accepted, but re-pointed by hand: ivalua's advertised feed is the site blog; its html
# newsroom (the redirect target of the known URL) passed on its own, 13 dated items.
HAND_REPOINT = {"ivalua": ("https://www.ivalua.com/company/newsroom/", "html")}

# Hand calls on notices found in a listing's own text (step 4), slug -> (reject?, quote).
HAND_NOTICE: dict[str, tuple[bool, str]] = {}

NOTICE_RE = re.compile(
    r"[^.]{0,160}\b(?:automated (?:means|access|tools|systems)|scrap(?:e|ing|er)|crawl(?:er|ing)|"
    r"spider|data mining|text and data mining|bots?\b)[^.]{0,160}\b(?:prohibit\w*|forbid\w*|"
    r"not (?:be )?permitted|may not|must not|reserve\w*)[^.]{0,120}",
    re.I)
# A challenge page names itself; the word "captcha" alone is not one (a newsletter
# form's reCAPTCHA settings put it on ordinary pages: Peterbilt, Stratasys, Ryder,
# Matternet and Hyundai were misread so on the first pass, fix round 2026-09-29).
CHALLENGE_MARKERS = re.compile(r"just a moment|enable javascript and cookies|cf-chl|attention required", re.I)
RSS_LINK_RE = re.compile(r"<link\b[^>]*type=[\"']application/rss\+xml[\"'][^>]*>", re.I)


class BudgetSpent(RuntimeError):
    pass


class DiskSession:
    """A requests session that saves every response as it arrives and replays it on
    a later run, and counts every request (redirect hops requests followed itself
    included) against the current candidate's budget."""

    def __init__(self):
        self.real = http.make_session()
        self.headers = self.real.headers
        self.calls: dict[str, int] = {}   # per URL, this process: the nth call replays the nth save
        self.used = 0
        self.log: list[dict] = []

    def start(self):
        self.used, self.log = 0, []

    def _paths(self, url: str, n: int):
        h = hashlib.sha1(url.encode()).hexdigest()[:20]
        return RESP / f"{h}.{n}.json", RESP / f"{h}.{n}.body"

    def get(self, url, params=None, headers=None, timeout=None, allow_redirects=True, **_kw):
        if self.used >= BUDGET:
            raise BudgetSpent(f"request budget of {BUDGET} spent before {url}")
        n = self.calls.get(url, 0)
        self.calls[url] = n + 1
        meta_p, body_p = self._paths(url, n)
        if meta_p.exists():
            meta = json.loads(meta_p.read_text())
            replayed = True
        else:
            replayed = False
            meta = {"url": url, "n": n, "fetched_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds")}
            try:
                r = self.real.get(url, params=params, headers=headers, timeout=timeout,
                                  allow_redirects=allow_redirects)
                body_p.write_bytes(r.content)
                meta.update(status=r.status_code, final_url=r.url, hops=len(r.history),
                            headers={k: v for k, v in r.headers.items()
                                     if k.lower() in ("content-type", "location", "retry-after")})
            except requests.RequestException as e:
                meta.update(error=f"{type(e).__name__}: {e}"[:300])
            meta_p.write_text(json.dumps(meta))
        self.used += 1 + meta.get("hops", 0)
        self.log.append({"url": url, "status": meta.get("status"), "error": meta.get("error"),
                         "hops": meta.get("hops", 0), "replayed": replayed})
        if "error" in meta:
            raise requests.ConnectionError(meta["error"])
        resp = requests.models.Response()
        resp._content = body_p.read_bytes()
        resp.status_code = meta["status"]
        resp.headers = CaseInsensitiveDict(meta["headers"])
        resp.url = meta["final_url"]
        resp.encoding = requests.utils.get_encoding_from_headers(resp.headers)
        return resp


class Discovery(PressroomCollector):
    """The collector's fetch path, with crawl-delay honoured in full rather than
    capped at 30 s (a discovery run fetches only a handful per host)."""

    def _robots(self, session, url, cache, limiters):
        rules, problem, delay, limiter = super()._robots(session, url, cache, limiters)
        limiter.min_interval = max(self.rate_limit_seconds, delay)
        return rules, problem, delay, limiter


def assess(kind: str, text: str, base: str, pages: dict) -> dict:
    items = items_for(kind, text, base, pages)
    dated = sorted((i.date for i in items if i.date), reverse=True)
    recent = [d for d in dated if YEAR_AGO <= d <= TODAY + dt.timedelta(days=1)]
    return {"kind": kind, "items": len(items), "dated": len(dated),
            "newest": dated[0].isoformat() if dated else None,
            "oldest": dated[-1].isoformat() if dated else None,
            "recent": len(recent), "ok": len(dated) >= 3 and bool(recent)}


def looks_blocked(r) -> str | None:
    """A challenge page or a JavaScript shell, on an HTML listing."""
    text = r.text or ""
    vis = visible_text(text)
    if len(vis) < SHELL_CHARS:
        if CHALLENGE_MARKERS.search(text):
            return "challenge page"
        return f"JavaScript shell ({len(vis)} visible characters)"
    return None


def notices(text: str) -> list[str]:
    return [m[0].strip()[:300] for m in NOTICE_RE.finditer(visible_text(text))][:5]


def is_xml(r) -> bool:
    head = (r.text or "")[:500].lstrip().lower()
    return head.startswith("<?xml") or head.startswith("<rss") or head.startswith("<urlset") \
        or head.startswith("<sitemapindex") or head.startswith("<feed")


def discover(col: Discovery, s: DiskSession, cand, cache, limiters) -> dict:
    slug, name, techs, known = cand
    s.start()
    dec = {"vendor": slug, "name": name, "chosen_for": techs, "tried": [], "checked": TODAY.isoformat()}

    def reject(reason, **extra):
        dec.update(outcome="rejected", reason=reason, **extra)
        return dec

    def get(url, item=False):
        """(response, None) or (None, reason). A 404 is returned as a reason
        beginning '404' so the caller may move on; all else is terminal."""
        try:
            r, note = col._get(s, url, cache, limiters, retries=1, item=item)
        except http.HttpError as e:
            code = e.status
            if code == 404 or code == 410:
                return None, f"{code} at {url}"
            if code == 403:
                return None, "403"
            if code == 429:
                return None, "429"
            return None, f"{code or 'network error'} at {url}"
        except ValueError as e:
            return None, f"bad url: {e}"
        if r is None:
            return None, note
        return r, None

    # 1. robots.txt for the newsroom host.
    first = known[0]
    try:
        rules, problem, delay, _ = col._robots(s, first, cache, limiters)
    except BudgetSpent as e:
        return reject(str(e))
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
                listing, listing_url, listing_idx = r, r.url, len(dec["tried"]) - 1
                break
            if not why.startswith(("404", "410")):
                return reject(why)

        html_assess = None
        if listing is not None and not is_xml(listing):
            blocked = looks_blocked(listing)
            if blocked:
                return reject(blocked)
            found = notices(listing.text)
            if found:
                dec["notice_candidates"] = found
                call = HAND_NOTICE.get(slug)
                if call is None:
                    return reject("notice found; awaiting hand read", pending=True)
                if call[0]:
                    return reject(f"notice forbidding automated access or reuse: \"{call[1]}\"")
            # 2b. an advertised RSS feed, preferred over the html it came from
            for tag in RSS_LINK_RE.findall(listing.text):
                href = re.search(r"href=[\"']([^\"']+)", tag)
                if not href:
                    continue
                feed_url = urljoin(listing_url, href[1].replace("&amp;", "&"))
                if "comments" in feed_url:
                    continue
                r, why = get(feed_url)
                dec["tried"].append({"url": feed_url, "result": why or r.status})
                if r is not None:
                    a = assess("rss", r.text, r.url, {})
                    dec["tried"][-1]["assess"] = a
                    if a["ok"]:
                        return {**dec, "outcome": "accepted", "url": r.url, **a}
                elif why in ("403", "429"):
                    return reject(f"{why} on advertised feed")
                break   # one advertised feed only
            html_assess = assess("html", listing.text, listing_url, {})
            dec["tried"][listing_idx]["assess"] = html_assess
            if html_assess["ok"]:
                return {**dec, "outcome": "accepted", "url": listing_url, **html_assess}
        elif listing is not None:   # the known URL is itself a feed or sitemap
            kind = "sitemap" if "<urlset" in listing.text[:2000] else "rss"
            a = assess(kind, listing.text, listing.url, {})
            if a["ok"]:
                return {**dec, "outcome": "accepted", "url": listing.url, **a}

        # 2c. the fallbacks, on the newsroom's host, while budget lasts
        host = _host(listing_url or first)
        for path in FALLBACKS:
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
                    pick = [k for k in kids if re.search(r"news|press", k, re.I)] or \
                           [k for k in kids if re.search(r"post", k, re.I)]
                    if pick and s.used < BUDGET:
                        r, why = get(pick[0])
                        dec["tried"].append({"url": pick[0], "result": why or r.status})
                        if r is not None and "<urlset" in r.text[:3000]:
                            a = assess("sitemap", r.text, r.url, {})
                            dec["tried"][-1]["assess"] = a
                            if a["ok"]:
                                return {**dec, "outcome": "accepted", "url": r.url, **a}
                continue   # a whole-site urlset is not a news sitemap
            if is_xml(r) and "<item" in r.text:
                a = assess("rss", r.text, r.url, {})
                dec["tried"][-1]["assess"] = a
                if a["ok"]:
                    return {**dec, "outcome": "accepted", "url": r.url, **a}

        # 2d. links:<path> on a listing that loaded, dated from at most 3 item pages
        if listing is not None and not is_xml(listing):
            path = urlparse(listing_url).path.rstrip("/") + "/"
            links = links_under(listing.text, listing_url, path)
            if len(links) >= 3 and s.used + MAX_LINK_PAGES <= BUDGET:
                pages = {}
                for u in links[:MAX_LINK_PAGES]:
                    r, why = get(u, item=True)
                    dec["tried"].append({"url": u, "result": why or r.status})
                    if r is not None:
                        pages[u] = r.text
                kind = f"links:{path}"
                # only the fetched pages can date; the weekly run fetches the first 15
                a = assess(kind, listing.text, listing_url, pages)
                a["dated_of_fetched"] = a["dated"]
                dec["links_assess"] = a
                if a["ok"]:
                    return {**dec, "outcome": "accepted", "url": listing_url, **a}
        if listing is None:
            return reject("no listing: " + "; ".join(str(t["result"]) for t in dec["tried"]))
        why = f"no dated listing (html: {html_assess['dated'] if html_assess else 0} dated, " \
              f"newest {html_assess['newest'] if html_assess else None})"
        return reject(why)
    except BudgetSpent as e:
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
    col, s = Discovery(), DiskSession()
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
        print(f"{time.monotonic() - t0:7.0f}s {cand[0]:16s} {dec['outcome']:9s} "
              f"{dec.get('kind', '')!s:14s} req={s.used} {dec.get('reason', '')}"
              f"{' items=%s newest=%s' % (dec.get('dated'), dec.get('newest')) if dec['outcome'] == 'accepted' else ''}",
              flush=True)
    return 0


def report() -> int:
    for slug, name, techs, _ in CANDIDATES:
        p = DEC / f"{slug}.json"
        if not p.exists():
            print(f"{slug}\t(not run)")
            continue
        d = json.loads(p.read_text())
        if slug in HAND_REJECT:
            d.update(outcome="rejected (hand)" if d["outcome"] == "accepted" else d["outcome"],
                     reason=HAND_REJECT[slug])
        if slug in HAND_REPOINT:
            d.update(url=HAND_REPOINT[slug][0], kind=HAND_REPOINT[slug][1], dated=13, newest="2026-09-25")
        print("\t".join(str(x) for x in (slug, name, ",".join(techs), d["outcome"], d.get("kind", ""),
                                          d.get("dated", ""), d.get("newest", ""), d.get("url", ""),
                                          d.get("reason", ""), d.get("requests", ""))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
