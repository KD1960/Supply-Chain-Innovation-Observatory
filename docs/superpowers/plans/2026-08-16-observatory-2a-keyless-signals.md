# Observatory 2A — Keyless Signals and Evidence

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill the Investment, Deployment, and Diffusion stages with real data from three more keyless public sources, and make every number on the dashboard clickable down to its evidence.

**Architecture:** Three new collectors (GDELT doc, GDELT geo, USAspending, SEC EDGAR) follow the existing `BaseCollector` contract — fetch raw to disk, parse purely from text. Two new aggregation shapes let one source feed two signals and let adoption be counted as distinct filers over a trailing year. A geocoding helper turns USAspending's state codes into map coordinates. The dashboard gains a Build Map block and a second self-contained page linking every count to the documents behind it.

**Tech Stack:** Python 3.11+, `requests`, `PyYAML`, `Jinja2`, `pytest`. Standard-library `sqlite3`, `csv`, `json`, `re`. No numpy, no pandas.

**Spec:** `docs/superpowers/specs/2026-08-16-supply-chain-innovation-observatory-design.md`

**Predecessor:** `docs/superpowers/plans/2026-08-16-observatory-core-pipeline.md` (complete, merged on `feat/core-pipeline`)

**Scope of this plan:** The keyless half of the spec's build-order phases 5–6. GitHub and PatentsView need API keys and are plan 2B; rising-term discovery, the offline lexicon tool, and backfill are plan 2C.

## Global Constraints

- Python 3.11 or newer; `X | None` type syntax throughout.
- Dependencies limited to `requests`, `PyYAML`, `Jinja2`, `pytest`. No numpy, no pandas.
- **No LLM importable from the weekly run.** `tests/test_guardrails.py` walks the import graph from `run.py`; any new module must stay clean.
- **No network in the test suite.** Every collector test runs against a saved fixture in `tests/fixtures/`.
- **Raw before parse.** `fetch_raw` writes untouched response bodies to `data/raw/<week>/<source>/` before any parsing.
- **A missing week is not a zero week.** A source absent from `ok_sources` gets no signal rows at all.
- **Minimum 12 observed weeks** before any score. `metrics.zscore`/`normalize_series`/`acceleration` gate on observed values, not carried-forward padding.
- **The dashboard references no external resource.** Charts are Python-generated inline SVG.
- Every HTTP request sends `User-Agent` = `SupplyChainObservatory/1.0 (<SEC_CONTACT_EMAIL>)`.
- ISO week strings are `YYYY-Www`, zero-padded.
- Observation week comes from the document's own date via `config.iso_week`, not the run week.
- Commit after every task, conventional-commit prefixes.

---

## Process rule for this plan: capture fixtures from the live API first

Plan 1 lost a full live run to a hand-written arXiv query whose unit test had frozen the *wrong* expected value in place. Tests passed; the API returned 500 every time. Nothing but a real request could have caught it.

So **every collector task in this plan begins by making one real request with `curl` and saving the response as the fixture.** Do not hand-write a fixture from this plan's description of the response shape — the shape in this document is a good-faith sketch and may be stale. Capture, look at what actually came back, and build the parser against that. If the real shape differs from what this plan describes, the real shape wins; note the difference in your report.

This is a development step, not a test. The saved fixture is what the tests use, and the test suite stays offline.

---

## File Structure

| Path | Responsibility |
|---|---|
| `observatory/geo.py` | US state centroids; state code → latitude/longitude |
| `observatory/collectors/gdelt_doc.py` | GDELT article volume and deployment-language articles |
| `observatory/collectors/gdelt_geo.py` | GDELT geocoded article points for the Build Map |
| `observatory/collectors/usaspending.py` | Federal award dollars and counts, with place of performance |
| `observatory/collectors/edgar.py` | SEC full-text search: filings and distinct filers |
| `observatory/normalize.py` | *(modify)* two new aggregation shapes |
| `observatory/http.py` | *(modify)* POST support for USAspending |
| `observatory/charts.py` | *(modify)* the Build Map |
| `observatory/render.py` | *(modify)* Build Map block, evidence links |
| `observatory/templates/evidence.html.j2` | The evidence drill-down page |
| `observatory/run.py` | *(modify)* register the new collectors |

---

### Task 1: Two new aggregation shapes

The existing `Aggregation` supports `count` and `sum_amount` over one week. Two of this plan's signals do not fit that: `media_deploy` counts only the subset of GDELT articles that use deployment language, and `edgar_filers` counts *distinct* filers over a trailing year rather than events in a week.

**Files:**
- Modify: `observatory/normalize.py`
- Test: `tests/test_normalize.py`

**Interfaces:**
- Consumes: `store.set_signal`, `config.trailing_weeks`, `matcher.Watchlist.active`.
- Produces: `Aggregation` gains two optional fields — `entity_filter: str | None = None` and `trailing_weeks: int | None = None`. New method value `"distinct_entities"`. `compute_signals(conn, week, watchlist, ok_sources) -> int` keeps its signature.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_normalize.py`:

```python
def test_entity_filter_counts_only_the_tagged_subset(conn, watchlist):
    store.upsert_observations(conn, [
        observation("autonomous_trucking", "gdelt_doc", "g1"),
        observation("autonomous_trucking", "gdelt_doc", "g2"),
        observation("autonomous_trucking", "gdelt_doc", "g3"),
    ])
    conn.execute("UPDATE observations SET entity = 'deployment' WHERE doc_id IN ('g1','g2')")
    conn.commit()
    normalize.compute_signals(conn, "2026-W33", watchlist, {"gdelt_doc"})
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "media_articles") == 3.0
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "media_deploy") == 2.0


def test_distinct_entities_counts_unique_filers_over_the_trailing_window(conn, watchlist):
    weeks = config.trailing_weeks("2026-W33", 3)
    rows = [
        observation("autonomous_trucking", "edgar", "f1", week=weeks[0], entity_id="0000320193"),
        observation("autonomous_trucking", "edgar", "f2", week=weeks[1], entity_id="0000320193"),
        observation("autonomous_trucking", "edgar", "f3", week=weeks[2], entity_id="0000789019"),
    ]
    store.upsert_observations(conn, rows)
    normalize.compute_signals(conn, "2026-W33", watchlist, {"edgar"})
    # Two distinct CIKs across the window, even though Apple filed twice.
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "edgar_filers") == 2.0


def test_distinct_entities_ignores_documents_outside_the_window(conn, watchlist):
    old = config.week_offset("2026-W33", -60)
    store.upsert_observations(conn, [
        observation("autonomous_trucking", "edgar", "old", week=old, entity_id="0000320193"),
    ])
    normalize.compute_signals(conn, "2026-W33", watchlist, {"edgar"})
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "edgar_filers") == 0.0


def test_distinct_entities_ignores_rows_with_no_entity_id(conn, watchlist):
    store.upsert_observations(conn, [
        observation("autonomous_trucking", "edgar", "f1", entity_id=None),
    ])
    normalize.compute_signals(conn, "2026-W33", watchlist, {"edgar"})
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "edgar_filers") == 0.0
```

The existing `observation()` helper in that file takes fixed values for `week` and `entity_id`. Extend its signature to accept overrides for both, defaulting to what it uses today, so the existing tests keep passing unchanged:

```python
def observation(tech_id, source, doc_id, amount=None, week="2026-W33", entity_id=None):
    return Observation(
        source=source, week=week, tech_id=tech_id, doc_id=doc_id,
        doc_date="2026-08-12", title="t", url="u", entity=None, entity_id=entity_id,
        amount=amount, lat=None, lon=None, matched_pattern="x", raw_ref=1,
    )
```

Add `from observatory import config` to that file's imports if it is not already there.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: the four new tests fail — `media_articles`, `media_deploy`, and `edgar_filers` are not in `AGGREGATIONS` yet, so `get_signal` returns `None`.

- [ ] **Step 3: Implement**

In `observatory/normalize.py`, extend the dataclass and the aggregation table:

```python
@dataclass(frozen=True)
class Aggregation:
    signal: str
    source: str
    method: str  # "count" | "sum_amount" | "distinct_entities"
    entity_filter: str | None = None
    trailing_weeks: int | None = None


AGGREGATIONS: tuple[Aggregation, ...] = (
    Aggregation("arxiv_papers", "arxiv", "count"),
    Aggregation("hn_points", "hn", "sum_amount"),
    Aggregation("fedreg_docs", "federalregister", "count"),
    Aggregation("media_articles", "gdelt_doc", "count"),
    Aggregation("media_deploy", "gdelt_doc", "count", entity_filter="deployment"),
    Aggregation("fed_obligated", "usaspending", "sum_amount"),
    Aggregation("fed_awards", "usaspending", "count"),
    Aggregation("edgar_filings", "edgar", "count"),
    Aggregation("edgar_filers", "edgar", "distinct_entities",
                trailing_weeks=config.TRAILING_WEEKS),
)
```

Add `from . import config, store` at the top (it currently imports only `store`).

Replace `_totals` with a version that handles all three methods:

```python
EXPRESSIONS = {
    "count": "COUNT(*)",
    "sum_amount": "COALESCE(SUM(amount), 0)",
    "distinct_entities": "COUNT(DISTINCT entity_id)",
}


def _totals(conn, week: str, aggregation: Aggregation) -> dict[str, float]:
    expression = EXPRESSIONS[aggregation.method]
    query = f"SELECT tech_id, {expression} AS total FROM observations WHERE source = ?"
    params: list = [aggregation.source]

    if aggregation.trailing_weeks:
        window = config.trailing_weeks(week, aggregation.trailing_weeks)
        query += f" AND week IN ({','.join('?' * len(window))})"
        params += window
    else:
        query += " AND week = ?"
        params.append(week)

    if aggregation.entity_filter is not None:
        query += " AND entity = ?"
        params.append(aggregation.entity_filter)

    if aggregation.method == "distinct_entities":
        query += " AND entity_id IS NOT NULL"

    rows = conn.execute(query + " GROUP BY tech_id", params).fetchall()
    return {row["tech_id"]: float(row["total"]) for row in rows}
```

The `EXPRESSIONS` lookup replaces the previous inline ternary — the two-literal invariant an earlier review asked about is now visible in one place, and the table is the only source of interpolated SQL text.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: all pass, including the five pre-existing tests unchanged.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: all pass. Signals for sources that do not exist yet are simply never written, because their source is never in `ok_sources`.

- [ ] **Step 6: Commit**

```bash
git add observatory/normalize.py tests/test_normalize.py
git commit -m "feat: entity-filtered and trailing distinct-count aggregations"
```

---

### Task 2: US state centroids and geocoding

USAspending returns a place of performance as a state code, not coordinates. The Build Map needs latitude and longitude.

The spec calls for a Census ZCTA ZIP-centroid table. This task ships **state centroids instead** — 51 rows written inline rather than a ~1 MB vendored file that would need a download step. At the national weekly scale the Build Map is answering "which states are getting new logistics capability", and state resolution answers that. Record the reduction in the report; ZIP-level refinement is a later concern.

**Files:**
- Create: `observatory/geo.py`
- Test: `tests/test_geo.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `STATE_CENTROIDS: dict[str, tuple[float, float]]` mapping a two-letter code to `(lat, lon)`; `centroid(state_code: str | None) -> tuple[float, float] | None`, case-insensitive, returning `None` for unknown or missing codes; `CONUS_BOUNDS: tuple[float, float, float, float]` as `(min_lat, max_lat, min_lon, max_lon)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_geo.py`:

```python
from observatory import geo


def test_known_state_resolves_to_plausible_coordinates():
    lat, lon = geo.centroid("AZ")
    assert 31 < lat < 37
    assert -115 < lon < -109


def test_lookup_is_case_insensitive_and_tolerates_whitespace():
    assert geo.centroid("az") == geo.centroid(" AZ ") == geo.centroid("AZ")


def test_unknown_or_missing_state_returns_none():
    assert geo.centroid("ZZ") is None
    assert geo.centroid(None) is None
    assert geo.centroid("") is None


def test_every_centroid_is_a_plausible_us_coordinate():
    for code, (lat, lon) in geo.STATE_CENTROIDS.items():
        assert -180 < lon < 0, code
        assert 15 < lat < 72, code


def test_the_table_covers_all_fifty_states_and_dc():
    assert len(geo.STATE_CENTROIDS) == 51
    for code in ("CA", "TX", "NY", "AK", "HI", "DC"):
        assert code in geo.STATE_CENTROIDS
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_geo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'observatory.geo'`

- [ ] **Step 3: Implement**

Create `observatory/geo.py`. These are approximate geographic centres of each state, sufficient for placing a dot on a national map:

```python
"""US state centroids for the Build Map.

USAspending reports a place of performance as a state code, so a dot needs
coordinates from somewhere. State resolution answers the question the Build Map
asks — which states are gaining logistics capability — without vendoring a
megabyte of ZIP centroids.
"""

from __future__ import annotations

STATE_CENTROIDS: dict[str, tuple[float, float]] = {
    "AL": (32.79, -86.83), "AK": (64.07, -152.28), "AZ": (34.27, -111.66),
    "AR": (34.90, -92.44), "CA": (37.18, -119.47), "CO": (38.997, -105.55),
    "CT": (41.62, -72.73), "DE": (38.99, -75.51), "DC": (38.90, -77.02),
    "FL": (28.63, -82.45), "GA": (32.64, -83.44), "HI": (20.29, -156.37),
    "ID": (44.39, -114.66), "IL": (40.06, -89.19), "IN": (39.89, -86.28),
    "IA": (42.07, -93.50), "KS": (38.49, -98.38), "KY": (37.53, -85.30),
    "LA": (31.07, -92.00), "ME": (45.37, -69.24), "MD": (39.04, -76.79),
    "MA": (42.26, -71.81), "MI": (44.35, -85.41), "MN": (46.28, -94.31),
    "MS": (32.74, -89.66), "MO": (38.37, -92.48), "MT": (47.05, -109.63),
    "NE": (41.53, -99.80), "NV": (39.35, -116.63), "NH": (43.68, -71.58),
    "NJ": (40.19, -74.67), "NM": (34.41, -106.11), "NY": (42.95, -75.53),
    "NC": (35.56, -79.39), "ND": (47.45, -100.47), "OH": (40.29, -82.79),
    "OK": (35.59, -97.49), "OR": (43.94, -120.56), "PA": (40.88, -77.80),
    "RI": (41.68, -71.56), "SC": (33.92, -80.90), "SD": (44.44, -100.23),
    "TN": (35.86, -86.35), "TX": (31.43, -99.33), "UT": (39.33, -111.68),
    "VT": (44.07, -72.67), "VA": (37.52, -78.85), "WA": (47.38, -120.45),
    "WV": (38.64, -80.62), "WI": (44.62, -89.99), "WY": (42.998, -107.55),
}

# Continental bounds, used to frame the Build Map. Alaska and Hawaii fall
# outside and are drawn clamped to the edge rather than dropped.
CONUS_BOUNDS = (24.5, 49.5, -125.0, -66.5)


def centroid(state_code: str | None) -> tuple[float, float] | None:
    if not state_code:
        return None
    return STATE_CENTROIDS.get(state_code.strip().upper())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_geo.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add observatory/geo.py tests/test_geo.py
git commit -m "feat: US state centroids for the Build Map"
```

---

### Task 3: GDELT document collector

Feeds two signals: `media_articles` (attention — the denominator of the substance index) and `media_deploy` (articles using deployment language, which is real evidence of capability going live).

**Files:**
- Create: `observatory/collectors/gdelt_doc.py`, `tests/fixtures/gdelt_doc_page.json`
- Test: `tests/test_collector_gdelt_doc.py`

**Interfaces:**
- Consumes: `base.BaseCollector`, `base.Document`, `base.RawPage`, `http.fetch`, `http.RateLimiter`, `config.week_bounds`, `config.LOOKBACK_DAYS`.
- Produces: `GdeltDocCollector` with `name = "gdelt_doc"`, `DEPLOYMENT_LEXICON: tuple[str, ...]`, `deployment_tag(text) -> str | None`, `window(week) -> tuple[str, str]`, `fetch_raw`, `parse`. Document `doc_id` is `gdelt:<sha1 of url>`, `entity` is `"deployment"` for articles using deployment language and `None` otherwise.

- [ ] **Step 1: Capture the fixture from the live API**

```bash
curl -s -A "SupplyChainObservatory/1.0 (kevindooley1960@gmail.com)" \
  --get "https://api.gdeltproject.org/api/v2/doc/doc" \
  --data-urlencode 'query="supply chain" sourcelang:english' \
  -d "mode=artlist" -d "format=json" -d "maxrecords=50" \
  -d "startdatetime=20260810000000" -d "enddatetime=20260817000000" \
  -o "tests/fixtures/gdelt_doc_page.json"
python3 -m json.tool tests/fixtures/gdelt_doc_page.json | head -30
```

Read what came back. The expected shape is `{"articles": [{"url", "title", "seendate", "domain", "language", "sourcecountry"}, ...]}` with `seendate` like `20260812T120000Z`. **If it differs, the live shape wins** — build the parser against what you actually received and note the difference in your report. If the response is empty or an error, widen the date window and try again; GDELT sometimes trails by a day.

Trim the fixture to about 6 articles so the file stays readable, keeping at least one whose title uses deployment language (opens, launches, breaks ground, goes live, begins operations, deploys) and at least one that does not. If none of the captured articles uses deployment language, edit one title so the fixture exercises both branches, and say so in your report.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_collector_gdelt_doc.py`:

```python
import json
from pathlib import Path

from observatory.collectors.gdelt_doc import GdeltDocCollector

FIXTURE = Path(__file__).parent / "fixtures" / "gdelt_doc_page.json"


def test_parse_returns_a_document_per_article():
    documents = GdeltDocCollector().parse(FIXTURE.read_text())
    assert len(documents) >= 2
    assert all(doc.doc_id.startswith("gdelt:") for doc in documents)


def test_doc_id_is_stable_for_the_same_url():
    collector = GdeltDocCollector()
    first = collector.parse(FIXTURE.read_text())
    second = collector.parse(FIXTURE.read_text())
    assert [d.doc_id for d in first] == [d.doc_id for d in second]


def test_seendate_becomes_an_iso_date():
    for doc in GdeltDocCollector().parse(FIXTURE.read_text()):
        assert doc.date is None or (len(doc.date) == 10 and doc.date[4] == "-")


def test_deployment_language_is_tagged_and_other_articles_are_not():
    entities = {doc.entity for doc in GdeltDocCollector().parse(FIXTURE.read_text())}
    assert "deployment" in entities
    assert None in entities


def test_deployment_tag_recognises_the_lexicon():
    collector = GdeltDocCollector()
    assert collector.deployment_tag("Port of Savannah opens automated terminal") == "deployment"
    assert collector.deployment_tag("Firm breaks ground on new warehouse") == "deployment"
    assert collector.deployment_tag("Analysts debate warehouse automation") is None


def test_deployment_tag_requires_a_word_boundary():
    collector = GdeltDocCollector()
    assert collector.deployment_tag("reopens discussion") is None


def test_window_spans_the_week_plus_the_lookback():
    start, end = GdeltDocCollector().window("2026-W33")
    assert start == "20260803000000"
    assert end == "20260817000000"


def test_parse_handles_an_empty_result_set():
    assert GdeltDocCollector().parse(json.dumps({"articles": []})) == []


def test_parse_tolerates_a_missing_articles_key():
    assert GdeltDocCollector().parse(json.dumps({})) == []
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/test_collector_gdelt_doc.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'observatory.collectors.gdelt_doc'`

- [ ] **Step 4: Implement**

Create `observatory/collectors/gdelt_doc.py`:

```python
"""GDELT DOC 2.0 — media attention, and the subset that reports capability going live.

Two signals come out of one sweep. Total article volume is the attention side of
the substance-versus-attention comparison. Articles whose headline uses
deployment language are tagged so they can be counted separately: "breaks ground
on a distribution centre" is evidence of a thing being built, not chatter about
one.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from typing import Iterator

from .. import config, http
from .base import BaseCollector, Document, RawPage

API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
MAX_RECORDS = 250

ANCHOR_QUERIES = (
    '"supply chain" sourcelang:english',
    '"logistics" sourcelang:english',
    '"freight" sourcelang:english',
    '"warehouse automation" sourcelang:english',
)

DEPLOYMENT_LEXICON = (
    "opens", "opened", "opening",
    "launches", "launched",
    "breaks ground", "broke ground", "groundbreaking",
    "goes live", "went live",
    "begins operations", "began operations",
    "deploys", "deployed", "rollout", "rolls out", "rolled out",
    "commissions", "commissioned",
    "starts production", "began production",
)

_DEPLOYMENT_RE = re.compile(
    r"\b(?:%s)\b" % "|".join(re.escape(term) for term in DEPLOYMENT_LEXICON),
    re.IGNORECASE,
)


class GdeltDocCollector(BaseCollector):
    name = "gdelt_doc"
    rate_limit_seconds = 5.0  # GDELT asks for a light touch on the public API

    def window(self, week: str) -> tuple[str, str]:
        start, end = config.week_bounds(week)
        start -= dt.timedelta(days=config.LOOKBACK_DAYS)
        end += dt.timedelta(days=1)
        return start.strftime("%Y%m%d000000"), end.strftime("%Y%m%d000000")

    def deployment_tag(self, text: str | None) -> str | None:
        return "deployment" if text and _DEPLOYMENT_RE.search(text) else None

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        limiter = http.RateLimiter(self.rate_limit_seconds)
        start, end = self.window(week)
        for query in ANCHOR_QUERIES:
            params = {
                "query": query,
                "mode": "artlist",
                "format": "json",
                "maxrecords": MAX_RECORDS,
                "startdatetime": start,
                "enddatetime": end,
            }
            response = http.fetch(session, API_URL, params=params, limiter=limiter)
            yield RawPage(response.url, response.status, response.text, "json")

    def parse(self, text: str) -> list[Document]:
        payload = json.loads(text or "{}")
        documents = []
        for article in payload.get("articles", []) or []:
            url = article.get("url")
            if not url:
                continue
            title = article.get("title")
            documents.append(
                Document(
                    doc_id=f"gdelt:{hashlib.sha1(url.encode()).hexdigest()}",
                    date=_iso_date(article.get("seendate")),
                    title=title,
                    text=article.get("domain") or "",
                    url=url,
                    entity=self.deployment_tag(title),
                )
            )
        return documents


def _iso_date(seendate: str | None) -> str | None:
    """GDELT stamps articles as 20260812T120000Z."""
    if not seendate or len(seendate) < 8:
        return None
    stamp = seendate[:8]
    try:
        return dt.datetime.strptime(stamp, "%Y%m%d").date().isoformat()
    except ValueError:
        return None
```

A note on `text`: the domain goes in the body rather than nothing, so an article from `freightwaves.com` carries a supply chain word for the matcher's context gate. GDELT does not return article bodies.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_collector_gdelt_doc.py -v`
Expected: all pass. If a test fails because the captured fixture's shape differs from this plan's sketch, fix the *parser* to match the real response and adjust the test's expectations to the real data — never edit the fixture to match a wrong parser.

- [ ] **Step 6: Commit**

```bash
git add observatory/collectors/gdelt_doc.py tests/test_collector_gdelt_doc.py tests/fixtures/gdelt_doc_page.json
git commit -m "feat: GDELT document collector with deployment-language tagging"
```

---

### Task 4: GDELT geo collector

Supplies the Build Map's news-derived points: where in the country supply chain capability is being reported.

**Files:**
- Create: `observatory/collectors/gdelt_geo.py`, `tests/fixtures/gdelt_geo_page.json`
- Test: `tests/test_collector_gdelt_geo.py`

**Interfaces:**
- Consumes: `base.BaseCollector`, `http.fetch`, `config.week_bounds`.
- Produces: `GdeltGeoCollector` with `name = "gdelt_geo"`, `fetch_raw`, `parse`. Document `lat`/`lon` carry the point, `amount` carries GDELT's article count for that location, `doc_id` is `gdeltgeo:<sha1 of name+coords>`.

- [ ] **Step 1: Capture the fixture from the live API**

```bash
curl -s -A "SupplyChainObservatory/1.0 (kevindooley1960@gmail.com)" \
  --get "https://api.gdeltproject.org/api/v2/geo/geo" \
  --data-urlencode 'query="distribution center" OR "warehouse"' \
  -d "format=GeoJSON" -d "mode=PointData" -d "TIMESPAN=7d" \
  -o "tests/fixtures/gdelt_geo_page.json"
python3 -m json.tool tests/fixtures/gdelt_geo_page.json | head -40
```

Expected shape is a GeoJSON `FeatureCollection` whose features carry `geometry.coordinates` as `[lon, lat]` — note the order, it is the opposite of how the rest of this codebase writes it — and `properties` with `name`, `count`, and `html`. **The live shape wins.** Trim to roughly 8 features.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_collector_gdelt_geo.py`:

```python
import json
from pathlib import Path

from observatory.collectors.gdelt_geo import GdeltGeoCollector

FIXTURE = Path(__file__).parent / "fixtures" / "gdelt_geo_page.json"


def test_parse_returns_points_with_coordinates():
    documents = GdeltGeoCollector().parse(FIXTURE.read_text())
    assert documents
    for doc in documents:
        assert doc.lat is not None and doc.lon is not None


def test_geojson_lon_lat_order_is_not_swapped():
    """GeoJSON is [lon, lat]; every other field in this codebase is (lat, lon)."""
    for doc in GdeltGeoCollector().parse(FIXTURE.read_text()):
        assert -90 <= doc.lat <= 90, f"latitude out of range: {doc.lat}"
        assert -180 <= doc.lon <= 180


def test_article_count_lands_in_amount():
    documents = GdeltGeoCollector().parse(FIXTURE.read_text())
    assert any(doc.amount and doc.amount > 0 for doc in documents)


def test_location_name_becomes_the_title():
    assert all(doc.title for doc in GdeltGeoCollector().parse(FIXTURE.read_text()))


def test_doc_id_is_stable_across_parses():
    collector = GdeltGeoCollector()
    assert [d.doc_id for d in collector.parse(FIXTURE.read_text())] == \
           [d.doc_id for d in collector.parse(FIXTURE.read_text())]


def test_features_without_geometry_are_skipped():
    payload = json.dumps({"features": [
        {"properties": {"name": "Nowhere", "count": 3}},
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-97.0, 35.0]},
         "properties": {"name": "Somewhere", "count": 2}},
    ]})
    documents = GdeltGeoCollector().parse(payload)
    assert len(documents) == 1
    assert documents[0].title == "Somewhere"


def test_parse_handles_an_empty_feature_collection():
    assert GdeltGeoCollector().parse(json.dumps({"features": []})) == []
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/test_collector_gdelt_geo.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement**

Create `observatory/collectors/gdelt_geo.py`:

```python
"""GDELT GEO 2.0 — where the news says things are happening.

Supplies the news half of the Build Map. GeoJSON orders coordinates as
[longitude, latitude], which is the reverse of every other coordinate pair in
this codebase, so the unpacking below is deliberate and tested.
"""

from __future__ import annotations

import hashlib
import json
from typing import Iterator

from .. import config, http
from .base import BaseCollector, Document, RawPage

API_URL = "https://api.gdeltproject.org/api/v2/geo/geo"

ANCHOR_QUERIES = (
    '"distribution center" OR "distribution centre"',
    '"warehouse" OR "fulfillment center"',
    '"intermodal terminal" OR "inland port"',
)


class GdeltGeoCollector(BaseCollector):
    name = "gdelt_geo"
    rate_limit_seconds = 5.0

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        limiter = http.RateLimiter(self.rate_limit_seconds)
        for query in ANCHOR_QUERIES:
            params = {
                "query": query,
                "format": "GeoJSON",
                "mode": "PointData",
                "TIMESPAN": f"{config.LOOKBACK_DAYS + 7}d",
            }
            response = http.fetch(session, API_URL, params=params, limiter=limiter)
            yield RawPage(response.url, response.status, response.text, "json")

    def parse(self, text: str) -> list[Document]:
        payload = json.loads(text or "{}")
        documents = []
        for feature in payload.get("features", []) or []:
            geometry = feature.get("geometry") or {}
            coordinates = geometry.get("coordinates") or []
            if len(coordinates) < 2:
                continue
            longitude, latitude = float(coordinates[0]), float(coordinates[1])
            properties = feature.get("properties") or {}
            name = properties.get("name") or "unknown location"
            key = hashlib.sha1(f"{name}|{latitude},{longitude}".encode()).hexdigest()
            documents.append(
                Document(
                    doc_id=f"gdeltgeo:{key}",
                    date=None,
                    title=name,
                    text=properties.get("html") or "",
                    url=properties.get("url"),
                    amount=float(properties.get("count") or 0),
                    lat=latitude,
                    lon=longitude,
                )
            )
        return documents
```

`date` is `None` because the GEO API reports a rolling timespan rather than per-article dates. `run._document_week` falls back to the run week for undated documents, which is the correct behaviour here.

Remove the unused `dt` and `end` lines if your final implementation does not need them — do not leave dead code behind.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_collector_gdelt_geo.py -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add observatory/collectors/gdelt_geo.py tests/test_collector_gdelt_geo.py tests/fixtures/gdelt_geo_page.json
git commit -m "feat: GDELT geo collector for Build Map points"
```

---

### Task 5: POST support in the HTTP client

USAspending's search endpoint takes a JSON body. The shared client only does GET.

**Files:**
- Modify: `observatory/http.py`
- Test: `tests/test_http.py`

**Interfaces:**
- Consumes: existing `Response`, `HttpError`, `RateLimiter`, `_backoff_seconds`.
- Produces: `fetch_post(session, url, payload: dict, *, headers=None, limiter=None, retries=3, sleep_fn=time.sleep) -> Response`, with the same retry, backoff, and network-exception behaviour as `fetch`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_http.py`:

```python
class FakePostSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_fetch_post_sends_the_payload_as_json():
    session = FakePostSession([FakeResponse(200, '{"results": []}')])
    result = http.fetch_post(session, "https://example.test/s", {"filters": {"a": 1}})
    assert result.status == 200
    assert session.calls[0]["json"] == {"filters": {"a": 1}}


def test_fetch_post_retries_on_server_error():
    slept = []
    session = FakePostSession([FakeResponse(500), FakeResponse(200, "ok")])
    assert http.fetch_post(session, "https://example.test/s", {}, sleep_fn=slept.append).text == "ok"
    assert slept == [1.0]


def test_fetch_post_retries_network_errors_like_fetch_does():
    slept = []
    session = FakePostSession([requests.ConnectionError("reset"), FakeResponse(200, "ok")])
    assert http.fetch_post(session, "https://example.test/s", {}, sleep_fn=slept.append).text == "ok"
    assert slept == [1.0]


def test_fetch_post_fails_fast_on_client_error():
    session = FakePostSession([FakeResponse(400)])
    with pytest.raises(http.HttpError):
        http.fetch_post(session, "https://example.test/s", {}, sleep_fn=lambda _: None)
    assert len(session.calls) == 1
```

Add `import requests` at the top of the test file if it is not already imported.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_http.py -v`
Expected: the four new tests fail with `AttributeError: module 'observatory.http' has no attribute 'fetch_post'`

- [ ] **Step 3: Implement**

The retry loop in `fetch` and the one `fetch_post` needs are the same shape. Extract the shared loop rather than copying it — a duplicated retry policy is exactly the kind of thing that drifts. In `observatory/http.py`, refactor so both call one private helper:

```python
def fetch(session, url, *, params=None, headers=None, limiter=None,
          retries=3, sleep_fn=time.sleep) -> Response:
    return _with_retries(
        lambda: session.get(url, params=params, headers=headers, timeout=TIMEOUT_SECONDS),
        url, retries, limiter, sleep_fn,
    )


def fetch_post(session, url, payload: dict, *, headers=None, limiter=None,
               retries=3, sleep_fn=time.sleep) -> Response:
    return _with_retries(
        lambda: session.post(url, json=payload, headers=headers, timeout=TIMEOUT_SECONDS),
        url, retries, limiter, sleep_fn,
    )


def _with_retries(send, url: str, retries: int, limiter, sleep_fn) -> Response:
    last_status = None
    last_exception = None
    for attempt in range(retries + 1):
        if limiter is not None:
            limiter.wait()
        try:
            raw = send()
        except requests.RequestException as error:
            last_exception = error
            last_status = None
            if attempt == retries:
                break
            sleep_fn(float(2**attempt))
            continue
        last_exception = None
        last_status = raw.status_code
        if raw.status_code == 200:
            return Response(
                url=getattr(raw, "url", url),
                status=raw.status_code,
                text=raw.text,
                content_type=raw.headers.get("Content-Type", ""),
            )
        if raw.status_code not in RETRYABLE_STATUSES:
            raise HttpError(f"{url} failed with status {raw.status_code}")
        if attempt == retries:
            break
        sleep_fn(_backoff_seconds(raw, attempt))
    if last_exception is not None:
        raise HttpError(f"{url} failed with network error: {last_exception}") from last_exception
    raise HttpError(f"{url} still failing with status {last_status} after {retries} retries")
```

Preserve the existing behaviour exactly: the `last_exception` reset on a non-exception attempt is the fix an earlier review asked for and must stay. All ten existing `test_http.py` tests must pass unchanged — if any fails, the refactor changed behaviour and you should stop and report rather than adjust the test.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_http.py -v`
Expected: all pass, existing tests unchanged.

- [ ] **Step 5: Commit**

```bash
git add observatory/http.py tests/test_http.py
git commit -m "feat: POST support sharing the GET retry policy"
```

---

### Task 6: USAspending collector

Federal contract and grant dollars are the Investment stage, and their place of performance is the Build Map's hard-money layer.

**Files:**
- Create: `observatory/collectors/usaspending.py`, `tests/fixtures/usaspending_page.json`
- Test: `tests/test_collector_usaspending.py`

**Interfaces:**
- Consumes: `base.BaseCollector`, `http.fetch_post`, `http.RateLimiter`, `config.week_bounds`, `config.LOOKBACK_DAYS`, `geo.centroid`.
- Produces: `UsaspendingCollector` with `name = "usaspending"`, `KEYWORDS: tuple[str, ...]`, `payload_for(week, keyword, page) -> dict`, `fetch_raw`, `parse`. Document `amount` is the award amount, `entity` is the recipient name, `lat`/`lon` come from the place-of-performance state, `doc_id` is `usaspend:<Award ID>`.

- [ ] **Step 1: Capture the fixture from the live API**

```bash
curl -s -A "SupplyChainObservatory/1.0 (kevindooley1960@gmail.com)" \
  -H "Content-Type: application/json" \
  -X POST "https://api.usaspending.gov/api/v2/search/spending_by_award/" \
  -d '{"filters":{"keywords":["port infrastructure"],"time_period":[{"start_date":"2026-05-01","end_date":"2026-08-17"}],"award_type_codes":["A","B","C","D"]},"fields":["Award ID","Recipient Name","Award Amount","Description","Place of Performance State Code","Start Date"],"page":1,"limit":20,"sort":"Award Amount","order":"desc","subawards":false}' \
  -o "tests/fixtures/usaspending_page.json"
python3 -m json.tool tests/fixtures/usaspending_page.json | head -40
```

Expected shape is `{"results": [...], "page_metadata": {"page": 1, "hasNext": false}}` where each result has the requested field names as keys, verbatim including spaces. **The live shape wins** — in particular, confirm the exact key for the state code, and confirm whether `Award Amount` arrives as a number or a string. Note either in your report. A wide date window is used here only to guarantee the capture returns rows.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_collector_usaspending.py`:

```python
import json
from pathlib import Path

from observatory.collectors.usaspending import UsaspendingCollector

FIXTURE = Path(__file__).parent / "fixtures" / "usaspending_page.json"


def test_parse_returns_a_document_per_award():
    documents = UsaspendingCollector().parse(FIXTURE.read_text())
    assert documents
    assert all(doc.doc_id.startswith("usaspend:") for doc in documents)


def test_award_amount_lands_in_amount_as_a_float():
    for doc in UsaspendingCollector().parse(FIXTURE.read_text()):
        assert doc.amount is None or isinstance(doc.amount, float)


def test_recipient_becomes_the_entity():
    assert any(doc.entity for doc in UsaspendingCollector().parse(FIXTURE.read_text()))


def test_state_code_is_resolved_to_coordinates():
    documents = UsaspendingCollector().parse(FIXTURE.read_text())
    located = [doc for doc in documents if doc.lat is not None]
    assert located, "at least one award should resolve to a state centroid"
    for doc in located:
        assert 15 < doc.lat < 72
        assert -180 < doc.lon < 0


def test_unknown_state_leaves_coordinates_empty_rather_than_guessing():
    payload = json.dumps({"results": [{
        "Award ID": "X1", "Recipient Name": "R", "Award Amount": 10.0,
        "Description": "d", "Place of Performance State Code": "ZZ",
        "Start Date": "2026-08-12",
    }]})
    doc = UsaspendingCollector().parse(payload)[0]
    assert doc.lat is None and doc.lon is None


def test_amount_survives_a_string_valued_award_amount():
    payload = json.dumps({"results": [{
        "Award ID": "X2", "Recipient Name": "R", "Award Amount": "1234.50",
        "Description": "d", "Place of Performance State Code": "AZ",
        "Start Date": "2026-08-12",
    }]})
    assert UsaspendingCollector().parse(payload)[0].amount == 1234.50


def test_payload_window_includes_the_lookback():
    payload = UsaspendingCollector().payload_for("2026-W33", "port infrastructure", 1)
    period = payload["filters"]["time_period"][0]
    assert period["start_date"] == "2026-08-03"
    assert period["end_date"] == "2026-08-16"
    assert payload["filters"]["keywords"] == ["port infrastructure"]
    assert payload["page"] == 1


def test_parse_handles_an_empty_result_set():
    assert UsaspendingCollector().parse(json.dumps({"results": []})) == []
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/test_collector_usaspending.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement**

Create `observatory/collectors/usaspending.py`:

```python
"""USAspending — federal award dollars and where the work happens.

This is the hardest of the hard signals: money obligated against a contract, with
a place of performance. It feeds both the Investment stage and the Build Map.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Iterator

from .. import config, geo, http
from .base import BaseCollector, Document, RawPage

API_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
PAGE_SIZE = 100
MAX_PAGES = 5

FIELDS = [
    "Award ID", "Recipient Name", "Award Amount", "Description",
    "Place of Performance State Code", "Start Date",
]

KEYWORDS = (
    "port infrastructure",
    "freight rail",
    "intermodal facility",
    "warehouse automation",
    "truck charging",
    "supply chain resilience",
)


class UsaspendingCollector(BaseCollector):
    name = "usaspending"
    rate_limit_seconds = 2.0

    def payload_for(self, week: str, keyword: str, page: int) -> dict:
        start, end = config.week_bounds(week)
        start -= dt.timedelta(days=config.LOOKBACK_DAYS)
        return {
            "filters": {
                "keywords": [keyword],
                "time_period": [
                    {"start_date": start.isoformat(), "end_date": end.isoformat()}
                ],
                "award_type_codes": ["A", "B", "C", "D"],
            },
            "fields": FIELDS,
            "page": page,
            "limit": PAGE_SIZE,
            "sort": "Award Amount",
            "order": "desc",
            "subawards": False,
        }

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        limiter = http.RateLimiter(self.rate_limit_seconds)
        for keyword in KEYWORDS:
            for page in range(1, MAX_PAGES + 1):
                payload = self.payload_for(week, keyword, page)
                response = http.fetch_post(session, API_URL, payload, limiter=limiter)
                yield RawPage(response.url, response.status, response.text, "json")
                metadata = json.loads(response.text).get("page_metadata") or {}
                if not metadata.get("hasNext"):
                    break

    def parse(self, text: str) -> list[Document]:
        payload = json.loads(text or "{}")
        documents = []
        for result in payload.get("results", []) or []:
            award_id = result.get("Award ID")
            if not award_id:
                continue
            point = geo.centroid(result.get("Place of Performance State Code"))
            documents.append(
                Document(
                    doc_id=f"usaspend:{award_id}",
                    date=result.get("Start Date"),
                    title=result.get("Description") or award_id,
                    text=result.get("Description") or "",
                    url=f"https://www.usaspending.gov/award/{award_id}",
                    entity=result.get("Recipient Name"),
                    entity_id=None,
                    amount=_amount(result.get("Award Amount")),
                    lat=point[0] if point else None,
                    lon=point[1] if point else None,
                )
            )
        return documents


def _amount(value) -> float | None:
    """The API has returned this as both a number and a numeric string."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_collector_usaspending.py -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add observatory/collectors/usaspending.py tests/test_collector_usaspending.py tests/fixtures/usaspending_page.json
git commit -m "feat: USAspending collector with place-of-performance geocoding"
```

---

### Task 7: SEC EDGAR collector

The Diffusion signal: how many *distinct* public companies name a technology in their filings. Breadth of adopters, not volume of mentions.

**Files:**
- Create: `observatory/collectors/edgar.py`, `tests/fixtures/edgar_page.json`
- Test: `tests/test_collector_edgar.py`

**Interfaces:**
- Consumes: `base.BaseCollector`, `http.fetch`, `http.RateLimiter`, `config.week_bounds`, `config.LOOKBACK_DAYS`, `config.require_env`.
- Produces: `EdgarCollector` with `name = "edgar"`, `FORMS: tuple[str, ...]`, `QUERY_TERMS: tuple[str, ...]`, `fetch_raw`, `parse`. Document `entity_id` is the zero-padded CIK — this is what `edgar_filers` counts distinctly — and `entity` is the filer's display name.

- [ ] **Step 1: Capture the fixture from the live API**

SEC requires a descriptive User-Agent with a contact address and rate-limits aggressively. Be polite.

```bash
curl -s -A "SupplyChainObservatory/1.0 (kevindooley1960@gmail.com)" \
  --get "https://efts.sec.gov/LATEST/search-index" \
  --data-urlencode 'q="autonomous trucking"' \
  -d "forms=10-K" -d "startdt=2026-01-01" -d "enddt=2026-08-17" \
  -o "tests/fixtures/edgar_page.json"
python3 -m json.tool tests/fixtures/edgar_page.json | head -50
```

Expected shape is Elasticsearch-flavoured: `{"hits": {"total": {"value": N}, "hits": [{"_id": "0000320193-26-000001:doc.htm", "_source": {"ciks": ["0000320193"], "display_names": ["Apple Inc. (AAPL)"], "file_date": "2026-08-12", "root_forms": ["10-K"], "file_type": "10-K"}}]}}`.

**This endpoint is the least documented of the four and the most likely to differ from the sketch above.** If the capture fails or returns something unexpected, try `https://efts.sec.gov/LATEST/search-index?q=%22autonomous%20trucking%22&forms=10-K` directly in a browser to see what the SEC's own full-text search UI calls, and build against that. If you cannot get a usable response at all, stop and report BLOCKED with what you tried — do not invent a fixture.

Trim to about 5 hits, keeping at least two that share a CIK so the distinct-count logic has something to collapse.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_collector_edgar.py`:

```python
import json
from pathlib import Path

from observatory.collectors.edgar import EdgarCollector

FIXTURE = Path(__file__).parent / "fixtures" / "edgar_page.json"


def test_parse_returns_a_document_per_hit():
    documents = EdgarCollector().parse(FIXTURE.read_text())
    assert documents
    assert all(doc.doc_id.startswith("edgar:") for doc in documents)


def test_cik_becomes_entity_id_zero_padded_to_ten_digits():
    for doc in EdgarCollector().parse(FIXTURE.read_text()):
        assert doc.entity_id is not None
        assert len(doc.entity_id) == 10
        assert doc.entity_id.isdigit()


def test_display_name_becomes_the_entity():
    assert all(doc.entity for doc in EdgarCollector().parse(FIXTURE.read_text()))


def test_file_date_becomes_an_iso_date():
    for doc in EdgarCollector().parse(FIXTURE.read_text()):
        assert doc.date is None or (len(doc.date) == 10 and doc.date[4] == "-")


def test_url_points_at_the_filing_on_sec_gov():
    for doc in EdgarCollector().parse(FIXTURE.read_text()):
        assert doc.url.startswith("https://www.sec.gov/")


def test_two_filings_from_one_company_share_an_entity_id():
    ids = [doc.entity_id for doc in EdgarCollector().parse(FIXTURE.read_text())]
    assert len(ids) > len(set(ids)), "fixture should contain a repeated filer"


def test_hits_without_a_cik_are_skipped():
    payload = json.dumps({"hits": {"hits": [
        {"_id": "x:doc.htm", "_source": {"display_names": ["Nobody"], "file_date": "2026-08-12"}},
    ]}})
    assert EdgarCollector().parse(payload) == []


def test_parse_handles_an_empty_result_set():
    assert EdgarCollector().parse(json.dumps({"hits": {"hits": []}})) == []
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/test_collector_edgar.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement**

Create `observatory/collectors/edgar.py`:

```python
"""SEC EDGAR full-text search — which public companies name a technology.

The signal that matters here is breadth, not volume: `edgar_filers` counts
distinct CIKs over a trailing year, so one company mentioning a technology in
every quarterly filing counts once, and ten companies mentioning it once each
counts ten. That is the difference between one enthusiast and an industry
adopting something.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Iterator

from .. import config, http
from .base import BaseCollector, Document, RawPage

API_URL = "https://efts.sec.gov/LATEST/search-index"
FORMS = ("10-K", "10-Q", "8-K", "S-1")

QUERY_TERMS = (
    "autonomous trucking",
    "warehouse robotics",
    "supply chain visibility",
    "digital freight",
    "cold chain",
    "nearshoring",
    "warehouse management system",
    "enterprise resource planning",
)


class EdgarCollector(BaseCollector):
    name = "edgar"
    rate_limit_seconds = 1.0  # SEC asks for no more than 10 requests/second

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        limiter = http.RateLimiter(self.rate_limit_seconds)
        start, end = config.week_bounds(week)
        start -= dt.timedelta(days=config.LOOKBACK_DAYS)
        for term in QUERY_TERMS:
            params = {
                "q": f'"{term}"',
                "forms": ",".join(FORMS),
                "startdt": start.isoformat(),
                "enddt": end.isoformat(),
            }
            response = http.fetch(session, API_URL, params=params, limiter=limiter)
            yield RawPage(response.url, response.status, response.text, "json")

    def parse(self, text: str) -> list[Document]:
        payload = json.loads(text or "{}")
        hits = ((payload.get("hits") or {}).get("hits")) or []
        documents = []
        for hit in hits:
            source = hit.get("_source") or {}
            ciks = source.get("ciks") or []
            if not ciks:
                continue
            cik = str(ciks[0]).strip().zfill(10)
            names = source.get("display_names") or []
            documents.append(
                Document(
                    doc_id=f"edgar:{hit.get('_id')}",
                    date=(source.get("file_date") or None),
                    title=names[0] if names else cik,
                    text=" ".join(source.get("root_forms") or []),
                    url=_filing_url(hit.get("_id"), cik),
                    entity=names[0] if names else None,
                    entity_id=cik,
                )
            )
        return documents


def _filing_url(hit_id: str | None, cik: str) -> str:
    """EDGAR ids look like 0000320193-26-000001:aapl-20260630.htm."""
    if not hit_id or ":" not in hit_id:
        return f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"
    accession, _, document = hit_id.partition(":")
    return (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession.replace('-', '')}/{document}"
    )
```

Note the matcher implication: `text` here is only the form type, so a filing matches a technology through the **query term** that retrieved it rather than through its body. That is intentional — full filing bodies are megabytes each and the search API has already done the matching. Because the query terms and the watchlist patterns are maintained separately, keep `QUERY_TERMS` aligned with the watchlist when either changes.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_collector_edgar.py -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add observatory/collectors/edgar.py tests/test_collector_edgar.py tests/fixtures/edgar_page.json
git commit -m "feat: SEC EDGAR collector counting distinct filers"
```

---

### Task 8: Register the collectors and run the pipeline for real

**Deferral affecting this task.** Tasks 3 and 4 (GDELT doc and geo) could not be completed:
GDELT rate-limited the project into an HTTP 429 IP cooldown during fixture capture, and it was
still refusing requests forty minutes later. Rather than hand-write a fixture — the exact
shortcut that shipped a broken collector in the previous plan — those two tasks are deferred
and their drafts parked. So this task registers **five** collectors, not seven, and the
aggregation-coverage test carries an explicit deferred set. When GDELT is reachable again,
tasks 3 and 4 land and both lists shrink by their two entries.

**Files:**
- Modify: `observatory/run.py`
- Test: `tests/test_run.py`

**Interfaces:**
- Consumes: `UsaspendingCollector`, `EdgarCollector`.
- Produces: `COLLECTORS` becomes a five-collector tuple.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_run.py`:

```python
# Sources whose collectors are not built yet. GDELT is deferred from this plan
# run (rate-limit cooldown during fixture capture); the rest arrive in plan 2B.
DEFERRED_SOURCES = {"gdelt_doc", "gdelt_geo"}
# Signals with no aggregation at all yet. The GDELT signals are NOT listed here:
# task 1 already declared their aggregations, so they are produced — they simply
# stay empty until their collector is registered.
DEFERRED_SIGNALS = {"patents", "gh_repos_new", "gh_commits", "gh_stars_delta"}


def test_every_collector_has_a_unique_name_and_a_rate_limit():
    names = [collector.name for collector in run.COLLECTORS]
    assert len(names) == len(set(names))
    assert set(names) == {
        "arxiv", "hn", "federalregister", "usaspending", "edgar",
    }
    for collector in run.COLLECTORS:
        assert collector.rate_limit_seconds > 0


def test_every_aggregation_names_a_registered_or_knowingly_deferred_collector():
    """A signal whose source does not exist would silently never be written."""
    from observatory import normalize

    names = {collector.name for collector in run.COLLECTORS} | DEFERRED_SOURCES
    for aggregation in normalize.AGGREGATIONS:
        assert aggregation.source in names, aggregation.signal


def test_deferred_sources_are_really_absent():
    """Keeps the allowance above honest — it must shrink when GDELT lands."""
    names = {collector.name for collector in run.COLLECTORS}
    assert not (names & DEFERRED_SOURCES), (
        "a deferred source is now registered; remove it from DEFERRED_SOURCES"
    )


def test_every_stage_signal_is_produced_by_some_aggregation():
    """Catches a typo between metrics.SIGNALS_BY_STAGE and normalize.AGGREGATIONS."""
    from observatory import metrics, normalize

    produced = {aggregation.signal for aggregation in normalize.AGGREGATIONS}
    for signal in metrics.ALL_SIGNALS:
        if signal in DEFERRED_SIGNALS:
            continue
        assert signal in produced, f"{signal} has no aggregation"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_run.py -v`
Expected: the collector-name test fails — the tuple still holds three.

- [ ] **Step 3: Implement**

In `observatory/run.py`, import and register the two new collectors:

```python
from .collectors.arxiv import ArxivCollector
from .collectors.edgar import EdgarCollector
from .collectors.federalregister import FederalRegisterCollector
from .collectors.hn import HackerNewsCollector
from .collectors.usaspending import UsaspendingCollector

COLLECTORS = (
    ArxivCollector(),
    HackerNewsCollector(),
    FederalRegisterCollector(),
    UsaspendingCollector(),
    EdgarCollector(),
)
```

Do not import the GDELT collectors — they do not exist in the tree.

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: all pass, including the guardrail tests.

- [ ] **Step 5: Run it for real**

Run: `python -m observatory.run --week 2026-W33`

This hits five live APIs and will take several minutes — arXiv alone is rate-limited to one request every three seconds. That is normal, not a hang.

Report honestly what happened: the status of each of the five sources, the observation count per source, and the signal counts. **If a source fails, report the actual error rather than retrying until it looks clean.** A genuinely broken endpoint is useful information and the run isolates it by design. If a collector fails on its very first live contact, that is what this step exists to find — diagnose it, fix the collector, and say so in your report.

- [ ] **Step 6: Commit**

```bash
git add observatory/run.py tests/test_run.py
git commit -m "feat: register the four keyless collectors"
```

---

### Task 9: The Build Map

**Files:**
- Modify: `observatory/charts.py`, `observatory/render.py`, `observatory/templates/dashboard.html.j2`
- Test: `tests/test_charts.py`, `tests/test_render.py`

**Interfaces:**
- Consumes: `geo.CONUS_BOUNDS`, `charts.Point`, `store`.
- Produces: `charts.build_map(points: list[Point], width=720, height=420) -> str`; `render.build_map_points(conn, week) -> list[charts.Point]`; context key `build_map_svg`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_charts.py`:

```python
def test_build_map_returns_svg_with_a_circle_per_point():
    svg = charts.build_map([
        charts.Point(x=-111.66, y=34.27, label="Arizona", size=8.0),
        charts.Point(x=-75.53, y=42.95, label="New York", size=4.0),
    ])
    assert svg.startswith("<svg")
    assert svg.count("<circle") == 2


def test_build_map_places_west_left_of_east():
    """Longitude runs west-to-east, so a more negative longitude sits further left."""
    svg = charts.build_map([
        charts.Point(x=-124.0, y=45.0, label="west"),
        charts.Point(x=-70.0, y=45.0, label="east"),
    ])
    xs = [float(v) for v in re.findall(r'<circle cx="([-\d.]+)"', svg)]
    assert xs[0] < xs[1]


def test_build_map_places_north_above_south():
    svg = charts.build_map([
        charts.Point(x=-100.0, y=48.0, label="north"),
        charts.Point(x=-100.0, y=26.0, label="south"),
    ])
    ys = [float(v) for v in re.findall(r'<circle cy="([-\d.]+)"', svg)]
    assert ys[0] < ys[1]


def test_build_map_clamps_points_outside_the_continental_frame():
    svg = charts.build_map([charts.Point(x=-152.28, y=64.07, label="Alaska")])
    assert "<circle" in svg
    assert "nan" not in svg.lower()


def test_build_map_of_nothing_is_still_valid_svg():
    assert charts.build_map([]).startswith("<svg")


def test_build_map_escapes_labels():
    svg = charts.build_map([charts.Point(x=-100.0, y=40.0, label='<b>&"')])
    assert "&lt;b&gt;" in svg and "<b>" not in svg
```

Add `import re` to that test file if it is not already imported.

Append to `tests/test_render.py`:

```python
def test_build_map_points_come_from_located_observations(conn, watchlist):
    from observatory.matcher import Observation

    store.upsert_observations(conn, [
        Observation(source="usaspending", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="a1", doc_date="2026-08-12", title="Corridor award",
                    url="u", entity="ACME", entity_id=None, amount=5_000_000.0,
                    lat=34.27, lon=-111.66, matched_pattern="x", raw_ref=1),
        Observation(source="arxiv", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="a2", doc_date="2026-08-12", title="A paper",
                    url="u", entity=None, entity_id=None, amount=None,
                    lat=None, lon=None, matched_pattern="x", raw_ref=1),
    ])
    points = render.build_map_points(conn, "2026-W33")
    assert len(points) == 1
    assert points[0].y == 34.27 and points[0].x == -111.66
    assert "ACME" in points[0].label


def test_dashboard_renders_the_build_map_block(conn, watchlist, tmp_path):
    path = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html")
    html = path.read_text()
    assert "Build Map" in html
    assert "Arrives with the USAspending collector" not in html
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_charts.py tests/test_render.py -v`
Expected: the new tests fail — `charts.build_map` and `render.build_map_points` do not exist.

- [ ] **Step 3: Implement the chart**

Add `from . import geo` to the imports at the top of `observatory/charts.py` — `geo` imports nothing, so there is no cycle — then append:

```python
def build_map(points: list[Point], width: int = 720, height: int = 420) -> str:
    """A US map without a coastline.

    Drawing an accurate outline would mean vendoring geodata; instead each point
    is placed by an equirectangular projection over the continental frame and
    labelled, which answers the question the block asks — which places are
    getting new capability — without pretending to cartographic precision.
    """
    min_lat, max_lat, min_lon, max_lon = geo.CONUS_BOUNDS
    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" '
        f'xmlns="http://www.w3.org/2000/svg" role="img">',
        f'<rect x="{PADDING}" y="{PADDING}" width="{width - 2 * PADDING}" '
        f'height="{height - 2 * PADDING}" fill="#f7f8f9" stroke="{AXIS_COLOUR}" />',
    ]
    for point in points:
        longitude = min(max(point.x, min_lon), max_lon)
        latitude = min(max(point.y, min_lat), max_lat)
        cx = _scale(longitude, min_lon, max_lon, PADDING, width - PADDING)
        cy = _scale(latitude, min_lat, max_lat, height - PADDING, PADDING)
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{point.size:.1f}" '
            f'fill="{escape(point.colour, quote=True)}" fill-opacity="0.6" '
            f'stroke="{escape(point.colour, quote=True)}">'
            f"<title>{escape(point.label, quote=True)}</title></circle>"
        )
    parts.append("</svg>")
    return "".join(parts)
```

Note the axis convention this block deliberately breaks: everywhere else in this codebase `Point.x`/`Point.y` are abstract chart axes, but here `x` is longitude and `y` is latitude. The tests pin that.

- [ ] **Step 4: Implement the renderer**

Add to `observatory/render.py`:

```python
MAP_MIN_RADIUS = 3.0
MAP_MAX_RADIUS = 18.0


def build_map_points(conn, week: str) -> list[charts.Point]:
    rows = conn.execute(
        "SELECT tech_id, title, entity, amount, lat, lon FROM observations "
        "WHERE week = ? AND lat IS NOT NULL AND lon IS NOT NULL",
        (week,),
    ).fetchall()
    if not rows:
        return []
    amounts = [float(row["amount"] or 0) for row in rows]
    largest = max(amounts) or 1.0
    points = []
    for row, amount in zip(rows, amounts):
        share = (amount / largest) ** 0.5
        label = " · ".join(
            part for part in (row["entity"], row["title"], _money(amount)) if part
        )
        points.append(
            charts.Point(
                x=float(row["lon"]),
                y=float(row["lat"]),
                label=label,
                size=MAP_MIN_RADIUS + share * (MAP_MAX_RADIUS - MAP_MIN_RADIUS),
            )
        )
    return points


def _money(amount: float) -> str:
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:,.1f}M"
    if amount > 0:
        return f"${amount:,.0f}"
    return ""
```

Add `"build_map_svg": Markup(charts.build_map(build_map_points(conn, week)))` to the dictionary `build_context` returns.

- [ ] **Step 5: Update the template**

In `observatory/templates/dashboard.html.j2`, replace the Build Map placeholder paragraph with the chart and a caption:

```html
  <h2>Build Map</h2>
  <p class="sub">Federal award dollars and news-reported activity, by location.
     Dot size follows the award amount.</p>
  {{ build_map_svg }}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest -q`
Expected: all pass, including the existing "no external resources" test — the map adds no fetched resource.

- [ ] **Step 7: Commit**

```bash
git add observatory/charts.py observatory/render.py observatory/templates/dashboard.html.j2 tests/test_charts.py tests/test_render.py
git commit -m "feat: Build Map block"
```

---

### Task 10: Evidence drill-down

Every count on the dashboard should be traceable to the documents behind it. This is the spec's traceability promise, and the thing that makes an off-concept match visible instead of invisible.

**Files:**
- Create: `observatory/templates/evidence.html.j2`
- Modify: `observatory/render.py`, `observatory/templates/dashboard.html.j2`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `store.observations_for`, `matcher.Watchlist`.
- Produces: `render.evidence_context(conn, week, watchlist) -> dict`; `render.render_evidence(conn, week, watchlist, out_path=None) -> Path`. `render_dashboard` gains anchors linking each technology to its evidence entry.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_render.py`:

```python
def test_evidence_page_lists_every_observation_with_its_pattern(conn, watchlist, tmp_path):
    from observatory.matcher import Observation

    store.upsert_observations(conn, [
        Observation(source="arxiv", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="a1", doc_date="2026-08-12",
                    title="Fleet learning for driverless trucks",
                    url="https://arxiv.org/abs/1", entity=None, entity_id=None,
                    amount=None, lat=None, lon=None,
                    matched_pattern="driverless truck(s|ing)?", raw_ref=1),
    ])
    path = render.render_evidence(conn, "2026-W33", watchlist, tmp_path / "e.html")
    html = path.read_text()
    assert "Fleet learning for driverless trucks" in html
    assert "driverless truck(s|ing)?" in html
    assert "https://arxiv.org/abs/1" in html


def test_evidence_page_groups_by_technology_with_a_stable_anchor(conn, watchlist, tmp_path):
    from observatory.matcher import Observation

    store.upsert_observations(conn, [
        Observation(source="arxiv", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="a1", doc_date="2026-08-12", title="T", url="u",
                    entity=None, entity_id=None, amount=None, lat=None, lon=None,
                    matched_pattern="x", raw_ref=1),
    ])
    html = render.render_evidence(conn, "2026-W33", watchlist, tmp_path / "e.html").read_text()
    assert 'id="autonomous_trucking"' in html


def test_evidence_page_escapes_hostile_titles(conn, watchlist, tmp_path):
    from observatory.matcher import Observation

    store.upsert_observations(conn, [
        Observation(source="arxiv", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="a1", doc_date="2026-08-12",
                    title="<script>alert(1)</script>", url="u",
                    entity=None, entity_id=None, amount=None, lat=None, lon=None,
                    matched_pattern="x", raw_ref=1),
    ])
    html = render.render_evidence(conn, "2026-W33", watchlist, tmp_path / "e.html").read_text()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_evidence_page_has_no_external_resources(conn, watchlist, tmp_path):
    html = render.render_evidence(conn, "2026-W33", watchlist, tmp_path / "e.html").read_text()
    assert not re.findall(r'\b(?:src|href)\s*=\s*[\'"](?:https?:)?//[^\'"]*[\'"]', html)


def test_dashboard_links_movers_to_their_evidence(conn, watchlist, tmp_path):
    html = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html").read_text()
    assert "evidence.html#" in html
```

The last test asserts a link exists even when the Movers table is empty, so put the link on the warming-up footer entries as well as the Movers rows.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_render.py -v`
Expected: FAIL — `render.render_evidence` does not exist.

- [ ] **Step 3: Write the evidence template**

Create `observatory/templates/evidence.html.j2`:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Observatory evidence &middot; {{ week }}</title>
<style>
  :root { --ink: #1d2125; --muted: #6b7580; --rule: #e3e6e9; }
  body { margin: 0; background: #fff; color: var(--ink);
         font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }
  main { max-width: 1080px; margin: 0 auto; padding: 32px 24px 96px; }
  h1 { font-size: 24px; margin: 0 0 4px; }
  h2 { font-size: 16px; margin: 40px 0 10px; padding-bottom: 6px;
       border-bottom: 1px solid var(--rule); }
  .sub { color: var(--muted); font-size: 13px; margin: 0 0 24px; }
  table { border-collapse: collapse; width: 100%; font-size: 14px; }
  th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--rule);
           vertical-align: top; }
  th { font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em;
       color: var(--muted); font-weight: 600; }
  code { font-size: 12px; color: var(--muted); }
  .empty { color: var(--muted); font-style: italic; }
  a { color: #2b5f8a; }
</style>
</head>
<body>
<main>
  <h1>Evidence &middot; week {{ week }}</h1>
  <p class="sub">Every observation behind this week's counts, and the pattern that
     matched it. Lexicon v{{ lexicon_version }}.</p>

  {% for group in groups %}
    <h2 id="{{ group.tech_id }}">{{ group.name }} <span class="sub">({{ group.rows|length }})</span></h2>
    <table>
      <thead><tr><th>Date</th><th>Source</th><th>Document</th><th>Matched pattern</th></tr></thead>
      <tbody>
      {% for row in group.rows %}
        <tr>
          <td>{{ row.doc_date or '—' }}</td>
          <td>{{ row.source }}</td>
          <td>
            {% if row.url %}<a href="{{ row.url }}">{{ row.title or row.doc_id }}</a>
            {% else %}{{ row.title or row.doc_id }}{% endif %}
            {% if row.entity %}<br><span class="sub">{{ row.entity }}</span>{% endif %}
          </td>
          <td><code>{{ row.matched_pattern }}</code></td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  {% else %}
    <p class="empty">No observations recorded for this week.</p>
  {% endfor %}
</main>
</body>
</html>
```

Jinja2 autoescaping handles the hostile-title case; `row.url` is escaped as an attribute value by the same mechanism.

- [ ] **Step 4: Implement the renderer**

Add to `observatory/render.py`:

```python
def evidence_context(conn, week: str, watchlist) -> dict:
    names = {tech.id: tech.name for tech in watchlist.technologies}
    rows = conn.execute(
        "SELECT tech_id, source, doc_id, doc_date, title, url, entity, matched_pattern "
        "FROM observations WHERE week = ? ORDER BY tech_id, doc_date DESC",
        (week,),
    ).fetchall()
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["tech_id"], []).append(dict(row))
    return {
        "week": week,
        "lexicon_version": watchlist.version,
        "groups": [
            {"tech_id": tech_id, "name": names.get(tech_id, tech_id), "rows": group}
            for tech_id, group in sorted(grouped.items())
        ],
    }


def render_evidence(conn, week: str, watchlist, out_path: Path | None = None) -> Path:
    context = evidence_context(conn, week, watchlist)
    html = _environment().get_template("evidence.html.j2").render(**context)
    target = Path(out_path) if out_path else config.OUTPUT_DIR / f"evidence-{week}.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html)
    if out_path is None:
        (config.OUTPUT_DIR / "evidence.html").write_text(html)
    return target
```

Then call it from `render_dashboard` so one command produces both pages. Add this just before `render_dashboard` returns, guarded so an explicit `out_path` writes the evidence page beside the dashboard rather than into `output/`:

```python
    evidence_target = None if out_path is None else target.parent / "evidence.html"
    render_evidence(conn, week, watchlist, evidence_target)
```

- [ ] **Step 5: Link from the dashboard**

In `observatory/templates/dashboard.html.j2`, make the technology name in the Movers table a link, and do the same for the warming-up footer list. In `build_context`, add a `tech_id` key to each mover dictionary and change `warming_up` from a list of names to a list of `{"tech_id": ..., "name": ...}` dictionaries, updating the footer loop accordingly:

```html
        <td><a href="evidence.html#{{ mover.tech_id }}">{{ mover.name }}</a></td>
```

```html
    Warming up (fewer than 12 weeks of history, no scores yet):
    {% for tech in warming_up %}<a href="evidence.html#{{ tech.tech_id }}">{{ tech.name }}</a>{% if not loop.last %}, {% endif %}{% endfor %}
```

The existing `test_context_excludes_warming_up_technologies_from_movers` asserts `"Quiet tech" in context["warming_up"]`. That becomes a membership test over dictionaries — update it to check the names, and say so in your report:

```python
    assert "Quiet tech" in [tech["name"] for tech in context["warming_up"]]
```

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Regenerate both pages from the data already on disk**

Run: `python -m observatory.run --rebuild`

This replays every week's saved raw through the current code with no network. Open `output/latest.html`, click a technology name, and confirm you land on its evidence list.

- [ ] **Step 8: Update the README and commit**

Add the evidence page to the README's output description, then:

```bash
git add observatory/render.py observatory/templates tests/test_render.py README.md
git commit -m "feat: evidence drill-down page linked from the dashboard"
```

---

## Outcome

Eight of ten tasks completed; 212 tests pass. Tasks 3 and 4 (GDELT) were deferred — see below.

The final whole-branch review found two Critical defects that eight clean task reviews had
missed, both visible only from an end-to-end view. Recording them because the *shape* of the
mistake will recur:

1. **Observations were keyed to the document's own week, but signals were computed only for
   the run week.** Any document dated outside the run week was stored and never counted. With
   a 7-day lookback and sources whose document dates trail their index date, that was the
   majority case: week 2026-W32 held 9 real observations and zero signal rows, while the
   dashboard reported 1 filing for a week in which 7 were observed. A run now rescores and
   re-archives every week it wrote into.
2. **USAspending awards were keyed to `Start Date`** — the period-of-performance start, which
   routinely predates the query window by years. The captured fixture's awards derived weeks
   in 2024 from a 2026 query, so `fed_awards` and `fed_obligated` were structurally zero and
   the Build Map could never plot a single dot from live data. Fixed by filtering and reading
   the same date (`last_modified_date`).

Both produced a confidently wrong number rather than an error — the failure mode this project
is least able to notice on its own, and the one worth designing tests around.

## Carried forward

- **GDELT (tasks 3 and 4) is unbuilt.** GDELT rate-limited the project into an IP cooldown
  during fixture capture and was still refusing forty minutes later. Hand-writing a fixture was
  refused on principle. The full implementation for both collectors is in this document; redo
  the tasks as written, starting from a real capture, once GDELT is reachable. Note that its
  API asks for **one request every five seconds** and enforces it at the IP level — a retry
  loop is what caused the cooldown. Until then `normalize.AGGREGATIONS` declares two inert
  aggregations against `gdelt_doc`, guarded by `DEFERRED_SOURCES` in `tests/test_run.py`, and
  the Substance vs. Attention block's "attention" half is Hacker News alone.
- **`adoption_new` is hardcoded to `0`** in `metrics.compute_week`. It is written to
  `weekly_metrics` and read by nothing. Spec §7.4 defines it as CIKs appearing for the first
  time this week; the honest interim value is `None`.
- **`fed_obligated` sums `Award Amount`** — total award value, not obligated dollars as spec
  §7.1 names it. Sharpened by the `last_modified_date` keying: an old award touched
  administratively this week contributes its full value to this week's Investment stage.
  Either rename the signal or change what it sums.
- **Award-to-week attribution is sticky.** Dedup is `UNIQUE (source, doc_id, tech_id)` with no
  week, so an award is fixed to the first week it was observed. This is what prevents
  double-counting under the new date field, but it means `fed_awards` is not "awards active
  this week".
- **`weeks_swept_by` assumes `LOOKBACK_DAYS` is a multiple of 7.** At 7 it is exact. At any
  other value it would declare a source complete for a week the run only partly covered —
  reintroducing a fabricated count. No test pins the invariant.
- **Hole healing is data-dependent.** A swept week is recomputed only if the run wrote new rows
  into it, so a source that failed in week W and recovers in W+1 with genuinely zero documents
  for W leaves W's hole in place. Conservative rather than fabricating, but asymmetric.
- **`output/evidence.html` is orphaned** now that dashboards link `evidence-<week>.html`.
- **Swept-week run-log lines** record `scoring_sources` under the key `ok_sources`, so the field
  now means "sources counted" rather than "sources that ran".

## What this plan does not cover

- **Plan 2B** — GitHub and PatentsView collectors, feeding `patents`, `gh_repos_new`, `gh_commits`, and `gh_stars_delta`. Both need free API keys. Note for that plan: `http.fetch` treats only HTTP 200 as success, and GitHub's `/repos/{r}/stats` endpoints return **202** while computing statistics — widen the accepted range or handle 202 explicitly there.
- **Plan 2C** — `discover.py` rising-term extraction into `candidate_terms`, the offline `lexicon.py` authoring CLI, and backfill across the trailing 52 weeks.
- **Docs reconciliation** — the design spec's §6 schema listing predates the `source_runs` table, and the core-pipeline plan's code blocks still show the removed `sources_with_raw`. The shipped code is the authority on both.
