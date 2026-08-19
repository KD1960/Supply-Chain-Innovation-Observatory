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


def test_adoption_is_absent_when_edgar_did_not_run(conn):
    """A week EDGAR failed writes no edgar_filers row. Reading that as 0 would
    print "0 adopters" for every technology on the week we did not look."""
    watchlist = Watchlist(version=1, technologies=(tech("a"),))
    seed(conn, "a", "arxiv_papers", [1] * 14)
    row = metrics.compute_week(conn, "2026-W33", watchlist)[0]
    assert row["adoption"] is None


def test_adoption_is_zero_when_edgar_ran_and_found_nobody(conn):
    watchlist = Watchlist(version=1, technologies=(tech("a"),))
    store.set_signal(conn, "a", "2026-W33", "edgar_filers", 0.0)
    row = metrics.compute_week(conn, "2026-W33", watchlist)[0]
    assert row["adoption"] == 0


def test_compute_week_stamps_the_lexicon_version(conn):
    watchlist = Watchlist(version=7, technologies=(tech("a"),))
    seed(conn, "a", "arxiv_papers", [1] * 14)
    row = metrics.compute_week(conn, "2026-W33", watchlist)[0]
    assert row["lexicon_version"] == 7