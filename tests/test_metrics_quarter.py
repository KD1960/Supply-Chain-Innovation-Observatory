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
    from observatory import quarter as quarters
    for name in ("2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3"):
        for week in quarters.weeks_in_quarter(name):
            conn.execute("INSERT OR IGNORE INTO source_runs (source, week, status) "
                         "VALUES ('arxiv', ?, 'ok')", (week,))
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


def test_an_annual_period_uses_its_own_four_quarters():
    """A year is not a quarter and cannot be stepped back from. Its window is
    the four quarters it contains, which is also the trailing four ending at
    its last."""
    assert metrics.trailing_quarters("2026") == [
        "2026-Q1", "2026-Q2", "2026-Q3", "2026-Q4"]


def test_an_annual_period_scores(conn):
    from observatory import quarter as quarters
    for week in quarters.weeks_in_year("2026"):
        conn.execute("INSERT OR IGNORE INTO source_runs (source, week, status) "
                     "VALUES ('arxiv', ?, 'ok')", (week,))
    for month in ("02", "05", "08", "11"):
        for day in ("04", "11", "18"):
            _observe(conn, "a", f"2026-{month}-{day}", "arxiv")
            _observe(conn, "a", f"2026-{month}-{day}", "github", suffix="g")
    rows = {row["tech_id"]: row for row in metrics.compute_quarter(conn, "2026", _watchlist())}
    assert rows["a"]["documents"] == 24
    assert rows["a"]["sai"] is not None


# --- the rule the window was breaking ---------------------------------------
#
# `quarterly_signal` takes `collected` and its docstring cites the project's
# oldest rule -- a missing period is not a zero period. compute_quarter never
# passed it. 2025-Q3 was collected for 5 of its 13 weeks and entered the window
# as a full quarter, so collection ramp-up read as a rise. It also made
# MIN_HISTORY_QUARTERS unreachable: every quarter was present, so the guard
# could never fire.


def test_a_partly_collected_quarter_is_not_treated_as_a_full_one(conn):
    for week in ("2025-W28", "2025-W29"):
        conn.execute("INSERT INTO source_runs (source, week, status) "
                     "VALUES ('arxiv', ?, 'ok')", (week,))
    conn.commit()
    assert "2025-Q3" not in metrics.collected_quarters(conn, ["2025-Q3"])


def test_a_fully_collected_quarter_counts(conn):
    from observatory import quarter as quarters
    for week in quarters.weeks_in_quarter("2026-Q2"):
        conn.execute("INSERT INTO source_runs (source, week, status) "
                     "VALUES ('arxiv', ?, 'ok')", (week,))
    conn.commit()
    assert "2026-Q2" in metrics.collected_quarters(conn, ["2026-Q2"])


def test_compute_quarter_excludes_the_quarters_it_did_not_collect(conn):
    """The bug in one line: without this, a quarter nobody ran contributes a
    zero to the spread, and a technology that simply was not being collected
    yet reads as one that has risen."""
    from observatory import quarter as quarters
    for week in quarters.weeks_in_quarter("2026-Q3"):
        conn.execute("INSERT INTO source_runs (source, week, status) "
                     "VALUES ('arxiv', ?, 'ok')", (week,))
    conn.commit()
    for day in ("04", "11", "18"):
        _observe(conn, "a", f"2026-08-{day}", "arxiv")
    rows = {row["tech_id"]: row for row in metrics.compute_quarter(conn, "2026-Q3", _watchlist())}
    # Three of the four quarters in the window were never collected, so there
    # is not enough history to score against and the row says so.
    assert rows["a"]["documents"] == 3
    assert rows["a"]["sai"] is None


def test_a_period_still_filling_up_is_not_scored(conn):
    """Excluding a partial quarter from the *window* is not enough: if the
    period being reported is itself partial, carry_forward fills its missing
    value from the quarter before, so the score belongs to that one. The report
    already withholds share movement on a partial period for the same reason."""
    from observatory import quarter as quarters
    for name in ("2025-Q4", "2026-Q1", "2026-Q2"):
        for week in quarters.weeks_in_quarter(name):
            conn.execute("INSERT OR IGNORE INTO source_runs (source, week, status) "
                         "VALUES ('arxiv', ?, 'ok')", (week,))
    # 2026-Q3 gets only part of its weeks, as a quarter in progress does.
    for week in quarters.weeks_in_quarter("2026-Q3")[:8]:
        conn.execute("INSERT OR IGNORE INTO source_runs (source, week, status) "
                     "VALUES ('arxiv', ?, 'ok')", (week,))
    conn.commit()
    for day in ("04", "11", "18"):
        _observe(conn, "a", f"2026-08-{day}", "arxiv")
    rows = {row["tech_id"]: row for row in metrics.compute_quarter(conn, "2026-Q3", _watchlist())}
    assert rows["a"]["documents"] == 3, "the count is an observation and stands"
    assert rows["a"]["sai"] is None, "the score is an inference and does not"
    assert rows["a"]["partial"] is True
