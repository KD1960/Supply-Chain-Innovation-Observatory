import json
import xml.etree.ElementTree as ET

import pytest

from observatory import http, run, store
from observatory.collectors.base import BaseCollector, Document, RawPage
from observatory.matcher import Technology, Watchlist


class StubCollector(BaseCollector):
    def __init__(self, pages, documents, name="stub"):
        self.name = name
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


class PoisonedCollector(BaseCollector):
    """Fetches fine, then cannot be parsed.

    arXiv returns HTML error bodies with a 200, which get written as .xml and
    blow up on every subsequent parse of that week, --skip-fetch included.
    """

    name = "arxiv"

    def fetch_raw(self, session, week):
        yield RawPage(url="https://x.test/err", status=200,
                      text="<!DOCTYPE html><html>503</html>", extension="xml")

    def parse(self, text):
        raise ET.ParseError("mismatched tag: line 1, column 24")


class PartialSweepCollector(BaseCollector):
    """Writes pages, then dies — the truncated week that stays on disk."""

    name = "arxiv"

    def fetch_raw(self, session, week):
        yield RawPage(url="https://x.test/1", status=200, text=json.dumps({"ok": 1}))
        raise http.HttpError("503 on the second sweep")

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
    monkeypatch.setattr(run.base.config, "OUTPUT_DIR", tmp_path / "output")
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def stub(name="stub", date="2026-08-12"):
    page = RawPage(url="https://x.test/1", status=200, text=json.dumps({"ok": 1}))
    document = Document(doc_id="d1", date=date,
                        title="Autonomous trucking corridor opens",
                        text="", url="https://x.test/a", amount=214.0)
    return StubCollector([page], [document], name=name)


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
    ok = run.fetch_week(conn, "2026-W33", [stub()], session=None)
    inserted, still_ok = run.ingest_week(conn, "2026-W33", watchlist, [stub()], ok)
    assert (inserted, still_ok) == (1, {"stub"})
    rows = store.observations_for(conn, "2026-W33", "autonomous_trucking")
    assert rows[0]["matched_pattern"] == "autonomous truck(s|ing)?"


def test_ingest_week_is_idempotent(conn, watchlist):
    ok = run.fetch_week(conn, "2026-W33", [stub()], session=None)
    run.ingest_week(conn, "2026-W33", watchlist, [stub()], ok)
    assert run.ingest_week(conn, "2026-W33", watchlist, [stub()], ok)[0] == 0


def test_ingest_week_isolates_a_collector_whose_parse_raises(conn, watchlist, tmp_path):
    collectors = [stub(name="hn"), PoisonedCollector()]
    result = run.run_week(conn, "2026-W33", watchlist, collectors, session=None,
                          out_path=tmp_path / "dashboard.html")

    assert result.exists()  # the run reaches render rather than dying at ingest
    assert store.observations_for(conn, "2026-W33", "autonomous_trucking", source="hn")

    statuses = {row["name"]: row for row in store.source_statuses(conn)}
    assert statuses["arxiv"]["status"] == "failed"
    assert "mismatched tag" in statuses["arxiv"]["note"]

    logged = json.loads((tmp_path / "run_log.jsonl").read_text().splitlines()[0])
    assert logged["ok_sources"] == ["hn"]

    # A failed parse must leave a hole, never a zero.
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "hn_points") == 214.0
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "arxiv_papers") is None


def test_partial_raw_from_a_failed_source_is_not_replayed_as_complete(conn, watchlist, tmp_path):
    collectors = [PartialSweepCollector()]
    ok = run.fetch_week(conn, "2026-W33", collectors, session=None)
    assert ok == set()
    # The pages written before the failure are still on disk.
    assert list((tmp_path / "raw" / "2026-W33" / "arxiv").iterdir())

    assert run.sources_ok_for_week(conn, "2026-W33", collectors) == set()

    run.run_week(conn, "2026-W33", watchlist, collectors, session=None,
                 skip_fetch=True, out_path=tmp_path / "dashboard.html")
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "arxiv_papers") is None


def test_rebuild_rematches_raw_under_the_current_watchlist(conn, watchlist, tmp_path):
    collectors = [stub()]
    run.run_week(conn, "2026-W33", watchlist, collectors, session=None,
                 out_path=tmp_path / "a.html")
    assert store.observations_for(conn, "2026-W33", "autonomous_trucking")

    # A parser fix or a widened pattern: the same document now matches
    # something else. INSERT OR IGNORE alone would leave the old rows in place.
    widened = Watchlist(version=2, technologies=(
        Technology(id="freight_corridors", name="Freight corridors", family="networks",
                   include=("corridor(s)?",), exclude=(), status="active",
                   added_week="2020-W01", patterns_changed_week="2020-W01"),
    ))
    run.rebuild(conn, widened, collectors)

    assert store.observations_for(conn, "2026-W33", "freight_corridors")
    assert store.observations_for(conn, "2026-W33", "autonomous_trucking") == []


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
