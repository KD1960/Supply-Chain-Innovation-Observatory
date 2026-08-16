import pytest

from observatory import normalize, store
from observatory.matcher import Observation, Technology, Watchlist


def tech(tech_id):
    return Technology(
        id=tech_id, name=tech_id, family="f", include=("x",), exclude=(),
        status="active", added_week="2026-W33", patterns_changed_week="2026-W33",
    )


@pytest.fixture()
def watchlist():
    return Watchlist(version=1, technologies=(tech("autonomous_trucking"), tech("quiet_tech")))


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def observation(tech_id, source, doc_id, amount=None):
    return Observation(
        source=source, week="2026-W33", tech_id=tech_id, doc_id=doc_id,
        doc_date="2026-08-12", title="t", url="u", entity=None, entity_id=None,
        amount=amount, lat=None, lon=None, matched_pattern="x", raw_ref=1,
    )


def test_counts_documents_for_count_signals(conn, watchlist):
    store.upsert_observations(conn, [
        observation("autonomous_trucking", "arxiv", "a1"),
        observation("autonomous_trucking", "arxiv", "a2"),
    ])
    normalize.compute_signals(conn, "2026-W33", watchlist, {"arxiv"})
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "arxiv_papers") == 2.0


def test_sums_amount_for_sum_signals(conn, watchlist):
    store.upsert_observations(conn, [
        observation("autonomous_trucking", "hn", "h1", amount=214.0),
        observation("autonomous_trucking", "hn", "h2", amount=38.0),
    ])
    normalize.compute_signals(conn, "2026-W33", watchlist, {"hn"})
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "hn_points") == 252.0


def test_writes_explicit_zero_for_a_technology_with_no_hits(conn, watchlist):
    store.upsert_observations(conn, [observation("autonomous_trucking", "arxiv", "a1")])
    normalize.compute_signals(conn, "2026-W33", watchlist, {"arxiv"})
    assert store.get_signal(conn, "quiet_tech", "2026-W33", "arxiv_papers") == 0.0


def test_a_failed_source_leaves_a_hole_rather_than_a_zero(conn, watchlist):
    normalize.compute_signals(conn, "2026-W33", watchlist, {"arxiv"})
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "arxiv_papers") == 0.0
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "hn_points") is None


def test_recomputing_the_same_week_is_idempotent(conn, watchlist):
    store.upsert_observations(conn, [observation("autonomous_trucking", "arxiv", "a1")])
    normalize.compute_signals(conn, "2026-W33", watchlist, {"arxiv"})
    normalize.compute_signals(conn, "2026-W33", watchlist, {"arxiv"})
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "arxiv_papers") == 1.0
