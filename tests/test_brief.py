"""The two-page brief: what a CAPS member reads instead of the whole report."""

import datetime as dt

import pytest

from observatory import brief, config, metrics, quarter, store
from observatory.matcher import Observation, Technology, Watchlist


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def observe(conn, tech_id, week, source, doc_id, entity_id=None):
    date = (config.week_bounds(week)[0] + dt.timedelta(days=3)).isoformat()
    store.upsert_observations(conn, [Observation(
        source=source, week=week, tech_id=tech_id, doc_id=doc_id, doc_date=date,
        title=doc_id, url=f"https://example.test/{doc_id}", entity=None,
        entity_id=entity_id, amount=None, lat=None, lon=None,
        matched_pattern="x", raw_ref=None)])


def a_quarter(conn, period="2026-Q2"):
    """Every week of the period marked collected, so the quarter is complete
    and its scores are not withheld for a reason the test did not intend."""
    # The period itself and the window a score is computed over. Without the
    # window, `short_history` withholds the scores and a test about findings
    # would be testing the withholding instead.
    for earlier in metrics.trailing_quarters(period):
        for week in quarter.weeks_in_quarter(earlier):
            store.set_source_status(conn, "edgar", week, "ok")
    for week in quarter.weeks_in_quarter(period):
        store.set_source_status(conn, "edgar", week, "ok")
    for index, entity in enumerate(("c1", "c2", "c3"), start=1):
        observe(conn, "a", "2026-W16", "edgar", f"f{index}", entity_id=entity)
    observe(conn, "a", "2026-W16", "arxiv", "p1")
    return Watchlist(version=1, technologies=(Technology(
        id="a", name="Autonomous trucking", family="f", include=("x",), exclude=(),
        status="active", added_week="2020-W01", patterns_changed_week="2020-W01"),))


def test_the_brief_leads_with_the_findings(conn):
    watchlist = a_quarter(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    composed = brief.compose(context, "2026-Q2")
    assert "2026 Q2" in composed["title"]
    assert any("Autonomous trucking" in text for _, text in composed["findings"])


def test_the_brief_says_what_is_withheld_and_why(conn):
    """A brief that quietly drops the withholding notice is a brief that
    over-claims. A quarter still filling up withholds its scores and the
    reader has to be told, exactly as the report tells them."""
    watchlist = a_quarter(conn)
    for week in quarter.weeks_in_quarter("2026-Q3")[:8]:
        store.set_source_status(conn, "edgar", week, "ok")
    context = quarter.build_context(conn, "2026-Q3", watchlist)
    composed = brief.compose(context, "2026-Q3")
    assert composed["withheld"]
    assert "withheld" in composed["withheld"].lower()


def test_a_complete_quarter_does_not_claim_something_is_withheld(conn):
    watchlist = a_quarter(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    assert brief.compose(context, "2026-Q2")["withheld"] is None


def test_the_brief_carries_its_provenance(conn):
    watchlist = a_quarter(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    composed = brief.compose(context, "2026-Q2")
    assert "github.com" in composed["provenance"]
    assert "lexicon" in composed["provenance"].lower()


def test_the_written_brief_is_a_two_page_pdf(conn, tmp_path):
    """Two pages is the format, not an accident of how much fitted. A third
    page means something has to be cut."""
    watchlist = a_quarter(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    path = brief.write(context, "2026-Q2", tmp_path)
    body = path.read_bytes()
    assert path.name == "brief-2026-Q2.pdf"
    assert body.startswith(b"%PDF")
    assert body.count(b"/Type /Page\n") == 2


def test_a_brief_that_would_run_off_the_page_says_so(conn):
    """reportlab draws past the bottom edge without complaint: the words are
    in the file and simply not on the paper. That is the silent-truncation
    shape this project keeps meeting, so overflow raises instead."""
    watchlist = a_quarter(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    from observatory.findings import Finding
    context["findings"] = [
        Finding(f"rule{index}", "word " * 400, "", stat="a stat", n=9)
        for index in range(5)]
    import tempfile
    with pytest.raises(brief.BriefOverflow):
        brief.write(context, "2026-Q2", tempfile.mkdtemp())
