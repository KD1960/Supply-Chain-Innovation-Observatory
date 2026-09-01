"""A collection failure has to outlive the retry that fixed it.

`source_runs` is keyed on `(source, week)` and upserts, so a week that failed
and was later refetched had its failure row overwritten by the success. The
table held 427 rows, all `ok`, and after any successful retry it was
structurally incapable of holding anything else -- which is how STATUS came to
claim "318 source runs, none has ever failed", a claim that could not have been
false.

Two further holes in the same wall. `raw_fetch` is described in STATUS as an
append-only log of fetch *attempts* and had `http_status = 200` on all 3,114
rows, because a failed fetch raises before the insert; it was a log of
successes. And a source that returns a valid but empty response was recorded
`ok` and written as a hard zero, so an API that quietly starts returning
nothing looks exactly like a technology nobody is working on.

The project's whole epistemology rests on separating "we looked and found
nothing" from "we did not look". These tests are that separation.
"""

import json

import pytest

from observatory import config, discover, http, render, run, store
from observatory.collectors.base import BaseCollector, Document, RawPage
from observatory.matcher import Technology, Watchlist


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def _watchlist():
    return Watchlist(version=1, context=("supply chain",), technologies=(Technology(
        id="a", name="A", family="f", include=("widget",), exclude=(),
        status="active", added_week="2020-W01", patterns_changed_week="2020-W01"),))


class _Fails(BaseCollector):
    name = "arxiv"

    def fetch_raw(self, session, week):
        raise http.HttpError("arxiv.test failed with status 503", url="https://arxiv.test/q",
                             status=503)
        yield  # pragma: no cover

    def parse(self, text):
        return []


class _Works(BaseCollector):
    name = "arxiv"

    def fetch_raw(self, session, week):
        yield RawPage(url="https://arxiv.test/q", status=200, text="widget supply chain",
                      extension="txt")

    def parse(self, text):
        return [Document(doc_id="d1", date="2026-08-12", title="widget",
                         text="widget supply chain", url="https://arxiv.test/d1")]


class _FetchesNothing(BaseCollector):
    """A valid run that yields no pages at all."""

    name = "nsf"

    def fetch_raw(self, session, week):
        return iter(())

    def parse(self, text):
        return []


class _ParsesToNothing(BaseCollector):
    """Pages arrive and hold no documents -- an empty-but-valid 200."""

    name = "hn"

    def fetch_raw(self, session, week):
        yield RawPage(url="https://hn.test/q", status=200, text="[]", extension="json")

    def parse(self, text):
        return []


# --- the failure survives its retry -----------------------------------------


def test_a_failure_survives_the_retry_that_fixed_it(conn):
    run.fetch_week(conn, "2026-W33", [_Fails()], session=None)
    run.fetch_week(conn, "2026-W33", [_Works()], session=None)

    attempts = store.source_attempts(conn, week="2026-W33")
    assert [row["status"] for row in attempts] == ["failed", "ok"]
    assert "503" in attempts[0]["note"]


def test_source_runs_still_answers_how_the_week_ended(conn):
    """The upsert is not the bug; losing the attempt was. `source_runs` is what
    resumability reads, and it must keep saying the week finished."""
    run.fetch_week(conn, "2026-W33", [_Fails()], session=None)
    run.fetch_week(conn, "2026-W33", [_Works()], session=None)
    assert store.ok_sources_for_week(conn, "2026-W33") == {"arxiv"}


def test_the_attempt_log_is_never_overwritten(conn):
    for _ in range(3):
        run.fetch_week(conn, "2026-W33", [_Fails()], session=None)
    assert len(store.source_attempts(conn, week="2026-W33")) == 3


# --- a failed fetch reaches raw_fetch ---------------------------------------


def test_a_non_200_is_recorded_in_raw_fetch(conn):
    """It was a log of successes: every one of 3,114 rows read 200, because the
    only insert sat downstream of the raise."""
    run.fetch_week(conn, "2026-W33", [_Fails()], session=None)
    rows = [dict(r) for r in conn.execute("SELECT * FROM raw_fetch")]
    assert [row["http_status"] for row in rows] == [503]
    assert rows[0]["source"] == "arxiv"
    assert rows[0]["path"] is None


# --- empty is neither ok nor failed -----------------------------------------


def test_a_source_that_fetched_nothing_is_recorded_empty(conn):
    run.fetch_week(conn, "2026-W33", [_FetchesNothing()], session=None)
    assert [r["status"] for r in store.source_attempts(conn, week="2026-W33")] == ["empty"]


def test_an_empty_source_is_still_collected_so_its_zero_stays_a_zero(conn):
    """The owner's call. A real zero and a broken API look identical in one
    response, and NSF's seasonal gap is a real zero -- so empty is surfaced and
    acted on by a human, never folded into a hole automatically."""
    ok = run.fetch_week(conn, "2026-W33", [_FetchesNothing()], session=None)
    assert ok == {"nsf"}
    assert store.ok_sources_for_week(conn, "2026-W33") == {"nsf"}


def test_pages_that_parse_to_no_documents_are_empty_too(conn, tmp_path, monkeypatch):
    """The other shape of nothing: the fetch worked and the corpus is zero."""
    monkeypatch.setattr(config, "RAW_DIR", tmp_path)
    collectors = [_ParsesToNothing()]
    run.fetch_week(conn, "2026-W33", collectors, session=None)
    run.ingest_week(conn, "2026-W33", _watchlist(), collectors, {"hn"})
    assert [r["status"] for r in store.source_attempts(conn, week="2026-W33")][-1] == "empty"


def test_a_source_that_found_documents_is_ok_not_empty(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path)
    collectors = [_Works()]
    run.fetch_week(conn, "2026-W33", collectors, session=None)
    run.ingest_week(conn, "2026-W33", _watchlist(), collectors, {"arxiv"})
    assert [r["status"] for r in store.source_attempts(conn, week="2026-W33")][-1] == "ok"


# --- the run log says what failed -------------------------------------------


def test_the_run_log_records_failures_not_only_successes(tmp_path, monkeypatch):
    """1,823 lines carried `ok_sources` and no failure field at all. Its first
    line reads `["hn"]` for a week whose later lines read three sources:
    something failed, and the log could not say what."""
    path = tmp_path / "run_log.jsonl"
    monkeypatch.setattr(config, "RUN_LOG_PATH", path)
    run._append_run_log("2026-W33", {"arxiv"}, 1, 1, 1,
                        discover.RisingTerms(candidates=[], total=0), "out.html",
                        failed_sources={"github"}, empty_sources={"nsf"})
    entry = json.loads(path.read_text().strip())
    assert entry["ok_sources"] == ["arxiv"]
    assert entry["failed_sources"] == ["github"]
    assert entry["empty_sources"] == ["nsf"]


# --- the weekly page shows the week it is about -----------------------------


def test_a_rerendered_old_week_shows_its_own_health_not_todays(conn):
    """`source_runs` was created for exactly this and the dashboard queried
    `sources` instead, which holds only the latest state -- so every replayed
    archive week was stamped with today's status."""
    store.set_source_status(conn, "arxiv", "2026-W30", "failed", "503 from arxiv")
    store.set_source_status(conn, "arxiv", "2026-W33", "ok", "")

    old = render.dashboard_context(conn, "2026-W30", _watchlist())
    assert [(s["name"], s["status"]) for s in old["sources"]] == [("arxiv", "failed")]

    now = render.dashboard_context(conn, "2026-W33", _watchlist())
    assert [(s["name"], s["status"]) for s in now["sources"]] == [("arxiv", "ok")]


def test_a_real_run_writes_its_failures_to_the_log(tmp_path, monkeypatch, conn):
    """Connecting the thing is the part this project forgets. `_append_run_log`
    taking the arguments is not the same as the run passing them, and a guard
    built and left unwired is the pattern the process review named five times.
    """
    monkeypatch.setattr(config, "RAW_DIR", tmp_path)
    monkeypatch.setattr(config, "RUN_LOG_PATH", tmp_path / "run_log.jsonl")
    monkeypatch.setattr(run, "COLLECTORS", ())
    run.run_week(conn, "2026-W33", _watchlist(),
                 collectors=[_Fails(), _FetchesNothing()],
                 session=None, out_path=tmp_path / "out.html")
    entry = json.loads((tmp_path / "run_log.jsonl").read_text().strip().split("\n")[-1])
    assert entry["failed_sources"] == ["arxiv"]
    assert entry["empty_sources"] == ["nsf"]


# --- latest.html is about now ------------------------------------------------


def test_a_future_week_never_takes_latest_html(conn, tmp_path, monkeypatch):
    """Risk 4 of the process review, watched happening.

    `--import-manual` re-renders every week holding an observation, ascending,
    and `_score_and_render` defaults `latest=True`, so whichever week is
    rendered last takes `latest.html`. Scopus exports carry issue dates months
    ahead -- `PUBYEAR = 2026` returns things dated to December -- so the store
    holds weeks that have not happened, and an import in September left
    `output/latest.html` showing 2026-W49. STATUS §4g records the broken weekly
    ranking being "spotted by the owner on 2026-W49" without anyone asking why
    a W49 dashboard existed.

    A page called `latest` is a claim about now. A week after this one cannot
    be it, whatever order the loop happened to render in.
    """
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(config, "current_week", lambda: "2026-W36")

    # No `out_path`: `latest.html` is only written when the dashboard goes to
    # its default location, so passing one would make this pass for the wrong
    # reason.
    run._score_and_render(conn, "2026-W49", _watchlist(), set(), 0, [])
    assert not (tmp_path / "latest.html").exists(), (
        "a week that has not happened took latest.html"
    )

    run._score_and_render(conn, "2026-W36", _watchlist(), set(), 0, [])
    assert (tmp_path / "latest.html").exists()
