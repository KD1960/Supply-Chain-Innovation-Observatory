# Pre-practice TRL Tracker, Phase 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the approved spec (`docs/superpowers/specs/2026-09-23-pre-practice-trl-tracker-design.md`) into a working, measured first version: a TRL claim schema, a deterministic scorer with an owner-editable weights table, an offline claim extractor over the documents the free collectors already fetch, a measurement of whether the pilot band (TRL 5–8) is reachable from free sources, a two-reader placement check, and a report page.

**Architecture:** The weekly run does not change. New code lives in two packages: `observatory/trl/` (pure, deterministic: schema, weights, scoring, document access, report context) and `observatory/claims/` (already on branch `phase0`: prompt, schema helpers, quote verification; the only place `anthropic` may be imported). Claims are a JSONL file per period under `data/trl/`, produced by an explicit command, never by cron. The report reads claims and the weights table and shows the estimate with its top claims. Measurement tasks (4 and 6) gate the tasks after them; a gate that fails stops the plan and is reported, not worked around.

**Tech Stack:** Python 3.13 at `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`, sqlite3, PyYAML, Jinja2, pytest, ruff; `anthropic>=1.3` under the `extract` extra only.

## Global Constraints

Copied from the spec; every task inherits them.

- **C1.** No collector, export or reported number may require a manual export from a library-licensed database. Scopus, ProQuest and library-Lens entries in `sources.yaml` are frozen, not run.
- **C2.** Phase 1 runs on free sources only. Paid sources are added later and history is rebuilt, never rescored by hand.
- **C3.** Source and stage are decoupled: source type is one feature of a claim, never the label.
- **C4.** Every published estimate is traceable to claims, each with a verified quote and a citation.
- **C5.** No LLM in the weekly run. `tests/test_claims_isolation.py` (from branch `phase0`) enforces by import graph that only `observatory/claims/` imports `anthropic`, and nothing on the weekly path imports `observatory.claims`. `observatory/trl/` must never import `observatory.claims` or `anthropic`.
- **C6.** Membership is the owner's ruling on `docs/audit/tech-practice-sort-2026-09-23.xlsx`. The tracked set is the rows whose `assistant call` begins with `pre-practice`, plus Kevin's additions.
- TRL bands: 1–3 research; 4–6 prototype and pilot; 7–8 demonstrated in an operational environment; 9 routine commercial operation.
- Point estimate is the **highest level with sufficient weighted support**, never an average.
- Standing rules: never `git add -A`; measure before building and record the rejection with its reversal condition; check the artifact, not the code that makes it.
- Model calls: pinned model id passed explicitly, system prompt cached, refusals recorded and never rerouted, a `--max-dollars` ceiling that refuses to start when the estimate exceeds it, `--limit` for smoke runs.
- Commit after every task with explicit paths.

## Branch and worktree

Work on a new branch `trl` from `main` in worktree `.worktrees/trl`, so the Monday cron keeps running from `main`. Before Task 1, bring the reusable claims modules over from `phase0` without merging the rest of that branch:

```bash
git worktree add .worktrees/trl -b trl main
cd .worktrees/trl
git checkout phase0 -- observatory/claims/__init__.py observatory/claims/prompt.py observatory/claims/schema.py observatory/claims/verify.py tests/test_claims_isolation.py tests/test_claims_verify.py tests/test_claims_schema.py
git checkout phase0 -- pyproject.toml
```

`observatory/claims/prompt.py` imports `observatory.sections`, which is not on `main`. Task 3 removes that import by writing a TRL prompt module beside it; until then, delete the line `from .. import matcher, sections` and the four functions that use `sections` (`system_windowed`, `user_windowed`) from the copied `prompt.py`, keep `PROMPT_VERSION`, `UNTRUSTED`, `_RULES`, `coding_frame`, `system_open`, `user_open`. Run `python -m pytest tests/test_claims_isolation.py tests/test_claims_verify.py tests/test_claims_schema.py -q`; expected: all pass. Commit:

```bash
git add observatory/claims tests/test_claims_isolation.py tests/test_claims_verify.py tests/test_claims_schema.py pyproject.toml
git commit -m "Bring the claims package (prompt rules, schema helpers, quote verification) over from phase0"
```

## File structure

| Path | Responsibility |
|---|---|
| `sources.yaml` | add `frozen: true` to library-licensed entries (Task 1) |
| `observatory/export.py`, `observatory/manual.py` | refuse frozen sources (Task 1) |
| `observatory/trl/__init__.py` | package marker, one docstring |
| `observatory/trl/schema.py` | closed vocabularies for TRL claims, band map, validation, claim ids (Task 2) |
| `observatory/trl/weights.yaml` | the owner's weights table: actor × source × claim type, recency half-life, support threshold (Task 3) |
| `observatory/trl/score.py` | `estimate()`; pure function from claims to a `TRLEstimate` (Task 3) |
| `observatory/trl/tracked.py` | reads the sort sheet's ruling, gives the tracked tech ids (Task 2) |
| `observatory/trl/documents.py` | re-parses raw files to give the text behind an observation (Task 5) |
| `observatory/claims/trl_prompt.py` | the TRL extraction prompt, versioned `trl-1` (Task 5) |
| `observatory/claims/extract_trl.py` | the offline extraction command (Task 5) |
| `observatory/trl/placement.py` | two-reader placement sheet and agreement measure (Task 6) |
| `observatory/trl/report.py`, `observatory/templates/trl.html.j2` | report context and page (Task 7) |
| `observatory/run.py` | `--trl-report PERIOD` only; extraction has its own entry point (Task 7) |
| `docs/experiments/trl/probe.py` | pilot-band source probe, an experiment not a module (Task 4) |
| `docs/trl-probe-2026-09-<dd>.md`, `docs/trl-placement-2026-<mm>-<dd>.md` | the two measurement reports (Tasks 4, 6) |
| `tests/test_trl_*.py`, `tests/test_claims_extract_trl.py`, `tests/fixtures/trl/` | tests and fixtures |

---

### Task 1: Freeze the library-licensed sources (C1)

**Files:**
- Modify: `sources.yaml` (the `scopus`, `proquest` and `lens` entries)
- Modify: `observatory/export.py` (the function that builds `--export-queries`)
- Modify: `observatory/manual.py` (the importer)
- Test: `tests/test_export.py`, `tests/test_manual.py`

**Interfaces:**
- Consumes: `sources.yaml` entries with `name`, `family`, `signal`, `stage`, `format`.
- Produces: a boolean `frozen` per source, read by `export.frozen_sources()` → `set[str]`.

- [ ] **Step 1: Read how export.py loads sources.yaml**

Run: `grep -n "sources.yaml\|def \|yaml" observatory/export.py | head -30` and `grep -n "def \|manual_sources\|sources.yaml" observatory/manual.py | head -30`. Note the function that returns the list of manual sources (call it `manual_sources()` below; use its real name).

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_export.py`:

```python
def test_frozen_sources_are_named_and_excluded_from_export_queries(tmp_path, monkeypatch):
    from observatory import export
    frozen = export.frozen_sources()
    assert {"scopus", "proquest", "lens"} <= frozen
    # A frozen source produces no query sheet: the owner must not be asked to export it.
    sheets = export.query_sheets("2026-Q3")   # use the real name of the function behind --export-queries
    assert not any(sheet.source in frozen for sheet in sheets)
```

Append to `tests/test_manual.py`:

```python
def test_import_manual_refuses_a_frozen_source(tmp_path, monkeypatch, capsys):
    from observatory import manual, config
    export_file = config.MANUAL_DIR / "scopus-2026-Q3.ris"
    export_file.write_text("TY  - JOUR\nTI  - A paper\nER  -\n")
    result = manual.import_all(conn=None)  # use the real entry point; it must return before touching the db
    out = capsys.readouterr().out
    assert "frozen" in out and "scopus" in out
```

Adjust the two tests to the real function names found in Step 1; the assertions are the contract.

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_export.py tests/test_manual.py -q -k frozen`
Expected: FAIL with `AttributeError: module 'observatory.export' has no attribute 'frozen_sources'`.

- [ ] **Step 4: Add the flag to sources.yaml**

For each of the three entries, add directly under `name:`:

```yaml
    frozen: true
    frozen_reason: >-
      Library licence forbids text mining and the report may not depend on
      manual library exports (spec 2026-09-23, constraint C1). Reversal
      condition: a licence or API agreement that permits mining, recorded here.
```

- [ ] **Step 5: Implement**

In `observatory/export.py`, add:

```python
def frozen_sources(path=None) -> set[str]:
    """Sources the owner may not be asked to export by hand (spec C1)."""
    entries = _load_sources(path)   # the existing loader; use its real name
    return {e["name"] for e in entries if e.get("frozen")}
```

and in the function behind `--export-queries`, skip any entry with `frozen`. In `manual.py`, at the top of the import loop, if the file's source is in `export.frozen_sources()`, print `f"{source}: frozen (see sources.yaml); {path.name} not imported"` and continue.

- [ ] **Step 6: Run the whole suite**

Run: `python -m pytest -q`
Expected: all pass (807 on `phase0` count plus the new ones; `main` had 746 plus the three claims test files).

- [ ] **Step 7: Commit**

```bash
git add sources.yaml observatory/export.py observatory/manual.py tests/test_export.py tests/test_manual.py
git commit -m "Freeze the library-licensed sources: no export sheets, no imports (spec C1)"
```

---

### Task 2: TRL claim schema and the tracked set

**Files:**
- Create: `observatory/trl/__init__.py`, `observatory/trl/schema.py`, `observatory/trl/tracked.py`
- Create: `tests/test_trl_schema.py`, `tests/test_trl_tracked.py`
- Create: `tests/fixtures/trl/sort-sheet.csv` (a five-row CSV in the sort sheet's column order)

**Interfaces:**
- Produces:
  - `CLAIM_TYPES`, `ACTOR_TYPES`, `SETTINGS`, `SOURCE_TYPES` tuples; `BAND: dict[str, tuple[int, int]]` mapping claim type → (low, high) TRL.
  - `validate(payload: dict, tech_ids: Sequence[str]) -> list[dict]` raising `ValueError`.
  - `claim_id(source: str, doc_id: str, tech_id: str, quote: str) -> str` (12 hex chars).
  - `tracked_ids(sheet_path: Path | None = None) -> tuple[str, ...]` reading the xlsx (openpyxl is installed for 3.13; add `"openpyxl>=3.1"` to `dependencies` in `pyproject.toml`).

- [ ] **Step 1: Write the failing tests**

`tests/test_trl_schema.py`:

```python
import pytest
from observatory.trl import schema


def _claim(**over):
    base = {"tech_id": "delivery_drones", "claim_type": "pilots", "actor_type": "user_firm",
            "actor": "Walmart", "setting": "multiple_sites", "quantity": "", "quote": "Walmart is piloting drone delivery at 34 stores.",
            "source_type": "press_release"}
    base.update(over)
    return base


def test_every_claim_type_has_a_band_inside_one_to_nine():
    for ct in schema.CLAIM_TYPES:
        lo, hi = schema.BAND[ct]
        assert 1 <= lo <= hi <= 9


def test_bands_are_monotone_in_the_listed_order():
    highs = [schema.BAND[ct][1] for ct in schema.CLAIM_TYPES if ct != "abandons"]
    assert highs == sorted(highs)


def test_validate_accepts_a_well_formed_claim():
    assert schema.validate({"claims": [_claim()]}, ["delivery_drones"]) == [_claim()]


@pytest.mark.parametrize("field,value", [
    ("tech_id", "erp"), ("claim_type", "diffuses"), ("actor_type", "person"), ("setting", "everywhere"),
])
def test_validate_rejects_values_outside_the_closed_sets(field, value):
    with pytest.raises(ValueError):
        schema.validate({"claims": [_claim(**{field: value})]}, ["delivery_drones"])


def test_validate_requires_every_field():
    claim = _claim(); del claim["quote"]
    with pytest.raises(ValueError, match="quote"):
        schema.validate({"claims": [claim]}, ["delivery_drones"])


def test_claim_id_is_stable_under_whitespace_and_curly_quotes():
    a = schema.claim_id("hn", "hn:1", "delivery_drones", "Walmart  is “piloting” drones")
    b = schema.claim_id("hn", "hn:1", "delivery_drones", 'Walmart is "piloting" drones')
    assert a == b and len(a) == 12
```

`tests/test_trl_tracked.py`:

```python
from pathlib import Path
from observatory.trl import tracked

FIXTURE = Path(__file__).parent / "fixtures" / "trl" / "sort-sheet.xlsx"


def test_tracked_ids_are_the_pre_practice_rows_in_sheet_order():
    assert tracked.tracked_ids(FIXTURE) == ("delivery_drones", "piece_picking", "additive_spares")


def test_tracked_ids_reads_the_real_sheet_and_finds_twenty_four():
    ids = tracked.tracked_ids()
    assert len(ids) == 24
    assert "erp" not in ids and "delivery_drones" in ids
```

Build the fixture with openpyxl in a throwaway script: a sheet named `Sort`, header row identical to the real sheet (`id, name, family, lexicon v10 status, assistant call, ...`), rows: `delivery_drones/pre-practice`, `erp/in-practice`, `piece_picking/pre-practice`, `operations_research/retire`, `additive_spares/pre-practice (borderline)`. Save to `tests/fixtures/trl/sort-sheet.xlsx`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_trl_schema.py tests/test_trl_tracked.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'observatory.trl'`.

- [ ] **Step 3: Implement schema.py**

```python
# observatory/trl/schema.py
"""What a TRL claim is. Closed vocabularies on purpose (spec §4): the argument
should be about the evidence, not the words used to code it.

A claim is one statement, in one document, about one tracked technology,
saying what someone did with it. Source type is a feature, not the label (C3).
"""

from __future__ import annotations

import hashlib
from typing import Sequence

from ..claims_free import normalize  # see Step 4: a copy of verify.normalize that keeps trl free of the claims package

CLAIM_TYPES = ("proposes", "simulates", "prototypes", "pilots", "demonstrates_in_operation",
               "sells", "buys", "operates_at_scale", "abandons")
# (low, high) TRL each claim type is evidence for. "abandons" is evidence
# that the level was NOT held: the scorer treats it as a contrary claim.
BAND = {
    "proposes": (1, 2), "simulates": (2, 3), "prototypes": (4, 5), "pilots": (5, 6),
    "demonstrates_in_operation": (7, 8), "sells": (7, 8), "buys": (7, 8),
    "operates_at_scale": (9, 9), "abandons": (0, 0),
}
ACTOR_TYPES = ("university", "startup", "incumbent_vendor", "user_firm", "government", "analyst", "unclear")
SETTINGS = ("lab", "test_site", "one_site", "multiple_sites", "network_wide", "unclear")
SOURCE_TYPES = ("paper", "patent", "filing", "press_release", "trade_article", "code_repository",
                "job_posting", "analyst_note", "funding_record", "government_record", "forum_post")

FIELDS = ("tech_id", "claim_type", "actor_type", "actor", "setting", "quantity", "quote", "source_type")


def response_schema(tech_ids: Sequence[str]) -> dict:
    """The JSON schema the model is held to for one document."""
    return {
        "type": "object",
        "properties": {"claims": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "tech_id": {"type": "string", "enum": list(tech_ids)},
                "claim_type": {"type": "string", "enum": list(CLAIM_TYPES)},
                "actor_type": {"type": "string", "enum": list(ACTOR_TYPES)},
                "actor": {"type": "string"},
                "setting": {"type": "string", "enum": list(SETTINGS)},
                "quantity": {"type": "string"},
                "quote": {"type": "string"},
                "source_type": {"type": "string", "enum": list(SOURCE_TYPES)},
            },
            "required": list(FIELDS), "additionalProperties": False}}},
        "required": ["claims"], "additionalProperties": False,
    }


def validate(payload: dict, tech_ids: Sequence[str]) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("claims"), list):
        raise ValueError("payload has no 'claims' list")
    allowed = set(tech_ids)
    for i, claim in enumerate(payload["claims"]):
        if not isinstance(claim, dict):
            raise ValueError(f"claim {i}: not an object")
        for field in FIELDS:
            if field not in claim:
                raise ValueError(f"claim {i}: missing {field}")
        checks = (("tech_id", allowed), ("claim_type", CLAIM_TYPES), ("actor_type", ACTOR_TYPES),
                  ("setting", SETTINGS), ("source_type", SOURCE_TYPES))
        for field, closed in checks:
            if claim[field] not in closed:
                raise ValueError(f"claim {i}: {field} {claim[field]!r} is not allowed")
    return payload["claims"]


def claim_id(source: str, doc_id: str, tech_id: str, quote: str) -> str:
    digest = hashlib.sha1(f"{source}|{doc_id}|{tech_id}|{normalize(quote)}".encode("utf8"))
    return digest.hexdigest()[:12]
```

- [ ] **Step 4: Keep `trl` free of the `claims` package**

`observatory/claims/verify.py` must not be imported from `trl` (C5's import-graph test forbids importing `claims` outside `claims`). Create `observatory/claims_free.py`? No: put the eleven-line `normalize()` into `observatory/textnorm.py` (copy the function body from `observatory/claims/verify.py` verbatim) and have **both** `claims/verify.py` and `trl/schema.py` import it from there: `from ..textnorm import normalize` and `from .textnorm import normalize`. Fix the import line in Step 3 accordingly. `tests/test_claims_verify.py` still passes because `verify.normalize` is re-exported.

- [ ] **Step 5: Implement tracked.py**

```python
# observatory/trl/tracked.py
"""The tracked set is the owner's ruling on the sort sheet (spec C6)."""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from .. import config

SHEET_PATH = config.ROOT / "docs" / "audit" / "tech-practice-sort-2026-09-23.xlsx"


def tracked_ids(sheet_path: Path | None = None) -> tuple[str, ...]:
    ws = load_workbook(sheet_path or SHEET_PATH, read_only=True)["Sort"]
    rows = ws.iter_rows(values_only=True)
    header = [str(h).strip() for h in next(rows)]
    id_col, call_col = header.index("id"), header.index("assistant call")
    own_col = header.index("Kevin: your call")
    out = []
    for row in rows:
        if row[id_col] is None:
            continue
        call = str(row[own_col] or row[call_col] or "").strip().lower()
        if call.startswith("pre-practice"):
            out.append(str(row[id_col]))
    return tuple(out)
```

Add `"openpyxl>=3.1"` to `dependencies` in `pyproject.toml`. `observatory/trl/__init__.py` holds one docstring: `"""Deterministic TRL scoring. Never imports observatory.claims or anthropic (C5)."""`.

- [ ] **Step 6: Extend the isolation test**

Append to `tests/test_claims_isolation.py`:

```python
def test_trl_package_never_imports_claims_or_anthropic():
    trl = PACKAGE / "trl"
    offenders = [p for p in trl.rglob("*.py")
                 if any(n == "anthropic" or "claims" in n.split(".") for n in _imports(p))]
    assert offenders == []
```

- [ ] **Step 7: Run tests**

Run: `python -m pytest tests/test_trl_schema.py tests/test_trl_tracked.py tests/test_claims_isolation.py tests/test_claims_verify.py -q`
Expected: all pass. Then `python -m pytest -q` and `ruff check observatory tests`; expected: clean.

- [ ] **Step 8: Commit**

```bash
git add observatory/trl observatory/textnorm.py observatory/claims/verify.py pyproject.toml tests/test_trl_schema.py tests/test_trl_tracked.py tests/test_claims_isolation.py tests/fixtures/trl/sort-sheet.xlsx
git commit -m "TRL claim schema, band map, and the tracked set read from the owner's sort sheet"
```

---

### Task 3: Weights table and the scorer

**Files:**
- Create: `observatory/trl/weights.yaml`, `observatory/trl/score.py`
- Test: `tests/test_trl_score.py`

**Interfaces:**
- Consumes: claim dicts with the eight `schema.FIELDS` plus `doc_date` (ISO date), `quote_verified` (bool), `claim_id`.
- Produces:
  - `load_weights(path=None) -> Weights` (frozen dataclass: `actor: dict[str,float]`, `source: dict[str,float]`, `half_life_days: int`, `support_threshold: float`, `contrary_penalty: float`, `version: int`).
  - `claim_weight(claim, as_of: date, w: Weights) -> float`.
  - `estimate(claims: list[dict], as_of: date, w: Weights) -> TRLEstimate` with fields `point: int | None`, `low: int | None`, `high: int | None`, `support: dict[int, float]` (weighted support by level), `top: list[dict]` (three claims that most support `point`), `contrary: dict | None`, `n_claims: int`, `n_verified: int`.

- [ ] **Step 1: Write the failing tests**

`tests/test_trl_score.py`:

```python
import datetime as dt
from observatory.trl import score

AS_OF = dt.date(2026, 9, 30)
W = score.load_weights()


def claim(ct, actor="user_firm", src="press_release", days_ago=30, verified=True, setting="one_site", cid=None):
    return {"claim_id": cid or f"{ct}-{actor}-{days_ago}", "tech_id": "delivery_drones", "claim_type": ct,
            "actor_type": actor, "actor": "x", "setting": setting, "quantity": "", "quote": "q",
            "source_type": src, "doc_date": (AS_OF - dt.timedelta(days=days_ago)).isoformat(),
            "quote_verified": verified}


def test_no_claims_gives_no_estimate():
    e = score.estimate([], AS_OF, W)
    assert e.point is None and e.low is None and e.high is None and e.n_claims == 0


def test_a_hundred_papers_cannot_lift_the_point_above_three():
    claims = [claim("proposes", actor="university", src="paper", cid=f"p{i}") for i in range(100)]
    assert score.estimate(claims, AS_OF, W).point <= 3


def test_one_verified_multi_site_operation_by_a_user_firm_sets_seven_or_eight():
    claims = [claim("proposes", actor="university", src="paper", cid=f"p{i}") for i in range(20)]
    claims.append(claim("demonstrates_in_operation", setting="multiple_sites"))
    assert score.estimate(claims, AS_OF, W).point in (7, 8)


def test_point_is_the_highest_level_with_sufficient_support_not_an_average():
    claims = [claim("pilots", cid=f"a{i}") for i in range(5)] + [claim("operates_at_scale", actor="startup", src="press_release", cid="b")]
    e = score.estimate(claims, AS_OF, W)
    # One startup press release is below the support threshold for 9; five user-firm pilots hold 6.
    assert e.point == 6 and e.high >= 6


def test_unverified_quotes_carry_no_weight():
    claims = [claim("operates_at_scale", verified=False)]
    assert score.estimate(claims, AS_OF, W).point is None


def test_recency_decays_with_the_half_life():
    fresh = score.claim_weight(claim("pilots", days_ago=0), AS_OF, W)
    old = score.claim_weight(claim("pilots", days_ago=W.half_life_days), AS_OF, W)
    assert abs(old - fresh / 2) < 1e-9


def test_abandons_is_reported_as_the_contrary_claim_and_lowers_support():
    base = [claim("demonstrates_in_operation", cid=f"d{i}") for i in range(3)]
    with_drop = base + [claim("abandons", cid="x")]
    a, b = score.estimate(base, AS_OF, W), score.estimate(with_drop, AS_OF, W)
    assert b.contrary is not None and b.contrary["claim_id"] == "x"
    assert b.support[8] < a.support[8]


def test_top_three_are_the_heaviest_claims_at_the_point_level():
    claims = [claim("pilots", actor="startup", cid="s"), claim("pilots", actor="user_firm", cid="u"),
              claim("pilots", actor="government", cid="g"), claim("pilots", actor="analyst", cid="a")]
    e = score.estimate(claims, AS_OF, W)
    assert len(e.top) == 3 and e.top[0]["claim_id"] == "u"


def test_weights_table_is_complete_over_the_closed_sets():
    from observatory.trl import schema
    assert set(W.actor) == set(schema.ACTOR_TYPES)
    assert set(W.source) == set(schema.SOURCE_TYPES)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_trl_score.py -q`
Expected: FAIL with `ImportError: cannot import name 'score'`.

- [ ] **Step 3: Write the weights table**

`observatory/trl/weights.yaml` (the owner edits this file, like the lexicon; every number is a decision):

```yaml
version: 1
# Weighted support for a TRL level = sum over claims of
#   actor[actor_type] * source[source_type] * setting[setting] * recency(doc_date)
# recency = 0.5 ** (days_old / half_life_days). Unverified quotes weigh 0.
# The point estimate is the HIGHEST level whose cumulative support (that level
# and above) reaches support_threshold. Averaging is deliberately absent.
half_life_days: 365
support_threshold: 1.0
# An "abandons" claim subtracts contrary_penalty * its weight from every level
# in the band it names, so a retreat shows as lowered support, not as silence.
contrary_penalty: 1.0
actor:
  user_firm: 1.0        # the party that would bear the cost of being wrong
  government: 0.9
  incumbent_vendor: 0.6
  startup: 0.4          # announcing is the business model
  analyst: 0.5
  university: 0.3
  unclear: 0.2
source:
  filing: 1.0           # attested under liability
  government_record: 1.0
  press_release: 0.6
  trade_article: 0.7
  paper: 0.5
  patent: 0.4
  funding_record: 0.6
  analyst_note: 0.6
  code_repository: 0.3
  job_posting: 0.5
  forum_post: 0.2
setting:
  network_wide: 1.0
  multiple_sites: 0.9
  one_site: 0.7
  test_site: 0.5
  lab: 0.3
  unclear: 0.4
```

- [ ] **Step 4: Implement score.py**

```python
# observatory/trl/score.py
"""Claims in, a TRL estimate out. Deterministic, and every number traceable
to the weights table and the claims listed in the result (spec §4, C4)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import schema

WEIGHTS_PATH = Path(__file__).with_name("weights.yaml")
LEVELS = tuple(range(1, 10))


@dataclass(frozen=True)
class Weights:
    version: int
    half_life_days: int
    support_threshold: float
    contrary_penalty: float
    actor: dict
    source: dict
    setting: dict


@dataclass(frozen=True)
class TRLEstimate:
    point: int | None
    low: int | None
    high: int | None
    support: dict = field(default_factory=dict)
    top: list = field(default_factory=list)
    contrary: dict | None = None
    n_claims: int = 0
    n_verified: int = 0


def load_weights(path: Path | None = None) -> Weights:
    raw = yaml.safe_load((path or WEIGHTS_PATH).read_text())
    return Weights(**{k: raw[k] for k in ("version", "half_life_days", "support_threshold",
                                          "contrary_penalty", "actor", "source", "setting")})


def _days_old(claim: dict, as_of: dt.date) -> int:
    try:
        return max(0, (as_of - dt.date.fromisoformat(str(claim.get("doc_date"))[:10])).days)
    except (TypeError, ValueError):
        return w_default_age()


def w_default_age() -> int:
    return 365 * 2  # an undated document is treated as two years old


def claim_weight(claim: dict, as_of: dt.date, w: Weights) -> float:
    if not claim.get("quote_verified"):
        return 0.0
    recency = 0.5 ** (_days_old(claim, as_of) / w.half_life_days)
    return (w.actor[claim["actor_type"]] * w.source[claim["source_type"]]
            * w.setting[claim["setting"]] * recency)


def estimate(claims: list[dict], as_of: dt.date, w: Weights) -> TRLEstimate:
    support = {level: 0.0 for level in LEVELS}
    weighted: list[tuple[float, dict]] = []
    contrary: tuple[float, dict] | None = None
    n_verified = 0
    for claim in claims:
        weight = claim_weight(claim, as_of, w)
        n_verified += 1 if claim.get("quote_verified") else 0
        if weight == 0.0:
            continue
        if claim["claim_type"] == "abandons":
            # The band it contradicts is the one its setting would otherwise evidence:
            # treat it as an operation-level claim withdrawn.
            for level in range(7, 10):
                support[level] -= w.contrary_penalty * weight
            if contrary is None or weight > contrary[0]:
                contrary = (weight, claim)
            continue
        lo, hi = schema.BAND[claim["claim_type"]]
        for level in range(lo, hi + 1):
            support[level] += weight
        weighted.append((weight, claim))
    if not weighted:
        return TRLEstimate(None, None, None, support, [], contrary[1] if contrary else None,
                           len(claims), n_verified)
    # Cumulative support from the top: a level is held if it, or anything above it, is evidenced enough.
    cumulative, running = {}, 0.0
    for level in reversed(LEVELS):
        running += max(0.0, support[level])
        cumulative[level] = running
    held = [level for level in LEVELS if cumulative[level] >= w.support_threshold]
    point = max(held) if held else min(schema.BAND[c["claim_type"]][0] for _, c in weighted)
    evidenced = [level for level in LEVELS if support[level] > 0]
    low, high = min(evidenced), max(evidenced)
    at_point = sorted((wt, c) for wt, c in weighted
                      if schema.BAND[c["claim_type"]][0] <= point <= schema.BAND[c["claim_type"]][1])
    top = [c for _, c in sorted(at_point, key=lambda x: -x[0])[:3]]
    return TRLEstimate(point, low, high, support, top, contrary[1] if contrary else None,
                       len(claims), n_verified)
```

Check `test_point_is_the_highest_level_with_sufficient_support_not_an_average` by hand before running: five user-firm press-release pilots at one site, 30 days old: each 1.0·0.6·0.7·0.5^(30/365)=0.397, total 1.98 on levels 5–6; the startup scale claim 0.4·0.6·0.7·0.945=0.159 on level 9. Cumulative at 9 is 0.159 < 1.0; at 6 is 2.14 ≥ 1.0 → point 6. High is 9 (evidenced), which satisfies `e.high >= 6`. For the multi-site test: one claim 1.0·0.6·0.9·0.945=0.51 on 7–8 — below threshold 1.0, so point falls to 6? No: cumulative at 7 = 0.51 + 0 = 0.51 < 1.0, so 7 is not held; the twenty papers hold 1–2; point = 2. **The test expects 7 or 8, so the threshold must be met by one strong claim.** Set `support_threshold: 0.5` in the yaml and recheck the scale test: cumulative at 9 = 0.159 < 0.5, still not held; at 6 = 2.14 → point 6. Good. Record the threshold's reasoning in the yaml comment: one recent, verified, multi-site claim from a user firm in a press release is enough to hold a level; one startup press release is not.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_trl_score.py -q`
Expected: all pass. If `test_top_three...` fails on ordering, sort key must be weight descending; `u` (1.0) > `g` (0.9) > `a` (0.5) > `s` (0.4).

- [ ] **Step 6: Commit**

```bash
git add observatory/trl/weights.yaml observatory/trl/score.py tests/test_trl_score.py
git commit -m "TRL scorer: weighted support per level, highest held level as the point, weights table the owner edits"
```

---

### Task 4: Pilot-band source probe (measurement; gates Task 5's source list)

**Why:** On 2026-09-24 the observatory's own database showed, for the 24 tracked technologies over the trailing 26 weeks, that evidence is almost all arXiv, GitHub and NSF (TRL 1–4), that seven technologies had one observation or none (`autonomous_yard` 0, `hydrogen_trucks` 0, `gs1_2d` 0, `freight_charging` 1, `smart_labels` 1, `quantum_logistics` 1, `private_5g_warehouse` 2), and that the pilot-and-first-site band has no free source at all now that trade press is frozen. If no free source reaches that band, Phase 1 can estimate TRL 1–4 only, and the owner must decide whether to wait for the paid news licence. This task measures that before Task 5 builds anything.

**Files:**
- Create: `docs/experiments/trl/probe.py`
- Create: `docs/trl-probe-2026-09-<dd>.md` (the measurement report; date of the run)
- No package code; no tests beyond a smoke run. Raw responses go to `data/trl/probe/` (gitignored: add `data/trl/` to `.gitignore` in this task).

**Interfaces:**
- Produces: a table, per candidate source × technology, of documents found in the last 8 weeks and a hand count of how many describe a pilot, first site, purchase or scaled operation.

- [ ] **Step 1: Write the probe**

```python
# docs/experiments/trl/probe.py
"""Can any free source reach the pilot band (TRL 5-8) for pre-practice
technologies? Three candidates, five technologies, eight weeks. Raw kept.

  GDELT DOC 2.0     article list by keyword; titles and URLs only; one request per 5 s.
  GlobeNewswire     press-release search page (HTML), full text on the release page.
  PR Newswire       press-release search page (HTML), full text on the release page.

Usage: probe.py [--weeks 8]
"""

import argparse, json, re, sys, time, datetime as dt
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from observatory import http  # noqa: E402

OUT = ROOT / "data" / "trl" / "probe"
TECHS = {
    "autonomous_trucking": '"autonomous truck" OR "driverless truck"',
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
    return r.text, sorted(set("https://www.globenewswire.com" + l for l in links))


def prnewswire(session, query):
    url = "https://www.prnewswire.com/search/news/?keyword=" + quote_plus(query.replace('"', ""))
    r = http.fetch(session, url, limiter=http.RateLimiter(2.0))
    links = re.findall(r'href="(/news-releases/[^"]+\.html)"', r.text)
    return r.text, sorted(set("https://www.prnewswire.com" + l for l in links))


def main():
    p = argparse.ArgumentParser(); p.add_argument("--weeks", type=int, default=8)
    args = p.parse_args()
    end = dt.date.today(); start = end - dt.timedelta(weeks=args.weeks)
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
                rows.append((tech, name, -1, -1, [str(e)])); continue
            (OUT / f"{name}-{tech}.html").write_text(raw)
            rows.append((tech, name, len(links), None, links[:5]))
    print("| technology | source | documents | pilot-worded titles | examples |")
    print("|---|---|---|---|---|")
    for tech, src, n, k, ex in rows:
        print(f"| {tech} | {src} | {n} | {'' if k is None else k} | {'<br>'.join(str(e)[:90] for e in ex)} |")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `python docs/experiments/trl/probe.py --weeks 8 | tee /dev/stderr > /tmp/probe.md`
Expected: a table with 15 rows; GDELT requests take at least 5 s each. If a press-release site returns 403 or a JavaScript shell, record that as the finding for that source.

- [ ] **Step 3: Hand-read**

For each technology, open the first ten GDELT titles and the first five press releases per site and count how many describe a pilot, first site, purchase, contract or scaled operation by a named user firm. Write `docs/trl-probe-2026-09-<dd>.md` with: the table, the hand counts, one paragraph per source on licence and mineability (GDELT: open data, mining permitted, titles and URLs only, article bodies are the publisher's; press releases: issued for redistribution, full text on the release page), and a **verdict**: which sources, if any, reach the pilot band at ≥ 3 pilot-band documents per technology per 8 weeks.

- [ ] **Step 4: Decide and record**

If at least one source passes for at least 3 of 5 technologies, Task 5 adds a collector for it (the plan gives the GDELT shape; a press-release collector follows the same `fetch_raw`/`parse` contract). If none passes, Task 5 runs on the existing collectors only and the report page (Task 7) carries a standing line: "Pilot-band evidence is not collected until a mineable news source is licensed." Either way, append the verdict and the reversal condition to the report and to STATUS §8 in Task 8.

- [ ] **Step 5: Commit**

```bash
git add docs/experiments/trl/probe.py docs/trl-probe-2026-09-*.md .gitignore
git commit -m "Probe: can free sources reach the pilot band for pre-practice technologies (measured, with verdict)"
```

---

### Task 5: Document access and the offline extraction command

**Files:**
- Create: `observatory/trl/documents.py`, `observatory/claims/trl_prompt.py`, `observatory/claims/extract_trl.py`
- Create (only if Task 4 passed for GDELT): `observatory/collectors/gdelt.py`, `tests/test_collector_gdelt.py`, `tests/fixtures/gdelt_page.json`; register in `observatory/run.py` `COLLECTORS` and add a `sources.yaml` entry with `family: news`, `signal: news_articles`, and a `licence:` note ("GDELT open data; article bodies are the publisher's; the report cites, never reproduces").
- Test: `tests/test_trl_documents.py`, `tests/test_claims_trl_prompt.py`, `tests/test_claims_extract_trl.py`, fixture `tests/fixtures/trl/raw/2026-W38/hn/000.json` (copy of `tests/fixtures/hn_page.json`).

**Interfaces:**
- Consumes: `store.connect()`, `base.read_raw(source, week)`, each collector's `parse(text) -> list[Document]`, `run.COLLECTORS`, `quarter.weeks_in_period(name)`.
- Produces:
  - `documents.texts_for(conn, tech_id: str, weeks: list[str], collectors) -> Iterator[DocText]` where `DocText` is a frozen dataclass `(source, doc_id, doc_date, title, url, text, observation_id)`; one per observation row whose raw file still parses to that `doc_id`.
  - `trl_prompt.PROMPT_VERSION = "trl-1"`, `system(tech_ids_with_names: list[tuple[str, str]]) -> str`, `user(doc: DocText) -> str`.
  - `extract_trl.main(argv)`; writes `data/trl/claims-<period>.jsonl`, `data/trl/raw-<period>-<model>/<claim source>-<doc_id hash>.json`, `data/trl/usage-<period>-<model>.json`. Each claim row: `claim_id, period, source, doc_id, doc_date, url, title, tech_id, claim_type, actor_type, actor, setting, quantity, quote, quote_verified, source_type, model, prompt_version`.

- [ ] **Step 1: Failing tests for documents.py**

`tests/test_trl_documents.py`:

```python
import shutil
from pathlib import Path

from observatory import config, matcher, store
from observatory.collectors.hn import HackerNewsCollector
from observatory.trl import documents

FIX = Path(__file__).parent / "fixtures"


def _seed(tmp_path, monkeypatch):
    raw = tmp_path / "raw"; monkeypatch.setattr(config, "RAW_DIR", raw)
    dst = raw / "2026-W38" / "hn"; dst.mkdir(parents=True)
    shutil.copy(FIX / "hn_page.json", dst / "000.json")
    conn = store.connect(":memory:"); store.init_schema(conn)
    raw_ref = store.record_raw(conn, "hn", "2026-W38", "http://x", 200, str(dst / "000.json"))
    wl = matcher.load_watchlist()
    for doc in HackerNewsCollector().parse((dst / "000.json").read_text()):
        store.upsert_observations(conn, matcher.observations_for_document(wl, doc, "hn", "2026-W38", raw_ref))
    return conn


def test_texts_for_returns_the_parsed_text_behind_each_observation(tmp_path, monkeypatch):
    conn = _seed(tmp_path, monkeypatch)
    tech = conn.execute("SELECT tech_id FROM observations LIMIT 1").fetchone()["tech_id"]
    docs = list(documents.texts_for(conn, tech, ["2026-W38"], (HackerNewsCollector(),)))
    assert docs and docs[0].source == "hn" and docs[0].text and docs[0].doc_id.startswith("hn:")


def test_texts_for_is_empty_for_a_week_with_no_raw(tmp_path, monkeypatch):
    conn = _seed(tmp_path, monkeypatch)
    assert list(documents.texts_for(conn, "delivery_drones", ["2026-W01"], (HackerNewsCollector(),))) == []
```

Check `store.record_raw`'s real signature (`sed -n 278,290p observatory/store.py`) and adjust the call.

- [ ] **Step 2: Implement documents.py**

```python
# observatory/trl/documents.py
"""The text behind an observation. The database stores no document text (raw
before parse); this re-parses the raw file the observation came from."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from ..collectors import base


@dataclass(frozen=True)
class DocText:
    source: str
    doc_id: str
    doc_date: str | None
    title: str | None
    url: str | None
    text: str
    observation_id: int


def texts_for(conn, tech_id: str, weeks: list[str], collectors) -> Iterator[DocText]:
    by_name = {c.name: c for c in collectors}
    marks = ",".join("?" * len(weeks))
    rows = conn.execute(
        f"SELECT id, source, week, doc_id, doc_date, title, url FROM observations "
        f"WHERE tech_id = ? AND week IN ({marks}) ORDER BY doc_date DESC", [tech_id, *weeks]).fetchall()
    wanted: dict[tuple[str, str], list] = {}
    for r in rows:
        wanted.setdefault((r["source"], r["week"]), []).append(dict(r))
    for (source, week), obs in wanted.items():
        collector = by_name.get(source)
        if collector is None:
            continue
        by_doc = {o["doc_id"]: o for o in obs}
        for _, text in base.read_raw(source, week):
            for doc in collector.parse(text):
                o = by_doc.pop(doc.doc_id, None)
                if o is None:
                    continue
                body = " ".join(p for p in (doc.title, doc.text) if p)
                yield DocText(source, doc.doc_id, doc.date, doc.title, doc.url, body, o["id"])
            if not by_doc:
                break
```

Run: `python -m pytest tests/test_trl_documents.py -q`; expected: pass.

- [ ] **Step 3: Failing tests for the prompt**

`tests/test_claims_trl_prompt.py`:

```python
from observatory.claims import trl_prompt
from observatory.trl.documents import DocText


def test_system_prompt_has_no_dates_or_ids_so_the_cache_holds():
    s = trl_prompt.system([("delivery_drones", "Delivery drones")])
    assert "2026" not in s and "delivery_drones" in s and trl_prompt.UNTRUSTED in s


def test_system_prompt_names_every_closed_set():
    from observatory.trl import schema
    s = trl_prompt.system([("delivery_drones", "Delivery drones")])
    for word in schema.CLAIM_TYPES + schema.ACTOR_TYPES + schema.SETTINGS + schema.SOURCE_TYPES:
        assert word in s


def test_user_prompt_wraps_the_document_and_marks_it_untrusted():
    d = DocText("hn", "hn:1", "2026-09-01", "T", "http://u", "Walmart pilots drones.", 1)
    u = trl_prompt.user(d)
    assert "DOCUMENT TEXT" in u and "Walmart pilots drones." in u and "hn" in u and "2026-09-01" in u
```

- [ ] **Step 4: Implement trl_prompt.py**

```python
# observatory/claims/trl_prompt.py
"""The TRL extraction prompt, versioned and published. Any change to a string
here is a change to the instrument: bump PROMPT_VERSION and re-run the
placement check (Task 6) before the new version reads a period."""

from __future__ import annotations

from ..trl import schema
from ..trl.documents import DocText
from .prompt import UNTRUSTED

PROMPT_VERSION = "trl-1"

_RULES = """\
You are coding documents for a research tracker that estimates how mature
supply chain technologies are, on a Technology Readiness Level scale.

A claim is one statement in this document that a named actor did something
with one of the tracked technologies. Code what the document SAYS HAPPENED,
not what the technology is or could do. Descriptions of the technology,
market forecasts and generic risk language are not claims.

claim_type, the strongest verb the text supports, taken literally:
- proposes: describes, analyses or argues for the technology; nothing built
- simulates: models or simulates it; nothing physical
- prototypes: built and tested a prototype in a lab or on a test track
- pilots: trial at one or a few real sites, explicitly limited
- demonstrates_in_operation: running in a real operation, not described as a trial
- sells: a vendor offers it commercially (a product launch counts)
- buys: a user firm orders or purchases it (an order or contract counts)
- operates_at_scale: across a network, in most facilities, or a count that says so
- abandons: discontinued, wound down, paused indefinitely, bankruptcy of the operator

actor_type: university, startup, incumbent_vendor, user_firm (the party that
uses it in its own operations), government, analyst, unclear.
actor: the actor's name as written, or "unclear".
setting: lab, test_site, one_site, multiple_sites, network_wide, unclear.
quantity: any count of sites, units, vehicles, customers or money the text
gives for THIS claim, verbatim; empty if none.
source_type: what this document is: paper, patent, filing, press_release,
trade_article, code_repository, job_posting, analyst_note, funding_record,
government_record, forum_post.
quote: copy the sentence or clause VERBATIM, at most 400 characters, no
paraphrase, no ellipsis. A quote not in the text is a failed claim.

If the document makes no claim about a tracked technology, return an empty
claims list.
"""


def system(techs: list[tuple[str, str]]) -> str:
    frame = "\n".join(f"- {tid}: {name}" for tid, name in techs)
    return _RULES + "\nTRACKED TECHNOLOGIES (tech_id must be one of these)\n" + frame + "\n\n" + UNTRUSTED.replace("FILING TEXT", "DOCUMENT TEXT").replace("filer", "document")


def user(doc: DocText) -> str:
    return (f"SOURCE: {doc.source}\nDOC_ID: {doc.doc_id}\nDATE: {doc.doc_date or 'unknown'}\n"
            f"TITLE: {doc.title or ''}\nURL: {doc.url or ''}\n\nDOCUMENT TEXT:\n{doc.text}\n")
```

Run: `python -m pytest tests/test_claims_trl_prompt.py -q`; expected: pass.

- [ ] **Step 5: Failing test for the extraction command, with a fake client**

`tests/test_claims_extract_trl.py`:

```python
import json
from types import SimpleNamespace

from observatory.claims import extract_trl
from observatory.trl.documents import DocText


class FakeStream:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def get_final_message(self):
        usage = SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=0, cache_creation_input_tokens=0)
        return SimpleNamespace(stop_reason="end_turn", usage=usage,
                               content=[SimpleNamespace(type="text", text=json.dumps(self.payload))],
                               to_json=lambda: "{}")


class FakeClient:
    def __init__(self, payload): self.payload = payload; self.calls = []
    class messages:  # noqa: N801
        pass
    def stream(self, **kw): self.calls.append(kw); return FakeStream(self.payload)


def test_one_document_yields_verified_claim_rows(tmp_path):
    doc = DocText("hn", "hn:1", "2026-09-01", "T", "http://u", "Walmart is piloting drone delivery at 34 stores.", 1)
    payload = {"claims": [{"tech_id": "delivery_drones", "claim_type": "pilots", "actor_type": "user_firm",
                           "actor": "Walmart", "setting": "multiple_sites", "quantity": "34 stores",
                           "quote": "Walmart is piloting drone delivery at 34 stores.", "source_type": "forum_post"}]}
    client = FakeClient(payload)
    rows = extract_trl.extract_document(client, "claude-sonnet-5", [("delivery_drones", "Delivery drones")], doc, "2026-Q3")
    assert len(rows) == 1 and rows[0]["quote_verified"] is True and rows[0]["claim_type"] == "pilots"
    assert rows[0]["prompt_version"] == "trl-1" and len(rows[0]["claim_id"]) == 12


def test_an_unverifiable_quote_is_kept_but_marked(tmp_path):
    doc = DocText("hn", "hn:1", "2026-09-01", "T", "http://u", "Nothing about drones here.", 1)
    payload = {"claims": [{"tech_id": "delivery_drones", "claim_type": "pilots", "actor_type": "user_firm",
                           "actor": "Walmart", "setting": "one_site", "quantity": "",
                           "quote": "Walmart pilots drones.", "source_type": "forum_post"}]}
    rows = extract_trl.extract_document(FakeClient(payload), "claude-sonnet-5", [("delivery_drones", "Delivery drones")], doc, "2026-Q3")
    assert rows[0]["quote_verified"] is False


def test_cost_estimate_refuses_above_the_ceiling():
    docs = [DocText("hn", f"hn:{i}", "2026-09-01", "T", None, "x" * 40000, i) for i in range(50)]
    assert extract_trl.estimate_dollars(docs, "claude-sonnet-5") > 1.0
```

- [ ] **Step 6: Implement extract_trl.py**

```python
# observatory/claims/extract_trl.py
"""The quarterly TRL claim extraction. Offline, explicit, pinned model, cached
system prompt, refusals recorded. The only sanctioned model call (spec C5).

  python -m observatory.claims.extract_trl --period 2026-Q3 [--model claude-sonnet-5]
         [--limit 5] [--max-dollars 20] [--tech delivery_drones]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from .. import config, matcher, quarter, store
from ..trl import documents, schema, tracked
from . import trl_prompt, verify

PRICE_PER_MTOK_INPUT = {"claude-opus-5-5": 5.00, "claude-sonnet-5": 3.00}
CHARS_PER_TOKEN = 3.5
TRL_DIR = config.DATA_DIR / "trl"


def estimate_dollars(docs, model: str) -> float:
    chars = sum(len(d.text) for d in docs) + 4000 * len(docs)
    return chars / CHARS_PER_TOKEN / 1e6 * PRICE_PER_MTOK_INPUT[model]


def _read(client, model: str, system: str, user: str, fmt: dict):
    with client.messages.stream(
        model=model, max_tokens=8000,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": fmt}},
    ) as stream:
        return stream.get_final_message()


def extract_document(client, model: str, techs: list[tuple[str, str]], doc: documents.DocText,
                     period: str) -> list[dict]:
    system = trl_prompt.system(techs)
    fmt = schema.response_schema([t for t, _ in techs])
    message = _read(client, model, system, trl_prompt.user(doc), fmt)
    if message.stop_reason == "refusal":
        return [{"refused": True, "source": doc.source, "doc_id": doc.doc_id, "period": period}]
    body = next((b.text for b in message.content if b.type == "text"), "")
    claims = schema.validate(json.loads(body), [t for t, _ in techs])
    rows = []
    for c in claims:
        rows.append({
            "claim_id": schema.claim_id(doc.source, doc.doc_id, c["tech_id"], c["quote"]),
            "period": period, "source": doc.source, "doc_id": doc.doc_id, "doc_date": doc.doc_date,
            "url": doc.url, "title": doc.title, **c,
            "quote_verified": verify.verify_quote(c["quote"], doc.text),
            "model": model, "prompt_version": trl_prompt.PROMPT_VERSION,
        })
    return rows


def main(argv=None) -> int:
    import anthropic  # here, not at module top: the import graph test allows it only in this package

    p = argparse.ArgumentParser()
    p.add_argument("--period", required=True, metavar="YYYY-Qn")
    p.add_argument("--model", default="claude-sonnet-5")
    p.add_argument("--limit", type=int, default=None, help="documents per technology")
    p.add_argument("--max-dollars", type=float, default=20.0)
    p.add_argument("--tech", default=None, help="one tech_id only")
    args = p.parse_args(argv)

    config.load_dotenv()
    from ..run import COLLECTORS
    watchlist = matcher.load_watchlist()
    ids = [args.tech] if args.tech else list(tracked.tracked_ids())
    techs = [(t, watchlist.by_id(t).name) for t in ids]
    weeks = quarter.weeks_in_period(args.period)
    conn = store.connect()
    docs = []
    for tid in ids:
        found = list(documents.texts_for(conn, tid, weeks, COLLECTORS))
        docs.extend(found[: args.limit] if args.limit else found)
    est = estimate_dollars(docs, args.model)
    print(f"{args.period} / {args.model}: {len(docs)} documents, ~${est:.2f} before caching")
    if est > args.max_dollars:
        print(f"estimate exceeds --max-dollars {args.max_dollars}; refusing to start"); return 2

    TRL_DIR.mkdir(parents=True, exist_ok=True)
    raw_dir = TRL_DIR / f"raw-{args.period}-{args.model}"; raw_dir.mkdir(exist_ok=True)
    out_path = TRL_DIR / f"claims-{args.period}.jsonl"
    client = anthropic.Anthropic()
    n = 0
    with open(out_path, "a", encoding="utf8") as out:
        for doc in docs:
            try:
                rows = extract_document(client, args.model, techs, doc, args.period)
            except anthropic.RateLimitError as e:
                time.sleep(int(e.response.headers.get("retry-after", "60")))
                rows = extract_document(client, args.model, techs, doc, args.period)
            except (anthropic.APIStatusError, anthropic.APIConnectionError, ValueError, json.JSONDecodeError) as e:
                print(f"{doc.source} {doc.doc_id}: {type(e).__name__}: {e} — recorded, skipped")
                rows = [{"error": str(e), "source": doc.source, "doc_id": doc.doc_id, "period": args.period}]
            key = hashlib.sha1(doc.doc_id.encode()).hexdigest()[:10]
            (raw_dir / f"{doc.source}-{key}.json").write_text(json.dumps(rows, ensure_ascii=False))
            for r in rows:
                out.write(json.dumps(r, ensure_ascii=False) + "\n"); n += 1
    print(f"{out_path}: {n} rows appended")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Note `--period` appends; a re-run of the same period must first delete the claims file, and the command should say so in its docstring. `config.load_dotenv` exists on `main` (used by `extract.py` on `phase0`); confirm with `grep -n load_dotenv observatory/config.py`.

- [ ] **Step 7: Run the tests, the isolation test, and a smoke extraction**

Run: `python -m pytest tests/test_claims_extract_trl.py tests/test_claims_isolation.py -q`; expected: pass.
Smoke: `python -m observatory.claims.extract_trl --period 2026-Q3 --tech supply_chain_digital_twin --limit 3 --max-dollars 1`; expected: three documents read, a claims file with rows, cost well under a dollar. Read the rows: quotes verified, claim types plausible.

- [ ] **Step 8: Commit**

```bash
git add observatory/trl/documents.py observatory/claims/trl_prompt.py observatory/claims/extract_trl.py tests/test_trl_documents.py tests/test_claims_trl_prompt.py tests/test_claims_extract_trl.py
git commit -m "TRL extraction: document text behind observations, versioned prompt trl-1, offline command with a cost ceiling"
```

If Task 4 passed for GDELT, add the collector in a second commit of this task, modelled on `observatory/collectors/hn.py`: `fetch_raw` builds one request per tracked technology's first include pattern (plain words, not regex; keep a `QUERIES` dict in the module), 5-second limiter, and `parse` yields `Document(doc_id=f"gdelt:{sha1(url)[:16]}", date=seendate[:8] as ISO, title=title, text=title, url=url, entity=domain)`. Test `parse` against a saved fixture exactly as `tests/test_collector_hn.py` does. Titles alone are thin text; the claim prompt will see mostly headlines from this source, which the probe report must state.

---

### Task 6: Two-reader placement check (measurement; gates Task 7)

**Why:** Spec §10 item 3. Before a report exists, show that two readers place a technology on the scale within one level of each other from the same twenty claims. If they cannot, the weights table is decorating noise.

**Files:**
- Create: `observatory/trl/placement.py`, `tests/test_trl_placement.py`
- Create: `docs/audit/trl-placement-sheet.md`, `docs/audit/trl-placement-verdicts.csv` (template; Kevin fills `reader_trl`), `docs/trl-placement-2026-<mm>-<dd>.md` (the report)

**Interfaces:**
- Consumes: `data/trl/claims-2026-Q3.jsonl` from Task 5; `score.estimate`.
- Produces: `placement.sheet(claims_by_tech: dict[str, list[dict]]) -> str` (Markdown), `placement.verdict_template(tech_ids) -> str` (CSV with `tech_id, reader_trl, reader_note`), `placement.agreement(verdicts: list[dict], estimates: dict[str, TRLEstimate]) -> dict` with keys `n`, `within_one`, `exact`, `mean_abs_diff`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_trl_placement.py
from observatory.trl import placement, score


def test_sheet_lists_each_technology_with_its_claims_fenced():
    md = placement.sheet({"delivery_drones": [{"claim_id": "abc", "claim_type": "pilots", "actor": "Walmart",
                                               "actor_type": "user_firm", "setting": "one_site", "quote": "q`x",
                                               "source": "hn", "doc_date": "2026-09-01", "url": "http://u",
                                               "quote_verified": True, "source_type": "forum_post", "quantity": ""}]})
    assert "## delivery_drones" in md and "abc" in md and "````" in md  # fence longer than the backtick in the quote


def test_agreement_counts_within_one_level():
    est = {"a": score.TRLEstimate(6, 5, 7), "b": score.TRLEstimate(3, 1, 3), "c": score.TRLEstimate(None, None, None)}
    verdicts = [{"tech_id": "a", "reader_trl": "7"}, {"tech_id": "b", "reader_trl": "5"}, {"tech_id": "c", "reader_trl": "4"}]
    r = placement.agreement(verdicts, est)
    assert r == {"n": 2, "within_one": 1, "exact": 0, "mean_abs_diff": 1.5}
```

- [ ] **Step 2: Implement placement.py**

```python
# observatory/trl/placement.py
"""The sheet a reader places technologies from, the CSV they hand back, and
the agreement measure. Same shape as docs/audit/sample-*.md."""

from __future__ import annotations

import csv
import io
import re

from .score import TRLEstimate

VERDICT_COLUMNS = ("tech_id", "reader_trl", "reader_note")


def _fence(*texts: str) -> str:
    longest = max((len(r) for t in texts for r in re.findall(r"`+", t or "")), default=0)
    return "`" * max(3, longest + 1)


def sheet(claims_by_tech: dict[str, list[dict]]) -> str:
    lines = ["# TRL placement sheet", "",
             "For each technology read its claims (at most twenty, heaviest first) and write ONE",
             "number, 1-9, in trl-placement-verdicts.csv: the highest level the evidence holds.",
             "Bands: 1-3 research; 4-6 prototype and pilot; 7-8 in real operation; 9 routine at scale.",
             "Do not look at the tracker's estimate first.", ""]
    for tech, claims in claims_by_tech.items():
        lines += [f"## {tech}", ""]
        for n, c in enumerate(claims[:20], start=1):
            f = _fence(c["quote"])
            lines += [f"{n}. `{c['claim_id']}` {c['claim_type']} | {c['actor_type']}: {c['actor']} | {c['setting']} | "
                      f"{c['source']} {c['doc_date'] or ''} | quote_verified: {'yes' if c.get('quote_verified') else 'no'}",
                      f"   {c.get('url') or ''}", f, c["quote"], f, ""]
    return "\n".join(lines)


def verdict_template(tech_ids) -> str:
    out = io.StringIO(); w = csv.DictWriter(out, fieldnames=list(VERDICT_COLUMNS)); w.writeheader()
    for t in tech_ids:
        w.writerow({"tech_id": t, "reader_trl": "", "reader_note": ""})
    return out.getvalue()


def agreement(verdicts: list[dict], estimates: dict[str, TRLEstimate]) -> dict:
    diffs = []
    for v in verdicts:
        e = estimates.get(v["tech_id"])
        if e is None or e.point is None or not str(v.get("reader_trl", "")).strip():
            continue
        diffs.append(abs(int(v["reader_trl"]) - e.point))
    n = len(diffs)
    return {"n": n, "within_one": sum(d <= 1 for d in diffs), "exact": sum(d == 0 for d in diffs),
            "mean_abs_diff": (sum(diffs) / n) if n else None}
```

Run: `python -m pytest tests/test_trl_placement.py -q`; expected: pass.

- [ ] **Step 3: Produce the sheet from real claims**

Run Task 5's command for ten technologies with the most observations (from the 2026-09-24 counts: `supply_chain_digital_twin`, `agentic_procurement`, `delivery_drones`, `cv_inspection`, `supply_chain_llm`, `autonomous_trucking`, `sidewalk_delivery_robots`, `additive_spares`, `electric_trucks`, `humanoid_logistics`), `--limit 20 --max-dollars 15`. Then a twelve-line script in `docs/experiments/trl/placement_sheet.py` that loads the JSONL, groups by tech, sorts each group by `score.claim_weight` descending, and writes `docs/audit/trl-placement-sheet.md` and `docs/audit/trl-placement-verdicts.csv`. Also run `score.estimate` per technology with `as_of = 2026-09-30` and save to `data/trl/estimates-2026-Q3.json` (not shown to the reader).

- [ ] **Step 4: Two readers**

Reader 1 is Kevin (the CSV). Reader 2 is a second model read: the same sheet, one call per technology, pinned model, prompt "Return the single TRL 1-9 the evidence holds, as JSON {\"trl\": n}"; store as `data/trl/placement-model.csv` with the same columns. The model is `claude-opus-5-5` so it is not the extractor grading itself. Both readers are compared with the tracker's estimate **and** with each other.

- [ ] **Step 5: Report and gate**

Write `docs/trl-placement-2026-<mm>-<dd>.md`: the three-way table (tech, Kevin, model, tracker point, tracker range), the three `agreement()` results, and the verdict. **Pass:** Kevin and the tracker within one level on at least 7 of 10, and Kevin and the model within one level on at least 7 of 10. **Fail:** anything less; then the weights table is revised once with the reasons written into the yaml comments, the estimates recomputed (no new extraction), and the comparison re-run once. A second fail stops the plan at this task; STATUS records it and the owner decides.

- [ ] **Step 6: Commit**

```bash
git add observatory/trl/placement.py tests/test_trl_placement.py docs/experiments/trl/placement_sheet.py docs/audit/trl-placement-sheet.md docs/audit/trl-placement-verdicts.csv docs/trl-placement-2026-*.md
git commit -m "Placement check: two readers against the tracker on ten technologies (measured, with verdict)"
```

---

### Task 7: The report page

**Files:**
- Create: `observatory/trl/report.py`, `observatory/templates/trl.html.j2`, `tests/test_trl_report.py`
- Modify: `observatory/run.py` (add `--trl-report PERIOD`)

**Interfaces:**
- Consumes: `data/trl/claims-<period>.jsonl`, `score.load_weights`, `score.estimate`, `tracked.tracked_ids`, `quarter.period_bounds(name)`, `quarter.brand_logo()`, `render`'s Jinja environment (check `grep -n "Environment\|def " observatory/render.py`).
- Produces: `report.build_context(period: str, claims_path: Path | None = None, as_of: date | None = None) -> dict` with keys `period`, `as_of`, `weights_version`, `prompt_versions`, `technologies` (list of dicts: `id, name, family, point, low, high, n_claims, n_verified, top, contrary, moved` where `moved` compares with the previous period's estimates file if present), `movers` (up, stalled, retreated), `notes` (standing lines such as the pilot-band caveat from Task 4); `report.render(period) -> Path` writing `output/trl-<period>.html`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_trl_report.py
import json
from observatory.trl import report


def _claims(tmp_path):
    rows = [{"claim_id": "a1", "period": "2026-Q3", "source": "hn", "doc_id": "hn:1", "doc_date": "2026-09-01",
             "url": "http://u", "title": "T", "tech_id": "delivery_drones", "claim_type": "pilots",
             "actor_type": "user_firm", "actor": "Walmart", "setting": "multiple_sites", "quantity": "34 stores",
             "quote": "Walmart is piloting drone delivery at 34 stores.", "quote_verified": True,
             "source_type": "forum_post", "model": "claude-sonnet-5", "prompt_version": "trl-1"},
            {"error": "boom", "source": "hn", "doc_id": "hn:2", "period": "2026-Q3"}]
    p = tmp_path / "claims-2026-Q3.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def test_context_estimates_each_tracked_technology_and_skips_error_rows(tmp_path):
    ctx = report.build_context("2026-Q3", _claims(tmp_path))
    drones = next(t for t in ctx["technologies"] if t["id"] == "delivery_drones")
    assert drones["point"] in (5, 6) and drones["n_claims"] == 1 and drones["top"][0]["claim_id"] == "a1"
    assert all(t["point"] is None for t in ctx["technologies"] if t["id"] != "delivery_drones")


def test_render_writes_a_page_that_shows_the_quote_and_the_weights_version(tmp_path, monkeypatch):
    from observatory import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    path = report.render("2026-Q3", _claims(tmp_path))
    html = path.read_text()
    assert "Walmart is piloting drone delivery" in html and "weights v1" in html and "TRL" in html
```

- [ ] **Step 2: Implement report.py**

```python
# observatory/trl/report.py
"""The TRL page: one estimate per tracked technology, the claims behind it,
and what moved since last period. Reads claims and weights; calls no model."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .. import config, matcher, quarter
from . import score, tracked

TRL_DIR = config.DATA_DIR / "trl"
TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def load_claims(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf8").splitlines():
        if line.strip():
            r = json.loads(line)
            if "claim_id" in r:
                rows.append(r)
    return rows


def _previous(period: str) -> dict:
    p = TRL_DIR / f"estimates-{quarter.previous_period(period)}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def build_context(period: str, claims_path: Path | None = None, as_of: dt.date | None = None) -> dict:
    claims_path = claims_path or TRL_DIR / f"claims-{period}.jsonl"
    claims = load_claims(claims_path)
    _, end = quarter.period_bounds(period)
    as_of = as_of or dt.date.fromisoformat(str(end)[:10])
    w = score.load_weights()
    watchlist = matcher.load_watchlist()
    previous = _previous(period)
    techs, estimates = [], {}
    for tid in tracked.tracked_ids():
        mine = [c for c in claims if c["tech_id"] == tid]
        e = score.estimate(mine, as_of, w)
        estimates[tid] = {"point": e.point, "low": e.low, "high": e.high}
        before = previous.get(tid, {}).get("point")
        moved = None if before is None or e.point is None else e.point - before
        t = watchlist.by_id(tid)
        techs.append({"id": tid, "name": t.name, "family": t.family, "point": e.point, "low": e.low,
                      "high": e.high, "n_claims": e.n_claims, "n_verified": e.n_verified, "top": e.top,
                      "contrary": e.contrary, "moved": moved})
    (TRL_DIR).mkdir(parents=True, exist_ok=True)
    (TRL_DIR / f"estimates-{period}.json").write_text(json.dumps(estimates, indent=2))
    movers = {"up": [t for t in techs if (t["moved"] or 0) > 0],
              "retreated": [t for t in techs if (t["moved"] or 0) < 0 or t["contrary"]],
              "unestimated": [t for t in techs if t["point"] is None]}
    return {"period": period, "period_display": quarter.period_display(period), "as_of": as_of.isoformat(),
            "weights_version": w.version, "prompt_versions": sorted({c["prompt_version"] for c in claims}),
            "technologies": sorted(techs, key=lambda t: (-(t["point"] or 0), t["name"])),
            "movers": movers, "logo": quarter.brand_logo(),
            "notes": ["Pilot-band evidence (TRL 5-8) is collected only from sources that permit mining; "
                      "see the probe report for what that covers this period."]}


def render(period: str, claims_path: Path | None = None) -> Path:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html"]))
    html = env.get_template("trl.html.j2").render(**build_context(period, claims_path))
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = config.OUTPUT_DIR / f"trl-{period}.html"
    out.write_text(html, encoding="utf8")
    return out
```

- [ ] **Step 3: The template**

`observatory/templates/trl.html.j2`, following `quarter.html.j2`'s head, branding block and fonts (copy its `<head>` and header markup; the NASPO / W. P. Carey lockup is required on every page). Body:

```html
<main>
  <h1>Pre-practice supply chain technologies: readiness, {{ period_display }}</h1>
  <p class="meta">As of {{ as_of }} · weights v{{ weights_version }} · prompt {{ prompt_versions|join(", ") }} · TRL is a maturity scale, not an adoption scale.</p>
  {% for note in notes %}<p class="note">{{ note }}</p>{% endfor %}
  <section id="movers">
    <h2>What moved</h2>
    <ul>
      {% for t in movers.up %}<li><strong>{{ t.name }}</strong> up to TRL {{ t.point }}</li>{% endfor %}
      {% for t in movers.retreated %}<li><strong>{{ t.name }}</strong> retreated{% if t.contrary %}: “{{ t.contrary.quote }}”{% endif %}</li>{% endfor %}
      {% if not movers.up and not movers.retreated %}<li>No level changes this period.</li>{% endif %}
    </ul>
  </section>
  {% for t in technologies %}
  <section class="tech" id="{{ t.id }}">
    <h2>{{ t.name }} <span class="trl">{% if t.point %}TRL {{ t.point }} <small>(range {{ t.low }}–{{ t.high }})</small>{% else %}not estimated{% endif %}</span></h2>
    <p class="counts">{{ t.n_claims }} claims, {{ t.n_verified }} with verified quotes.</p>
    {% for c in t.top %}
    <blockquote><p>“{{ c.quote }}”</p><footer>{{ c.actor }} ({{ c.actor_type }}), {{ c.claim_type }}, {{ c.setting }} · {{ c.source }} {{ c.doc_date }} · <a href="{{ c.url }}">source</a> · claim {{ c.claim_id }}</footer></blockquote>
    {% endfor %}
    {% if t.contrary %}<p class="contrary">Contrary: “{{ t.contrary.quote }}” — {{ t.contrary.actor }}, {{ t.contrary.doc_date }}</p>{% endif %}
  </section>
  {% endfor %}
</main>
```

- [ ] **Step 4: The CLI flag**

In `observatory/run.py` `main()`, add `parser.add_argument("--trl-report", default=None, metavar="YYYY-Qn", help="write the TRL page from data/trl/claims-<period>.jsonl")` and, beside the `--quarter` branch, `if args.trl_report: from .trl import report; print(report.render(args.trl_report)); return 0`. The import is local so the weekly path never loads `trl` (the isolation test allows `trl` anywhere, but keep the weekly import surface unchanged).

- [ ] **Step 5: Run tests and render the real page**

Run: `python -m pytest tests/test_trl_report.py tests/test_report_branding.py -q`; expected: pass (extend `test_report_branding.py` to include `output/trl-*.html` if it enumerates report files).
Run: `python -m observatory.run --trl-report 2026-Q3` and open `output/trl-2026-Q3.html`. Check the artifact: every estimated technology shows at least one quote with a working link; unestimated technologies say so; the lockup is present.

- [ ] **Step 6: Commit**

```bash
git add observatory/trl/report.py observatory/templates/trl.html.j2 observatory/run.py tests/test_trl_report.py tests/test_report_branding.py
git commit -m "TRL report page: estimate, range, top claims and contrary claim per technology; what moved"
```

---

### Task 8: STATUS, README and the rejection log

**Files:**
- Modify: `STATUS.md` (§1 what this is, §3 how to run, §7 next, §8 decisions), `README.md`, `docs/superpowers/specs/2026-09-23-pre-practice-trl-tracker-design.md` (§9 status lines only)

- [ ] **Step 1: STATUS**

Bring `STATUS.md` on branch `trl` to the current state: the 2026-09-23 direction, the two measurement verdicts (Tasks 4 and 6) with their reversal conditions, the commands (`extract_trl`, `--trl-report`), the frozen sources, and that the `phase0` branch is parked. Keep §2's generated table untouched; run `python -m observatory.run --write-status` and `python -m pytest tests/test_status_table.py -q`.

- [ ] **Step 2: README**

Replace the DAI paragraph with three sentences on the TRL tracker and a link to the spec.

- [ ] **Step 3: Full suite, lint, commit**

Run: `python -m pytest -q && ruff check observatory tests`; expected: clean.

```bash
git add STATUS.md README.md docs/superpowers/specs/2026-09-23-pre-practice-trl-tracker-design.md
git commit -m "STATUS and README for the TRL tracker; measurement verdicts and reversal conditions recorded"
```

- [ ] **Step 4: Hand back**

Do not merge `trl` into `main` and do not push. Report to the owner: test count, the two verdicts, the page path, and what the weights table's numbers are so he can change them.

---

## Self-review against the spec

- **§2 C1** → Task 1. **C2** → Task 4's licence paragraphs, sources.yaml `licence:` note in Task 5. **C3, §4 features and bands** → Task 2 schema, Task 3 scorer. **C4** → `quote_verified` gating in Task 3, quotes and links on the page in Task 7. **C5** → isolation test extended in Task 2, extraction only in `claims/` in Task 5. **C6** → Task 2 `tracked.py`.
- **§5 dashboard**: point, range, top three, contrary, movers → Task 7. The eight-quarter trajectory needs eight periods of estimates; Task 7 writes `estimates-<period>.json` each run so the trajectory can be drawn once history exists (not drawn in Phase 1, by design: there is one period). The quarterly model narrative (§5, approved) is **not in this plan**; it needs a period of claims to write from and is the first task of Phase 2.
- **§6 sources**: free-source set kept; paid additions out of scope (C2); the pilot-band gap measured in Task 4.
- **§7 candidates and the measurability gate**: not in this plan. The gate needs the extraction command (Task 5) to exist; running it for candidates is a Phase 2 task.
- **§9**: phase0 parked, nothing deleted; cron untouched (worktree).
- **§10 item 3** → Task 6. **Item 6 stall and retreat** → `abandons`, `contrary`, `movers.retreated`.
- Placeholder scan: Task 1 names two functions by role (`_load_sources`, `query_sheets`, `import_all`) because their real names must be read from the file; the step says so and gives the grep. No other TBDs.
- Type consistency: `DocText` fields used identically in Tasks 5, 6, 7; `TRLEstimate` fields (`point, low, high, support, top, contrary, n_claims, n_verified`) used identically in Tasks 3, 6, 7; `schema.FIELDS` order matches the prompt and the response schema; `claim_id(source, doc_id, tech_id, quote)` used identically in Tasks 2 and 5.
