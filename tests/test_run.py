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
    monkeypatch.setattr(run.base.config, "RUN_LOG_PATH", tmp_path / "run_log.jsonl")
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

    log_lines = (tmp_path / "run_log.jsonl").read_text().splitlines()
    assert len(log_lines) == 1
    assert json.loads(log_lines[0])["week"] == "2026-W33"


def test_running_the_same_week_twice_gives_identical_metrics(conn, watchlist, tmp_path):
    run.run_week(conn, "2026-W33", watchlist, [stub()], session=None,
                 out_path=tmp_path / "a.html")
    first = store.metrics_for_week(conn, "2026-W33")
    run.run_week(conn, "2026-W33", watchlist, [stub()], session=None,
                 skip_fetch=True, out_path=tmp_path / "b.html")
    assert store.metrics_for_week(conn, "2026-W33") == first
