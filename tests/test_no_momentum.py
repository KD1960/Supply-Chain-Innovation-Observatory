"""Momentum was dropped: with collection weekly and the annual report the
deliverable, the only metric that needed a time series is gone, and it was the
one that kept reporting noise as trend."""
import pytest

from observatory import config, metrics, store
from observatory.matcher import Technology, Watchlist


def tech(tech_id):
    return Technology(
        id=tech_id, name=tech_id, family="f", include=("x",), exclude=(),
        status="active", added_week="2020-W01", patterns_changed_week="2020-W01",
    )


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def seed(conn, tech_id, signal, values, end_week="2026-W33"):
    for week, value in zip(config.trailing_weeks(end_week, len(values)), values):
        store.set_signal(conn, tech_id, week, signal, float(value))


def test_compute_week_no_longer_reports_momentum(conn):
    watchlist = Watchlist(version=1, technologies=(tech("a"), tech("b")))
    seed(conn, "a", "arxiv_papers", [1] * 13 + [2] * 13 + [4] * 13)
    seed(conn, "b", "arxiv_papers", [5] * 39)
    rows = metrics.compute_week(conn, "2026-W33", watchlist)
    assert rows
    assert all("momentum" not in row for row in rows)


def test_the_momentum_helpers_are_gone():
    for name in ("acceleration", "quarterly_acceleration", "to_quarters",
                 "has_trend_support", "cross_sectional_z", "momentum_suppressed",
                 "normalize_series", "trailing_mean"):
        assert not hasattr(metrics, name), f"{name} outlived momentum"


