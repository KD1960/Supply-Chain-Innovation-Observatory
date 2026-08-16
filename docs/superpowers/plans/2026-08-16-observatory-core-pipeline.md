# Supply Chain Innovation Observatory — Core Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deterministic weekly pipeline end to end — fetch, store, match, score, render — producing a real dashboard from three keyless public sources.

**Architecture:** Collectors fetch public data and write raw text to disk before anything is parsed. A deterministic regex matcher turns raw documents into observation rows in SQLite. Observations aggregate into weekly signals, signals into z-scores and four headline metrics, and metrics render into one self-contained HTML file. Every stage reads only the stage above it, so each is testable with fixture data alone.

**Tech Stack:** Python 3.11+, `requests`, `PyYAML`, `Jinja2`, `pytest`. Standard-library `sqlite3`, `re`, `xml.etree`, `statistics`. No numpy, no pandas.

**Spec:** `docs/superpowers/specs/2026-08-16-supply-chain-innovation-observatory-design.md`

**Scope of this plan:** Spec build-order phases 1–4, plus the three keyless collectors (arXiv, Hacker News, Federal Register) and a first working dashboard. A second plan covers the remaining six collectors, the Build Map, evidence drill-down, rising-term discovery, and the offline `lexicon` tool. This split is deliberate: collector code for GitHub, EDGAR, USAspending, and PatentsView is much easier to write correctly once real response shapes from the first three are in hand, and this plan already produces working software on its own.

## Global Constraints

- Python 3.11 or newer. `datetime.date.fromisocalendar` and `X | None` type syntax are used throughout.
- Dependencies limited to `requests`, `PyYAML`, `Jinja2`, `pytest`. No numpy, no pandas — the statistics are small and must be explicit.
- **No LLM client may be importable from the weekly run.** Task 14 enforces this with a test. Nothing in `observatory/` except a future `lexicon.py` may import `anthropic`.
- **No network in tests.** Every collector test runs against a saved fixture file in `tests/fixtures/`.
- **Raw before parse.** A collector writes the raw response body to `data/raw/<week>/<source>/` before any parsing happens. A parser bug must never cost a re-fetch.
- **A missing week is not a zero week.** When a source fails, its signals are left absent and carried forward at metric time. Writing 0 would fabricate a decline.
- Minimum history for any z-score, momentum, SAI, or LFI value is **12 weeks**. Below that the value is `None` and the UI shows "warming up".
- Every HTTP request sends a `User-Agent` of the form
  `SupplyChainObservatory/1.0 (<SEC_CONTACT_EMAIL>)`. SEC requires it; the others tolerate it.
- ISO week strings are always the format `YYYY-Www` with a zero-padded two-digit week, e.g. `2026-W33`.
- Commit after every task. Conventional-commit prefixes (`feat:`, `test:`, `chore:`).

---

## File Structure

| Path | Responsibility |
|---|---|
| `observatory/config.py` | Paths, env loading, ISO-week arithmetic |
| `observatory/http.py` | Shared session, retry/backoff, per-source rate limiting |
| `observatory/store.py` | SQLite schema and all queries |
| `observatory/matcher.py` | Watchlist loading, pattern compilation, document → observations |
| `observatory/collectors/base.py` | `Document`, `RawPage`, `BaseCollector`, raw read/write |
| `observatory/collectors/arxiv.py` | arXiv Atom API |
| `observatory/collectors/hn.py` | Hacker News Algolia API |
| `observatory/collectors/federalregister.py` | Federal Register documents API |
| `observatory/normalize.py` | Observations → `weekly_signals` |
| `observatory/metrics.py` | z-scores, stage scores, momentum, SAI, LFI |
| `observatory/charts.py` | Inline SVG chart generation |
| `observatory/render.py` | Jinja2 → `dashboard.html` |
| `observatory/templates/dashboard.html.j2` | The dashboard markup |
| `observatory/run.py` | Orchestration and CLI |
| `watchlist.yaml` | The 32 tracked technologies |
| `tests/` | Unit tests and saved fixtures |

---

### Task 1: Project skeleton, config, and ISO-week arithmetic

**Files:**
- Create: `pyproject.toml`, `.env.example`, `observatory/__init__.py`, `observatory/config.py`, `observatory/collectors/__init__.py`, `tests/__init__.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ROOT`, `DATA_DIR`, `RAW_DIR`, `OUTPUT_DIR`, `DB_PATH`, `WATCHLIST_PATH`, `RUN_LOG_PATH` (all `pathlib.Path`); constants `MIN_HISTORY_WEEKS = 12`, `TRAILING_WEEKS = 52`; `iso_week(d: date) -> str`; `week_bounds(week: str) -> tuple[date, date]`; `week_offset(week: str, delta: int) -> str`; `week_range(start: str, end: str) -> list[str]`; `trailing_weeks(week: str, count: int) -> list[str]`; `current_week(today=None) -> str`; `require_env(name: str) -> str`; `user_agent() -> str`; `load_dotenv(path=None) -> None`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
import datetime as dt

import pytest

from observatory import config


def test_iso_week_formats_with_padded_week():
    assert config.iso_week(dt.date(2026, 8, 16)) == "2026-W33"
    assert config.iso_week(dt.date(2026, 1, 1)) == "2026-W01"


def test_week_bounds_returns_monday_through_sunday():
    start, end = config.week_bounds("2026-W33")
    assert start == dt.date(2026, 8, 10)
    assert end == dt.date(2026, 8, 16)
    assert start.weekday() == 0
    assert end.weekday() == 6


def test_week_offset_crosses_the_year_boundary():
    assert config.week_offset("2026-W01", -1) == "2025-W52"
    assert config.week_offset("2025-W52", 1) == "2026-W01"
    assert config.week_offset("2026-W33", -12) == "2026-W21"


def test_week_range_is_inclusive_and_ordered():
    weeks = config.week_range("2026-W31", "2026-W34")
    assert weeks == ["2026-W31", "2026-W32", "2026-W33", "2026-W34"]


def test_require_env_names_the_missing_variable(monkeypatch):
    monkeypatch.delenv("SEC_CONTACT_EMAIL", raising=False)
    with pytest.raises(RuntimeError) as excinfo:
        config.require_env("SEC_CONTACT_EMAIL")
    assert "SEC_CONTACT_EMAIL" in str(excinfo.value)


def test_user_agent_includes_contact_email(monkeypatch):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "someone@example.edu")
    assert "someone@example.edu" in config.user_agent()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'observatory'`

- [ ] **Step 3: Write the implementation**

Create `pyproject.toml`:

```toml
[project]
name = "supply-chain-observatory"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["requests>=2.31", "PyYAML>=6.0", "Jinja2>=3.1"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.setuptools.packages.find]
include = ["observatory*"]
```

Create `.env.example`:

```
# Required by every run: SEC and other agencies want a contact address in the User-Agent.
SEC_CONTACT_EMAIL=you@example.edu

# Added in the second plan, not needed yet.
# GITHUB_TOKEN=
# PATENTSVIEW_API_KEY=
```

Create empty `observatory/__init__.py`, `observatory/collectors/__init__.py`, and `tests/__init__.py`.

Create `observatory/config.py`:

```python
"""Paths, environment, and ISO-week arithmetic.

Every week in this system is an ISO week string like "2026-W33". Weeks run
Monday through Sunday. All date maths goes through this module so that week
boundaries are defined in exactly one place.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
OUTPUT_DIR = ROOT / "output"
DB_PATH = DATA_DIR / "observatory.db"
WATCHLIST_PATH = ROOT / "watchlist.yaml"
RUN_LOG_PATH = DATA_DIR / "run_log.jsonl"

MIN_HISTORY_WEEKS = 12
TRAILING_WEEKS = 52


def iso_week(d: dt.date) -> str:
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def week_bounds(week: str) -> tuple[dt.date, dt.date]:
    year_part, week_part = week.split("-W")
    monday = dt.date.fromisocalendar(int(year_part), int(week_part), 1)
    return monday, monday + dt.timedelta(days=6)


def week_offset(week: str, delta: int) -> str:
    monday, _ = week_bounds(week)
    return iso_week(monday + dt.timedelta(weeks=delta))


def week_range(start: str, end: str) -> list[str]:
    weeks = [start]
    while weeks[-1] != end:
        weeks.append(week_offset(weeks[-1], 1))
        if len(weeks) > 5000:
            raise ValueError(f"week_range({start!r}, {end!r}) did not terminate")
    return weeks


def trailing_weeks(week: str, count: int) -> list[str]:
    """The `count` weeks ending at `week`, oldest first."""
    return week_range(week_offset(week, -(count - 1)), week)


def current_week(today: dt.date | None = None) -> str:
    return iso_week(today or dt.date.today())


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


def user_agent() -> str:
    return f"SupplyChainObservatory/1.0 ({require_env('SEC_CONTACT_EMAIL')})"


def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env loader. Existing environment variables always win."""
    env_path = path or (ROOT / ".env")
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pip install -e ".[dev]" && python -m pytest tests/test_config.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .env.example observatory tests
git commit -m "feat: project skeleton with ISO-week arithmetic and env config"
```

---

### Task 2: HTTP client with retry, backoff, and rate limiting

**Files:**
- Create: `observatory/http.py`
- Test: `tests/test_http.py`

**Interfaces:**
- Consumes: `config.user_agent`.
- Produces: `RateLimiter(min_interval_seconds: float, sleep_fn=time.sleep)` with `.wait()`; `make_session() -> requests.Session`; `fetch(session, url, *, params=None, headers=None, limiter=None, retries=3, sleep_fn=time.sleep) -> Response`, where `Response` is a dataclass with fields `url: str`, `status: int`, `text: str`, `content_type: str`. `fetch` raises `HttpError` on unrecoverable failure.

- [ ] **Step 1: Write the failing test**

Create `tests/test_http.py`:

```python
import pytest

from observatory import http


class FakeResponse:
    def __init__(self, status_code, text="{}", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {"Content-Type": "application/json"}
        self.url = "https://example.test/x"


class FakeSession:
    """Returns queued responses in order and records every call."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        return self._responses.pop(0)


def test_fetch_returns_body_on_success():
    session = FakeSession([FakeResponse(200, '{"ok": true}')])
    result = http.fetch(session, "https://example.test/x")
    assert result.status == 200
    assert result.text == '{"ok": true}'


def test_fetch_retries_on_429_then_succeeds():
    slept = []
    session = FakeSession([FakeResponse(429), FakeResponse(200, "fine")])
    result = http.fetch(session, "https://example.test/x", sleep_fn=slept.append)
    assert result.text == "fine"
    assert len(session.calls) == 2
    assert slept == [1.0]


def test_fetch_backs_off_exponentially_on_server_errors():
    slept = []
    session = FakeSession([FakeResponse(500), FakeResponse(503), FakeResponse(200, "ok")])
    http.fetch(session, "https://example.test/x", sleep_fn=slept.append)
    assert slept == [1.0, 2.0]


def test_fetch_honours_retry_after_header():
    slept = []
    session = FakeSession(
        [FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(200, "ok")]
    )
    http.fetch(session, "https://example.test/x", sleep_fn=slept.append)
    assert slept == [7.0]


def test_fetch_gives_up_after_retry_budget():
    session = FakeSession([FakeResponse(500)] * 4)
    with pytest.raises(http.HttpError) as excinfo:
        http.fetch(session, "https://example.test/x", retries=3, sleep_fn=lambda _: None)
    assert "500" in str(excinfo.value)


def test_fetch_fails_fast_on_client_error():
    session = FakeSession([FakeResponse(404)])
    with pytest.raises(http.HttpError):
        http.fetch(session, "https://example.test/x", sleep_fn=lambda _: None)
    assert len(session.calls) == 1


def test_rate_limiter_sleeps_the_remaining_interval():
    now = [100.0]
    slept = []
    limiter = http.RateLimiter(2.0, sleep_fn=slept.append, clock_fn=lambda: now[0])
    limiter.wait()
    now[0] = 100.5
    limiter.wait()
    assert slept == [1.5]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_http.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'observatory.http'`

- [ ] **Step 3: Write the implementation**

Create `observatory/http.py`:

```python
"""One shared HTTP path for every collector: same User-Agent, same retry rules,
same rate limiting. Collectors never call requests directly."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

from . import config

TIMEOUT_SECONDS = 60
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class HttpError(RuntimeError):
    pass


@dataclass(frozen=True)
class Response:
    url: str
    status: int
    text: str
    content_type: str


class RateLimiter:
    """Enforces a minimum gap between requests to one host."""

    def __init__(
        self,
        min_interval_seconds: float,
        sleep_fn: Callable[[float], Any] = time.sleep,
        clock_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.min_interval = min_interval_seconds
        self._sleep = sleep_fn
        self._clock = clock_fn
        self._last: float | None = None

    def wait(self) -> None:
        now = self._clock()
        if self._last is not None:
            remaining = self.min_interval - (now - self._last)
            if remaining > 0:
                self._sleep(remaining)
        self._last = self._clock()


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = config.user_agent()
    session.headers["Accept-Encoding"] = "gzip, deflate"
    return session


def fetch(
    session: Any,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    limiter: RateLimiter | None = None,
    retries: int = 3,
    sleep_fn: Callable[[float], Any] = time.sleep,
) -> Response:
    last_status = None
    for attempt in range(retries + 1):
        if limiter is not None:
            limiter.wait()
        raw = session.get(url, params=params, headers=headers, timeout=TIMEOUT_SECONDS)
        last_status = raw.status_code
        if raw.status_code == 200:
            return Response(
                url=url,
                status=raw.status_code,
                text=raw.text,
                content_type=raw.headers.get("Content-Type", ""),
            )
        if raw.status_code not in RETRYABLE_STATUSES:
            raise HttpError(f"GET {url} failed with status {raw.status_code}")
        if attempt == retries:
            break
        sleep_fn(_backoff_seconds(raw, attempt))
    raise HttpError(f"GET {url} still failing with status {last_status} after {retries} retries")


def _backoff_seconds(raw: Any, attempt: int) -> float:
    retry_after = raw.headers.get("Retry-After") if hasattr(raw, "headers") else None
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return float(2**attempt)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_http.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add observatory/http.py tests/test_http.py
git commit -m "feat: shared HTTP client with backoff and rate limiting"
```

---

### Task 3: SQLite store

**Files:**
- Create: `observatory/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: `config.DB_PATH`.
- Produces: `connect(path) -> sqlite3.Connection`; `init_schema(conn)`; `record_raw(conn, source, week, url, http_status, path) -> int`; `upsert_observations(conn, rows) -> int`; `set_signal(conn, tech_id, week, signal, value)`; `get_signal(conn, tech_id, week, signal) -> float | None`; `signal_series(conn, tech_id, signal, weeks) -> list[float | None]`; `set_source_status(conn, name, week, status, note)`; `source_statuses(conn) -> list[dict]`; `upsert_metrics(conn, row: dict)`; `metrics_for_week(conn, week) -> list[dict]`. `upsert_observations` takes any iterable of `matcher.Observation` and ignores duplicates on `(source, doc_id, tech_id)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_store.py`:

```python
import pytest

from observatory import store
from observatory.matcher import Observation


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def observation(**overrides):
    base = dict(
        source="arxiv",
        week="2026-W33",
        tech_id="autonomous_trucking",
        doc_id="arxiv:2608.00001",
        doc_date="2026-08-12",
        title="A paper about autonomous trucking",
        url="https://arxiv.org/abs/2608.00001",
        entity=None,
        entity_id=None,
        amount=None,
        lat=None,
        lon=None,
        matched_pattern="autonomous truck",
        raw_ref=1,
    )
    base.update(overrides)
    return Observation(**base)


def test_init_schema_is_idempotent(conn):
    store.init_schema(conn)
    store.init_schema(conn)
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"sources", "raw_fetch", "observations", "weekly_signals",
            "weekly_metrics", "candidate_terms"} <= tables


def test_upsert_observations_ignores_duplicates(conn):
    assert store.upsert_observations(conn, [observation()]) == 1
    assert store.upsert_observations(conn, [observation()]) == 0
    count = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert count == 1


def test_same_document_can_match_two_technologies(conn):
    store.upsert_observations(
        conn,
        [observation(), observation(tech_id="warehouse_robotics")],
    )
    count = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert count == 2


def test_signal_series_returns_none_for_missing_weeks(conn):
    store.set_signal(conn, "autonomous_trucking", "2026-W31", "arxiv_papers", 4.0)
    store.set_signal(conn, "autonomous_trucking", "2026-W33", "arxiv_papers", 6.0)
    series = store.signal_series(
        conn, "autonomous_trucking", "arxiv_papers",
        ["2026-W31", "2026-W32", "2026-W33"],
    )
    assert series == [4.0, None, 6.0]


def test_set_signal_overwrites_on_rerun(conn):
    store.set_signal(conn, "t", "2026-W33", "arxiv_papers", 1.0)
    store.set_signal(conn, "t", "2026-W33", "arxiv_papers", 9.0)
    assert store.get_signal(conn, "t", "2026-W33", "arxiv_papers") == 9.0


def test_source_status_round_trips(conn):
    store.set_source_status(conn, "arxiv", "2026-W33", "ok", "")
    store.set_source_status(conn, "hn", "2026-W33", "failed", "timeout")
    statuses = {row["name"]: row for row in store.source_statuses(conn)}
    assert statuses["arxiv"]["status"] == "ok"
    assert statuses["hn"]["note"] == "timeout"


def test_metrics_round_trip(conn):
    store.upsert_metrics(conn, {
        "tech_id": "autonomous_trucking", "week": "2026-W33",
        "momentum": 1.5, "sai": -0.2, "lfi": 0.3,
        "adoption": 12, "adoption_new": 2,
        "stage_idea": 0.1, "stage_experiment": 0.2, "stage_investment": 0.3,
        "stage_deployment": 0.4, "stage_diffusion": 0.5, "position": 3.2,
        "lexicon_version": 1,
    })
    rows = store.metrics_for_week(conn, "2026-W33")
    assert len(rows) == 1
    assert rows[0]["momentum"] == 1.5
    assert rows[0]["lexicon_version"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'observatory.store'`

- [ ] **Step 3: Write the implementation**

Create `observatory/store.py`:

```python
"""SQLite persistence. The database is a derived artifact: everything in it can
be rebuilt from the raw files on disk, so the schema is free to change."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    name TEXT PRIMARY KEY,
    last_run_week TEXT,
    status TEXT,
    note TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS raw_fetch (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    week TEXT NOT NULL,
    url TEXT NOT NULL,
    http_status INTEGER,
    fetched_at TEXT,
    path TEXT
);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    week TEXT NOT NULL,
    tech_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    doc_date TEXT,
    title TEXT,
    url TEXT,
    entity TEXT,
    entity_id TEXT,
    amount REAL,
    lat REAL,
    lon REAL,
    matched_pattern TEXT,
    raw_ref INTEGER,
    UNIQUE (source, doc_id, tech_id)
);

CREATE INDEX IF NOT EXISTS observations_week_tech
    ON observations (week, tech_id);

CREATE TABLE IF NOT EXISTS weekly_signals (
    tech_id TEXT NOT NULL,
    week TEXT NOT NULL,
    signal TEXT NOT NULL,
    value REAL,
    PRIMARY KEY (tech_id, week, signal)
);

CREATE TABLE IF NOT EXISTS weekly_metrics (
    tech_id TEXT NOT NULL,
    week TEXT NOT NULL,
    momentum REAL,
    sai REAL,
    lfi REAL,
    adoption INTEGER,
    adoption_new INTEGER,
    stage_idea REAL,
    stage_experiment REAL,
    stage_investment REAL,
    stage_deployment REAL,
    stage_diffusion REAL,
    position REAL,
    lexicon_version INTEGER,
    PRIMARY KEY (tech_id, week)
);

CREATE TABLE IF NOT EXISTS candidate_terms (
    term TEXT NOT NULL,
    week TEXT NOT NULL,
    count INTEGER,
    baseline REAL,
    ratio REAL,
    status TEXT,
    PRIMARY KEY (term, week)
);
"""

METRIC_COLUMNS = [
    "tech_id", "week", "momentum", "sai", "lfi", "adoption", "adoption_new",
    "stage_idea", "stage_experiment", "stage_investment", "stage_deployment",
    "stage_diffusion", "position", "lexicon_version",
]


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    target = str(path or config.DB_PATH)
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def record_raw(conn, source: str, week: str, url: str, http_status: int, path: str) -> int:
    cursor = conn.execute(
        "INSERT INTO raw_fetch (source, week, url, http_status, fetched_at, path) "
        "VALUES (?, ?, ?, ?, datetime('now'), ?)",
        (source, week, url, http_status, path),
    )
    conn.commit()
    return int(cursor.lastrowid)


def upsert_observations(conn, rows: Iterable[Any]) -> int:
    inserted = 0
    for row in rows:
        data = asdict(row)
        cursor = conn.execute(
            "INSERT OR IGNORE INTO observations "
            "(source, week, tech_id, doc_id, doc_date, title, url, entity, "
            " entity_id, amount, lat, lon, matched_pattern, raw_ref) "
            "VALUES (:source, :week, :tech_id, :doc_id, :doc_date, :title, :url, "
            " :entity, :entity_id, :amount, :lat, :lon, :matched_pattern, :raw_ref)",
            data,
        )
        inserted += cursor.rowcount
    conn.commit()
    return inserted


def set_signal(conn, tech_id: str, week: str, signal: str, value: float) -> None:
    conn.execute(
        "INSERT INTO weekly_signals (tech_id, week, signal, value) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (tech_id, week, signal) DO UPDATE SET value = excluded.value",
        (tech_id, week, signal, value),
    )
    conn.commit()


def get_signal(conn, tech_id: str, week: str, signal: str) -> float | None:
    row = conn.execute(
        "SELECT value FROM weekly_signals WHERE tech_id = ? AND week = ? AND signal = ?",
        (tech_id, week, signal),
    ).fetchone()
    return None if row is None else row["value"]


def signal_series(conn, tech_id: str, signal: str, weeks: list[str]) -> list[float | None]:
    rows = conn.execute(
        "SELECT week, value FROM weekly_signals WHERE tech_id = ? AND signal = ?",
        (tech_id, signal),
    ).fetchall()
    by_week = {row["week"]: row["value"] for row in rows}
    return [by_week.get(week) for week in weeks]


def set_source_status(conn, name: str, week: str, status: str, note: str = "") -> None:
    conn.execute(
        "INSERT INTO sources (name, last_run_week, status, note, updated_at) "
        "VALUES (?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT (name) DO UPDATE SET last_run_week = excluded.last_run_week, "
        "status = excluded.status, note = excluded.note, updated_at = excluded.updated_at",
        (name, week, status, note),
    )
    conn.commit()


def source_statuses(conn) -> list[dict]:
    return [dict(row) for row in conn.execute("SELECT * FROM sources ORDER BY name")]


def upsert_metrics(conn, row: dict) -> None:
    placeholders = ", ".join(f":{column}" for column in METRIC_COLUMNS)
    updates = ", ".join(
        f"{column} = excluded.{column}"
        for column in METRIC_COLUMNS
        if column not in ("tech_id", "week")
    )
    conn.execute(
        f"INSERT INTO weekly_metrics ({', '.join(METRIC_COLUMNS)}) VALUES ({placeholders}) "
        f"ON CONFLICT (tech_id, week) DO UPDATE SET {updates}",
        {column: row.get(column) for column in METRIC_COLUMNS},
    )
    conn.commit()


def metrics_for_week(conn, week: str) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM weekly_metrics WHERE week = ? ORDER BY tech_id", (week,)
        )
    ]


def observations_for(conn, week: str, tech_id: str, source: str | None = None) -> list[dict]:
    query = "SELECT * FROM observations WHERE week = ? AND tech_id = ?"
    params: list[Any] = [week, tech_id]
    if source is not None:
        query += " AND source = ?"
        params.append(source)
    return [dict(row) for row in conn.execute(query + " ORDER BY doc_date DESC", params)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_store.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add observatory/store.py tests/test_store.py
git commit -m "feat: SQLite store for observations, signals, and metrics"
```

---

### Task 4: Watchlist and deterministic term matcher

**Files:**
- Create: `watchlist.yaml`, `observatory/matcher.py`
- Test: `tests/test_matcher.py`

**Interfaces:**
- Consumes: `config.WATCHLIST_PATH`, `collectors.base.Document` (defined in Task 5 — this task defines `Observation` and takes a duck-typed document object with `doc_id`, `date`, `title`, `text`, `url`, `entity`, `entity_id`, `amount`, `lat`, `lon`).
- Produces: `Technology` and `Watchlist` dataclasses; `Observation` dataclass with fields in the exact order `source, week, tech_id, doc_id, doc_date, title, url, entity, entity_id, amount, lat, lon, matched_pattern, raw_ref`; `load_watchlist(path=None) -> Watchlist`; `Watchlist.active` property; `Watchlist.match(text) -> list[tuple[str, str]]` returning `(tech_id, matched_pattern)`; `observations_for_document(watchlist, document, source, week, raw_ref) -> list[Observation]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_matcher.py`:

```python
import textwrap

import pytest

from observatory import matcher


@pytest.fixture()
def watchlist(tmp_path):
    path = tmp_path / "watchlist.yaml"
    path.write_text(textwrap.dedent("""
        lexicon_version: 1
        technologies:
          - id: autonomous_trucking
            name: Autonomous trucking
            family: vehicles
            include:
              - "autonomous truck(s|ing)?"
              - "driverless truck"
            exclude:
              - "autonomous trucking bill"
            status: active
            added_week: 2026-W33
            patterns_changed_week: 2026-W33
          - id: warehouse_robotics
            name: Warehouse robotics
            family: automation
            include:
              - "warehouse robot(s|ics)?"
            exclude: []
            status: active
            added_week: 2026-W33
            patterns_changed_week: 2026-W33
          - id: retired_thing
            name: Retired thing
            family: automation
            include:
              - "retired thing"
            exclude: []
            status: retired
            added_week: 2026-W33
            patterns_changed_week: 2026-W33
    """))
    return matcher.load_watchlist(path)


class FakeDocument:
    def __init__(self, title, text=""):
        self.doc_id = "doc-1"
        self.date = "2026-08-12"
        self.title = title
        self.text = text
        self.url = "https://example.test/doc-1"
        self.entity = None
        self.entity_id = None
        self.amount = None
        self.lat = None
        self.lon = None


def test_load_watchlist_reads_version_and_active_entries(watchlist):
    assert watchlist.version == 1
    assert [tech.id for tech in watchlist.active] == [
        "autonomous_trucking", "warehouse_robotics"
    ]


def test_include_pattern_matches_case_insensitively(watchlist):
    assert watchlist.match("Autonomous Trucking pilot expands") == [
        ("autonomous_trucking", "autonomous truck(s|ing)?")
    ]


def test_exclude_pattern_vetoes_the_document(watchlist):
    assert watchlist.match("The autonomous trucking bill passed the senate") == []


def test_word_boundaries_prevent_substring_matches(watchlist):
    assert watchlist.match("semiautonomous truckload brokerage") == []


def test_one_document_can_match_two_technologies(watchlist):
    hits = watchlist.match("Warehouse robots meet driverless truck yards")
    assert sorted(tech_id for tech_id, _ in hits) == [
        "autonomous_trucking", "warehouse_robotics"
    ]


def test_a_technology_matches_at_most_once_per_document(watchlist):
    hits = watchlist.match("autonomous truck and autonomous trucking and driverless truck")
    assert len(hits) == 1


def test_retired_technologies_never_match(watchlist):
    assert watchlist.match("a retired thing appeared") == []


def test_observations_carry_document_fields_and_matched_pattern(watchlist):
    document = FakeDocument("Warehouse robotics rollout")
    rows = matcher.observations_for_document(
        watchlist, document, source="arxiv", week="2026-W33", raw_ref=7
    )
    assert len(rows) == 1
    observation = rows[0]
    assert observation.tech_id == "warehouse_robotics"
    assert observation.source == "arxiv"
    assert observation.week == "2026-W33"
    assert observation.doc_date == "2026-08-12"
    assert observation.url == "https://example.test/doc-1"
    assert observation.matched_pattern == "warehouse robot(s|ics)?"
    assert observation.raw_ref == 7


def test_matching_searches_title_and_body(watchlist):
    document = FakeDocument("An unrelated title", "buried mention of driverless truck fleets")
    rows = matcher.observations_for_document(
        watchlist, document, source="arxiv", week="2026-W33", raw_ref=1
    )
    assert [row.tech_id for row in rows] == ["autonomous_trucking"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_matcher.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'observatory.matcher'`

- [ ] **Step 3: Write the implementation**

Create `observatory/matcher.py`:

```python
"""Deterministic term matching.

This module is the reason the pipeline is reproducible. No model, no scoring,
no randomness: a document either matches a compiled pattern or it does not, and
the pattern that fired is recorded on every observation so any number on the
dashboard can be traced back to its evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import config


@dataclass(frozen=True)
class Observation:
    source: str
    week: str
    tech_id: str
    doc_id: str
    doc_date: str | None
    title: str | None
    url: str | None
    entity: str | None
    entity_id: str | None
    amount: float | None
    lat: float | None
    lon: float | None
    matched_pattern: str
    raw_ref: int | None


@dataclass(frozen=True)
class Technology:
    id: str
    name: str
    family: str
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    status: str
    added_week: str
    patterns_changed_week: str
    include_res: tuple[re.Pattern, ...] = field(repr=False, default=())
    exclude_res: tuple[re.Pattern, ...] = field(repr=False, default=())


@dataclass(frozen=True)
class Watchlist:
    version: int
    technologies: tuple[Technology, ...]

    @property
    def active(self) -> tuple[Technology, ...]:
        return tuple(tech for tech in self.technologies if tech.status == "active")

    def by_id(self, tech_id: str) -> Technology:
        for tech in self.technologies:
            if tech.id == tech_id:
                return tech
        raise KeyError(tech_id)

    def match(self, text: str) -> list[tuple[str, str]]:
        """Return one (tech_id, matched_pattern) per matching active technology."""
        hits: list[tuple[str, str]] = []
        for tech in self.active:
            if any(pattern.search(text) for pattern in tech.exclude_res):
                continue
            for source_pattern, compiled in zip(tech.include, tech.include_res):
                if compiled.search(text):
                    hits.append((tech.id, source_pattern))
                    break
        return hits


def compile_pattern(pattern: str) -> re.Pattern:
    return re.compile(rf"\b(?:{pattern})\b", re.IGNORECASE)


def load_watchlist(path: str | Path | None = None) -> Watchlist:
    raw = yaml.safe_load(Path(path or config.WATCHLIST_PATH).read_text())
    technologies = []
    for entry in raw["technologies"]:
        include = tuple(entry.get("include", ()))
        exclude = tuple(entry.get("exclude", ()) or ())
        technologies.append(
            Technology(
                id=entry["id"],
                name=entry["name"],
                family=entry["family"],
                include=include,
                exclude=exclude,
                status=entry.get("status", "active"),
                added_week=entry["added_week"],
                patterns_changed_week=entry.get("patterns_changed_week", entry["added_week"]),
                include_res=tuple(compile_pattern(p) for p in include),
                exclude_res=tuple(compile_pattern(p) for p in exclude),
            )
        )
    return Watchlist(version=int(raw["lexicon_version"]), technologies=tuple(technologies))


def observations_for_document(
    watchlist: Watchlist, document, source: str, week: str, raw_ref: int | None
) -> list[Observation]:
    haystack = f"{document.title or ''}\n{document.text or ''}"
    return [
        Observation(
            source=source,
            week=week,
            tech_id=tech_id,
            doc_id=document.doc_id,
            doc_date=document.date,
            title=document.title,
            url=document.url,
            entity=document.entity,
            entity_id=document.entity_id,
            amount=document.amount,
            lat=document.lat,
            lon=document.lon,
            matched_pattern=pattern,
            raw_ref=raw_ref,
        )
        for tech_id, pattern in watchlist.match(haystack)
    ]
```

- [ ] **Step 4: Write the real watchlist**

Create `watchlist.yaml`. These patterns are a deliberate first cut — narrow and precise, so early weeks under-count rather than over-count. The second plan's `lexicon propose --all` widens them with review.

```yaml
lexicon_version: 1
technologies:
  # --- Automation & robotics -------------------------------------------------
  - {id: warehouse_robotics, name: Warehouse robotics, family: automation,
     include: ["warehouse robot(s|ics)?", "autonomous mobile robot(s)?", "\\bAMRs?\\b",
               "automated storage and retrieval", "\\bAS/RS\\b"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: piece_picking, name: Piece-picking robotics, family: automation,
     include: ["piece[- ]picking", "robotic (item |piece )?picking", "bin picking"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: humanoid_logistics, name: Humanoid robots in logistics, family: automation,
     include: ["humanoid robot(s)?", "general[- ]purpose humanoid"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: autonomous_yard, name: Autonomous yard trucks, family: automation,
     include: ["autonomous yard (truck|tractor|spotter)(s)?", "yard automation"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: port_automation, name: Port and terminal automation, family: automation,
     include: ["automated (container )?terminal(s)?", "port automation",
               "automated stacking crane(s)?", "\\bAGVs? at (the )?port"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: sidewalk_delivery_robots, name: Last-mile delivery robots, family: automation,
     include: ["sidewalk (delivery )?robot(s)?", "last[- ]mile robot(s)?",
               "delivery robot(s)?"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: delivery_drones, name: Delivery drones, family: automation,
     include: ["delivery drone(s)?", "drone delivery", "\\bBVLOS\\b"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}

  # --- Vehicles & energy -----------------------------------------------------
  - {id: autonomous_trucking, name: Autonomous trucking, family: vehicles,
     include: ["autonomous truck(s|ing)?", "driverless truck(s|ing)?",
               "self[- ]driving (truck|freight)"],
     exclude: ["autonomous trucking (bill|act)"],
     status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: electric_trucks, name: Electric heavy-duty trucks, family: vehicles,
     include: ["electric (semi|truck|tractor)(s)?", "battery[- ]electric truck(s)?",
               "zero[- ]emission truck(s)?"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: hydrogen_trucks, name: Hydrogen fuel cell trucks, family: vehicles,
     include: ["hydrogen (fuel cell )?truck(s)?", "fuel cell electric truck(s)?",
               "\\bFCEV\\b"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: freight_charging, name: Freight EV charging infrastructure, family: vehicles,
     include: ["truck charging (corridor|depot|hub)(s)?", "megawatt charging",
               "depot charging"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: port_electrification, name: Port electrification and shore power, family: vehicles,
     include: ["shore power", "cold ironing", "port electrification"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}

  # --- Digital planning & AI -------------------------------------------------
  - {id: agentic_procurement, name: Agentic AI for procurement, family: digital,
     include: ["agentic (ai|procurement|sourcing)", "\\bai agent(s)? (for|in) (procurement|sourcing|supply chain)"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: supply_chain_digital_twin, name: Supply chain digital twins, family: digital,
     include: ["(supply chain|logistics|warehouse) digital twin(s)?",
               "digital twin of (the )?(supply chain|network)"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: demand_forecasting_ml, name: ML demand forecasting, family: digital,
     include: ["demand forecasting", "demand sensing", "probabilistic forecast(ing|s)?"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: control_tower, name: Supply chain control towers, family: digital,
     include: ["(supply chain|logistics) control tower(s)?"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: genai_planning, name: Generative AI for supply chain planning, family: digital,
     include: ["generative ai (in|for) (supply chain|procurement|logistics)",
               "\\bllm(s)? (in|for) (supply chain|logistics|procurement)"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: tms_ai, name: AI transportation management, family: digital,
     include: ["transportation management system(s)?", "\\bTMS\\b",
               "\\bai\\b[^.]{0,30}route optimi[sz]ation"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: digital_freight, name: Digital freight matching, family: digital,
     include: ["digital freight (matching|brokerage|network)", "freight marketplace(s)?",
               "digital broker(age)?"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}

  # --- Data, identity & traceability ----------------------------------------
  - {id: item_level_rfid, name: Item-level RFID, family: traceability,
     include: ["item[- ]level rfid", "rfid tagging", "\\bRAIN RFID\\b"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: digital_product_passport, name: Digital product passport, family: traceability,
     include: ["digital product passport(s)?", "\\bDPP\\b battery"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: gs1_2d, name: GS1 2D barcode transition, family: traceability,
     include: ["gs1 (digital link|sunrise)", "2d barcode(s)?", "sunrise 2027"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: blockchain_traceability, name: Blockchain traceability, family: traceability,
     include: ["blockchain (traceability|provenance)",
               "distributed ledger[^.]{0,20}(supply chain|provenance)"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: minerals_traceability, name: Critical minerals traceability, family: traceability,
     include: ["critical mineral(s)? (traceability|supply chain)",
               "battery passport", "conflict mineral(s)? tracing"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}

  # --- Physical & cold chain -------------------------------------------------
  - {id: cold_chain_iot, name: Cold chain IoT monitoring, family: physical,
     include: ["cold chain (monitoring|visibility|sensor(s)?)",
               "temperature[- ]controlled (logistics|monitoring)"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: active_cold_packaging, name: Active cold chain packaging, family: physical,
     include: ["active (thermal |cold )?packaging", "phase change (material|packaging)"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: additive_spares, name: Additive manufacturing for spare parts, family: physical,
     include: ["additive manufacturing", "3d[- ]printed (spare |replacement )?part(s)?",
               "digital (parts )?inventory"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: microfactories, name: Microfactories and distributed manufacturing, family: physical,
     include: ["microfactor(y|ies)", "distributed manufacturing", "on[- ]demand manufacturing"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: microfulfillment, name: Microfulfillment automation, family: physical,
     include: ["micro[- ]fulfil(l)?ment", "dark store(s)?", "automated fulfil(l)?ment cent(er|re)"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: cv_inspection, name: Computer vision for damage inspection, family: physical,
     include: ["(damage|cargo|container) (detection|inspection)[^.]{0,20}(vision|ai)",
               "automated (damage|defect) inspection"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}

  # --- Networks & resilience -------------------------------------------------
  - {id: risk_intelligence, name: Supply chain risk intelligence, family: networks,
     include: ["supply chain risk (intelligence|monitoring|platform)",
               "\\bn[- ]tier (visibility|mapping)", "supplier risk platform(s)?"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: nearshoring_analytics, name: Nearshoring and network redesign analytics, family: networks,
     include: ["nearshoring", "reshoring", "network (re)?design optimi[sz]ation",
               "friend[- ]shoring"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: rail_intermodal_tech, name: Rail intermodal technology, family: networks,
     include: ["intermodal (terminal|technology|automation)",
               "positive train control", "automated (rail )?inspection portal(s)?"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: inland_ports, name: Inland ports, family: networks,
     include: ["inland port(s)?", "dry port(s)?", "inland (container )?terminal(s)?"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: private_5g_warehouse, name: Private 5G in warehouses, family: networks,
     include: ["private (5g|lte) network(s)?", "private cellular[^.]{0,20}(warehouse|factory)"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
  - {id: quantum_logistics, name: Quantum optimization for logistics, family: networks,
     include: ["quantum (annealing|optimi[sz]ation)[^.]{0,30}(logistics|routing|supply chain)",
               "quantum[- ]inspired optimi[sz]ation"],
     exclude: [], status: active, added_week: 2026-W33, patterns_changed_week: 2026-W33}
```

- [ ] **Step 5: Add a test that the real watchlist loads and compiles**

Append to `tests/test_matcher.py`:

```python
def test_shipped_watchlist_loads_and_every_pattern_compiles():
    real = matcher.load_watchlist()
    assert real.version >= 1
    assert len(real.active) >= 30
    assert len({tech.id for tech in real.technologies}) == len(real.technologies)
    for tech in real.technologies:
        assert tech.include, f"{tech.id} has no include patterns"
        assert len(tech.include_res) == len(tech.include)
        assert len(tech.exclude_res) == len(tech.exclude)


def test_shipped_watchlist_matches_an_obvious_headline():
    real = matcher.load_watchlist()
    hits = dict(real.match("Aurora expands its driverless truck lanes in Texas"))
    assert "autonomous_trucking" in hits
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_matcher.py -v`
Expected: 11 passed

- [ ] **Step 7: Commit**

```bash
git add observatory/matcher.py watchlist.yaml tests/test_matcher.py
git commit -m "feat: watchlist of 32 technologies and deterministic term matcher"
```

---

### Task 5: Collector base — documents, raw pages, and raw-file storage

**Files:**
- Create: `observatory/collectors/base.py`
- Test: `tests/test_collector_base.py`

**Interfaces:**
- Consumes: `config.RAW_DIR`.
- Produces: `Document` dataclass with fields `doc_id, date, title, text, url, entity=None, entity_id=None, amount=None, lat=None, lon=None`; `RawPage` dataclass with fields `url, status, text, extension`; `BaseCollector` with class attributes `name: str`, `rate_limit_seconds: float`, and methods `fetch_raw(session, week) -> Iterator[RawPage]` and `parse(text: str) -> list[Document]`; `write_raw(source, week, index, page) -> Path`; `read_raw(source, week) -> Iterator[tuple[Path, str]]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_collector_base.py`:

```python
import pytest

from observatory.collectors import base


def test_write_raw_stores_the_body_verbatim(tmp_path, monkeypatch):
    monkeypatch.setattr(base.config, "RAW_DIR", tmp_path)
    page = base.RawPage(url="https://x.test/a", status=200, text='{"a": 1}', extension="json")
    path = base.write_raw("arxiv", "2026-W33", 0, page)
    assert path.read_text() == '{"a": 1}'
    assert path.parent == tmp_path / "2026-W33" / "arxiv"
    assert path.name == "000.json"


def test_read_raw_returns_pages_in_stable_order(tmp_path, monkeypatch):
    monkeypatch.setattr(base.config, "RAW_DIR", tmp_path)
    for index, body in enumerate(["first", "second", "third"]):
        base.write_raw("hn", "2026-W33", index, base.RawPage("u", 200, body, "json"))
    bodies = [text for _, text in base.read_raw("hn", "2026-W33")]
    assert bodies == ["first", "second", "third"]


def test_read_raw_is_empty_when_the_source_never_ran(tmp_path, monkeypatch):
    monkeypatch.setattr(base.config, "RAW_DIR", tmp_path)
    assert list(base.read_raw("hn", "2026-W33")) == []


def test_base_collector_requires_subclasses_to_implement_parse():
    class Incomplete(base.BaseCollector):
        name = "incomplete"

    with pytest.raises(NotImplementedError):
        Incomplete().parse("{}")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_collector_base.py -v`
Expected: FAIL with `ImportError: cannot import name 'base'`

- [ ] **Step 3: Write the implementation**

Create `observatory/collectors/base.py`:

```python
"""Shared collector contract.

Fetching and parsing are deliberately separate. `fetch_raw` touches the network
and yields untouched response bodies; `parse` is a pure function from body text
to documents. Tests only ever exercise `parse`, against saved fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .. import config


@dataclass(frozen=True)
class Document:
    doc_id: str
    date: str | None
    title: str | None
    text: str | None
    url: str | None
    entity: str | None = None
    entity_id: str | None = None
    amount: float | None = None
    lat: float | None = None
    lon: float | None = None


@dataclass(frozen=True)
class RawPage:
    url: str
    status: int
    text: str
    extension: str = "json"


class BaseCollector:
    name: str = "base"
    rate_limit_seconds: float = 1.0

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        raise NotImplementedError(f"{type(self).__name__} must implement fetch_raw")

    def parse(self, text: str) -> list[Document]:
        raise NotImplementedError(f"{type(self).__name__} must implement parse")


def raw_dir(source: str, week: str) -> Path:
    return config.RAW_DIR / week / source


def write_raw(source: str, week: str, index: int, page: RawPage) -> Path:
    directory = raw_dir(source, week)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{index:03d}.{page.extension}"
    path.write_text(page.text)
    return path


def read_raw(source: str, week: str) -> Iterator[tuple[Path, str]]:
    directory = raw_dir(source, week)
    if not directory.exists():
        return
    for path in sorted(directory.iterdir()):
        if path.is_file():
            yield path, path.read_text()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_collector_base.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add observatory/collectors/base.py tests/test_collector_base.py
git commit -m "feat: collector base contract with raw-before-parse storage"
```

---

### Task 6: arXiv collector

**Files:**
- Create: `observatory/collectors/arxiv.py`, `tests/fixtures/arxiv_page.xml`
- Test: `tests/test_collector_arxiv.py`

**Interfaces:**
- Consumes: `base.BaseCollector`, `base.RawPage`, `base.Document`, `http.fetch`, `http.RateLimiter`, `config.week_bounds`.
- Produces: `ArxivCollector` with `name = "arxiv"`, `parse(text) -> list[Document]` and `fetch_raw(session, week)`. Document `doc_id` is the bare arXiv id prefixed `arxiv:`, `text` is the abstract.

- [ ] **Step 1: Save the fixture**

Create `tests/fixtures/arxiv_page.xml` with a two-entry Atom response (this is a trimmed real response shape):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">2</opensearch:totalResults>
  <entry>
    <id>http://arxiv.org/abs/2608.01234v1</id>
    <updated>2026-08-12T15:04:05Z</updated>
    <published>2026-08-12T15:04:05Z</published>
    <title>Fleet Learning for Autonomous Trucking on Interstate Corridors</title>
    <summary>  We study closed-loop fleet learning for driverless truck operations
across long-haul corridors.
</summary>
    <link href="http://arxiv.org/abs/2608.01234v1" rel="alternate" type="text/html"/>
    <category term="cs.RO" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2608.05678v2</id>
    <updated>2026-08-14T09:00:00Z</updated>
    <published>2026-08-13T09:00:00Z</published>
    <title>Scheduling Warehouse Robots under Stochastic Demand</title>
    <summary>An approximation algorithm for warehouse robotics fleets.</summary>
    <link href="http://arxiv.org/abs/2608.05678v2" rel="alternate" type="text/html"/>
    <category term="math.OC" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
</feed>
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_collector_arxiv.py`:

```python
from pathlib import Path

from observatory.collectors.arxiv import ArxivCollector

FIXTURE = Path(__file__).parent / "fixtures" / "arxiv_page.xml"


def test_parse_extracts_both_entries():
    documents = ArxivCollector().parse(FIXTURE.read_text())
    assert len(documents) == 2


def test_parse_uses_the_versionless_id_and_published_date():
    first = ArxivCollector().parse(FIXTURE.read_text())[0]
    assert first.doc_id == "arxiv:2608.01234"
    assert first.date == "2026-08-12"


def test_parse_normalises_whitespace_in_title_and_abstract():
    first = ArxivCollector().parse(FIXTURE.read_text())[0]
    assert first.title == "Fleet Learning for Autonomous Trucking on Interstate Corridors"
    assert first.text.startswith("We study closed-loop fleet learning")
    assert "\n" not in first.text


def test_parse_keeps_the_abstract_url():
    first = ArxivCollector().parse(FIXTURE.read_text())[0]
    assert first.url == "https://arxiv.org/abs/2608.01234"


def test_parse_returns_nothing_for_an_empty_feed():
    empty = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
    assert ArxivCollector().parse(empty) == []


def test_query_window_covers_the_whole_iso_week():
    query = ArxivCollector().date_filter("2026-W33")
    assert query == "submittedDate:[202608100000+TO+202608170000]"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_collector_arxiv.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'observatory.collectors.arxiv'`

- [ ] **Step 4: Write the implementation**

Create `observatory/collectors/arxiv.py`:

```python
"""arXiv Atom API.

Two sweeps per week rather than one query per technology: a category sweep over
the robotics/systems/optimisation categories, and a keyword sweep over supply
chain language across all categories. Fetching a corpus rather than per-term
results keeps request counts flat as the watchlist grows, and gives the rising-
term discovery step something to mine.
"""

from __future__ import annotations

import datetime as dt
import re
import xml.etree.ElementTree as ET
from typing import Iterator

from .. import config, http
from .base import BaseCollector, Document, RawPage

API_URL = "http://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
PAGE_SIZE = 200
MAX_PAGES = 10

CATEGORY_SWEEP = "cat:cs.RO OR cat:eess.SY OR cat:math.OC OR cat:cs.MA"
KEYWORD_SWEEP = (
    'all:"supply chain" OR all:logistics OR all:freight OR all:warehouse '
    'OR all:procurement OR all:"last mile"'
)
SWEEPS = (CATEGORY_SWEEP, KEYWORD_SWEEP)

_WHITESPACE = re.compile(r"\s+")


class ArxivCollector(BaseCollector):
    name = "arxiv"
    rate_limit_seconds = 3.0  # arXiv asks for one request every three seconds

    def date_filter(self, week: str) -> str:
        """arXiv wants a half-open window, so the upper bound is the Monday after."""
        start, end = config.week_bounds(week)
        end_exclusive = end + dt.timedelta(days=1)
        return (
            f"submittedDate:[{start.strftime('%Y%m%d')}0000+TO+"
            f"{end_exclusive.strftime('%Y%m%d')}0000]"
        )

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        limiter = http.RateLimiter(self.rate_limit_seconds)
        for sweep in SWEEPS:
            for page in range(MAX_PAGES):
                params = {
                    "search_query": f"({sweep}) AND {self.date_filter(week)}",
                    "start": page * PAGE_SIZE,
                    "max_results": PAGE_SIZE,
                    "sortBy": "submittedDate",
                    "sortOrder": "ascending",
                }
                response = http.fetch(session, API_URL, params=params, limiter=limiter)
                yield RawPage(
                    url=response.url, status=response.status,
                    text=response.text, extension="xml",
                )
                if len(self.parse(response.text)) < PAGE_SIZE:
                    break

    def parse(self, text: str) -> list[Document]:
        root = ET.fromstring(text)
        documents = []
        for entry in root.findall(f"{ATOM}entry"):
            raw_id = _text(entry, f"{ATOM}id")
            if not raw_id:
                continue
            bare_id = raw_id.rsplit("/", 1)[-1].split("v")[0]
            published = _text(entry, f"{ATOM}published") or ""
            documents.append(
                Document(
                    doc_id=f"arxiv:{bare_id}",
                    date=published[:10] or None,
                    title=_clean(_text(entry, f"{ATOM}title")),
                    text=_clean(_text(entry, f"{ATOM}summary")),
                    url=f"https://arxiv.org/abs/{bare_id}",
                )
            )
        return documents


def _text(element, tag: str) -> str | None:
    found = element.find(tag)
    return None if found is None or found.text is None else found.text


def _clean(value: str | None) -> str | None:
    return None if value is None else _WHITESPACE.sub(" ", value).strip()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_collector_arxiv.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add observatory/collectors/arxiv.py tests/test_collector_arxiv.py tests/fixtures/arxiv_page.xml
git commit -m "feat: arXiv collector with category and keyword sweeps"
```

---

### Task 7: Hacker News collector

**Files:**
- Create: `observatory/collectors/hn.py`, `tests/fixtures/hn_page.json`
- Test: `tests/test_collector_hn.py`

**Interfaces:**
- Consumes: `base.BaseCollector`, `http.fetch`, `config.week_bounds`.
- Produces: `HackerNewsCollector` with `name = "hn"`. Document `amount` carries the story's points, so the `hn_points` signal is a sum of `amount`.

- [ ] **Step 1: Save the fixture**

Create `tests/fixtures/hn_page.json`:

```json
{
  "hits": [
    {
      "objectID": "41234567",
      "created_at": "2026-08-12T18:22:01.000Z",
      "title": "Aurora expands driverless truck lanes to Phoenix",
      "url": "https://example.test/aurora",
      "points": 214,
      "num_comments": 96,
      "story_text": null
    },
    {
      "objectID": "41234599",
      "created_at": "2026-08-14T02:10:00.000Z",
      "title": "Ask HN: what is your warehouse robotics stack?",
      "url": null,
      "points": 38,
      "num_comments": 41,
      "story_text": "We run AMRs in two buildings."
    }
  ],
  "nbHits": 2,
  "page": 0,
  "nbPages": 1
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_collector_hn.py`:

```python
import json
from pathlib import Path

from observatory.collectors.hn import HackerNewsCollector

FIXTURE = Path(__file__).parent / "fixtures" / "hn_page.json"


def test_parse_extracts_both_stories():
    assert len(HackerNewsCollector().parse(FIXTURE.read_text())) == 2


def test_points_land_in_amount_for_summing():
    documents = HackerNewsCollector().parse(FIXTURE.read_text())
    assert documents[0].amount == 214.0
    assert documents[1].amount == 38.0


def test_doc_id_is_namespaced_and_date_is_iso():
    first = HackerNewsCollector().parse(FIXTURE.read_text())[0]
    assert first.doc_id == "hn:41234567"
    assert first.date == "2026-08-12"


def test_story_without_url_falls_back_to_the_item_page():
    second = HackerNewsCollector().parse(FIXTURE.read_text())[1]
    assert second.url == "https://news.ycombinator.com/item?id=41234599"


def test_story_text_is_searchable_body():
    second = HackerNewsCollector().parse(FIXTURE.read_text())[1]
    assert "AMRs" in second.text


def test_parse_handles_an_empty_result_set():
    assert HackerNewsCollector().parse(json.dumps({"hits": []})) == []


def test_numeric_filters_bound_the_week():
    filters = HackerNewsCollector().numeric_filters("2026-W33")
    assert filters == "created_at_i>=1786320000,created_at_i<1786924800"
```

Note on the expected timestamps: `2026-08-10T00:00:00Z` is epoch `1786320000` and `2026-08-17T00:00:00Z` is `1786924800`. If these differ on your machine, compute them with
`python -c "import datetime as dt;print(int(dt.datetime(2026,8,10,tzinfo=dt.timezone.utc).timestamp()))"` and correct the test — the implementation must use UTC, not local time.

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_collector_hn.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'observatory.collectors.hn'`

- [ ] **Step 4: Write the implementation**

Create `observatory/collectors/hn.py`:

```python
"""Hacker News via the Algolia search API.

Anchor queries rather than per-technology queries: seven broad supply chain
terms give a corpus that the matcher then narrows. This is the "attention" side
of the substance-versus-attention comparison.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Iterator

from .. import config, http
from .base import BaseCollector, Document, RawPage

API_URL = "https://hn.algolia.com/api/v1/search_by_date"
PAGE_SIZE = 100
MAX_PAGES = 10

ANCHOR_QUERIES = (
    "supply chain",
    "logistics",
    "freight",
    "warehouse",
    "robotics",
    "procurement",
    "shipping",
)


class HackerNewsCollector(BaseCollector):
    name = "hn"
    rate_limit_seconds = 1.0

    def numeric_filters(self, week: str) -> str:
        start, end = config.week_bounds(week)
        start_epoch = int(
            dt.datetime.combine(start, dt.time.min, tzinfo=dt.timezone.utc).timestamp()
        )
        end_epoch = int(
            dt.datetime.combine(
                end + dt.timedelta(days=1), dt.time.min, tzinfo=dt.timezone.utc
            ).timestamp()
        )
        return f"created_at_i>={start_epoch},created_at_i<{end_epoch}"

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        limiter = http.RateLimiter(self.rate_limit_seconds)
        filters = self.numeric_filters(week)
        for query in ANCHOR_QUERIES:
            for page in range(MAX_PAGES):
                params = {
                    "query": query,
                    "tags": "story",
                    "numericFilters": filters,
                    "hitsPerPage": PAGE_SIZE,
                    "page": page,
                }
                response = http.fetch(session, API_URL, params=params, limiter=limiter)
                yield RawPage(response.url, response.status, response.text, "json")
                payload = json.loads(response.text)
                if page + 1 >= payload.get("nbPages", 1):
                    break

    def parse(self, text: str) -> list[Document]:
        payload = json.loads(text)
        documents = []
        for hit in payload.get("hits", []):
            object_id = hit.get("objectID")
            if not object_id:
                continue
            documents.append(
                Document(
                    doc_id=f"hn:{object_id}",
                    date=(hit.get("created_at") or "")[:10] or None,
                    title=hit.get("title"),
                    text=hit.get("story_text") or "",
                    url=hit.get("url")
                    or f"https://news.ycombinator.com/item?id={object_id}",
                    amount=float(hit.get("points") or 0),
                )
            )
        return documents
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_collector_hn.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add observatory/collectors/hn.py tests/test_collector_hn.py tests/fixtures/hn_page.json
git commit -m "feat: Hacker News collector with anchor-query sweep"
```

---

### Task 8: Federal Register collector

**Files:**
- Create: `observatory/collectors/federalregister.py`, `tests/fixtures/federalregister_page.json`
- Test: `tests/test_collector_federalregister.py`

**Interfaces:**
- Consumes: `base.BaseCollector`, `http.fetch`, `config.week_bounds`.
- Produces: `FederalRegisterCollector` with `name = "federalregister"`. Document `entity` is the first agency name, `text` is the abstract.

- [ ] **Step 1: Save the fixture**

Create `tests/fixtures/federalregister_page.json`:

```json
{
  "count": 2,
  "total_pages": 1,
  "results": [
    {
      "document_number": "2026-17421",
      "publication_date": "2026-08-12",
      "title": "Automated Driving Systems for Commercial Motor Vehicles; Exemption",
      "abstract": "FMCSA grants an exemption enabling driverless truck operations on designated corridors.",
      "html_url": "https://www.federalregister.gov/documents/2026/08/12/2026-17421/automated-driving-systems",
      "type": "Notice",
      "agencies": [{"name": "Federal Motor Carrier Safety Administration", "id": 200}]
    },
    {
      "document_number": "2026-17500",
      "publication_date": "2026-08-14",
      "title": "Port Infrastructure Development Program; Shore Power Grants",
      "abstract": "MARAD announces awards supporting port electrification and shore power.",
      "html_url": "https://www.federalregister.gov/documents/2026/08/14/2026-17500/port-infrastructure",
      "type": "Notice",
      "agencies": [{"name": "Maritime Administration", "id": 210}]
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_collector_federalregister.py`:

```python
import json
from pathlib import Path

from observatory.collectors.federalregister import FederalRegisterCollector

FIXTURE = Path(__file__).parent / "fixtures" / "federalregister_page.json"


def test_parse_extracts_both_documents():
    assert len(FederalRegisterCollector().parse(FIXTURE.read_text())) == 2


def test_doc_id_uses_the_document_number():
    first = FederalRegisterCollector().parse(FIXTURE.read_text())[0]
    assert first.doc_id == "fedreg:2026-17421"
    assert first.date == "2026-08-12"


def test_agency_becomes_the_entity():
    first = FederalRegisterCollector().parse(FIXTURE.read_text())[0]
    assert first.entity == "Federal Motor Carrier Safety Administration"
    assert first.entity_id == "200"


def test_abstract_is_the_searchable_body():
    first = FederalRegisterCollector().parse(FIXTURE.read_text())[0]
    assert "driverless truck" in first.text


def test_missing_agencies_do_not_raise():
    payload = json.dumps({"results": [{
        "document_number": "2026-1", "publication_date": "2026-08-12",
        "title": "T", "abstract": None, "html_url": "https://x.test", "agencies": []
    }]})
    document = FederalRegisterCollector().parse(payload)[0]
    assert document.entity is None
    assert document.text == ""


def test_parse_handles_an_empty_result_set():
    assert FederalRegisterCollector().parse(json.dumps({"results": []})) == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_collector_federalregister.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Write the implementation**

Create `observatory/collectors/federalregister.py`:

```python
"""Federal Register documents API.

Filtered by transport and trade agencies rather than by keyword, so the corpus
is bounded and every document is plausibly about physical logistics capability.
This is the regulatory half of the deployment signal.
"""

from __future__ import annotations

import json
from typing import Iterator

from .. import config, http
from .base import BaseCollector, Document, RawPage

API_URL = "https://www.federalregister.gov/api/v1/documents.json"
PAGE_SIZE = 100
MAX_PAGES = 20

AGENCY_SLUGS = (
    "transportation-department",
    "federal-motor-carrier-safety-administration",
    "federal-aviation-administration",
    "federal-railroad-administration",
    "maritime-administration",
    "national-highway-traffic-safety-administration",
    "customs-and-border-protection",
    "federal-highway-administration",
    "energy-department",
    "commerce-department",
)


class FederalRegisterCollector(BaseCollector):
    name = "federalregister"
    rate_limit_seconds = 1.0

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        limiter = http.RateLimiter(self.rate_limit_seconds)
        start, end = config.week_bounds(week)
        for page in range(1, MAX_PAGES + 1):
            params = [
                ("per_page", PAGE_SIZE),
                ("page", page),
                ("order", "oldest"),
                ("conditions[publication_date][gte]", start.isoformat()),
                ("conditions[publication_date][lte]", end.isoformat()),
                ("fields[]", "document_number"),
                ("fields[]", "publication_date"),
                ("fields[]", "title"),
                ("fields[]", "abstract"),
                ("fields[]", "html_url"),
                ("fields[]", "type"),
                ("fields[]", "agencies"),
            ]
            params += [("conditions[agencies][]", slug) for slug in AGENCY_SLUGS]
            response = http.fetch(session, API_URL, params=params, limiter=limiter)
            yield RawPage(response.url, response.status, response.text, "json")
            payload = json.loads(response.text)
            if page >= int(payload.get("total_pages") or 1):
                break

    def parse(self, text: str) -> list[Document]:
        payload = json.loads(text)
        documents = []
        for result in payload.get("results", []) or []:
            number = result.get("document_number")
            if not number:
                continue
            agencies = result.get("agencies") or []
            first_agency = agencies[0] if agencies else {}
            documents.append(
                Document(
                    doc_id=f"fedreg:{number}",
                    date=result.get("publication_date"),
                    title=result.get("title"),
                    text=result.get("abstract") or "",
                    url=result.get("html_url"),
                    entity=first_agency.get("name"),
                    entity_id=str(first_agency["id"]) if first_agency.get("id") else None,
                )
            )
        return documents
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_collector_federalregister.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add observatory/collectors/federalregister.py tests/test_collector_federalregister.py tests/fixtures/federalregister_page.json
git commit -m "feat: Federal Register collector filtered to transport agencies"
```

---

### Task 9: Normalize observations into weekly signals

**Files:**
- Create: `observatory/normalize.py`
- Test: `tests/test_normalize.py`

**Interfaces:**
- Consumes: `store`, `matcher.Watchlist`.
- Produces: `AGGREGATIONS: tuple[Aggregation, ...]` where `Aggregation` has fields `signal, source, method` and `method` is `"count"` or `"sum_amount"`; `signals_for_source(source) -> list[Aggregation]`; `compute_signals(conn, week, watchlist, ok_sources: set[str]) -> int` returning the number of signal rows written.

- [ ] **Step 1: Write the failing test**

Create `tests/test_normalize.py`:

```python
import pytest

from observatory import normalize, store
from observatory.matcher import Observation, Technology, Watchlist


def tech(tech_id):
    return Technology(
        id=tech_id, name=tech_id, family="f", include=("x",), exclude=(),
        status="active", added_week="2026-W33", patterns_changed_week="2026-W33",
    )


@pytest.fixture()
def watchlist():
    return Watchlist(version=1, technologies=(tech("autonomous_trucking"), tech("quiet_tech")))


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def observation(tech_id, source, doc_id, amount=None):
    return Observation(
        source=source, week="2026-W33", tech_id=tech_id, doc_id=doc_id,
        doc_date="2026-08-12", title="t", url="u", entity=None, entity_id=None,
        amount=amount, lat=None, lon=None, matched_pattern="x", raw_ref=1,
    )


def test_counts_documents_for_count_signals(conn, watchlist):
    store.upsert_observations(conn, [
        observation("autonomous_trucking", "arxiv", "a1"),
        observation("autonomous_trucking", "arxiv", "a2"),
    ])
    normalize.compute_signals(conn, "2026-W33", watchlist, {"arxiv"})
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "arxiv_papers") == 2.0


def test_sums_amount_for_sum_signals(conn, watchlist):
    store.upsert_observations(conn, [
        observation("autonomous_trucking", "hn", "h1", amount=214.0),
        observation("autonomous_trucking", "hn", "h2", amount=38.0),
    ])
    normalize.compute_signals(conn, "2026-W33", watchlist, {"hn"})
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "hn_points") == 252.0


def test_writes_explicit_zero_for_a_technology_with_no_hits(conn, watchlist):
    store.upsert_observations(conn, [observation("autonomous_trucking", "arxiv", "a1")])
    normalize.compute_signals(conn, "2026-W33", watchlist, {"arxiv"})
    assert store.get_signal(conn, "quiet_tech", "2026-W33", "arxiv_papers") == 0.0


def test_a_failed_source_leaves_a_hole_rather_than_a_zero(conn, watchlist):
    normalize.compute_signals(conn, "2026-W33", watchlist, {"arxiv"})
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "arxiv_papers") == 0.0
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "hn_points") is None


def test_recomputing_the_same_week_is_idempotent(conn, watchlist):
    store.upsert_observations(conn, [observation("autonomous_trucking", "arxiv", "a1")])
    normalize.compute_signals(conn, "2026-W33", watchlist, {"arxiv"})
    normalize.compute_signals(conn, "2026-W33", watchlist, {"arxiv"})
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "arxiv_papers") == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'observatory.normalize'`

- [ ] **Step 3: Write the implementation**

Create `observatory/normalize.py`:

```python
"""Observations to weekly signals.

The only subtle rule lives here: a source that failed this week must leave its
signals absent, not zero. A zero says "nothing happened"; an absence says "we
did not look". Confusing the two invents declines that never occurred.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import store
from .matcher import Watchlist


@dataclass(frozen=True)
class Aggregation:
    signal: str
    source: str
    method: str  # "count" | "sum_amount"


AGGREGATIONS: tuple[Aggregation, ...] = (
    Aggregation("arxiv_papers", "arxiv", "count"),
    Aggregation("hn_points", "hn", "sum_amount"),
    Aggregation("fedreg_docs", "federalregister", "count"),
)


def signals_for_source(source: str) -> list[Aggregation]:
    return [aggregation for aggregation in AGGREGATIONS if aggregation.source == source]


def compute_signals(conn, week: str, watchlist: Watchlist, ok_sources: set[str]) -> int:
    written = 0
    for aggregation in AGGREGATIONS:
        if aggregation.source not in ok_sources:
            continue
        totals = _totals(conn, week, aggregation)
        for tech in watchlist.active:
            store.set_signal(
                conn, tech.id, week, aggregation.signal, float(totals.get(tech.id, 0.0))
            )
            written += 1
    return written


def _totals(conn, week: str, aggregation: Aggregation) -> dict[str, float]:
    expression = "COUNT(*)" if aggregation.method == "count" else "COALESCE(SUM(amount), 0)"
    rows = conn.execute(
        f"SELECT tech_id, {expression} AS total FROM observations "
        "WHERE week = ? AND source = ? GROUP BY tech_id",
        (week, aggregation.source),
    ).fetchall()
    return {row["tech_id"]: float(row["total"]) for row in rows}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add observatory/normalize.py tests/test_normalize.py
git commit -m "feat: aggregate observations into weekly signals"
```

---

### Task 10: Metric primitives — z-scores, carry-forward, acceleration

**Files:**
- Create: `observatory/metrics.py`
- Test: `tests/test_metrics_primitives.py`

**Interfaces:**
- Consumes: `config.MIN_HISTORY_WEEKS`.
- Produces: pure functions `carry_forward(series: list[float | None]) -> list[float | None]`; `zscore(series: list[float | None], min_periods: int = 12) -> float | None`; `trailing_mean(series: list[float], window: int) -> float`; `acceleration(series: list[float | None]) -> float | None`; `cross_sectional_z(values: dict[str, float | None]) -> dict[str, float | None]`; `mean_of_present(values: list[float | None]) -> float | None`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_metrics_primitives.py`:

```python
import pytest

from observatory import metrics


def test_carry_forward_fills_holes_with_the_previous_value():
    assert metrics.carry_forward([1.0, None, None, 4.0]) == [1.0, 1.0, 1.0, 4.0]


def test_carry_forward_leaves_leading_holes_alone():
    assert metrics.carry_forward([None, None, 3.0]) == [None, None, 3.0]


def test_zscore_of_the_last_value_against_its_history():
    series = [0.0] * 11 + [1.0]
    # mean of the 12 values is 1/12, population sd is sqrt(11)/12
    assert metrics.zscore(series) == pytest.approx(3.3166, abs=1e-3)


def test_zscore_is_none_below_the_minimum_history():
    assert metrics.zscore([1.0] * 11) is None


def test_zscore_is_zero_for_a_flat_series_rather_than_dividing_by_zero():
    assert metrics.zscore([5.0] * 20) == 0.0


def test_zscore_carries_holes_forward_before_scoring():
    assert metrics.zscore([2.0] + [None] * 11) == 0.0


def test_acceleration_is_zero_for_a_straight_line():
    series = [float(i) for i in range(1, 21)]
    assert metrics.acceleration(series) == pytest.approx(0.0, abs=1e-9)


def test_acceleration_is_positive_when_growth_speeds_up():
    series = [float(i * i) for i in range(1, 21)]
    assert metrics.acceleration(series) > 0


def test_acceleration_is_negative_when_growth_slows():
    series = [float(i**0.5) for i in range(1, 21)]
    assert metrics.acceleration(series) < 0


def test_acceleration_needs_twelve_weeks():
    assert metrics.acceleration([1.0] * 11) is None


def test_cross_sectional_z_ranks_within_the_week():
    result = metrics.cross_sectional_z({"a": 1.0, "b": 2.0, "c": 3.0})
    assert result["b"] == pytest.approx(0.0)
    assert result["a"] < 0 < result["c"]


def test_cross_sectional_z_passes_through_missing_values():
    result = metrics.cross_sectional_z({"a": 1.0, "b": None, "c": 3.0})
    assert result["b"] is None


def test_mean_of_present_ignores_missing_components():
    assert metrics.mean_of_present([1.0, None, 3.0]) == 2.0
    assert metrics.mean_of_present([None, None]) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_metrics_primitives.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'observatory.metrics'`

- [ ] **Step 3: Write the implementation**

Create `observatory/metrics.py`:

```python
"""Scoring.

Every function here is pure and takes plain lists, so the maths can be tested
against series with known answers. Nothing in this module touches the network,
the clock, or a model.
"""

from __future__ import annotations

import statistics

from . import config

STAGES = ("idea", "experiment", "investment", "deployment", "diffusion")


def carry_forward(series: list[float | None]) -> list[float | None]:
    filled: list[float | None] = []
    last: float | None = None
    for value in series:
        if value is None:
            filled.append(last)
        else:
            filled.append(value)
            last = value
    return filled


def mean_of_present(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return statistics.fmean(present) if present else None


def zscore(series: list[float | None], min_periods: int = config.MIN_HISTORY_WEEKS) -> float | None:
    filled = [value for value in carry_forward(series) if value is not None]
    if len(filled) < min_periods:
        return None
    spread = statistics.pstdev(filled)
    if spread == 0:
        return 0.0
    return (filled[-1] - statistics.fmean(filled)) / spread


def trailing_mean(series: list[float], window: int) -> float:
    return statistics.fmean(series[-window:])


def acceleration(series: list[float | None]) -> float | None:
    """Change in the four-week slope: is growth itself speeding up?"""
    filled = [value for value in carry_forward(series) if value is not None]
    if len(filled) < config.MIN_HISTORY_WEEKS:
        return None
    now = trailing_mean(filled, 4)
    four_back = trailing_mean(filled[:-4], 4)
    eight_back = trailing_mean(filled[:-8], 4)
    return (now - four_back) - (four_back - eight_back)


def cross_sectional_z(values: dict[str, float | None]) -> dict[str, float | None]:
    present = [value for value in values.values() if value is not None]
    if len(present) < 2:
        return {key: None for key in values}
    centre = statistics.fmean(present)
    spread = statistics.pstdev(present)
    if spread == 0:
        return {key: (None if value is None else 0.0) for key, value in values.items()}
    return {
        key: (None if value is None else (value - centre) / spread)
        for key, value in values.items()
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_metrics_primitives.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add observatory/metrics.py tests/test_metrics_primitives.py
git commit -m "feat: metric primitives for z-scores and acceleration"
```

---

### Task 11: Stage scores and the four headline metrics

**Files:**
- Modify: `observatory/metrics.py`
- Test: `tests/test_metrics_week.py`

**Interfaces:**
- Consumes: `store.signal_series`, `config.trailing_weeks`, `matcher.Watchlist`, primitives from Task 10.
- Produces: `SIGNALS_BY_STAGE: dict[str, tuple[str, ...]]`; `HARD_SIGNALS`, `SOFT_SIGNALS`; `stage_scores(z_by_signal) -> dict[str, float | None]`; `pipeline_position(stages) -> float | None`; `substance_index(z_by_signal) -> float | None`; `lab_to_field(stages) -> float | None`; `compute_week(conn, week, watchlist) -> list[dict]` writing nothing, returning metric dicts ready for `store.upsert_metrics`; `momentum_suppressed(tech, week) -> bool`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_metrics_week.py`:

```python
import pytest

from observatory import config, metrics, store
from observatory.matcher import Technology, Watchlist


def tech(tech_id, patterns_changed_week="2020-W01"):
    return Technology(
        id=tech_id, name=tech_id, family="f", include=("x",), exclude=(),
        status="active", added_week="2020-W01",
        patterns_changed_week=patterns_changed_week,
    )


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def seed(conn, tech_id, signal, values, end_week="2026-W33"):
    weeks = config.trailing_weeks(end_week, len(values))
    for week, value in zip(weeks, values):
        store.set_signal(conn, tech_id, week, signal, float(value))


def test_stage_scores_average_their_member_signals():
    stages = metrics.stage_scores({"arxiv_papers": 1.0, "hn_points": 3.0})
    assert stages["idea"] == 2.0


def test_stage_with_no_present_signals_is_none():
    stages = metrics.stage_scores({"arxiv_papers": 1.0})
    assert stages["experiment"] is None


def test_pipeline_position_sits_between_one_and_five():
    late = metrics.pipeline_position(
        {"idea": -2.0, "experiment": -1.0, "investment": 0.0,
         "deployment": 2.0, "diffusion": 2.0}
    )
    early = metrics.pipeline_position(
        {"idea": 2.0, "experiment": 2.0, "investment": 0.0,
         "deployment": -1.0, "diffusion": -2.0}
    )
    assert 1.0 <= early < late <= 5.0


def test_substance_index_is_positive_when_building_beats_talking():
    assert metrics.substance_index({"arxiv_papers": 0.0, "patents": 2.0,
                                    "hn_points": -1.0, "media_articles": None}) > 0


def test_lab_to_field_turns_positive_when_deployment_leads():
    stages = {"idea": -1.0, "experiment": -1.0, "investment": 1.0,
              "deployment": 2.0, "diffusion": 0.0}
    assert metrics.lab_to_field(stages) == pytest.approx(2.5)


def test_compute_week_is_warming_up_below_twelve_weeks(conn):
    watchlist = Watchlist(version=1, technologies=(tech("a"), tech("b")))
    seed(conn, "a", "arxiv_papers", [1] * 8)
    seed(conn, "b", "arxiv_papers", [1] * 8)
    rows = {row["tech_id"]: row for row in metrics.compute_week(conn, "2026-W33", watchlist)}
    assert rows["a"]["momentum"] is None
    assert rows["a"]["stage_idea"] is None


def test_compute_week_ranks_the_accelerating_technology_higher(conn):
    watchlist = Watchlist(version=1, technologies=(tech("fast"), tech("flat")))
    seed(conn, "fast", "arxiv_papers", [1, 1, 1, 1, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55])
    seed(conn, "flat", "arxiv_papers", [5] * 14)
    seed(conn, "fast", "hn_points", [1] * 14)
    seed(conn, "flat", "hn_points", [1] * 14)
    seed(conn, "fast", "fedreg_docs", [0] * 14)
    seed(conn, "flat", "fedreg_docs", [0] * 14)
    rows = {row["tech_id"]: row for row in metrics.compute_week(conn, "2026-W33", watchlist)}
    assert rows["fast"]["momentum"] > rows["flat"]["momentum"]


def test_compute_week_stamps_the_lexicon_version(conn):
    watchlist = Watchlist(version=7, technologies=(tech("a"),))
    seed(conn, "a", "arxiv_papers", [1] * 14)
    row = metrics.compute_week(conn, "2026-W33", watchlist)[0]
    assert row["lexicon_version"] == 7


def test_momentum_is_suppressed_after_a_recent_pattern_change(conn):
    # Three technologies, because a cross-sectional z-score needs at least two
    # surviving values to mean anything.
    recent = tech("changed", patterns_changed_week="2026-W30")
    watchlist = Watchlist(
        version=1, technologies=(recent, tech("stable"), tech("rising"))
    )
    seed(conn, "changed", "arxiv_papers", [1, 1, 1, 1, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55])
    seed(conn, "stable", "arxiv_papers", [5] * 14)
    seed(conn, "rising", "arxiv_papers", [1, 1, 2, 2, 3, 3, 4, 6, 9, 13, 18, 24, 31, 39])
    rows = {row["tech_id"]: row for row in metrics.compute_week(conn, "2026-W33", watchlist)}
    assert rows["changed"]["momentum"] is None
    assert rows["stable"]["momentum"] is not None
    assert rows["rising"]["momentum"] > rows["stable"]["momentum"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_metrics_week.py -v`
Expected: FAIL with `AttributeError: module 'observatory.metrics' has no attribute 'stage_scores'`

- [ ] **Step 3: Write the implementation**

First fix the imports at the top of `observatory/metrics.py`: add `import math` beside
`import statistics`, and change `from . import config` to `from . import config, store`.
`store` does not import `metrics`, so there is no cycle. Then append:

```python
SIGNALS_BY_STAGE: dict[str, tuple[str, ...]] = {
    "idea": ("arxiv_papers", "hn_points"),
    "experiment": ("patents", "gh_repos_new", "gh_commits", "gh_stars_delta"),
    "investment": ("fed_obligated", "edgar_filings"),
    "deployment": ("fed_awards", "fedreg_docs", "media_deploy"),
    "diffusion": ("edgar_filers", "media_articles"),
}

ALL_SIGNALS = tuple(
    signal for signals in SIGNALS_BY_STAGE.values() for signal in signals
)

HARD_SIGNALS = ("patents", "gh_repos_new", "gh_commits", "fed_awards", "edgar_filers")
SOFT_SIGNALS = ("media_articles", "hn_points")

STAGE_INDEX = {stage: position for position, stage in enumerate(STAGES, start=1)}
MOMENTUM_SUPPRESSION_WEEKS = 8


def stage_scores(z_by_signal: dict[str, float | None]) -> dict[str, float | None]:
    return {
        stage: mean_of_present([z_by_signal.get(signal) for signal in signals])
        for stage, signals in SIGNALS_BY_STAGE.items()
    }


def pipeline_position(stages: dict[str, float | None]) -> float | None:
    present = {stage: value for stage, value in stages.items() if value is not None}
    if not present:
        return None
    weights = {stage: _exp(value) for stage, value in present.items()}
    total = sum(weights.values())
    return sum(STAGE_INDEX[stage] * weight for stage, weight in weights.items()) / total


def substance_index(z_by_signal: dict[str, float | None]) -> float | None:
    hard = mean_of_present([z_by_signal.get(signal) for signal in HARD_SIGNALS])
    soft = mean_of_present([z_by_signal.get(signal) for signal in SOFT_SIGNALS])
    if hard is None or soft is None:
        return None
    return hard - soft


def lab_to_field(stages: dict[str, float | None]) -> float | None:
    late = mean_of_present([stages.get("investment"), stages.get("deployment")])
    early = mean_of_present([stages.get("idea"), stages.get("experiment")])
    if late is None or early is None:
        return None
    return late - early


def momentum_suppressed(tech, week: str) -> bool:
    """A widened pattern looks exactly like real acceleration. Do not report it."""
    cutoff = config.week_offset(week, -MOMENTUM_SUPPRESSION_WEEKS)
    return tech.patterns_changed_week > cutoff


def compute_week(conn, week: str, watchlist) -> list[dict]:
    weeks = config.trailing_weeks(week, config.TRAILING_WEEKS)
    raw_accelerations: dict[str, float | None] = {}
    partial: dict[str, dict] = {}

    for tech in watchlist.active:
        z_by_signal: dict[str, float | None] = {}
        composite_inputs: list[list[float | None]] = []
        for signal in ALL_SIGNALS:
            series = store.signal_series(conn, tech.id, signal, weeks)
            z_by_signal[signal] = zscore(series)
            if any(value is not None for value in series):
                composite_inputs.append(series)

        stages = stage_scores(z_by_signal)
        composite = _composite_series(composite_inputs)
        raw = acceleration(composite)
        raw_accelerations[tech.id] = None if momentum_suppressed(tech, week) else raw

        partial[tech.id] = {
            "tech_id": tech.id,
            "week": week,
            "sai": substance_index(z_by_signal),
            "lfi": lab_to_field(stages),
            "adoption": int(store.get_signal(conn, tech.id, week, "edgar_filers") or 0),
            "adoption_new": 0,
            "stage_idea": stages["idea"],
            "stage_experiment": stages["experiment"],
            "stage_investment": stages["investment"],
            "stage_deployment": stages["deployment"],
            "stage_diffusion": stages["diffusion"],
            "position": pipeline_position(stages),
            "lexicon_version": watchlist.version,
        }

    momentum_by_tech = cross_sectional_z(raw_accelerations)
    for tech_id, row in partial.items():
        row["momentum"] = momentum_by_tech[tech_id]
    return [partial[tech.id] for tech in watchlist.active]


def _composite_series(series_list: list[list[float | None]]) -> list[float | None]:
    """Mean across signals, week by week, of whatever is present."""
    if not series_list:
        return []
    length = len(series_list[0])
    return [
        mean_of_present([series[index] for series in series_list])
        for index in range(length)
    ]


def _exp(value: float) -> float:
    """Clamped exponential — softmax weights must not overflow on an outlier."""
    return math.exp(max(min(value, 20.0), -20.0))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_metrics_week.py -v`
Expected: 9 passed

- [ ] **Step 5: Run the whole suite to catch regressions**

Run: `python -m pytest -v`
Expected: all passing

- [ ] **Step 6: Commit**

```bash
git add observatory/metrics.py tests/test_metrics_week.py
git commit -m "feat: stage scores, momentum, substance index, and lab-to-field"
```

---

### Task 12: Inline SVG charts

**Files:**
- Create: `observatory/charts.py`
- Test: `tests/test_charts.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `scatter(points: list[Point], width=720, height=440, x_label="", y_label="") -> str`; `sparkline(values: list[float | None], width=120, height=28) -> str`; `Point` dataclass with fields `x, y, label, size=6.0, colour="#5b7fa6"`. All return SVG markup strings with no external references.

- [ ] **Step 1: Write the failing test**

Create `tests/test_charts.py`:

```python
from observatory import charts


def points():
    return [
        charts.Point(x=1.0, y=2.0, label="alpha"),
        charts.Point(x=3.0, y=-1.0, label="beta"),
        charts.Point(x=2.0, y=0.5, label="gamma"),
    ]


def test_scatter_returns_an_svg_element():
    svg = charts.scatter(points())
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")


def test_scatter_draws_one_circle_per_point():
    assert charts.scatter(points()).count("<circle") == 3


def test_scatter_labels_are_escaped():
    svg = charts.scatter([charts.Point(1.0, 1.0, label='rob"ots & <carts>')])
    assert "&amp;" in svg and "&lt;carts&gt;" in svg
    assert "<carts>" not in svg


def test_scatter_never_references_an_external_resource():
    # The opening tag carries the SVG xmlns, which is an identifier and not a
    # fetched resource. Everything after it must be free of URLs.
    body = charts.scatter(points()).split(">", 1)[1]
    assert "http://" not in body and "https://" not in body


def test_scatter_of_identical_points_does_not_divide_by_zero():
    svg = charts.scatter([charts.Point(1.0, 1.0, "a"), charts.Point(1.0, 1.0, "b")])
    assert "<circle" in svg
    assert "nan" not in svg.lower()


def test_scatter_handles_an_empty_series():
    assert "<svg" in charts.scatter([])


def test_sparkline_draws_a_polyline_through_every_value():
    svg = charts.sparkline([1.0, 2.0, 1.5, 3.0])
    assert "<polyline" in svg
    assert svg.count(",") >= 4


def test_sparkline_skips_missing_values_without_crashing():
    assert "<polyline" in charts.sparkline([1.0, None, 3.0])


def test_sparkline_of_nothing_is_still_valid_svg():
    assert charts.sparkline([]).startswith("<svg")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_charts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'observatory.charts'`

- [ ] **Step 3: Write the implementation**

Create `observatory/charts.py`:

```python
"""Charts as inline SVG strings.

Generated in Python rather than by a JavaScript library so the dashboard has no
external dependencies and renders identically offline, forever.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

PADDING = 48
AXIS_COLOUR = "#c9cdd2"
TEXT_COLOUR = "#3d4348"


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    label: str = ""
    size: float = 6.0
    colour: str = "#5b7fa6"


def _scale(value: float, low: float, high: float, out_low: float, out_high: float) -> float:
    if high - low == 0:
        return (out_low + out_high) / 2
    return out_low + (value - low) * (out_high - out_low) / (high - low)


def scatter(
    points: list[Point],
    width: int = 720,
    height: int = 440,
    x_label: str = "",
    y_label: str = "",
) -> str:
    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" '
        f'xmlns="http://www.w3.org/2000/svg" role="img">'
    ]
    parts.append(
        f'<line x1="{PADDING}" y1="{height - PADDING}" x2="{width - PADDING}" '
        f'y2="{height - PADDING}" stroke="{AXIS_COLOUR}" />'
        f'<line x1="{PADDING}" y1="{PADDING}" x2="{PADDING}" '
        f'y2="{height - PADDING}" stroke="{AXIS_COLOUR}" />'
    )
    if points:
        xs = [point.x for point in points]
        ys = [point.y for point in points]
        x_low, x_high = min(xs), max(xs)
        y_low, y_high = min(ys), max(ys)
        for point in points:
            cx = _scale(point.x, x_low, x_high, PADDING, width - PADDING)
            cy = _scale(point.y, y_low, y_high, height - PADDING, PADDING)
            parts.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{point.size:.1f}" '
                f'fill="{point.colour}" fill-opacity="0.75">'
                f"<title>{escape(point.label, quote=True)}</title></circle>"
            )
    if x_label:
        parts.append(
            f'<text x="{width / 2:.0f}" y="{height - 12}" text-anchor="middle" '
            f'font-size="12" fill="{TEXT_COLOUR}">{escape(x_label)}</text>'
        )
    if y_label:
        parts.append(
            f'<text x="14" y="{height / 2:.0f}" text-anchor="middle" font-size="12" '
            f'fill="{TEXT_COLOUR}" transform="rotate(-90 14 {height / 2:.0f})">'
            f"{escape(y_label)}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def sparkline(values: list[float | None], width: int = 120, height: int = 28) -> str:
    present = [(index, value) for index, value in enumerate(values) if value is not None]
    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img">'
    ]
    if len(present) >= 2:
        only_values = [value for _, value in present]
        low, high = min(only_values), max(only_values)
        coordinates = " ".join(
            f"{_scale(index, 0, len(values) - 1, 1, width - 1):.1f},"
            f"{_scale(value, low, high, height - 2, 2):.1f}"
            for index, value in present
        )
        parts.append(
            f'<polyline points="{coordinates}" fill="none" '
            f'stroke="#5b7fa6" stroke-width="1.5" />'
        )
    parts.append("</svg>")
    return "".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_charts.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add observatory/charts.py tests/test_charts.py
git commit -m "feat: inline SVG scatter and sparkline charts"
```

---

### Task 13: Render the dashboard

**Files:**
- Create: `observatory/render.py`, `observatory/templates/dashboard.html.j2`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `store.metrics_for_week`, `store.source_statuses`, `charts`, `matcher.Watchlist`, `config.OUTPUT_DIR`.
- Produces: `build_context(conn, week, watchlist) -> dict` with keys `week`, `generated_for`, `lexicon_version`, `sources`, `movers`, `stage_board_svg`, `substance_svg`, `crossovers`, `warming_up`; `render_dashboard(conn, week, watchlist, out_path=None) -> Path`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_render.py`:

```python
import re

import pytest

from observatory import render, store
from observatory.matcher import Technology, Watchlist


def tech(tech_id, name=None, family="automation"):
    return Technology(
        id=tech_id, name=name or tech_id, family=family, include=("x",), exclude=(),
        status="active", added_week="2020-W01", patterns_changed_week="2020-W01",
    )


@pytest.fixture()
def watchlist():
    return Watchlist(version=3, technologies=(
        tech("autonomous_trucking", "Autonomous trucking", "vehicles"),
        tech("warehouse_robotics", "Warehouse robotics"),
        tech("quiet_tech", "Quiet tech"),
    ))


@pytest.fixture()
def conn(watchlist):
    connection = store.connect(":memory:")
    store.init_schema(connection)
    store.set_source_status(connection, "arxiv", "2026-W33", "ok", "")
    store.set_source_status(connection, "hn", "2026-W33", "failed", "read timeout")
    metrics = [
        dict(tech_id="autonomous_trucking", week="2026-W33", momentum=2.4, sai=0.9,
             lfi=0.6, adoption=14, adoption_new=2, stage_idea=0.2, stage_experiment=0.4,
             stage_investment=0.9, stage_deployment=1.2, stage_diffusion=0.5,
             position=3.8, lexicon_version=3),
        dict(tech_id="warehouse_robotics", week="2026-W33", momentum=-0.5, sai=-1.3,
             lfi=-0.4, adoption=9, adoption_new=0, stage_idea=1.1, stage_experiment=0.8,
             stage_investment=0.1, stage_deployment=-0.2, stage_diffusion=0.0,
             position=2.1, lexicon_version=3),
        dict(tech_id="quiet_tech", week="2026-W33", momentum=None, sai=None, lfi=None,
             adoption=0, adoption_new=0, stage_idea=None, stage_experiment=None,
             stage_investment=None, stage_deployment=None, stage_diffusion=None,
             position=None, lexicon_version=3),
    ]
    for row in metrics:
        store.upsert_metrics(connection, row)
    yield connection
    connection.close()


def test_context_ranks_movers_by_momentum(conn, watchlist):
    context = render.build_context(conn, "2026-W33", watchlist)
    assert [mover["name"] for mover in context["movers"]] == [
        "Autonomous trucking", "Warehouse robotics"
    ]


def test_context_excludes_warming_up_technologies_from_movers(conn, watchlist):
    context = render.build_context(conn, "2026-W33", watchlist)
    assert "Quiet tech" not in [mover["name"] for mover in context["movers"]]
    assert "Quiet tech" in context["warming_up"]


def test_context_reports_source_health(conn, watchlist):
    context = render.build_context(conn, "2026-W33", watchlist)
    statuses = {source["name"]: source["status"] for source in context["sources"]}
    assert statuses == {"arxiv": "ok", "hn": "failed"}


def test_render_writes_a_file_containing_every_block(conn, watchlist, tmp_path):
    path = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "dashboard.html")
    html = path.read_text()
    for block in [
        "Source health", "This Week's Movers", "Stage Board",
        "Substance vs. Attention", "Lab &rarr; Field", "Build Map", "Rising Terms",
    ]:
        assert block in html


def test_rendered_page_has_no_external_resources(conn, watchlist, tmp_path):
    path = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "dashboard.html")
    html = path.read_text()
    external = re.findall(r'(?:src|href)="https?://[^"]+"', html)
    assert external == []


def test_rendered_page_states_the_lexicon_version(conn, watchlist, tmp_path):
    path = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "dashboard.html")
    assert "lexicon v3" in path.read_text()


def test_rendered_page_escapes_technology_names(conn, tmp_path):
    hostile = Watchlist(version=1, technologies=(tech("x", "<script>alert(1)</script>"),))
    connection = store.connect(":memory:")
    store.init_schema(connection)
    store.upsert_metrics(connection, dict(
        tech_id="x", week="2026-W33", momentum=1.0, sai=0.0, lfi=0.0, adoption=0,
        adoption_new=0, stage_idea=0.0, stage_experiment=0.0, stage_investment=0.0,
        stage_deployment=0.0, stage_diffusion=0.0, position=3.0, lexicon_version=1))
    path = render.render_dashboard(connection, "2026-W33", hostile, tmp_path / "d.html")
    html = path.read_text()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    connection.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'observatory.render'`

- [ ] **Step 3: Write the template**

Create `observatory/templates/dashboard.html.j2`:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Supply Chain Innovation Observatory &middot; {{ week }}</title>
<style>
  :root { --ink: #1d2125; --muted: #6b7580; --rule: #e3e6e9; --bg: #ffffff;
          --up: #1f7a4d; --down: #a33a3a; }
  body { margin: 0; background: var(--bg); color: var(--ink);
         font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }
  main { max-width: 1080px; margin: 0 auto; padding: 32px 24px 96px; }
  h1 { font-size: 26px; margin: 0 0 4px; letter-spacing: -0.01em; }
  h2 { font-size: 17px; margin: 44px 0 12px; padding-bottom: 8px;
       border-bottom: 1px solid var(--rule); }
  .sub { color: var(--muted); margin: 0 0 24px; font-size: 13px; }
  .health { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 8px; padding: 0; list-style: none; }
  .chip { font-size: 12px; padding: 3px 10px; border-radius: 999px; border: 1px solid var(--rule); }
  .chip.ok { background: #edf7f1; border-color: #cfe8db; }
  .chip.stale { background: #fdf6e8; border-color: #f0e0bb; }
  .chip.failed { background: #fbeeee; border-color: #eccccc; }
  table { border-collapse: collapse; width: 100%; font-size: 14px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--rule); }
  th { font-weight: 600; color: var(--muted); font-size: 12px;
       text-transform: uppercase; letter-spacing: 0.04em; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  .up { color: var(--up); } .down { color: var(--down); }
  .empty { color: var(--muted); font-style: italic; }
  footer { margin-top: 56px; color: var(--muted); font-size: 12px;
           border-top: 1px solid var(--rule); padding-top: 16px; }
</style>
</head>
<body>
<main>
  <h1>Supply Chain Innovation Observatory</h1>
  <p class="sub">Week {{ week }} &middot; generated {{ generated_for }} &middot; lexicon v{{ lexicon_version }}</p>

  <h2>Source health</h2>
  <ul class="health">
    {% for source in sources %}
      <li class="chip {{ source.status }}" title="{{ source.note }}">{{ source.name }}</li>
    {% else %}
      <li class="empty">No sources have run yet.</li>
    {% endfor %}
  </ul>

  <h2>This Week's Movers</h2>
  {% if movers %}
  <table>
    <thead><tr><th>Technology</th><th>Family</th><th class="num">Momentum</th>
      <th class="num">Substance</th><th class="num">Lab&nbsp;&rarr;&nbsp;Field</th>
      <th class="num">Adopters</th></tr></thead>
    <tbody>
    {% for mover in movers %}
      <tr>
        <td>{{ mover.name }}</td>
        <td>{{ mover.family }}</td>
        <td class="num {{ 'up' if mover.momentum > 0 else 'down' }}">{{ '%+.2f'|format(mover.momentum) }}</td>
        <td class="num">{{ '%+.2f'|format(mover.sai) if mover.sai is not none else '—' }}</td>
        <td class="num">{{ '%+.2f'|format(mover.lfi) if mover.lfi is not none else '—' }}</td>
        <td class="num">{{ mover.adoption }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p class="empty">Not enough history yet to rank movers.</p>
  {% endif %}

  <h2>Stage Board</h2>
  <p class="sub">Horizontal: position in the pipeline, 1 = idea to 5 = diffusion. Vertical: momentum.</p>
  {{ stage_board_svg }}

  <h2>Substance vs. Attention</h2>
  <p class="sub">Above the line, more building than talking.</p>
  {{ substance_svg }}

  <h2>Lab &rarr; Field Watch</h2>
  {% if crossovers %}
  <table>
    <thead><tr><th>Technology</th><th class="num">Lab&nbsp;&rarr;&nbsp;Field</th><th>Trend</th></tr></thead>
    <tbody>
    {% for row in crossovers %}
      <tr><td>{{ row.name }}</td><td class="num">{{ '%+.2f'|format(row.lfi) }}</td><td>{{ row.spark }}</td></tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p class="empty">No technology has crossed into deployment this week.</p>
  {% endif %}

  <h2>Build Map</h2>
  <p class="empty">Arrives with the USAspending collector in the next phase.</p>

  <h2>Rising Terms</h2>
  <p class="empty">Arrives with the discovery step in the next phase.</p>

  {% if warming_up %}
  <footer>
    Warming up (fewer than 12 weeks of history, no scores yet):
    {{ warming_up|join(', ') }}
  </footer>
  {% endif %}
</main>
</body>
</html>
```

- [ ] **Step 4: Write the renderer**

Create `observatory/render.py`:

```python
"""Dashboard rendering.

One self-contained HTML file: inline CSS, inline SVG, no scripts, no network at
view time. It has to open by double-click in five years and still work.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from . import charts, config, store

TEMPLATE_DIR = Path(__file__).parent / "templates"
FAMILY_COLOURS = {
    "automation": "#5b7fa6",
    "vehicles": "#8a6fa8",
    "digital": "#3f8f7a",
    "traceability": "#b5854b",
    "physical": "#a35f6d",
    "networks": "#5f7355",
}
MOVER_COUNT = 5


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def build_context(conn, week: str, watchlist) -> dict:
    names = {tech.id: tech.name for tech in watchlist.technologies}
    families = {tech.id: tech.family for tech in watchlist.technologies}
    rows = store.metrics_for_week(conn, week)

    scored = [row for row in rows if row.get("momentum") is not None]
    warming = [names.get(row["tech_id"], row["tech_id"]) for row in rows
               if row.get("momentum") is None]
    scored.sort(key=lambda row: row["momentum"], reverse=True)

    movers = [
        {
            "name": names.get(row["tech_id"], row["tech_id"]),
            "family": families.get(row["tech_id"], ""),
            "momentum": row["momentum"],
            "sai": row["sai"],
            "lfi": row["lfi"],
            "adoption": row["adoption"] or 0,
        }
        for row in scored[:MOVER_COUNT]
    ]

    stage_points = [
        charts.Point(
            x=row["position"], y=row["momentum"],
            label=f"{names.get(row['tech_id'], row['tech_id'])} "
                  f"(position {row['position']:.1f}, momentum {row['momentum']:+.2f})",
            colour=FAMILY_COLOURS.get(families.get(row["tech_id"], ""), "#5b7fa6"),
        )
        for row in scored if row.get("position") is not None
    ]

    substance_points = [
        charts.Point(
            x=row["sai"], y=row["lfi"],
            label=f"{names.get(row['tech_id'], row['tech_id'])} "
                  f"(substance {row['sai']:+.2f}, lab-to-field {row['lfi']:+.2f})",
            colour=FAMILY_COLOURS.get(families.get(row["tech_id"], ""), "#5b7fa6"),
        )
        for row in rows if row.get("sai") is not None and row.get("lfi") is not None
    ]

    crossovers = [
        {
            "name": names.get(row["tech_id"], row["tech_id"]),
            "lfi": row["lfi"],
            "spark": Markup(charts.sparkline(_lfi_history(conn, row["tech_id"], week))),
        }
        for row in rows if (row.get("lfi") or 0) > 0
    ]
    crossovers.sort(key=lambda row: row["lfi"], reverse=True)

    return {
        "week": week,
        "generated_for": dt.date.today().isoformat(),
        "lexicon_version": watchlist.version,
        "sources": store.source_statuses(conn),
        "movers": movers,
        "stage_board_svg": Markup(
            charts.scatter(stage_points, x_label="Pipeline position", y_label="Momentum")
        ),
        "substance_svg": Markup(
            charts.scatter(substance_points, x_label="Substance minus attention",
                           y_label="Lab to field")
        ),
        "crossovers": crossovers,
        "warming_up": sorted(warming),
    }


def _lfi_history(conn, tech_id: str, week: str, weeks: int = 12) -> list[float | None]:
    wanted = set(config.trailing_weeks(week, weeks))
    rows = conn.execute(
        "SELECT week, lfi FROM weekly_metrics WHERE tech_id = ? ORDER BY week", (tech_id,)
    ).fetchall()
    by_week = {row["week"]: row["lfi"] for row in rows if row["week"] in wanted}
    return [by_week.get(w) for w in config.trailing_weeks(week, weeks)]


def render_dashboard(conn, week: str, watchlist, out_path: Path | None = None) -> Path:
    context = build_context(conn, week, watchlist)
    html = _environment().get_template("dashboard.html.j2").render(**context)
    target = Path(out_path) if out_path else config.OUTPUT_DIR / f"dashboard-{week}.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html)
    if out_path is None:
        (config.OUTPUT_DIR / "latest.html").write_text(html)
    return target
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_render.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add observatory/render.py observatory/templates tests/test_render.py
git commit -m "feat: self-contained HTML dashboard renderer"
```

---

### Task 14: Orchestration, CLI, and the guardrail tests

**Files:**
- Create: `observatory/run.py`, `README.md`
- Test: `tests/test_run.py`, `tests/test_guardrails.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `COLLECTORS: tuple[BaseCollector, ...]`; `fetch_week(conn, week, collectors, session) -> set[str]` returning the names of sources that succeeded; `sources_with_raw(week, collectors) -> set[str]`; `ingest_week(conn, week, watchlist, collectors) -> int`; `score_week(conn, week, watchlist) -> int`; `run_week(conn, week, watchlist, collectors=COLLECTORS, session=None, skip_fetch=False, out_path=None) -> Path`; `main(argv=None) -> int`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_run.py`:

```python
import json

import pytest

from observatory import http, run, store
from observatory.collectors.base import BaseCollector, Document, RawPage
from observatory.matcher import Technology, Watchlist


class StubCollector(BaseCollector):
    name = "stub"

    def __init__(self, pages, documents):
        self._pages = pages
        self._documents = documents

    def fetch_raw(self, session, week):
        yield from self._pages

    def parse(self, text):
        return self._documents


class ExplodingCollector(BaseCollector):
    name = "boom"

    def fetch_raw(self, session, week):
        raise http.HttpError("service unavailable")
        yield  # pragma: no cover

    def parse(self, text):
        return []


@pytest.fixture()
def watchlist():
    return Watchlist(version=1, technologies=(
        Technology(id="autonomous_trucking", name="Autonomous trucking", family="vehicles",
                   include=("autonomous truck(s|ing)?",), exclude=(), status="active",
                   added_week="2020-W01", patterns_changed_week="2020-W01"),
    ))


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(run.base.config, "RAW_DIR", tmp_path / "raw")
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def stub():
    page = RawPage(url="https://x.test/1", status=200, text=json.dumps({"ok": 1}))
    document = Document(doc_id="d1", date="2026-08-12",
                        title="Autonomous trucking corridor opens",
                        text="", url="https://x.test/a")
    return StubCollector([page], [document])


def test_fetch_week_writes_raw_and_marks_the_source_ok(conn, tmp_path):
    ok = run.fetch_week(conn, "2026-W33", [stub()], session=None)
    assert ok == {"stub"}
    written = list((tmp_path / "raw" / "2026-W33" / "stub").iterdir())
    assert len(written) == 1


def test_fetch_week_isolates_a_failing_collector(conn):
    ok = run.fetch_week(conn, "2026-W33", [stub(), ExplodingCollector()], session=None)
    assert ok == {"stub"}
    statuses = {row["name"]: row for row in store.source_statuses(conn)}
    assert statuses["boom"]["status"] == "failed"
    assert "service unavailable" in statuses["boom"]["note"]


def test_ingest_week_turns_raw_files_into_observations(conn, watchlist):
    run.fetch_week(conn, "2026-W33", [stub()], session=None)
    assert run.ingest_week(conn, "2026-W33", watchlist, [stub()]) == 1
    rows = store.observations_for(conn, "2026-W33", "autonomous_trucking")
    assert rows[0]["matched_pattern"] == "autonomous truck(s|ing)?"


def test_ingest_week_is_idempotent(conn, watchlist):
    run.fetch_week(conn, "2026-W33", [stub()], session=None)
    run.ingest_week(conn, "2026-W33", watchlist, [stub()])
    assert run.ingest_week(conn, "2026-W33", watchlist, [stub()]) == 0


def test_run_week_produces_a_dashboard_file(conn, watchlist, tmp_path):
    output = tmp_path / "dashboard.html"
    result = run.run_week(conn, "2026-W33", watchlist, [stub()],
                          session=None, out_path=output)
    assert result.exists()
    assert "Supply Chain Innovation Observatory" in result.read_text()


def test_running_the_same_week_twice_gives_identical_metrics(conn, watchlist, tmp_path):
    run.run_week(conn, "2026-W33", watchlist, [stub()], session=None,
                 out_path=tmp_path / "a.html")
    first = store.metrics_for_week(conn, "2026-W33")
    run.run_week(conn, "2026-W33", watchlist, [stub()], session=None,
                 skip_fetch=True, out_path=tmp_path / "b.html")
    assert store.metrics_for_week(conn, "2026-W33") == first
```

Create `tests/test_guardrails.py`:

```python
"""These tests protect the two rules the whole design rests on."""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "observatory"
BANNED_AT_RUNTIME = {"anthropic", "openai", "observatory.lexicon"}
ENTRY_POINT = "run"


def _imports(path: Path) -> set[str]:
    """Module names imported by one file.

    Relative imports matter here: `from . import config` and `from .. import http`
    both arrive with node.module set to None, and missing them would let the
    guardrail walk stop at run.py and pass vacuously.
    """
    tree = ast.parse(path.read_text())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.add(node.module)
                found.update(f"{node.module}.{alias.name}" for alias in node.names)
            else:
                found.update(alias.name for alias in node.names)
    return found


def _reachable_modules(entry: str) -> set[str]:
    seen: set[str] = set()
    queue = [entry]
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        path = PACKAGE / f"{name.replace('.', '/')}.py"
        if not path.exists():
            continue
        for imported in _imports(path):
            local = imported.lstrip(".")
            if (PACKAGE / f"{local.replace('.', '/')}.py").exists():
                queue.append(local)
    return seen


def test_the_module_walk_actually_reaches_the_pipeline():
    """Without this, a broken walk would make the guardrail below pass vacuously."""
    reachable = _reachable_modules(ENTRY_POINT)
    assert {"config", "store", "matcher", "metrics", "normalize", "render",
            "collectors.arxiv"} <= reachable


def test_the_weekly_run_never_imports_a_model_client():
    for module in _reachable_modules(ENTRY_POINT):
        path = PACKAGE / f"{module.replace('.', '/')}.py"
        if not path.exists():
            continue
        offenders = _imports(path) & BANNED_AT_RUNTIME
        assert not offenders, f"{module} imports {offenders} — the weekly run must stay deterministic"


def test_no_module_in_the_package_imports_pandas_or_numpy():
    for path in PACKAGE.rglob("*.py"):
        imported = _imports(path)
        assert "pandas" not in imported and "numpy" not in imported, path
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_run.py tests/test_guardrails.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'observatory.run'`

- [ ] **Step 3: Write the implementation**

Create `observatory/run.py`:

```python
"""Orchestration and CLI.

Order is fixed: fetch every source to disk, then parse and match from disk, then
aggregate, then score, then render. A collector failure is contained to its own
source and never stops the run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config, http, matcher, metrics, normalize, render, store
from .collectors import base
from .collectors.arxiv import ArxivCollector
from .collectors.federalregister import FederalRegisterCollector
from .collectors.hn import HackerNewsCollector

COLLECTORS = (ArxivCollector(), HackerNewsCollector(), FederalRegisterCollector())


def fetch_week(conn, week: str, collectors, session) -> set[str]:
    succeeded: set[str] = set()
    for collector in collectors:
        try:
            for index, page in enumerate(collector.fetch_raw(session, week)):
                path = base.write_raw(collector.name, week, index, page)
                store.record_raw(conn, collector.name, week, page.url, page.status, str(path))
            store.set_source_status(conn, collector.name, week, "ok", "")
            succeeded.add(collector.name)
        except Exception as error:  # one bad source must not end the run
            store.set_source_status(conn, collector.name, week, "failed", str(error))
            print(f"  ! {collector.name} failed: {error}", file=sys.stderr)
    return succeeded


def sources_with_raw(week: str, collectors) -> set[str]:
    return {
        collector.name
        for collector in collectors
        if any(base.read_raw(collector.name, week))
    }


def ingest_week(conn, week: str, watchlist, collectors) -> int:
    inserted = 0
    for collector in collectors:
        for path, text in base.read_raw(collector.name, week):
            raw_ref = _raw_ref(conn, str(path))
            for document in collector.parse(text):
                inserted += store.upsert_observations(
                    conn,
                    matcher.observations_for_document(
                        watchlist, document, collector.name, week, raw_ref
                    ),
                )
    return inserted


def _raw_ref(conn, path: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM raw_fetch WHERE path = ? ORDER BY id DESC LIMIT 1", (path,)
    ).fetchone()
    return None if row is None else int(row["id"])


def score_week(conn, week: str, watchlist) -> int:
    rows = metrics.compute_week(conn, week, watchlist)
    for row in rows:
        store.upsert_metrics(conn, row)
    return len(rows)


def run_week(
    conn,
    week: str,
    watchlist,
    collectors=COLLECTORS,
    session=None,
    skip_fetch: bool = False,
    out_path: Path | None = None,
) -> Path:
    if skip_fetch:
        ok_sources = sources_with_raw(week, collectors)
        print(f"Skipping fetch; replaying raw for {sorted(ok_sources)}")
    else:
        print(f"Fetching {week}")
        ok_sources = fetch_week(conn, week, collectors, session)

    observations = ingest_week(conn, week, watchlist, collectors)
    signals = normalize.compute_signals(conn, week, watchlist, ok_sources)
    scored = score_week(conn, week, watchlist)
    path = render.render_dashboard(conn, week, watchlist, out_path)

    _append_run_log(week, ok_sources, observations, signals, scored, path)
    print(
        f"{week}: {observations} new observations, {signals} signals, "
        f"{scored} scored -> {path}"
    )
    return path


def _append_run_log(week, ok_sources, observations, signals, scored, path) -> None:
    config.RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with config.RUN_LOG_PATH.open("a") as handle:
        handle.write(json.dumps({
            "week": week,
            "ok_sources": sorted(ok_sources),
            "new_observations": observations,
            "signals_written": signals,
            "technologies_scored": scored,
            "output": str(path),
        }) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="observatory.run")
    parser.add_argument("--week", default=None, help="ISO week, e.g. 2026-W33")
    parser.add_argument("--skip-fetch", action="store_true",
                        help="recompute from raw files already on disk")
    parser.add_argument("--rebuild", action="store_true",
                        help="recompute every week that has raw data")
    parser.add_argument("--only", default=None, help="run a single collector by name")
    args = parser.parse_args(argv)

    config.load_dotenv()
    watchlist = matcher.load_watchlist()
    collectors = COLLECTORS
    if args.only:
        collectors = tuple(c for c in COLLECTORS if c.name == args.only)
        if not collectors:
            parser.error(f"unknown collector {args.only!r}")

    conn = store.connect()
    store.init_schema(conn)
    try:
        if args.rebuild:
            weeks = sorted(p.name for p in config.RAW_DIR.glob("*-W*") if p.is_dir())
            for week in weeks:
                run_week(conn, week, watchlist, collectors, skip_fetch=True)
            return 0
        week = args.week or config.current_week()
        session = None if args.skip_fetch else http.make_session()
        run_week(conn, week, watchlist, collectors, session=session,
                 skip_fetch=args.skip_fetch)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Write the README**

Create `README.md`:

```markdown
# Supply Chain Innovation Observatory

A weekly dashboard that tracks supply chain technologies moving from idea to
experimentation, investment, deployment, and diffusion — built entirely from
public data.

## Setup

    python -m pip install -e ".[dev]"
    cp .env.example .env      # then fill in SEC_CONTACT_EMAIL

## Run a week

    python -m observatory.run

Other forms:

    python -m observatory.run --week 2026-W33   # a specific week
    python -m observatory.run --skip-fetch      # recompute from saved raw files
    python -m observatory.run --rebuild         # recompute all weeks from raw
    python -m observatory.run --only arxiv      # a single collector

Output lands in `output/latest.html` — one self-contained file, no server needed.

## Design rules

1. **No LLM in the weekly run.** Scoring and matching are deterministic, so any
   week recomputes identically. A test enforces this.
2. **No paid data sources.**
3. **Raw before parse.** Responses are written to `data/raw/` before parsing, so
   a parser fix never costs a re-fetch.
4. **A missing week is not a zero week.** Failed sources carry forward.

Full design: `docs/superpowers/specs/2026-08-16-supply-chain-innovation-observatory-design.md`

## Weekly cron (optional, not installed)

    0 7 * * MON cd /path/to/repo && /usr/bin/python3 -m observatory.run >> data/cron.log 2>&1

## Tests

    python -m pytest
```

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -v`
Expected: all tests pass, including the three guardrail tests

- [ ] **Step 6: Run it for real against live sources**

Run: `python -m observatory.run --week 2026-W33`
Expected: three sources report `ok`, a nonzero observation count, and `output/latest.html` written. Open it and confirm the source-health chips are green and the "warming up" footer lists every technology (correct — there is no history yet).

- [ ] **Step 7: Commit**

```bash
git add observatory/run.py README.md tests/test_run.py tests/test_guardrails.py
git commit -m "feat: weekly run orchestration, CLI, and determinism guardrails"
```

---

## What this plan does not cover

Carried to the second plan, in this order:

1. **GDELT** doc and geo collectors — media volume, deployment lexicon, map points.
2. **USAspending** — federal obligations, award counts, place-of-performance geocoding against a bundled Census ZCTA centroid table.
3. **SEC EDGAR** full-text search — filings and distinct-filer adoption counts.
4. **GitHub** — new repos, stars, commits, with `GITHUB_TOKEN`.
5. **PatentsView** — granted patents, with `PATENTSVIEW_API_KEY`.
6. **Build Map** and **evidence drill-down** (`evidence.html`) blocks.
7. **`discover.py`** — rising-term extraction into `candidate_terms`.
8. **`lexicon.py`** — the offline LLM authoring CLI (`propose`, `triage`, `diff`), `lexicon/CHANGELOG.md`, and the `patterns_changed_week` bump workflow.
9. **Backfill** — `--rebuild` across the trailing 52 weeks for the sources that support historical queries.
