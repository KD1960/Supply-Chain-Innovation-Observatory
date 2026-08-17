# Observatory 2C — Backfill, Discovery, and the Lexicon Workflow

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the dashboard real history so it can actually score, surface the terms the watchlist is missing, and make improving the watchlist a reviewed workflow instead of guesswork.

**Architecture:** A resumable backfill fetches up to a year of raw data from the five working collectors and replays it through the existing rebuild path. A discovery module re-parses that raw — including documents that matched nothing — to find phrases rising sharply against their own baseline. A lexicon CLI packages those candidates into a request a human answers in a Claude session, then validates the resulting proposals before the human merges them by hand.

**Tech Stack:** Python 3.11+, `requests`, `PyYAML`, `Jinja2`, `pytest`. Standard-library `collections`, `re`, `json`. No numpy, no pandas.

**Spec:** `docs/superpowers/specs/2026-08-16-supply-chain-innovation-observatory-design.md`

**Predecessors:** `2026-08-16-observatory-core-pipeline.md` (complete) and `2026-08-16-observatory-2a-keyless-signals.md` (complete except its GDELT tasks 3 and 4).

## Why this plan matters more than its size suggests

Right now every technology on the dashboard reads "warming up". One week of data cannot produce a z-score, so momentum, substance-vs-attention, and lab-to-field are all `None` and every chart is empty. **Backfill is what turns the dashboard on.** All five working collectors accept a historical date window, so a year of history is available for the asking.

The second half addresses a defect the first live run exposed: nine of ten matches were off-concept, and USAspending's six keywords matched nothing at all. The watchlist is the weak link, and it is the owner's domain judgement — not an implementer's — that should fix it. Discovery finds what is being missed; the lexicon workflow turns that into reviewed patterns.

## Global Constraints

- Python 3.11 or newer; `X | None` type syntax throughout.
- Dependencies limited to `requests`, `PyYAML`, `Jinja2`, `pytest`. No numpy, no pandas.
- **No LLM importable from the weekly run.** `tests/test_guardrails.py` walks the import graph from `run.py` and bans `anthropic`, `openai`, and `lexicon`. `observatory/lexicon.py` must stay unreachable from `run.py`; `observatory/discover.py` is reachable and must contain no model call of any kind.
- **The pipeline never edits `watchlist.yaml`.** Spec §4 and §5.1 are explicit: proposals are written to a separate file and merging is a human edit reviewed as a normal diff. The lexicon tool validates and hands over a paste-ready block; it does not write the watchlist.
- **No network in the test suite.** Backfill's live fetching is exercised by hand, not by tests.
- A missing week is not a zero week — the `ok_sources` contract holds per week.
- Minimum 12 observed weeks before any score; observed excludes carried-forward padding.
- Observation week comes from the document's own date.
- Commit after every task, conventional-commit prefixes.

---

## File Structure

| Path | Responsibility |
|---|---|
| `observatory/run.py` | *(modify)* `--backfill N`, resumable |
| `observatory/discover.py` | Phrase extraction and rising-term detection |
| `observatory/store.py` | *(modify)* candidate-term persistence and reads |
| `observatory/render.py` | *(modify)* Rising Terms block |
| `observatory/templates/dashboard.html.j2` | *(modify)* Rising Terms block |
| `observatory/lexicon.py` | Offline CLI: `prepare` and `check`. Never imported by `run.py` |
| `lexicon/requests/`, `lexicon/proposals/` | Working files for the human-in-the-loop workflow |

---

### Task 1: Resumable backfill

**Files:**
- Modify: `observatory/run.py`
- Test: `tests/test_run.py`

**Interfaces:**
- Consumes: `fetch_week`, `rebuild`, `config.trailing_weeks`, `config.current_week`, `store.ok_sources_for_week`, `collectors.base.read_raw`.
- Produces: `weeks_needing_fetch(conn, weeks, collectors) -> list[str]`; `backfill(conn, weeks_back: int, collectors=COLLECTORS, session=None) -> list[str]` returning the weeks it fetched; a `--backfill N` CLI flag.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_run.py`:

```python
def test_weeks_needing_fetch_skips_weeks_already_complete(conn):
    weeks = ["2026-W30", "2026-W31", "2026-W32"]
    collectors = [stub()]
    for week in ("2026-W30", "2026-W32"):
        store.set_source_status(conn, "stub", week, "ok", "")
    assert run.weeks_needing_fetch(conn, weeks, collectors) == ["2026-W31"]


def test_weeks_needing_fetch_retries_a_week_whose_source_failed(conn):
    store.set_source_status(conn, "stub", "2026-W30", "failed", "timeout")
    assert run.weeks_needing_fetch(conn, ["2026-W30"], [stub()]) == ["2026-W30"]


def test_weeks_needing_fetch_requires_every_collector(conn):
    """A week is complete only when every registered collector has run it."""
    store.set_source_status(conn, "stub", "2026-W30", "ok", "")
    two = [stub(), StubCollector([], [], name="second")]
    assert run.weeks_needing_fetch(conn, ["2026-W30"], two) == ["2026-W30"]


def test_backfill_fetches_oldest_first_and_returns_what_it_fetched(conn, watchlist, tmp_path):
    calls = []

    class RecordingCollector(StubCollector):
        def fetch_raw(self, session, week):
            calls.append(week)
            yield from super().fetch_raw(session, week)

    collector = RecordingCollector(
        [RawPage(url="https://x.test/1", status=200, text=json.dumps({"ok": 1}))],
        [Document(doc_id="d1", date="2026-08-12", title="Autonomous trucking corridor",
                  text="", url="https://x.test/a")],
    )
    fetched = run.backfill(conn, watchlist, weeks_back=3, collectors=[collector], session=None)
    assert calls == sorted(calls), "backfill must fetch oldest first"
    assert fetched == calls


def test_backfill_skips_weeks_it_has_already_fetched(conn, watchlist):
    collector = stub()
    first = run.backfill(conn, watchlist, weeks_back=2, collectors=[collector], session=None)
    second = run.backfill(conn, watchlist, weeks_back=2, collectors=[collector], session=None)
    assert first, "first pass should fetch something"
    assert second == [], "second pass should find everything already fetched"


def test_backfill_rejects_a_nonsensical_window(conn, watchlist):
    with pytest.raises(ValueError):
        run.backfill(conn, watchlist, weeks_back=0, collectors=[stub()], session=None)
```

The existing `StubCollector` in that file takes `(pages, documents)`. Give it an optional `name` keyword defaulting to `"stub"` so `test_weeks_needing_fetch_requires_every_collector` can build a second one:

```python
class StubCollector(BaseCollector):
    def __init__(self, pages, documents, name="stub"):
        self.name = name
        self._pages = pages
        self._documents = documents
```

Keep `name` as an instance attribute — `BaseCollector` declares it as a class attribute and instance assignment shadows it cleanly.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_run.py -v`
Expected: the new tests fail with `AttributeError: module 'observatory.run' has no attribute 'weeks_needing_fetch'`.

- [ ] **Step 3: Implement**

Add to `observatory/run.py`:

```python
def weeks_needing_fetch(conn, weeks: list[str], collectors) -> list[str]:
    """Weeks where some collector has not yet recorded a successful run.

    This is what makes backfill resumable: a year of history is hours of
    polite fetching, and it must survive being interrupted and restarted
    without re-downloading what it already has.
    """
    wanted = {collector.name for collector in collectors}
    return [week for week in weeks if not wanted <= store.ok_sources_for_week(conn, week)]


def backfill(conn, weeks_back: int, collectors=COLLECTORS, session=None) -> list[str]:
    if weeks_back < 1:
        raise ValueError(f"weeks_back must be at least 1, got {weeks_back}")

    weeks = config.trailing_weeks(config.current_week(), weeks_back)
    pending = weeks_needing_fetch(conn, weeks, collectors)
    if not pending:
        print(f"Backfill: all {len(weeks)} weeks already fetched")
        return []

    print(f"Backfill: {len(pending)} of {len(weeks)} weeks to fetch, oldest first")
    for position, week in enumerate(pending, start=1):
        print(f"  [{position}/{len(pending)}] {week}")
        fetch_week(conn, week, collectors, session)
    return pending
```

Then extend the CLI. In `main`, add the argument:

```python
    parser.add_argument("--backfill", type=int, default=None, metavar="WEEKS",
                        help="fetch this many trailing weeks of history, then rebuild")
```

`--backfill` must reject `--only` the same way `--rebuild` already does — a backfill ends in a
full rebuild, and `rebuild` clears every derived table before replaying, so a narrowed collector
tuple would wipe the other sources' data and never rewrite it. Add that `parser.error` guard
beside the existing one, then handle the flag before the `--rebuild` branch:

```python
    if args.backfill is not None:
        session = http.make_session()
        backfill(conn, args.backfill, collectors, session)
        rebuild(conn, watchlist, collectors)
        return 0
```

Backfill deliberately fetches only, then hands off to `rebuild`, which already ingests every week before scoring any of them — the ordering that makes late-arriving documents land in the right week.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_run.py -v`
Expected: all pass, existing tests unchanged.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`

- [ ] **Step 6: Commit**

```bash
git add observatory/run.py tests/test_run.py
git commit -m "feat: resumable backfill across trailing weeks"
```

- [ ] **Step 7: Report the runtime estimate — do not start the real backfill**

A 52-week backfill makes roughly 52 × (20 arXiv + 7 HN + a few Federal Register + 6 USAspending + 8 EDGAR) requests, and arXiv alone is rate-limited to one request every three seconds. That is **hours**, not minutes.

Do not run it. Instead, work out and report in your report: the request count per week per collector from each collector's constants, the resulting wall-clock estimate at each collector's `rate_limit_seconds`, and the total. The controller will decide how to schedule it.

---

### Task 2: Phrase extraction

Discovery must see documents that matched *nothing* — those are exactly where the missing vocabulary lives. Observations only record matches, so this reads the raw files back through each collector's own parser.

**Files:**
- Create: `observatory/discover.py`
- Test: `tests/test_discover.py`

**Interfaces:**
- Consumes: nothing (pure functions).
- Produces: `STOPWORDS: frozenset[str]`; `MIN_TOKENS = 2`; `MAX_TOKENS = 4`; `normalise(text) -> list[str]`; `extract_phrases(text) -> list[str]` returning every n-gram of length `MIN_TOKENS..MAX_TOKENS` that contains no stopword and no pure number.

- [ ] **Step 1: Write the failing test**

Create `tests/test_discover.py`:

```python
from observatory import discover


def test_normalise_lowercases_and_splits_on_non_letters():
    assert discover.normalise("Autonomous-Trucking, at scale!") == [
        "autonomous", "trucking", "at", "scale"
    ]


def test_extract_phrases_returns_two_to_four_word_windows():
    phrases = discover.extract_phrases("humanoid warehouse picking robots")
    assert "humanoid warehouse" in phrases
    assert "humanoid warehouse picking" in phrases
    assert "humanoid warehouse picking robots" in phrases
    assert "humanoid" not in phrases, "single words are too noisy to be candidates"


def test_extract_phrases_rejects_windows_containing_a_stopword():
    phrases = discover.extract_phrases("robots in the warehouse")
    assert phrases == [], "every window here spans a stopword"


def test_extract_phrases_spans_stopwords_without_bridging_them():
    phrases = discover.extract_phrases("cold chain for frozen goods")
    assert "cold chain" in phrases
    assert "frozen goods" in phrases
    assert "chain frozen" not in phrases, "a phrase must not bridge a stopword"


def test_extract_phrases_drops_pure_numbers():
    assert discover.extract_phrases("2026 2027 forecast") == []


def test_extract_phrases_is_deterministic():
    text = "automated storage and retrieval systems for cold chain logistics"
    assert discover.extract_phrases(text) == discover.extract_phrases(text)


def test_extract_phrases_handles_empty_and_none():
    assert discover.extract_phrases("") == []
    assert discover.extract_phrases(None) == []


def test_stopwords_cover_the_obvious_connectives():
    for word in ("the", "a", "of", "for", "and", "in", "on", "with", "to"):
        assert word in discover.STOPWORDS
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_discover.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'observatory.discover'`

- [ ] **Step 3: Implement**

Create `observatory/discover.py`:

```python
"""Finding the vocabulary the watchlist is missing.

Discovery reads raw files back through each collector's parser rather than
reading the observations table, because the observations table only holds
documents that already matched something. The interesting terms are in the
documents that matched nothing.

Everything here is deterministic: no model, no randomness, no clock.
"""

from __future__ import annotations

import re

MIN_TOKENS = 2
MAX_TOKENS = 4

STOPWORDS = frozenset("""
a an and are as at be been but by for from has have how in into is it its of on
or over that the their there these this to under up via was were what when
where which who will with without you your our we they he she
""".split())


def normalise(text: str | None) -> list[str]:
    return [token for token in re.split(r"[^0-9a-z]+", (text or "").lower()) if token]


def extract_phrases(text: str | None) -> list[str]:
    """Every 2-to-4 word window that contains no stopword and no bare number.

    Windows never bridge a stopword: "cold chain for frozen goods" yields
    "cold chain" and "frozen goods" but never "chain frozen", which would be a
    phrase no human wrote.
    """
    phrases: list[str] = []
    for run_of_words in _runs(normalise(text)):
        for size in range(MIN_TOKENS, MAX_TOKENS + 1):
            for start in range(len(run_of_words) - size + 1):
                phrases.append(" ".join(run_of_words[start:start + size]))
    return phrases


def _runs(tokens: list[str]) -> list[list[str]]:
    """Split a token list into stretches uninterrupted by stopwords or numbers."""
    runs: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in STOPWORDS or token.isdigit():
            if current:
                runs.append(current)
            current = []
        else:
            current.append(token)
    if current:
        runs.append(current)
    return runs
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_discover.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add observatory/discover.py tests/test_discover.py
git commit -m "feat: deterministic phrase extraction for term discovery"
```

---

### Task 3: Rising-term detection

**Files:**
- Modify: `observatory/discover.py`, `observatory/store.py`, `observatory/run.py`
- Test: `tests/test_discover.py`, `tests/test_store.py`

**Interfaces:**
- Consumes: `collectors.base.read_raw`, `config.trailing_weeks`, `matcher.Watchlist.match`, `store`.
- Produces: in `discover`: `MIN_COUNT = 5`, `MIN_RATIO = 3.0`, `BASELINE_WEEKS = 12`, `Candidate` dataclass with fields `term, count, baseline, ratio, examples`, `week_phrase_counts(week, collectors) -> Counter[str]`, `week_examples(week, collectors, terms) -> dict[str, list[tuple[str, str]]]`, `detect_rising(week, collectors, watchlist) -> list[Candidate]`. In `store`: `upsert_candidates(conn, week, candidates) -> int`, `candidates_for_week(conn, week) -> list[dict]`.
- `run.run_week` and `run.rebuild` call detection after scoring.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_discover.py`:

```python
import json
from collections import Counter

import pytest

from observatory.collectors.base import BaseCollector, Document, RawPage
from observatory.matcher import Technology, Watchlist


class FakeCollector(BaseCollector):
    """Serves canned documents per week without touching the network or disk."""

    name = "fake"

    def __init__(self, by_week):
        self._by_week = by_week

    def documents_for(self, week):
        return self._by_week.get(week, [])


@pytest.fixture()
def watchlist():
    return Watchlist(
        version=1,
        technologies=(
            Technology(id="cold_chain_iot", name="Cold chain IoT", family="physical",
                       include=("cold chain monitoring",), exclude=(), status="active",
                       added_week="2020-W01", patterns_changed_week="2020-W01"),
        ),
        context=("logistics",),
    )


def documents(*titles):
    return [Document(doc_id=f"d{i}", date="2026-08-12", title=title, text="",
                     url=f"https://x.test/{i}") for i, title in enumerate(titles)]


def test_detect_rising_surfaces_a_term_that_spikes(monkeypatch, watchlist):
    weeks = {"2026-W33": documents(*["dark factory retrofit"] * 6)}
    for week in config_weeks_before("2026-W33", 12):
        weeks[week] = documents("unrelated shipping news")
    collector = FakeCollector(weeks)
    monkeypatch.setattr(discover, "_documents_for_week", lambda week, collectors: collector.documents_for(week))

    rising = discover.detect_rising("2026-W33", [collector], watchlist)
    terms = {candidate.term for candidate in rising}
    assert "dark factory" in terms


def test_detect_rising_ignores_a_term_the_watchlist_already_matches(monkeypatch, watchlist):
    weeks = {"2026-W33": documents(*["cold chain monitoring rollout"] * 8)}
    for week in config_weeks_before("2026-W33", 12):
        weeks[week] = []
    collector = FakeCollector(weeks)
    monkeypatch.setattr(discover, "_documents_for_week", lambda week, collectors: collector.documents_for(week))

    terms = {c.term for c in discover.detect_rising("2026-W33", [collector], watchlist)}
    assert "cold chain monitoring" not in terms


def test_detect_rising_requires_the_minimum_count(monkeypatch, watchlist):
    weeks = {"2026-W33": documents(*["dark factory retrofit"] * 2)}
    for week in config_weeks_before("2026-W33", 12):
        weeks[week] = []
    collector = FakeCollector(weeks)
    monkeypatch.setattr(discover, "_documents_for_week", lambda week, collectors: collector.documents_for(week))
    assert discover.detect_rising("2026-W33", [collector], watchlist) == []


def test_detect_rising_requires_the_minimum_ratio(monkeypatch, watchlist):
    weeks = {"2026-W33": documents(*["dark factory retrofit"] * 6)}
    for week in config_weeks_before("2026-W33", 12):
        weeks[week] = documents(*["dark factory retrofit"] * 6)
    collector = FakeCollector(weeks)
    monkeypatch.setattr(discover, "_documents_for_week", lambda week, collectors: collector.documents_for(week))
    assert discover.detect_rising("2026-W33", [collector], watchlist) == []


def test_candidates_carry_example_documents(monkeypatch, watchlist):
    weeks = {"2026-W33": documents(*[f"dark factory retrofit {n}" for n in range(6)])}
    for week in config_weeks_before("2026-W33", 12):
        weeks[week] = []
    collector = FakeCollector(weeks)
    monkeypatch.setattr(discover, "_documents_for_week", lambda week, collectors: collector.documents_for(week))

    rising = {c.term: c for c in discover.detect_rising("2026-W33", [collector], watchlist)}
    examples = rising["dark factory"].examples
    assert 1 <= len(examples) <= discover.MAX_EXAMPLES
    assert all(title and url for title, url in examples)


def config_weeks_before(week, count):
    from observatory import config
    return config.trailing_weeks(config.week_offset(week, -1), count)
```

Append to `tests/test_store.py`:

```python
def test_candidates_round_trip(conn):
    from observatory.discover import Candidate

    store.upsert_candidates(conn, "2026-W33", [
        Candidate(term="dark factory", count=6, baseline=1.0, ratio=6.0,
                  examples=[("Dark factory retrofit", "https://x.test/1")]),
    ])
    rows = store.candidates_for_week(conn, "2026-W33")
    assert len(rows) == 1
    assert rows[0]["term"] == "dark factory"
    assert rows[0]["ratio"] == 6.0
    assert rows[0]["status"] == "new"


def test_candidates_upsert_is_idempotent(conn):
    from observatory.discover import Candidate

    candidate = Candidate(term="dark factory", count=6, baseline=1.0, ratio=6.0, examples=[])
    store.upsert_candidates(conn, "2026-W33", [candidate])
    store.upsert_candidates(conn, "2026-W33", [candidate])
    assert len(store.candidates_for_week(conn, "2026-W33")) == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_discover.py tests/test_store.py -v`
Expected: failures for the missing `detect_rising`, `Candidate`, `upsert_candidates`, and `candidates_for_week`.

- [ ] **Step 3: Extend the store**

The `candidate_terms` table already exists with columns `term, week, count, baseline, ratio, status`. Examples need somewhere to live; add an `examples` column carrying a JSON array, since it is display-only data with no query against it:

```python
def upsert_candidates(conn, week: str, candidates) -> int:
    candidates = list(candidates)
    for candidate in candidates:
        conn.execute(
            "INSERT INTO candidate_terms (term, week, count, baseline, ratio, status, examples) "
            "VALUES (?, ?, ?, ?, ?, 'new', ?) "
            "ON CONFLICT (term, week) DO UPDATE SET count = excluded.count, "
            "baseline = excluded.baseline, ratio = excluded.ratio, examples = excluded.examples",
            (candidate.term, week, candidate.count, candidate.baseline, candidate.ratio,
             json.dumps(candidate.examples)),
        )
    conn.commit()
    return len(candidates)


def candidates_for_week(conn, week: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM candidate_terms WHERE week = ? ORDER BY ratio DESC, term", (week,)
    ).fetchall()
    result = []
    for row in rows:
        record = dict(row)
        record["examples"] = json.loads(record.get("examples") or "[]")
        result.append(record)
    return result
```

Add `examples TEXT` to the `candidate_terms` block in `SCHEMA`, and `import json` at the top of `store.py`.

- [ ] **Step 4: Implement detection**

First extend the imports at the top of `observatory/discover.py` — all imports go at the top of the file, not beside the code that uses them:

```python
import re
from collections import Counter
from dataclasses import dataclass

from . import config
from .collectors import base
```

Then append:

```python
MIN_COUNT = 5
MIN_RATIO = 3.0
BASELINE_WEEKS = 12
MAX_EXAMPLES = 3


@dataclass(frozen=True)
class Candidate:
    term: str
    count: int
    baseline: float
    ratio: float
    examples: list[tuple[str, str]]


def _documents_for_week(week: str, collectors) -> list:
    """Every document fetched for a week, matched or not, re-parsed from raw."""
    documents = []
    for collector in collectors:
        for _, text in base.read_raw(collector.name, week):
            try:
                documents.extend(collector.parse(text))
            except Exception:  # a poisoned raw file must not stop discovery
                continue
    return documents


def week_phrase_counts(week: str, collectors) -> Counter:
    counts: Counter = Counter()
    for document in _documents_for_week(week, collectors):
        counts.update(set(extract_phrases(document.title)))
    return counts


def detect_rising(week: str, collectors, watchlist) -> list[Candidate]:
    """Phrases spiking against their own trailing baseline that nothing matches yet."""
    current = week_phrase_counts(week, collectors)
    if not current:
        return []

    history: Counter = Counter()
    baseline_weeks = config.trailing_weeks(config.week_offset(week, -1), BASELINE_WEEKS)
    for past in baseline_weeks:
        history.update(week_phrase_counts(past, collectors))

    documents = _documents_for_week(week, collectors)
    candidates = []
    for term, count in current.items():
        if count < MIN_COUNT:
            continue
        baseline = history[term] / len(baseline_weeks)
        ratio = count / baseline if baseline else float(count)
        if ratio < MIN_RATIO:
            continue
        if _already_covered(watchlist, term):
            continue  # an active technology's pattern already covers this phrase
        candidates.append(
            Candidate(term=term, count=count, baseline=round(baseline, 3),
                      ratio=round(ratio, 2), examples=_examples(documents, term))
        )
    candidates.sort(key=lambda candidate: (-candidate.ratio, candidate.term))
    return candidates


def _already_covered(watchlist, term: str) -> bool:
    """Does any active technology's pattern already cover this phrase?

    Deliberately ignores `needs_context`. The context gate decides whether a
    *document* counts; it has no bearing on whether a phrase is already in the
    lexicon. Asking `watchlist.match(term)` here instead would fail for every
    context-gated technology, because a bare two-word phrase almost never
    carries a context word of its own — and nineteen of the shipped
    technologies are context-gated.
    """
    for tech in watchlist.active:
        if any(pattern.search(term) for pattern in tech.exclude_res):
            continue
        if any(pattern.search(term) for pattern in tech.include_res):
            return True
    return False


def _examples(documents, term: str) -> list[tuple[str, str]]:
    found = []
    for document in documents:
        if term in extract_phrases(document.title):
            found.append((document.title, document.url))
            if len(found) == MAX_EXAMPLES:
                break
    return found
```

Note the deliberate breadth of `extract_phrases` — a 4-word phrase also yields its 2- and 3-word sub-phrases, so a rising 4-word term surfaces alongside its parts. That redundancy is fine: the human reviewing candidates picks the useful granularity, and suppressing sub-phrases automatically would need a judgement call this module has no business making.

- [ ] **Step 5: Wire detection into the run**

In `observatory/run.py`, import `discover` and call it inside `_score_and_render`, after scoring and before rendering, so the rendered page can show the week's candidates:

```python
    candidates = discover.detect_rising(week, collectors, watchlist)
    store.upsert_candidates(conn, week, candidates)
```

`_score_and_render` will need `collectors` passed through if it does not already receive it. Thread it from both call sites rather than reaching for a module global.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Confirm the guardrail still holds**

Run: `python -m pytest tests/test_guardrails.py -v`
Expected: pass. `discover.py` is now reachable from `run.py` and must import no model client.

- [ ] **Step 8: Commit**

```bash
git add observatory/discover.py observatory/store.py observatory/run.py tests/test_discover.py tests/test_store.py
git commit -m "feat: rising-term detection from raw, including unmatched documents"
```

---

### Task 4: The Rising Terms block

**Files:**
- Modify: `observatory/render.py`, `observatory/templates/dashboard.html.j2`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `store.candidates_for_week`.
- Produces: context key `rising_terms` — a list of dicts with `term`, `count`, `baseline`, `ratio`, `examples`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_render.py`:

```python
def test_rising_terms_appear_in_the_context(conn, watchlist):
    from observatory.discover import Candidate

    store.upsert_candidates(conn, "2026-W33", [
        Candidate(term="dark factory", count=7, baseline=1.0, ratio=7.0,
                  examples=[("Dark factory retrofit in Ohio", "https://x.test/1")]),
    ])
    context = render.build_context(conn, "2026-W33", watchlist)
    assert context["rising_terms"][0]["term"] == "dark factory"


def test_rising_terms_render_with_their_evidence(conn, watchlist, tmp_path):
    from observatory.discover import Candidate

    store.upsert_candidates(conn, "2026-W33", [
        Candidate(term="dark factory", count=7, baseline=1.0, ratio=7.0,
                  examples=[("Dark factory retrofit in Ohio", "https://x.test/1")]),
    ])
    html = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html").read_text()
    assert "dark factory" in html
    assert "Dark factory retrofit in Ohio" in html
    assert "Arrives with the discovery step" not in html


def test_rising_terms_block_says_so_when_there_are_none(conn, watchlist, tmp_path):
    html = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html").read_text()
    assert "No new terms rose above the threshold this week." in html


def test_rising_term_titles_are_escaped(conn, watchlist, tmp_path):
    from observatory.discover import Candidate

    store.upsert_candidates(conn, "2026-W33", [
        Candidate(term="dark factory", count=7, baseline=1.0, ratio=7.0,
                  examples=[("<script>alert(1)</script>", "https://x.test/1")]),
    ])
    html = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html").read_text()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_render.py -v`
Expected: `KeyError: 'rising_terms'` and the placeholder-text assertions failing.

- [ ] **Step 3: Implement**

In `observatory/render.py`, add `"rising_terms": store.candidates_for_week(conn, week)` to the dictionary `build_context` returns.

Replace the Rising Terms placeholder in `observatory/templates/dashboard.html.j2`:

```html
  <h2>Rising Terms</h2>
  <p class="sub">Phrases spiking against their own 12-week baseline that no active
     technology matches yet. Promote one by adding it to <code>watchlist.yaml</code>.</p>
  {% if rising_terms %}
  <table>
    <thead><tr><th>Term</th><th class="num">This week</th><th class="num">Baseline</th>
      <th class="num">Ratio</th><th>Examples</th></tr></thead>
    <tbody>
    {% for candidate in rising_terms %}
      <tr>
        <td><code>{{ candidate.term }}</code></td>
        <td class="num">{{ candidate.count }}</td>
        <td class="num">{{ '%.1f'|format(candidate.baseline) }}</td>
        <td class="num">{{ '%.1f'|format(candidate.ratio) }}&times;</td>
        <td>
          {% for title, url in candidate.examples %}
            <a href="{{ url }}">{{ title }}</a>{% if not loop.last %}<br>{% endif %}
          {% endfor %}
        </td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p class="empty">No new terms rose above the threshold this week.</p>
  {% endif %}
```

Note that this block, like the evidence page's rows, carries genuine outbound links to source documents. The dashboard's existing no-external-resource test greps for `src`/`href` pointing at an external host — check whether adding these links breaks it. If it does, the test's intent is "no external *resources* are fetched to render the page", and an anchor the reader clicks is not that; narrow the assertion to `src` and stylesheet `href`s, and say so in your report rather than removing the test.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest -q`

- [ ] **Step 5: Commit**

```bash
git add observatory/render.py observatory/templates/dashboard.html.j2 tests/test_render.py
git commit -m "feat: Rising Terms block"
```

---

### Task 5: `lexicon prepare`

**Files:**
- Create: `observatory/lexicon.py`
- Test: `tests/test_lexicon.py`

**Interfaces:**
- Consumes: `store.candidates_for_week`, `matcher.load_watchlist`, `config`.
- Produces: `REQUEST_DIR`, `PROPOSAL_DIR`; `prepare(conn, week, watchlist, out_path=None) -> Path`; `main(argv=None) -> int` handling the `prepare` subcommand.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_lexicon.py`:

```python
import pytest

from observatory import lexicon, store
from observatory.discover import Candidate
from observatory.matcher import Technology, Watchlist


@pytest.fixture()
def watchlist():
    return Watchlist(
        version=4,
        technologies=(
            Technology(id="cold_chain_iot", name="Cold chain IoT", family="physical",
                       include=("cold chain monitoring",), exclude=(), status="active",
                       added_week="2020-W01", patterns_changed_week="2020-W01"),
        ),
        context=("logistics", "warehouse"),
    )


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    store.upsert_candidates(connection, "2026-W33", [
        Candidate(term="dark factory", count=7, baseline=1.0, ratio=7.0,
                  examples=[("Dark factory retrofit in Ohio", "https://x.test/1")]),
    ])
    yield connection
    connection.close()


def test_prepare_writes_a_request_naming_the_week(conn, watchlist, tmp_path):
    path = lexicon.prepare(conn, "2026-W33", watchlist, tmp_path / "req.md")
    assert path.exists()
    assert "2026-W33" in path.read_text()


def test_request_carries_the_candidates_and_their_evidence(conn, watchlist, tmp_path):
    text = lexicon.prepare(conn, "2026-W33", watchlist, tmp_path / "req.md").read_text()
    assert "dark factory" in text
    assert "Dark factory retrofit in Ohio" in text
    assert "https://x.test/1" in text


def test_request_lists_the_existing_technologies_so_duplicates_are_visible(conn, watchlist, tmp_path):
    text = lexicon.prepare(conn, "2026-W33", watchlist, tmp_path / "req.md").read_text()
    assert "cold_chain_iot" in text
    assert "Cold chain IoT" in text


def test_request_states_the_context_vocabulary(conn, watchlist, tmp_path):
    text = lexicon.prepare(conn, "2026-W33", watchlist, tmp_path / "req.md").read_text()
    assert "logistics" in text
    assert "warehouse" in text


def test_request_names_the_proposal_file_to_write(conn, watchlist, tmp_path):
    text = lexicon.prepare(conn, "2026-W33", watchlist, tmp_path / "req.md").read_text()
    assert "proposals/2026-W33.yaml" in text


def test_prepare_says_so_when_there_are_no_candidates(watchlist, tmp_path):
    connection = store.connect(":memory:")
    store.init_schema(connection)
    text = lexicon.prepare(connection, "2026-W33", watchlist, tmp_path / "req.md").read_text()
    assert "no candidate terms" in text.lower()
    connection.close()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_lexicon.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'observatory.lexicon'`

- [ ] **Step 3: Implement**

Create `observatory/lexicon.py`:

```python
"""The offline lexicon workflow — never imported by the weekly run.

The pipeline cannot judge whether "dark factory" is a supply chain technology
or a metal band. That judgement is the owner's, and this module's whole job is
to package the evidence so it can be made well: `prepare` writes a request, a
human answers it in a Claude session by writing a proposals file, and `check`
validates the result before the human merges it into watchlist.yaml by hand.

The pipeline never edits the watchlist. Spec §4 and §5.1 are explicit about
that, and it is why this module writes proposals rather than patterns.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config, matcher, store

REQUEST_DIR = config.ROOT / "lexicon" / "requests"
PROPOSAL_DIR = config.ROOT / "lexicon" / "proposals"

INSTRUCTIONS = """\
## What to do with this

Read the candidates below, decide which are real supply chain or operations
technologies, and write a proposals file at `lexicon/proposals/{week}.yaml`.

For each term you want to promote, decide two things:

1. **The patterns.** What would a document actually say? Include spelling
   variants, common abbreviations, and vendor names. Add `exclude` patterns for
   the near-misses that would otherwise match.
2. **Whether it needs context.** If the term belongs to every field — "digital
   twin", "computer vision", "blockchain" — set `needs_context: true` and it
   will only count when the document also uses one of the context words listed
   above. If the term is self-scoping — "inland port", "cold chain" — leave it
   out.

Getting this wrong in the permissive direction is expensive: an earlier run
matched nine off-concept documents out of ten because patterns were broader
than their own names.

Write the file in this shape:

```yaml
technologies:
  - id: dark_factory
    name: Dark factories
    family: physical
    include:
      - "dark factor(y|ies)"
      - "lights[- ]out manufacturing"
    exclude: []
    needs_context: true
```

Then run `python -m observatory.lexicon check {week}` to validate it.
"""


def prepare(conn, week: str, watchlist, out_path: Path | None = None) -> Path:
    candidates = store.candidates_for_week(conn, week)
    lines = [
        f"# Lexicon request — week {week}",
        "",
        f"Lexicon version in use: {watchlist.version}",
        "",
        "## Context vocabulary",
        "",
        "A technology marked `needs_context` only counts when the document also",
        "uses one of these words:",
        "",
        "".join(f"- `{term}`\n" for term in watchlist.context) or "- (none defined)\n",
        "## Technologies already tracked",
        "",
        "Do not propose a duplicate of one of these; propose a pattern change instead.",
        "",
    ]
    for tech in watchlist.active:
        lines.append(f"- `{tech.id}` — {tech.name} ({tech.family})")
    lines += ["", "## Candidate terms", ""]

    if not candidates:
        lines.append("There are no candidate terms for this week.")
    else:
        for candidate in candidates:
            lines.append(
                f"### `{candidate['term']}` — {candidate['count']} this week, "
                f"baseline {candidate['baseline']:.1f}, {candidate['ratio']:.1f}× "
            )
            lines.append("")
            for title, url in candidate["examples"]:
                lines.append(f"- [{title}]({url})")
            lines.append("")

    lines += ["", INSTRUCTIONS.format(week=week)]

    target = Path(out_path) if out_path else REQUEST_DIR / f"{week}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines))
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="observatory.lexicon")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare", help="write a lexicon request for a week")
    prepare_parser.add_argument("week")
    args = parser.parse_args(argv)

    config.load_dotenv()
    watchlist = matcher.load_watchlist()
    conn = store.connect()
    store.init_schema(conn)
    try:
        if args.command == "prepare":
            path = prepare(conn, args.week, watchlist)
            print(f"Wrote {path}")
            print("Open a Claude session and ask it to answer this request.")
            return 0
    finally:
        conn.close()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_lexicon.py -v`
Expected: 6 passed

- [ ] **Step 5: Confirm the guardrail still holds**

Run: `python -m pytest tests/test_guardrails.py -v`
Expected: pass. `lexicon` is on the banned-import list for the weekly run's import graph, and `run.py` must not import it.

- [ ] **Step 6: Commit**

```bash
git add observatory/lexicon.py tests/test_lexicon.py
git commit -m "feat: lexicon prepare writes a reviewable request"
```

---

### Task 6: `lexicon check`

Validation is where this workflow earns its keep. A proposal that looks reasonable and quietly matches nothing — or matches everything — is exactly the failure this project keeps hitting.

**Files:**
- Modify: `observatory/lexicon.py`
- Test: `tests/test_lexicon.py`

**Interfaces:**
- Consumes: `matcher.compile_pattern`, `matcher.Watchlist`, `store.candidates_for_week`.
- Produces: `Problem` dataclass with fields `term, message`; `check(conn, week, watchlist, proposals_path=None) -> tuple[list[Problem], str]` returning problems and a paste-ready YAML block; `check` wired into `main` as a subcommand returning exit code 1 when problems are found.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_lexicon.py`:

```python
import textwrap


def write_proposal(tmp_path, body):
    path = tmp_path / "proposal.yaml"
    path.write_text(textwrap.dedent(body))
    return path


def test_check_accepts_a_sound_proposal(conn, watchlist, tmp_path):
    path = write_proposal(tmp_path, """
        technologies:
          - id: dark_factory
            name: Dark factories
            family: physical
            include: ["dark factor(y|ies)"]
            exclude: []
            needs_context: true
    """)
    problems, block = lexicon.check(conn, "2026-W33", watchlist, path)
    assert problems == []
    assert "dark_factory" in block


def test_check_rejects_a_pattern_that_does_not_compile(conn, watchlist, tmp_path):
    path = write_proposal(tmp_path, """
        technologies:
          - id: dark_factory
            name: Dark factories
            family: physical
            include: ["dark factor(y|ies"]
            exclude: []
    """)
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert any("compile" in problem.message for problem in problems)


def test_check_rejects_an_id_that_already_exists(conn, watchlist, tmp_path):
    path = write_proposal(tmp_path, """
        technologies:
          - id: cold_chain_iot
            name: Duplicate
            family: physical
            include: ["something else"]
            exclude: []
    """)
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert any("already" in problem.message for problem in problems)


def test_check_rejects_a_proposal_that_matches_none_of_its_own_evidence(conn, watchlist, tmp_path):
    """A pattern that cannot match the documents that inspired it is useless."""
    path = write_proposal(tmp_path, """
        technologies:
          - id: dark_factory
            name: Dark factories
            family: physical
            include: ["completely unrelated phrase"]
            exclude: []
    """)
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert any("evidence" in problem.message for problem in problems)


def test_check_warns_when_a_gated_pattern_can_never_pass_its_gate(conn, watchlist, tmp_path):
    """needs_context plus evidence that contains no context word is a silent zero."""
    path = write_proposal(tmp_path, """
        technologies:
          - id: dark_factory
            name: Dark factories
            family: physical
            include: ["dark factor(y|ies)"]
            exclude: []
            needs_context: true
    """)
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    # The example title "Dark factory retrofit in Ohio" has no context word.
    assert any("context" in problem.message for problem in problems)


def test_check_reports_a_missing_proposal_file(conn, watchlist, tmp_path):
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, tmp_path / "absent.yaml")
    assert any("not found" in problem.message for problem in problems)
```

Note the fifth test and the first test pull in opposite directions on the same proposal — the first asserts no problems, the fifth asserts a context problem for an identical entry. Reconcile them by making the context finding a **warning that is still a `Problem`**, and giving the first test's proposal an example that does contain a context word. Adjust the `conn` fixture so its candidate example title is `"Dark factory retrofit in Ohio warehouse"`, which contains `warehouse`, and keep the fifth test's expectation by giving that test its own candidate with a context-free example. Do this rather than weakening either assertion, and describe what you did in your report.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_lexicon.py -v`
Expected: FAIL with `AttributeError: module 'observatory.lexicon' has no attribute 'check'`

- [ ] **Step 3: Implement**

Append to `observatory/lexicon.py`:

Add these to the imports at the top of the file — `re`, `dataclasses.dataclass`, and `yaml` — then append:

```python
@dataclass(frozen=True)
class Problem:
    term: str
    message: str


def check(conn, week: str, watchlist, proposals_path: Path | None = None) -> tuple[list[Problem], str]:
    path = Path(proposals_path) if proposals_path else PROPOSAL_DIR / f"{week}.yaml"
    if not path.exists():
        return [Problem("", f"proposal file not found: {path}")], ""

    proposed = yaml.safe_load(path.read_text()) or {}
    entries = proposed.get("technologies") or []
    existing = {tech.id for tech in watchlist.technologies}
    evidence = {row["term"]: row["examples"] for row in store.candidates_for_week(conn, week)}
    context_res = watchlist.context_res

    problems: list[Problem] = []
    for entry in entries:
        tech_id = entry.get("id", "(missing id)")
        if tech_id in existing:
            problems.append(Problem(tech_id, f"id {tech_id} already exists in the watchlist"))

        compiled = []
        for pattern in entry.get("include", ()):
            try:
                compiled.append(matcher.compile_pattern(pattern))
            except re.error as error:
                problems.append(Problem(tech_id, f"include pattern does not compile: {pattern!r} ({error})"))

        titles = [title for examples in evidence.values() for title, _ in examples]
        matched = [title for title in titles if any(p.search(title) for p in compiled)]
        if compiled and not matched:
            problems.append(Problem(tech_id, "matches none of this week's candidate evidence"))

        if entry.get("needs_context") and matched:
            gated = [t for t in matched if any(p.search(t) for p in context_res)]
            if not gated:
                problems.append(Problem(
                    tech_id,
                    "needs_context is set but no matching evidence contains a context word, "
                    "so this would silently count zero",
                ))

    return problems, yaml.safe_dump({"technologies": entries}, sort_keys=False)
```

Add the `check` subcommand to `main`, printing each problem and returning exit code 1 when any are found; on success, print the paste-ready block and remind the reader to bump `lexicon_version` and set `patterns_changed_week` when they merge it by hand.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_lexicon.py -v`

- [ ] **Step 5: Run the full suite and the guardrail**

Run: `python -m pytest -q`

- [ ] **Step 6: Document the workflow in the README**

Add a short section showing the loop end to end: run the week, `lexicon prepare`, answer it in a session, `lexicon check`, paste into `watchlist.yaml`, bump `lexicon_version`, set `patterns_changed_week`, then `--rebuild` to recompute history under the new patterns. Mention that momentum is suppressed for eight weeks after a pattern change, and why.

- [ ] **Step 7: Commit**

```bash
git add observatory/lexicon.py tests/test_lexicon.py README.md
git commit -m "feat: lexicon check validates proposals before a human merges them"
```

---

## What this plan does not cover

- **GDELT (plan 2A tasks 3 and 4)** — still blocked by a rate-limit cooldown. Redo them from plan 2A as written, starting from a real capture.
- **Plan 2B** — GitHub and PatentsView collectors, feeding `patents`, `gh_repos_new`, `gh_commits`, `gh_stars_delta`. Both need free API keys. Note for that plan: `http.fetch` treats only HTTP 200 as success, and GitHub's `/repos/{r}/stats` returns **202** while computing statistics.
- **The carry-forward list from plan 2A** — `adoption_new` hardcoded to `0`, `fed_obligated` summing total award value rather than obligated dollars, sticky award-to-week attribution, the `weeks_swept_by` multiple-of-7 assumption, data-dependent hole healing, and the orphaned `output/evidence.html`. None block this plan.
