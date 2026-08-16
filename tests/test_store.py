import pytest
from dataclasses import dataclass

from observatory import store

# Task 4 will move this to observatory.matcher
@dataclass
class Observation:
    source: str
    week: str
    tech_id: str
    doc_id: str
    doc_date: str
    title: str
    url: str
    entity: str | None
    entity_id: str | None
    amount: float | None
    lat: float | None
    lon: float | None
    matched_pattern: str
    raw_ref: int


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def observation(**overrides):
    base = dict(
        source="arxiv",
        week="2026-W33",
        tech_id="autonomous_trucking",
        doc_id="arxiv:2608.00001",
        doc_date="2026-08-12",
        title="A paper about autonomous trucking",
        url="https://arxiv.org/abs/2608.00001",
        entity=None,
        entity_id=None,
        amount=None,
        lat=None,
        lon=None,
        matched_pattern="autonomous truck",
        raw_ref=1,
    )
    base.update(overrides)
    return Observation(**base)


def test_init_schema_is_idempotent(conn):
    store.init_schema(conn)
    store.init_schema(conn)
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"sources", "raw_fetch", "observations", "weekly_signals",
            "weekly_metrics", "candidate_terms"} <= tables


def test_upsert_observations_ignores_duplicates(conn):
    assert store.upsert_observations(conn, [observation()]) == 1
    assert store.upsert_observations(conn, [observation()]) == 0
    count = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert count == 1


def test_same_document_can_match_two_technologies(conn):
    store.upsert_observations(
        conn,
        [observation(), observation(tech_id="warehouse_robotics")],
    )
    count = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert count == 2


def test_signal_series_returns_none_for_missing_weeks(conn):
    store.set_signal(conn, "autonomous_trucking", "2026-W31", "arxiv_papers", 4.0)
    store.set_signal(conn, "autonomous_trucking", "2026-W33", "arxiv_papers", 6.0)
    series = store.signal_series(
        conn, "autonomous_trucking", "arxiv_papers",
        ["2026-W31", "2026-W32", "2026-W33"],
    )
    assert series == [4.0, None, 6.0]


def test_set_signal_overwrites_on_rerun(conn):
    store.set_signal(conn, "t", "2026-W33", "arxiv_papers", 1.0)
    store.set_signal(conn, "t", "2026-W33", "arxiv_papers", 9.0)
    assert store.get_signal(conn, "t", "2026-W33", "arxiv_papers") == 9.0


def test_source_status_round_trips(conn):
    store.set_source_status(conn, "arxiv", "2026-W33", "ok", "")
    store.set_source_status(conn, "hn", "2026-W33", "failed", "timeout")
    statuses = {row["name"]: row for row in store.source_statuses(conn)}
    assert statuses["arxiv"]["status"] == "ok"
    assert statuses["hn"]["note"] == "timeout"


def test_metrics_round_trip(conn):
    store.upsert_metrics(conn, {
        "tech_id": "autonomous_trucking", "week": "2026-W33",
        "momentum": 1.5, "sai": -0.2, "lfi": 0.3,
        "adoption": 12, "adoption_new": 2,
        "stage_idea": 0.1, "stage_experiment": 0.2, "stage_investment": 0.3,
        "stage_deployment": 0.4, "stage_diffusion": 0.5, "position": 3.2,
        "lexicon_version": 1,
    })
    rows = store.metrics_for_week(conn, "2026-W33")
    assert len(rows) == 1
    assert rows[0]["momentum"] == 1.5
    assert rows[0]["lexicon_version"] == 1
