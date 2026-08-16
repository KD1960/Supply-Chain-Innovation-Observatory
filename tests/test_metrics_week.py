import pytest

from observatory import config, metrics, store
from observatory.matcher import Technology, Watchlist


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


def test_stage_scores_average_their_member_signals():
    stages = metrics.stage_scores({"arxiv_papers": 1.0, "hn_points": 3.0})
    assert stages["idea"] == 2.0


def test_stage_with_no_present_signals_is_none():
    stages = metrics.stage_scores({"arxiv_papers": 1.0})
    assert stages["experiment"] is None


def test_pipeline_position_sits_between_one_and_five():
    late = metrics.pipeline_position(
        {"idea": -2.0, "experiment": -1.0, "investment": 0.0,
         "deployment": 2.0, "diffusion": 2.0}
    )
    early = metrics.pipeline_position(
        {"idea": 2.0, "experiment": 2.0, "investment": 0.0,
         "deployment": -1.0, "diffusion": -2.0}
    )
    assert 1.0 <= early < late <= 5.0


def test_substance_index_is_positive_when_building_beats_talking():
    assert metrics.substance_index({"arxiv_papers": 0.0, "patents": 2.0,
                                    "hn_points": -1.0, "media_articles": None}) > 0


def test_lab_to_field_turns_positive_when_deployment_leads():
    stages = {"idea": -1.0, "experiment": -1.0, "investment": 1.0,
              "deployment": 2.0, "diffusion": 0.0}
    assert metrics.lab_to_field(stages) == pytest.approx(2.5)


def test_compute_week_is_warming_up_below_twelve_weeks(conn):
    watchlist = Watchlist(version=1, technologies=(tech("a"), tech("b")))
    seed(conn, "a", "arxiv_papers", [1] * 8)
    seed(conn, "b", "arxiv_papers", [1] * 8)
    rows = {row["tech_id"]: row for row in metrics.compute_week(conn, "2026-W33", watchlist)}
    assert rows["a"]["momentum"] is None
    assert rows["a"]["stage_idea"] is None


def test_compute_week_ranks_the_accelerating_technology_higher(conn):
    watchlist = Watchlist(version=1, technologies=(tech("fast"), tech("flat")))
    seed(conn, "fast", "arxiv_papers", [1, 1, 1, 1, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55])
    seed(conn, "flat", "arxiv_papers", [5] * 14)
    seed(conn, "fast", "hn_points", [1] * 14)
    seed(conn, "flat", "hn_points", [1] * 14)
    seed(conn, "fast", "fedreg_docs", [0] * 14)
    seed(conn, "flat", "fedreg_docs", [0] * 14)
    rows = {row["tech_id"]: row for row in metrics.compute_week(conn, "2026-W33", watchlist)}
    assert rows["fast"]["momentum"] > rows["flat"]["momentum"]


def test_compute_week_stamps_the_lexicon_version(conn):
    watchlist = Watchlist(version=7, technologies=(tech("a"),))
    seed(conn, "a", "arxiv_papers", [1] * 14)
    row = metrics.compute_week(conn, "2026-W33", watchlist)[0]
    assert row["lexicon_version"] == 7


def test_momentum_is_suppressed_after_a_recent_pattern_change(conn):
    # Three technologies, because a cross-sectional z-score needs at least two
    # surviving values to mean anything.
    recent = tech("changed", patterns_changed_week="2026-W30")
    watchlist = Watchlist(
        version=1, technologies=(recent, tech("stable"), tech("rising"))
    )
    seed(conn, "changed", "arxiv_papers", [1, 1, 1, 1, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55])
    seed(conn, "stable", "arxiv_papers", [5] * 14)
    seed(conn, "rising", "arxiv_papers", [1, 1, 2, 2, 3, 3, 4, 6, 9, 13, 18, 24, 31, 39])
    rows = {row["tech_id"]: row for row in metrics.compute_week(conn, "2026-W33", watchlist)}
    assert rows["changed"]["momentum"] is None
    assert rows["stable"]["momentum"] is not None
    assert rows["rising"]["momentum"] > rows["stable"]["momentum"]
