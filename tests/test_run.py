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
    def __init__(self, name="boom"):
        self.name = name

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


class WeeklyPayloadCollector(BaseCollector):
    """Each week's raw file carries its own documents.

    Needed to exercise the lookback: a run's raw legitimately holds documents
    belonging to the week before it.
    """

    name = "arxiv"

    def __init__(self, documents_by_week):
        self._documents_by_week = documents_by_week

    def fetch_raw(self, session, week):
        yield RawPage(url=f"https://x.test/{week}", status=200,
                      text=json.dumps(self._documents_by_week[week]))

    def parse(self, text):
        return [Document(**fields) for fields in json.loads(text)]


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
    # main() opens its own connection from DB_PATH. Redirect it too, so a test
    # that reaches main can never touch the real database.
    monkeypatch.setattr(run.base.config, "DB_PATH", tmp_path / "observatory.db")
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


def test_an_observation_is_keyed_by_the_documents_week_not_the_run_week(conn, watchlist):
    # The lookback overlap means a run routinely sees last week's documents.
    # 2026-08-05 is in 2026-W32, so that is where the observation belongs.
    late = stub(date="2026-08-05")
    ok = run.fetch_week(conn, "2026-W33", [late], session=None)
    run.ingest_week(conn, "2026-W33", watchlist, [late], ok)

    assert store.observations_for(conn, "2026-W32", "autonomous_trucking")
    assert store.observations_for(conn, "2026-W33", "autonomous_trucking") == []


def test_a_document_without_a_date_falls_back_to_the_run_week(conn, watchlist):
    undated = stub(date=None)
    ok = run.fetch_week(conn, "2026-W33", [undated], session=None)
    run.ingest_week(conn, "2026-W33", watchlist, [undated], ok)

    assert store.observations_for(conn, "2026-W33", "autonomous_trucking")


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


def paper(doc_id, date):
    return {"doc_id": doc_id, "date": date, "text": "",
            "title": "Autonomous trucking corridor opens",
            "url": f"https://x.test/{doc_id}"}


def test_rebuild_folds_lookback_documents_into_the_earlier_weeks_signals(conn, watchlist, tmp_path):
    # W33's query window reaches seven days back and picks up d2, which was
    # published in W32 but indexed too late for W32's own run.
    collector = WeeklyPayloadCollector({
        "2026-W32": [paper("d1", "2026-08-05")],
        "2026-W33": [paper("d2", "2026-08-06"), paper("d3", "2026-08-12")],
    })
    for week in ("2026-W32", "2026-W33"):
        run.run_week(conn, week, watchlist, [collector], session=None,
                     out_path=tmp_path / f"{week}.html")

    # The W33 run already folded the late document into W32's count (see
    # test_a_late_document_reaches_the_earlier_weeks_signal_in_the_same_run).
    assert len(store.observations_for(conn, "2026-W32", "autonomous_trucking")) == 2
    assert store.get_signal(conn, "autonomous_trucking", "2026-W32", "arxiv_papers") == 2.0

    run.rebuild(conn, watchlist, [collector])

    # Ingest every week before counting any, and the number still matches the
    # evidence list beneath it.
    assert store.get_signal(conn, "autonomous_trucking", "2026-W32", "arxiv_papers") == 2.0
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "arxiv_papers") == 1.0

    # Each week still gets its dated archive.
    assert (tmp_path / "output" / "dashboard-2026-W32.html").exists()
    assert (tmp_path / "output" / "dashboard-2026-W33.html").exists()


def test_a_late_document_reaches_the_earlier_weeks_signal_in_the_same_run(
    conn, watchlist, tmp_path
):
    """The weekly path, not just --rebuild.

    d2 belongs to W32 and arrives in W33's raw through the lookback. Writing it
    to `observations` under W32 and then computing signals for the run week
    alone leaves it uncounted permanently — nobody runs --rebuild every week.
    """
    collector = WeeklyPayloadCollector({
        "2026-W32": [paper("d1", "2026-08-05")],
        "2026-W33": [paper("d2", "2026-08-06"), paper("d3", "2026-08-12")],
    })
    for week in ("2026-W32", "2026-W33"):
        run.run_week(conn, week, watchlist, [collector], session=None,
                     out_path=tmp_path / f"{week}.html")

    assert store.get_signal(conn, "autonomous_trucking", "2026-W32", "arxiv_papers") == 2.0
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "arxiv_papers") == 1.0

    # And the archived artifacts were rewritten, so the page a reader opens for
    # W32 agrees with the number now stored for it.
    assert (tmp_path / "output" / "dashboard-2026-W32.html").exists()
    assert (tmp_path / "output" / "evidence-2026-W32.html").exists()


def test_a_recomputed_earlier_week_does_not_take_over_latest(conn, watchlist, tmp_path):
    collector = WeeklyPayloadCollector({"2026-W33": [paper("d2", "2026-08-06")]})
    run.run_week(conn, "2026-W33", watchlist, [collector], session=None)

    output = tmp_path / "output"
    assert (output / "dashboard-2026-W32.html").exists()
    assert (output / "latest.html").read_text() == (output / "dashboard-2026-W33.html").read_text()
    assert (output / "evidence.html").read_text() == (output / "evidence-2026-W33.html").read_text()


def test_a_failed_source_leaves_a_hole_in_the_late_week_too(conn, watchlist, tmp_path):
    """The per-week ok_sources contract survives the recompute: hn never ran
    for W32 either, so its signal there stays absent rather than becoming 0."""
    collectors = [
        WeeklyPayloadCollector({"2026-W33": [paper("d2", "2026-08-06")]}),
        ExplodingCollector(name="hn"),
    ]
    run.run_week(conn, "2026-W33", watchlist, collectors, session=None,
                 out_path=tmp_path / "d.html")

    assert store.get_signal(conn, "autonomous_trucking", "2026-W32", "arxiv_papers") == 1.0
    assert store.get_signal(conn, "autonomous_trucking", "2026-W32", "hn_points") is None


def test_rebuild_scores_a_week_that_only_a_neighbours_raw_reached(conn, watchlist, tmp_path):
    """W32 has no raw directory of its own — every W32 document arrived through
    W33's lookback — so scoring only the directories would leave it uncounted."""
    collector = WeeklyPayloadCollector({"2026-W33": [paper("d2", "2026-08-06")]})
    run.run_week(conn, "2026-W33", watchlist, [collector], session=None,
                 out_path=tmp_path / "d.html")
    assert not (tmp_path / "raw" / "2026-W32").exists()

    run.rebuild(conn, watchlist, [collector])

    assert store.get_signal(conn, "autonomous_trucking", "2026-W32", "arxiv_papers") == 1.0


def test_rebuild_keeps_ok_sources_per_week(conn, watchlist, tmp_path):
    # arxiv succeeded in W32 and failed in W33. The second pass has to honour
    # each week's own status, not the last one recorded.
    collector = WeeklyPayloadCollector({"2026-W32": [paper("d1", "2026-08-05")]})
    run.run_week(conn, "2026-W32", watchlist, [collector], session=None,
                 out_path=tmp_path / "a.html")
    store.set_source_status(conn, "arxiv", "2026-W33", "failed", "503")
    (tmp_path / "raw" / "2026-W33" / "arxiv").mkdir(parents=True)

    run.rebuild(conn, watchlist, [collector])

    assert store.get_signal(conn, "autonomous_trucking", "2026-W32", "arxiv_papers") == 1.0
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "arxiv_papers") is None


def test_rebuild_and_only_are_rejected_together(conn, capsys):
    # clear_derived is unconditional, so replaying a filtered collector tuple
    # would delete the other sources' rows and never rewrite them. The guard
    # fires before main opens anything; the conn fixture redirects the paths
    # anyway so a regression here cannot destroy real data.
    with pytest.raises(SystemExit) as excinfo:
        run.main(["--rebuild", "--only", "arxiv"])
    assert excinfo.value.code == 2
    assert "--rebuild always replays every source" in capsys.readouterr().err


def test_backfill_and_only_are_rejected_together(conn, capsys, monkeypatch):
    # --backfill always ends in a full rebuild, which hits the same
    # clear_derived-then-replay-one-source hole as --rebuild --only. Unlike
    # the --rebuild guard above, a regression here doesn't just fail an
    # assertion: main's backfill branch opens a real session and fetches
    # live, so a broken guard would have this test hammering arXiv and SEC on
    # every `pytest` run. Make that structurally impossible rather than
    # trusting the guard to keep working.
    def no_network():
        raise AssertionError("the test suite must not open a network session")

    monkeypatch.setattr(run.http, "make_session", no_network)

    with pytest.raises(SystemExit) as excinfo:
        run.main(["--backfill", "3", "--only", "arxiv"])
    assert excinfo.value.code == 2
    assert "backfill always fetches every source" in capsys.readouterr().err


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


def test_backfill_fetches_oldest_first_and_returns_what_it_fetched(conn, tmp_path):
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
    fetched = run.backfill(conn, weeks_back=3, collectors=[collector], session=None)
    assert calls == sorted(calls), "backfill must fetch oldest first"
    assert fetched == calls


def test_backfill_skips_weeks_it_has_already_fetched(conn):
    collector = stub()
    first = run.backfill(conn, weeks_back=2, collectors=[collector], session=None)
    second = run.backfill(conn, weeks_back=2, collectors=[collector], session=None)
    assert first, "first pass should fetch something"
    assert second == [], "second pass should find everything already fetched"


def test_backfill_rejects_a_nonsensical_window(conn):
    with pytest.raises(ValueError):
        run.backfill(conn, weeks_back=0, collectors=[stub()], session=None)
