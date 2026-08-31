"""Metrics on a four-quarter window rather than a fifty-two-week one.

Week to week is too noisy to interpret: two thirds of technology-weeks hold
zero observations and the median is zero, so a weekly score mostly reported
which week a collector caught something. Worse, a trailing z-score let a
technology with no documents at all this week sit at the top of "This Week's
Movers" -- on 2026-W36, seven of the top eight had nothing in the week they
were named for.

Collection stays weekly. Only the interpretation moves.
"""

import pytest

from observatory import metrics, store


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def test_the_window_is_the_quarter_and_the_three_before_it():
    assert metrics.trailing_quarters("2026-Q3", 4) == [
        "2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3"]


def test_the_window_crosses_a_year_boundary():
    assert metrics.trailing_quarters("2026-Q1", 4) == [
        "2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1"]


def test_a_signal_series_is_read_by_quarter(conn):
    _observe(conn, "a", "2026-05-04", "arxiv")
    _observe(conn, "a", "2026-05-06", "arxiv")
    _observe(conn, "a", "2026-08-04", "arxiv")
    # research_papers, not arxiv_papers: the quarterly signals are per family,
    # so a stage does not swing on which of three research sources happened to
    # be collected that quarter.
    series = metrics.quarterly_signal(conn, "a", "research_papers",
                                      ["2026-Q1", "2026-Q2", "2026-Q3"])
    assert series == [0, 2, 1]


def test_a_quarter_that_was_never_collected_is_absent_not_zero(conn):
    """The project's oldest rule. A quarter nobody ran leaves its signals
    missing; folding that into zero invents a decline."""
    _observe(conn, "a", "2026-08-04", "arxiv")
    series = metrics.quarterly_signal(conn, "a", "research_papers",
                                      ["2025-Q1", "2026-Q3"], collected={"2026-Q3"})
    assert series == [None, 1]


def test_a_score_needs_enough_quarters_to_mean_anything(conn):
    """Four quarters of history, and a z-score from two of them is a claim
    about a spread computed from two numbers."""
    assert metrics.zscore_quarters([None, None, 3.0]) is None
    assert metrics.zscore_quarters([1.0, 2.0, 3.0]) is not None


def test_a_technology_with_no_documents_in_the_quarter_is_not_scored(conn):
    """What the whole change is for. A quarterly score belongs to a quarter the
    technology actually appeared in."""
    for month in ("02", "05"):
        _observe(conn, "a", f"2026-{month}-04", "arxiv")
    rows = {row["tech_id"]: row for row in
            metrics.compute_quarter(conn, "2026-Q3", _watchlist())}
    assert rows["a"]["documents"] == 0
    assert rows["a"]["sai"] is None


def test_a_technology_present_in_the_quarter_is_scored(conn):
    import datetime as dt
    for quarter_start in ("2025-11", "2026-02", "2026-05", "2026-08"):
        for day in ("04", "11", "18"):
            _observe(conn, "a", f"{quarter_start}-{day}", "arxiv")
            _observe(conn, "a", f"{quarter_start}-{day}", "github", suffix="g")
    rows = {row["tech_id"]: row for row in
            metrics.compute_quarter(conn, "2026-Q3", _watchlist())}
    assert rows["a"]["documents"] == 6
    assert rows["a"]["sai"] is not None


def _observe(conn, tech_id, date, source, suffix=""):
    from observatory.matcher import Observation
    store.upsert_observations(conn, [Observation(
        source=source, week="2026-W01", tech_id=tech_id,
        doc_id=f"{source}{suffix}:{date}", doc_date=date, title="t", url="",
        entity=None, entity_id=None, amount=None, lat=None, lon=None,
        matched_pattern="x", raw_ref=None)])


def _watchlist():
    from observatory.matcher import Technology, Watchlist
    return Watchlist(version=1, context=("x",), technologies=(Technology(
        id="a", name="A", family="f", include=("x",), exclude=(), status="active",
        added_week="2020-W01", patterns_changed_week="2020-W01"),))
