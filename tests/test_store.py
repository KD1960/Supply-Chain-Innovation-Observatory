import pytest

from observatory import store
from observatory.matcher import Observation


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


def test_init_schema_migrates_a_pre_existing_candidate_terms_table():
    """A database written before `examples` (task 3) or `total` (task 4) were
    added to `candidate_terms` has neither column on disk -- `CREATE TABLE IF
    NOT EXISTS` is a no-op against a table that already exists, no matter how
    the definition in code has changed since. `init_schema` must add the
    missing columns to that table in place, without touching its data."""
    import sqlite3

    from observatory.discover import Candidate

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE candidate_terms (term TEXT NOT NULL, week TEXT NOT NULL, "
        "count INTEGER, baseline REAL, ratio REAL, status TEXT, "
        "PRIMARY KEY (term, week))"
    )
    connection.execute(
        "INSERT INTO candidate_terms (term, week, count, baseline, ratio, status) "
        "VALUES ('dark factory', '2026-W20', 6, 1.0, 6.0, 'new')"
    )
    connection.commit()

    store.init_schema(connection)

    columns = {row["name"] for row in connection.execute("PRAGMA table_info(candidate_terms)")}
    assert {"examples", "total"} <= columns

    row = connection.execute(
        "SELECT * FROM candidate_terms WHERE term = 'dark factory' AND week = '2026-W20'"
    ).fetchone()
    assert row is not None
    assert row["count"] == 6
    assert row["ratio"] == 6.0

    store.upsert_candidates(connection, "2026-W21", [
        Candidate(term="vision language", count=8, baseline=1.0, ratio=8.0, examples=[]),
    ])
    assert len(store.candidates_for_week(connection, "2026-W21")) == 1
    connection.close()


def test_init_schema_backfills_total_for_pre_existing_rows():
    """Adding the `total` column with no DEFAULT and no backfill would leave
    every legacy row NULL, and the render path crashes on that (see
    render.build_context). The honest backfill for a row written before
    `total` existed is the number of stored rows for that row's own week --
    counted per week, not globally, since two different weeks' candidate
    lists are unrelated truncations."""
    import sqlite3

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE candidate_terms (term TEXT NOT NULL, week TEXT NOT NULL, "
        "count INTEGER, baseline REAL, ratio REAL, status TEXT, "
        "PRIMARY KEY (term, week))"
    )
    connection.executemany(
        "INSERT INTO candidate_terms (term, week, count, baseline, ratio, status) "
        "VALUES (?, ?, 6, 1.0, 6.0, 'new')",
        [
            ("dark factory", "2026-W20"),
            ("vision language", "2026-W20"),
            ("multi agent", "2026-W21"),
        ],
    )
    connection.commit()

    store.init_schema(connection)

    rows = connection.execute(
        "SELECT term, week, total FROM candidate_terms ORDER BY week, term"
    ).fetchall()
    totals = {(row["term"], row["week"]): row["total"] for row in rows}
    assert None not in totals.values()
    assert totals[("dark factory", "2026-W20")] == 2
    assert totals[("vision language", "2026-W20")] == 2
    assert totals[("multi agent", "2026-W21")] == 1
    connection.close()


def test_init_schema_migration_is_idempotent():
    import sqlite3

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    store.init_schema(connection)
    store.init_schema(connection)
    columns = [row["name"] for row in connection.execute("PRAGMA table_info(candidate_terms)")]
    assert columns.count("examples") == 1
    assert columns.count("total") == 1
    assert set(columns) == {
        "term", "week", "count", "baseline", "ratio", "status", "examples", "total",
    }
    connection.close()


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


def test_candidates_round_trip(conn):
    from observatory.discover import Candidate

    store.upsert_candidates(conn, "2026-W33", [
        Candidate(term="dark factory", count=6, baseline=1.0, ratio=6.0,
                  examples=[("Dark factory retrofit", "https://x.test/1")]),
    ])
    rows = store.candidates_for_week(conn, "2026-W33")
    assert len(rows) == 1
    assert rows[0]["term"] == "dark factory"
    assert rows[0]["ratio"] == 6.0
    assert rows[0]["status"] == "new"


def test_candidates_upsert_is_idempotent(conn):
    from observatory.discover import Candidate

    candidate = Candidate(term="dark factory", count=6, baseline=1.0, ratio=6.0, examples=[])
    store.upsert_candidates(conn, "2026-W33", [candidate])
    store.upsert_candidates(conn, "2026-W33", [candidate])
    assert len(store.candidates_for_week(conn, "2026-W33")) == 1


def test_candidates_upsert_replaces_the_weeks_rows(conn):
    """A term stops qualifying — most importantly because the owner just
    promoted it to the watchlist, which is the point of the discovery loop.
    Merging would keep its row forever: it would stay on the dashboard and in
    the next lexicon request, push the table past MAX_CANDIDATES, and leave two
    different `total`s stored for one week, so the highest-ratio row that
    render and lexicon read the total from could carry a stale one."""
    from observatory.discover import Candidate

    first = [
        Candidate(term="multi agent", count=9, baseline=1.0, ratio=9.0, examples=[]),
        Candidate(term="dark factory", count=6, baseline=1.0, ratio=6.0, examples=[]),
        Candidate(term="vision language", count=5, baseline=1.0, ratio=5.0, examples=[]),
    ]
    store.upsert_candidates(conn, "2026-W33", first, total=225)

    second = [
        Candidate(term="dark factory", count=6, baseline=1.0, ratio=6.0, examples=[]),
        Candidate(term="vision language", count=5, baseline=1.0, ratio=5.0, examples=[]),
    ]
    store.upsert_candidates(conn, "2026-W33", second, total=221)

    rows = store.candidates_for_week(conn, "2026-W33")
    assert [row["term"] for row in rows] == ["dark factory", "vision language"]
    assert {row["total"] for row in rows} == {221}


def test_candidates_upsert_leaves_other_weeks_alone(conn):
    from observatory.discover import Candidate

    store.upsert_candidates(conn, "2026-W32", [
        Candidate(term="dark factory", count=6, baseline=1.0, ratio=6.0, examples=[]),
    ])
    store.upsert_candidates(conn, "2026-W33", [
        Candidate(term="vision language", count=5, baseline=1.0, ratio=5.0, examples=[]),
    ])
    assert [row["term"] for row in store.candidates_for_week(conn, "2026-W32")] == ["dark factory"]


def test_clear_derived_drops_candidate_terms(conn):
    from observatory.discover import Candidate

    store.upsert_candidates(conn, "2026-W33", [
        Candidate(term="dark factory", count=6, baseline=1.0, ratio=6.0, examples=[]),
    ])
    store.clear_derived(conn)
    assert store.candidates_for_week(conn, "2026-W33") == []
