"""Can any free source reach the pilot band (TRL 5-8) for pre-practice
technologies? Three candidates, five technologies, eight weeks. Raw kept.

  GDELT DOC 2.0     article list by keyword; titles and URLs only; one request per 5 s.
  GlobeNewswire     press-release search page (HTML), full text on the release page.
  PR Newswire       press-release search page (HTML), full text on the release page.

Usage: probe.py [--weeks 8]
"""

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from observatory import http  # noqa: E402

OUT = ROOT / "data" / "trl" / "probe"
TECHS = {
    "autonomous_trucking": '("autonomous truck" OR "driverless truck")',
    "delivery_drones": '"drone delivery"',
    "digital_product_passport": '"digital product passport"',
    "humanoid_logistics": '"humanoid robot" warehouse',
    "gs1_2d": '"2D barcode" GS1',
}
PILOT_WORDS = re.compile(r"\b(pilot|deploy|deployed|deployment|rollout|roll out|first (commercial|customer)|"
                         r"in operation|goes live|went live|launch(es|ed)? (at|in|across)|contract|purchase order)\b", re.I)


def gdelt(session, query, start, end):
    url = ("https://api.gdeltproject.org/api/v2/doc/doc?query=" + quote_plus(query + " sourcelang:english")
           + f"&mode=artlist&format=json&maxrecords=250&startdatetime={start:%Y%m%d}000000&enddatetime={end:%Y%m%d}235959")
    r = http.fetch(session, url, limiter=http.RateLimiter(5.0))
    return r.text, [a for a in json.loads(r.text or "{}").get("articles", [])]


def globenewswire(session, query):
    url = "https://www.globenewswire.com/search/keyword/" + quote_plus(query.replace('"', ""))
    r = http.fetch(session, url, limiter=http.RateLimiter(2.0))
    links = re.findall(r'href="(/news-release/[^"]+)"', r.text)
    return r.text, sorted(set("https://www.globenewswire.com" + link for link in links))


def prnewswire(session, query):
    url = "https://www.prnewswire.com/search/news/?keyword=" + quote_plus(query.replace('"', ""))
    r = http.fetch(session, url, limiter=http.RateLimiter(2.0))
    links = re.findall(r'href="(/news-releases/[^"]+\.html)"', r.text)
    return r.text, sorted(set("https://www.prnewswire.com" + link for link in links))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--weeks", type=int, default=8)
    args = p.parse_args()
    end = dt.date.today()
    start = end - dt.timedelta(weeks=args.weeks)
    session = http.make_session()
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for tech, query in TECHS.items():
        raw, arts = gdelt(session, query, start, end)
        (OUT / f"gdelt-{tech}.json").write_text(raw)
        pilotish = [a for a in arts if PILOT_WORDS.search(a.get("title", ""))]
        rows.append((tech, "gdelt", len(arts), len(pilotish), [a["title"] for a in pilotish[:5]]))
        for name, fn in (("globenewswire", globenewswire), ("prnewswire", prnewswire)):
            try:
                raw, links = fn(session, query)
            except http.HttpError as e:
                rows.append((tech, name, -1, -1, [str(e)]))
                continue
            (OUT / f"{name}-{tech}.html").write_text(raw)
            rows.append((tech, name, len(links), None, links[:5]))
    print("| technology | source | documents | pilot-worded titles | examples |")
    print("|---|---|---|---|---|")
    for tech, src, n, k, ex in rows:
        print(f"| {tech} | {src} | {n} | {'' if k is None else k} | {'<br>'.join(str(e)[:90] for e in ex)} |")


if __name__ == "__main__":
    main()
