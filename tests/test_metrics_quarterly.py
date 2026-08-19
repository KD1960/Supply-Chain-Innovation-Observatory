import pytest

from observatory import config, metrics, store
from observatory.matcher import Technology, Watchlist


def test_to_quarters_sums_each_thirteen_week_block():
    series = [1.0] * 13 + [2.0] * 13 + [3.0] * 13 + [4.0] * 13
    assert metrics.to_quarters(series) == [13.0, 26.0, 39.0, 52.0]


def test_a_quarter_with_no_observed_week_is_none_not_zero():
    """The hole rule, one level up: a quarter we never saw is not a quiet quarter."""
    series = [None] * 13 + [1.0] * 13 + [None] * 13 + [2.0] * 13
    assert metrics.to_quarters(series) == [None, 13.0, None, 26.0]


def test_a_partly_observed_quarter_sums_only_the_weeks_present():
    series = [None] * 12 + [5.0] + [1.0] * 13
    assert metrics.to_quarters(series) == [5.0, 13.0]


def test_quarters_are_cut_from_the_most_recent_week_backwards():
    """A short leading remainder must not shift every later boundary by a week."""
    series = [9.0] + [1.0] * 13
    assert metrics.to_quarters(series) == [9.0, 13.0]


def test_quarterly_acceleration_is_the_second_difference():
    # growth of 10, then growth of 20: acceleration is +10
    assert metrics.quarterly_acceleration([10.0, 20.0, 40.0]) == 10.0


def test_quarterly_acceleration_is_negative_when_growth_slows():
    assert metrics.quarterly_acceleration([10.0, 30.0, 40.0]) == -10.0


def test_quarterly_acceleration_needs_three_observed_quarters():
    assert metrics.quarterly_acceleration([None, 20.0, 40.0]) is None
    assert metrics.quarterly_acceleration([20.0, 40.0]) is None


def test_quarterly_acceleration_uses_the_three_most_recent_quarters():
    assert metrics.quarterly_acceleration([99.0, 10.0, 20.0, 40.0]) == 10.0



def tech(tech_id, patterns_changed_week="2020-W01"):
    return Technology(
        id=tech_id, name=tech_id, family="f", include=("x",), exclude=(),
        status="active", added_week="2020-W01",
        patterns_changed_week=patterns_changed_week,
    )


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def seed(conn, tech_id, signal, values, end_week="2026-W33"):
    weeks = config.trailing_weeks(end_week, len(values))
    for week, value in zip(weeks, values):
        store.set_signal(conn, tech_id, week, signal, float(value))


def test_momentum_is_none_with_only_two_quarters_of_history(conn):
    """Twenty-six weeks is two quarters. A second difference needs three."""
    watchlist = Watchlist(version=1, technologies=(tech("a"), tech("b")))
    seed(conn, "a", "arxiv_papers", [1, 2] * 13)
    seed(conn, "b", "arxiv_papers", [1] * 26)
    rows = {row["tech_id"]: row for row in metrics.compute_week(conn, "2026-W33", watchlist)}
    assert rows["a"]["momentum"] is None


def test_momentum_ranks_the_quarter_over_quarter_accelerator_higher(conn):
    watchlist = Watchlist(version=1, technologies=(tech("fast"), tech("flat")))
    seed(conn, "fast", "arxiv_papers", [1] * 13 + [2] * 13 + [4] * 13)
    seed(conn, "flat", "arxiv_papers", [5] * 39)
    rows = {row["tech_id"]: row for row in metrics.compute_week(conn, "2026-W33", watchlist)}
    assert rows["fast"]["momentum"] > rows["flat"]["momentum"]


def test_momentum_ignores_how_a_quarter_is_spread_across_its_weeks(conn):
    """The reason for the change. Two technologies with identical quarterly
    totals, one arriving smoothly and one in a lump, are the same story. At
    weekly resolution they scored differently, which was measuring the
    collector's timing rather than the technology."""
    watchlist = Watchlist(
        version=1, technologies=(tech("smooth"), tech("lumpy"), tech("flat"))
    )
    smooth = [1] * 13 + [2] * 13 + [4] * 13
    lumpy = [0] * 12 + [13] + [0] * 12 + [26] + [0] * 12 + [52]
    assert sum(smooth) == sum(lumpy)

    # The weekly method separated these two; that is what is being replaced.
    weekly_smooth = metrics.acceleration(metrics.normalize_series([float(v) for v in smooth]))
    weekly_lumpy = metrics.acceleration(metrics.normalize_series([float(v) for v in lumpy]))
    assert weekly_smooth != pytest.approx(weekly_lumpy, abs=0.1)

    seed(conn, "smooth", "arxiv_papers", smooth)
    seed(conn, "lumpy", "arxiv_papers", lumpy)
    seed(conn, "flat", "arxiv_papers", [5] * 39)
    rows = {row["tech_id"]: row for row in metrics.compute_week(conn, "2026-W33", watchlist)}
    assert rows["smooth"]["momentum"] == pytest.approx(rows["lumpy"]["momentum"])
    assert rows["smooth"]["momentum"] != pytest.approx(rows["flat"]["momentum"])


def test_a_technology_seen_once_gets_no_momentum(conn):
    """95% of the signals table is observed zeros. Normalising a series that is
    almost all zeros turns one document into a large z-score, which is how a
    technology with three documents in a year came to rank first."""
    watchlist = Watchlist(
        version=1, technologies=(tech("once"), tech("steady"), tech("rising"))
    )
    seed(conn, "once", "arxiv_papers", [0] * 20 + [1] + [0] * 18)
    seed(conn, "steady", "arxiv_papers", [5] * 39)
    seed(conn, "rising", "arxiv_papers", [1] * 13 + [2] * 13 + [4] * 13)
    rows = {row["tech_id"]: row for row in metrics.compute_week(conn, "2026-W33", watchlist)}
    assert rows["once"]["momentum"] is None
    assert rows["rising"]["momentum"] is not None


def test_a_technology_falling_to_zero_keeps_its_momentum(conn):
    """Two present quarters are enough to state a trend, and a decline into
    zero is a real one. The guard is against absence, not against bad news."""
    watchlist = Watchlist(
        version=1, technologies=(tech("fading"), tech("steady"), tech("rising"))
    )
    seed(conn, "fading", "arxiv_papers", [10] * 13 + [5] * 13 + [0] * 13)
    seed(conn, "steady", "arxiv_papers", [5] * 39)
    seed(conn, "rising", "arxiv_papers", [1] * 13 + [2] * 13 + [4] * 13)
    rows = {row["tech_id"]: row for row in metrics.compute_week(conn, "2026-W33", watchlist)}
    assert rows["fading"]["momentum"] is not None
    assert rows["fading"]["momentum"] < rows["rising"]["momentum"]


def test_a_signal_too_thin_to_carry_a_trend_is_left_out(conn):
    """One document per quarter clears the presence guard and still says
    nothing: a second difference over counts that small is decided by which
    quarter a single document happened to land in."""
    watchlist = Watchlist(
        version=1, technologies=(tech("thin"), tech("steady"), tech("rising"))
    )
    seed(conn, "thin", "arxiv_papers", [0] * 12 + [1] + [0] * 12 + [1] + [0] * 12 + [1])
    seed(conn, "steady", "arxiv_papers", [5] * 39)
    seed(conn, "rising", "arxiv_papers", [1] * 13 + [2] * 13 + [4] * 13)
    rows = {row["tech_id"]: row for row in metrics.compute_week(conn, "2026-W33", watchlist)}
    assert rows["thin"]["momentum"] is None
    assert rows["rising"]["momentum"] is not None


def test_a_stock_signal_folds_to_its_latest_value_not_its_sum():
    assert metrics.to_quarters([2.0] * 13, how="last") == [2.0]
    assert metrics.to_quarters([1.0, 2.0, 3.0], size=3, how="last") == [3.0]


def test_a_stock_signal_is_not_multiplied_across_the_quarter(conn):
    """edgar_filers counts distinct companies over a trailing window, so the
    same companies reappear in it every week. Summing thirteen weeks of that
    turned two filers into twenty-six and floated a four-document technology
    into the ranking."""
    watchlist = Watchlist(
        version=1, technologies=(tech("stocky"), tech("steady"), tech("rising"))
    )
    seed(conn, "stocky", "edgar_filers", [2] * 39)
    seed(conn, "steady", "arxiv_papers", [5] * 39)
    seed(conn, "rising", "arxiv_papers", [1] * 13 + [2] * 13 + [4] * 13)
    rows = {row["tech_id"]: row for row in metrics.compute_week(conn, "2026-W33", watchlist)}
    assert rows["stocky"]["momentum"] is None
