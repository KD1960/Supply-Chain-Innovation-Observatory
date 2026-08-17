import pytest

from observatory import config, normalize, store
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


def observation(tech_id, source, doc_id, amount=None, week="2026-W33", entity_id=None):
    return Observation(
        source=source, week=week, tech_id=tech_id, doc_id=doc_id,
        doc_date="2026-08-12", title="t", url="u", entity=None, entity_id=entity_id,
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


def test_entity_filter_counts_only_the_tagged_subset(conn, watchlist):
    store.upsert_observations(conn, [
        observation("autonomous_trucking", "gdelt_doc", "g1"),
        observation("autonomous_trucking", "gdelt_doc", "g2"),
        observation("autonomous_trucking", "gdelt_doc", "g3"),
    ])
    conn.execute("UPDATE observations SET entity = 'deployment' WHERE doc_id IN ('g1','g2')")
    conn.commit()
    normalize.compute_signals(conn, "2026-W33", watchlist, {"gdelt_doc"})
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "media_articles") == 3.0
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "media_deploy") == 2.0


def test_distinct_entities_counts_unique_filers_over_the_trailing_window(conn, watchlist):
    weeks = config.trailing_weeks("2026-W33", 3)
    rows = [
        observation("autonomous_trucking", "edgar", "f1", week=weeks[0], entity_id="0000320193"),
        observation("autonomous_trucking", "edgar", "f2", week=weeks[1], entity_id="0000320193"),
        observation("autonomous_trucking", "edgar", "f3", week=weeks[2], entity_id="0000789019"),
    ]
    store.upsert_observations(conn, rows)
    normalize.compute_signals(conn, "2026-W33", watchlist, {"edgar"})
    # Two distinct CIKs across the window, even though Apple filed twice.
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "edgar_filers") == 2.0


def test_distinct_entities_ignores_documents_outside_the_window(conn, watchlist):
    old = config.week_offset("2026-W33", -60)
    store.upsert_observations(conn, [
        observation("autonomous_trucking", "edgar", "old", week=old, entity_id="0000320193"),
    ])
    normalize.compute_signals(conn, "2026-W33", watchlist, {"edgar"})
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "edgar_filers") == 0.0


def test_distinct_entities_ignores_rows_with_no_entity_id(conn, watchlist):
    store.upsert_observations(conn, [
        observation("autonomous_trucking", "edgar", "f1", entity_id=None),
    ])
    normalize.compute_signals(conn, "2026-W33", watchlist, {"edgar"})
    assert store.get_signal(conn, "autonomous_trucking", "2026-W33", "edgar_filers") == 0.0
