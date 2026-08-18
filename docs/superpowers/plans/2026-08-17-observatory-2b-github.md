# Observatory 2B — The Developer Signal

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Answer "what are developers actually building?" by counting new public repositories per technology, per week — the one signal in the project that moves in days rather than quarters.

**Architecture:** One more collector following the established contract: fetch raw to disk, parse purely from text. GitHub's repository search accepts a `created:` date range, so unlike every other source added so far this one backfills a full year in a single pass.

**Tech Stack:** Python 3.11+, `requests`, `PyYAML`, `Jinja2`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-08-16-supply-chain-innovation-observatory-design.md`

**Predecessors:** the core pipeline, 2A (keyless signals), and 2C (backfill, discovery, lexicon) — all merged to `main`.

## Scope

**In:** the GitHub repository-search collector feeding `gh_repos_new`, registered into the weekly run, backfilled across 52 weeks.

**Out, and why:**

- **PatentsView** — the key has been requested but not issued. It gets its own plan when it arrives rather than sitting as a deferred task; the GDELT deferral in 2A showed what that costs.
- **`gh_commits`** — `/repos/{owner}/{repo}/stats/commit_activity` returns **HTTP 202** while GitHub computes the statistics (confirmed live on 2026-08-17), so it needs polling, and `http.fetch` currently treats only 200 as success. It also returns all 52 weeks in one response, which fits awkwardly into a per-week fetch model. Both are solvable; neither is solvable in passing.
- **`gh_stars_delta`** — GitHub exposes only a repository's *current* star count, so a weekly delta cannot be reconstructed historically. It can only accrue forward from stored snapshots. This collector stores the star count on every observation so that work is possible later without a re-fetch.

`metrics.mean_of_present` averages whatever signals are present, so the Experiment stage scores correctly on `gh_repos_new` alone.

## Global Constraints

- Python 3.11 or newer; `X | None` type syntax throughout.
- Dependencies limited to `requests`, `PyYAML`, `Jinja2`, `pytest`. No numpy, no pandas.
- **No LLM importable from the weekly run.** `tests/test_guardrails.py` walks the import graph from `run.py`.
- **No network in the test suite.** The fixture is captured live once, by hand, and committed.
- **Raw before parse.** `fetch_raw` writes untouched response bodies before anything is parsed.
- **The token never reaches disk or a log.** It goes in an `Authorization` header, never a query parameter — `raw_fetch` records resolved URLs and a token in a URL would be written to the database and the raw tree.
- A missing week is not a zero week; observation week comes from the document's own date.
- Commit after every task, conventional-commit prefixes.

---

### Task 1: The GitHub collector

**Files:**
- Create: `observatory/collectors/github.py`, `tests/fixtures/github_page.json`
- Test: `tests/test_collector_github.py`

**Interfaces:**
- Consumes: `base.BaseCollector`, `base.Document`, `base.RawPage`, `http.fetch`, `http.RateLimiter`, `config.week_bounds`, `config.LOOKBACK_DAYS`, `config.require_env`.
- Produces: `GithubCollector` with `name = "github"`, `ANCHOR_QUERIES`, `date_range(week) -> str`, `auth_headers() -> dict`, `fetch_raw(session, week)`, `parse(text) -> list[Document]`. Document `doc_id` is `github:<full_name>`, `date` is the repository's `created_at` date, `amount` is `stargazers_count`, `text` carries the description and language.

- [ ] **Step 1: Capture the fixture from the live API**

The token is in `.env` as `GITHUB_TOKEN`. **Never print it, never paste it into a file, never pass it as a URL parameter.**

```bash
python3 - <<'PY'
import os, json, requests
from observatory import config
config.load_dotenv()
s = requests.Session()
s.headers.update({"User-Agent": config.user_agent(),
                  "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                  "Accept": "application/vnd.github+json"})
r = s.get("https://api.github.com/search/repositories",
          params={"q": "supply chain created:2026-08-03..2026-08-16",
                  "per_page": 20, "sort": "stars", "order": "desc"}, timeout=30)
print(r.status_code, r.json().get("total_count"))
open("tests/fixtures/github_page.json", "w").write(json.dumps(r.json(), indent=1))
PY
python3 -m json.tool tests/fixtures/github_page.json | head -40
```

Read what came back. The expected shape is `{"total_count": N, "incomplete_results": false, "items": [{"full_name", "html_url", "description", "created_at", "stargazers_count", "language", ...}]}`. **If the real shape differs, the real shape wins** — build the parser against it and note the difference in your report.

Trim the fixture to about six repositories, keeping at least one whose `description` is `null` and one whose `language` is `null`; both are common and both must parse. If the capture contains neither, edit one entry to have them and say so in your report.

**Check the committed fixture contains no token** before you commit it — search it for `ghp_`, `github_pat_`, and `Authorization`.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_collector_github.py`:

```python
import json
from pathlib import Path

from observatory.collectors.github import GithubCollector

FIXTURE = Path(__file__).parent / "fixtures" / "github_page.json"


def test_parse_returns_a_document_per_repository():
    documents = GithubCollector().parse(FIXTURE.read_text())
    assert documents
    assert all(doc.doc_id.startswith("github:") for doc in documents)


def test_doc_id_is_the_full_name_so_a_repo_counts_once():
    first = GithubCollector().parse(FIXTURE.read_text())[0]
    assert first.doc_id == f"github:{first.title}"
    assert "/" in first.title


def test_created_at_becomes_the_document_date():
    for doc in GithubCollector().parse(FIXTURE.read_text()):
        assert doc.date is None or (len(doc.date) == 10 and doc.date[4] == "-")


def test_star_count_lands_in_amount():
    for doc in GithubCollector().parse(FIXTURE.read_text()):
        assert doc.amount is None or isinstance(doc.amount, float)


def test_description_and_language_are_searchable_body():
    documents = GithubCollector().parse(FIXTURE.read_text())
    assert any(doc.text for doc in documents)


def test_a_null_description_does_not_crash_or_become_the_string_none():
    payload = json.dumps({"items": [{
        "full_name": "acme/thing", "html_url": "https://github.com/acme/thing",
        "description": None, "language": None,
        "created_at": "2026-08-12T10:00:00Z", "stargazers_count": 4,
    }]})
    doc = GithubCollector().parse(payload)[0]
    assert doc.text == ""
    assert "None" not in (doc.text or "")


def test_items_without_a_full_name_are_skipped():
    payload = json.dumps({"items": [{"html_url": "https://github.com/x"}]})
    assert GithubCollector().parse(payload) == []


def test_parse_handles_an_empty_result_set():
    assert GithubCollector().parse(json.dumps({"items": []})) == []


def test_date_range_covers_the_week_plus_the_lookback():
    assert GithubCollector().date_range("2026-W33") == "created:2026-08-03..2026-08-16"


def test_auth_headers_carry_a_bearer_token_and_never_a_url_parameter(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-value")
    headers = GithubCollector().auth_headers()
    assert headers["Authorization"] == "Bearer test-token-value"
    assert headers["Accept"] == "application/vnd.github+json"


def test_the_committed_fixture_contains_no_credential():
    text = FIXTURE.read_text()
    for marker in ("ghp_", "github_pat_", "Authorization", "Bearer "):
        assert marker not in text, f"fixture leaks {marker}"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/test_collector_github.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'observatory.collectors.github'`

- [ ] **Step 4: Implement**

Create `observatory/collectors/github.py`:

```python
"""GitHub repository search — the Experiment stage's developer signal.

The one source in this project that moves in days. A patent lags eighteen
months and an SEC filing a quarter; a repository appears the week someone
starts building.

Unlike every other collector here, GitHub's search accepts an explicit
`created:` range, so this one backfills a year of history as readily as it
fetches the current week.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Iterator

from .. import config, http
from .base import BaseCollector, Document, RawPage

API_URL = "https://api.github.com/search/repositories"
PAGE_SIZE = 100
MAX_PAGES = 5

# Broad sweeps rather than one query per technology: the request count stays
# flat as the watchlist grows, and the matcher does the narrowing — the same
# shape as the arXiv and Hacker News collectors.
ANCHOR_QUERIES = (
    "supply chain",
    "logistics",
    "warehouse automation",
    "freight",
    "inventory management",
    "procurement",
)


class GithubCollector(BaseCollector):
    name = "github"
    rate_limit_seconds = 2.5  # authenticated search allows 30/minute

    def date_range(self, week: str) -> str:
        start, end = config.week_bounds(week)
        start -= dt.timedelta(days=config.LOOKBACK_DAYS)
        return f"created:{start.isoformat()}..{end.isoformat()}"

    def auth_headers(self) -> dict:
        """The token goes in a header, never a query parameter.

        `raw_fetch` records the resolved URL of every request, so a token in
        the query string would be written to the database and the raw tree.
        """
        return {
            "Authorization": f"Bearer {config.require_env('GITHUB_TOKEN')}",
            "Accept": "application/vnd.github+json",
        }

    def fetch_raw(self, session, week: str) -> Iterator[RawPage]:
        limiter = http.RateLimiter(self.rate_limit_seconds)
        headers = self.auth_headers()
        window = self.date_range(week)
        for query in ANCHOR_QUERIES:
            for page in range(1, MAX_PAGES + 1):
                params = {
                    "q": f"{query} {window}",
                    "per_page": PAGE_SIZE,
                    "page": page,
                    "sort": "stars",
                    "order": "desc",
                }
                response = http.fetch(session, API_URL, params=params,
                                      headers=headers, limiter=limiter)
                yield RawPage(response.url, response.status, response.text, "json")
                if len(self.parse(response.text)) < PAGE_SIZE:
                    break

    def parse(self, text: str) -> list[Document]:
        payload = json.loads(text or "{}")
        documents = []
        for item in payload.get("items", []) or []:
            full_name = item.get("full_name")
            if not full_name:
                continue
            body = " ".join(
                part for part in (item.get("description"), item.get("language")) if part
            )
            documents.append(
                Document(
                    doc_id=f"github:{full_name}",
                    date=(item.get("created_at") or "")[:10] or None,
                    title=full_name,
                    text=body,
                    url=item.get("html_url"),
                    amount=float(item.get("stargazers_count") or 0),
                )
            )
        return documents
```

Note what `text` carries: a repository has no abstract, so the description and language are all the matcher gets. That is thin, and it is why the anchor queries matter — a repo surfaced by the "warehouse automation" sweep whose description says "AMR fleet controller" still needs the watchlist's own patterns to match it.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_collector_github.py -v`
Expected: all pass. If a test fails because the captured fixture differs from this plan's sketch, fix the *parser* to match reality and adjust the expectation to the real data — never edit the fixture to suit a wrong parser.

- [ ] **Step 6: Commit**

```bash
git add observatory/collectors/github.py tests/test_collector_github.py tests/fixtures/github_page.json
git commit -m "feat: GitHub repository-search collector for the developer signal"
```

---

### Task 2: Register it and run the pipeline for real

**Files:**
- Modify: `observatory/run.py`, `observatory/normalize.py`, `.env.example`
- Test: `tests/test_run.py`

**Interfaces:**
- Produces: `COLLECTORS` becomes six; `AGGREGATIONS` gains `Aggregation("gh_repos_new", "github", "count")`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_run.py`, update the collector-name set to include `"github"`, and remove `"gh_repos_new"` from `DEFERRED_SIGNALS` so the signal-coverage test now requires it. Those two edits are forced by this task; the other assertions stay exactly as they are.

Then append:

```python
def test_github_is_registered_and_produces_its_signal():
    from observatory import normalize

    assert "github" in {collector.name for collector in run.COLLECTORS}
    sources = {aggregation.source for aggregation in normalize.AGGREGATIONS}
    assert "github" in sources
    signals = {a.signal for a in normalize.AGGREGATIONS if a.source == "github"}
    assert signals == {"gh_repos_new"}


def test_the_remaining_deferred_signals_are_only_the_unbuilt_ones():
    """Keeps the allowance honest — it must shrink as collectors land."""
    assert DEFERRED_SIGNALS == {"patents", "gh_commits", "gh_stars_delta"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_run.py -v`
Expected: the collector-set and signal-coverage assertions fail — `github` is not registered and `gh_repos_new` has no aggregation.

- [ ] **Step 3: Implement**

In `observatory/normalize.py`, add to `AGGREGATIONS`:

```python
    Aggregation("gh_repos_new", "github", "count"),
```

In `observatory/run.py`, import `GithubCollector` and add it to `COLLECTORS`.

In `.env.example`, uncomment `GITHUB_TOKEN=` and add a comment naming where to get one and that it needs no scopes for public data.

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: all pass, including `tests/test_guardrails.py`.

- [ ] **Step 5: Run the current week for real**

Run: `python -m observatory.run`

Six sources now. Report per-source status, observation counts, and how many repositories matched a technology. **If GitHub returns 401 or 403, stop and report** — do not retry, and do not print the token or any header while diagnosing.

A low match count is a finding worth reporting honestly, not a failure to hide: repository descriptions are terse, and if the watchlist's patterns do not fit how developers name things, that is exactly what the owner needs to know.

- [ ] **Step 6: Commit**

```bash
git add observatory/run.py observatory/normalize.py .env.example tests/test_run.py
git commit -m "feat: register the GitHub collector"
```

---

### Task 3: Backfill GitHub and verify the Experiment stage

**Files:** none — this is an operational task with a written verification.

- [ ] **Step 1: Confirm resumption will fetch GitHub only**

Run:

```bash
python3 -c "
from observatory import run, store
conn = store.connect()
weeks = run.config.trailing_weeks(run.config.current_week(), 52)
pending = run.weeks_needing_fetch(conn, weeks, run.COLLECTORS)
print('weeks pending:', len(pending))
for week in pending[:3]:
    print(' ', week, '->', [c.name for c in run.collectors_needing_fetch(conn, week, run.COLLECTORS)])
"
```

Every pending week should list `github` and nothing else, except the handful of weeks where arXiv previously failed. Report what it printed.

- [ ] **Step 2: Estimate the runtime before starting it**

GitHub's authenticated search allows 30 requests per minute and the collector paces at 2.5 seconds. Work out the requests per week from `ANCHOR_QUERIES` and `MAX_PAGES`, multiply by the pending weeks, and report the estimate. Do not start until you have.

- [ ] **Step 3: Run the backfill**

```bash
python -m observatory.run --backfill 52
```

Watch the first few weeks. **If GitHub starts returning 403 with a rate-limit message, stop.** Secondary rate limits are enforced on sustained search traffic, and this project has already lost two collectors to exactly that pattern — GDELT is still unavailable and arXiv only tolerated three weeks of bulk fetching.

- [ ] **Step 4: Verify the Experiment stage came alive**

```bash
python3 -c "
from observatory import store
c = store.connect()
print('github observations:', c.execute(\"SELECT COUNT(*) FROM observations WHERE source='github'\").fetchone()[0])
print('weeks with gh_repos_new > 0:', c.execute(\"SELECT COUNT(DISTINCT week) FROM weekly_signals WHERE signal='gh_repos_new' AND value > 0\").fetchone()[0])
print()
for r in c.execute(\"SELECT tech_id, SUM(value) t FROM weekly_signals WHERE signal='gh_repos_new' GROUP BY tech_id HAVING t > 0 ORDER BY t DESC LIMIT 10\"):
    print(f'  {r[0]:<26} {r[1]:.0f} repos')
print()
print('stage_experiment now scored:', c.execute('SELECT COUNT(*) FROM weekly_metrics WHERE stage_experiment IS NOT NULL').fetchone()[0], 'rows')
"
```

Report the output. `stage_experiment` was `NULL` everywhere before this plan; if it is still `NULL`, say so plainly rather than reporting the task as done — that would mean GitHub observations exist but are not reaching the metric, which is a defect in the wiring, not a data characteristic.

- [ ] **Step 5: Record the outcome**

Add a short section to `README.md` covering: that GitHub needs a token with no scopes, that repository search backfills historically unlike the other collectors, and whatever the real match rate turned out to be.

```bash
git add README.md
git commit -m "docs: record the GitHub backfill outcome"
```

---

## What this plan does not cover

- **PatentsView** — its own plan when the key arrives, feeding `patents`.
- **`gh_commits`** — needs `http.fetch` widened to the 2xx range plus 202 polling, and a decision about a source whose single response covers 52 weeks.
- **`gh_stars_delta`** — impossible historically; this collector stores the star count on every observation so a forward-accruing delta can be built later without re-fetching.
