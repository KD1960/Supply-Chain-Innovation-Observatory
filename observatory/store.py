"""SQLite persistence. The database is a derived artifact: everything in it can
be rebuilt from the raw files on disk, so the schema is free to change."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    name TEXT PRIMARY KEY,
    last_run_week TEXT,
    status TEXT,
    note TEXT,
    updated_at TEXT
);

-- `sources` holds only the latest state, which is all the health strip needs.
-- Replaying an old week needs to know how that week went, not how the last one
-- did, so every status write is also appended here, one row per source per week.
CREATE TABLE IF NOT EXISTS source_runs (
    source TEXT NOT NULL,
    week TEXT NOT NULL,
    status TEXT,
    note TEXT,
    updated_at TEXT,
    PRIMARY KEY (source, week)
);

CREATE TABLE IF NOT EXISTS raw_fetch (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    week TEXT NOT NULL,
    url TEXT NOT NULL,
    http_status INTEGER,
    fetched_at TEXT,
    path TEXT
);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    week TEXT NOT NULL,
    tech_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    doc_date TEXT,
    title TEXT,
    url TEXT,
    entity TEXT,
    entity_id TEXT,
    amount REAL,
    lat REAL,
    lon REAL,
    matched_pattern TEXT,
    raw_ref INTEGER,
    UNIQUE (source, doc_id, tech_id)
);

CREATE INDEX IF NOT EXISTS observations_week_tech
    ON observations (week, tech_id);

CREATE TABLE IF NOT EXISTS weekly_signals (
    tech_id TEXT NOT NULL,
    week TEXT NOT NULL,
    signal TEXT NOT NULL,
    value REAL,
    PRIMARY KEY (tech_id, week, signal)
);

CREATE TABLE IF NOT EXISTS weekly_metrics (
    tech_id TEXT NOT NULL,
    week TEXT NOT NULL,
    sai REAL,
    lfi REAL,
    adoption INTEGER,
    adoption_new INTEGER,
    stage_idea REAL,
    stage_experiment REAL,
    stage_investment REAL,
    stage_deployment REAL,
    stage_diffusion REAL,
    position REAL,
    lexicon_version INTEGER,
    PRIMARY KEY (tech_id, week)
);

-- How many documents each source retrieved, by the document's own date.
--
-- The denominator of every rate. The numerator has always been dated by the
-- document itself; counting the denominator by which week's directory a raw
-- file sat in was a different thing, and ISO weeks do not line up with
-- calendar quarters -- 2026-Q4 ran to December 27th and the last four days of
-- the year fell out of the annual report.
--
-- Keyed by week as well as date so a rebuild can replace a week wholesale.
-- Adding instead would inflate the denominator once per rebuild, which reads
-- as a rate that quietly shrinks.
CREATE TABLE IF NOT EXISTS corpus (
    source TEXT NOT NULL,
    week TEXT NOT NULL,
    doc_date TEXT,
    documents INTEGER NOT NULL,
    PRIMARY KEY (source, week, doc_date)
);

CREATE TABLE IF NOT EXISTS candidate_terms (
    term TEXT NOT NULL,
    week TEXT NOT NULL,
    count INTEGER,
    baseline REAL,
    ratio REAL,
    status TEXT,
    examples TEXT,
    total INTEGER,
    PRIMARY KEY (term, week)
);
"""

METRIC_COLUMNS = [
    "tech_id", "week", "sai", "lfi", "adoption", "adoption_new",
    "stage_idea", "stage_experiment", "stage_investment", "stage_deployment",
    "stage_diffusion", "position", "lexicon_version",
]

# Columns added to a table after a database may already exist on disk.
# `CREATE TABLE IF NOT EXISTS` is a no-op against a table that already
# exists, no matter how its definition in `SCHEMA` has since changed, so
# every column added after the table's first release needs an explicit,
# additive entry here -- append to this list, in the order added. The
# fourth element is optional backfill SQL, run once right after the column
# is added, for columns where leaving existing rows at the SQL-level NULL
# default would be actively wrong rather than merely unknown.
MIGRATIONS: list[tuple[str, str, str, str | None]] = [
    ("candidate_terms", "examples", "TEXT", None),
    ("candidate_terms", "total", "INTEGER",
     "UPDATE candidate_terms SET total = "
     "(SELECT COUNT(*) FROM candidate_terms c2 WHERE c2.week = candidate_terms.week) "
     "WHERE total IS NULL"),
]


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    target = str(path or config.DB_PATH)
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add any column in `MIGRATIONS` that this database's table doesn't have
    yet, and backfill it where declared. Additive only -- never drops or
    rewrites a column -- and a no-op on a database that already has the
    column, so it never re-runs the backfill over rows a later, unrelated
    write set to NULL on purpose."""
    for table, column, definition, backfill in MIGRATIONS:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            if backfill:
                conn.execute(backfill)


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _migrate(conn)
    # Databases written before source_runs existed know only each source's last
    # week. Seed that, so replaying it does not find the source silently absent.
    conn.execute(
        "INSERT OR IGNORE INTO source_runs (source, week, status, note, updated_at) "
        "SELECT name, last_run_week, status, note, updated_at FROM sources "
        "WHERE last_run_week IS NOT NULL"
    )
    conn.commit()


# The week key a hand-fetched source's corpus is filed under. Fixed, because an
# export has no week: keying by the export date filed twelve Scopus files under
# one key and let each wipe the last, and then fixing that left the old rows
# beside the new ones, summing to 370 against an export of 185.
MANUAL_KEY = "manual"


def forget_manual_corpus(conn: sqlite3.Connection, source: str) -> None:
    """Drop every corpus row for a hand-fetched source, whatever it was keyed by.

    Called before recording, so a change in how the counting is keyed cannot
    leave a stale row summing alongside the new one.
    """
    conn.execute("DELETE FROM corpus WHERE source = ?", (source,))
    conn.commit()


def record_corpus(conn: sqlite3.Connection, source: str, week: str,
                  counts) -> None:
    """Replace a week's retrieved counts for one source.

    Replace rather than add: a rebuild replays every week, and adding would
    multiply the denominator by however many rebuilds had run.
    """
    conn.execute("DELETE FROM corpus WHERE source = ? AND week = ?", (source, week))
    conn.executemany(
        "INSERT INTO corpus (source, week, doc_date, documents) VALUES (?, ?, ?, ?)",
        [(source, week, date, number) for date, number in counts],
    )
    conn.commit()


def corpus_between(conn: sqlite3.Connection, start: str, end: str) -> dict[str, int]:
    """Documents retrieved whose own date falls in the period, by source.

    An undated document is excluded: it exists, and `corpus_undated` counts it,
    but placing it in a period it may not belong to would be an invention.
    """
    rows = conn.execute(
        "SELECT source, SUM(documents) AS n FROM corpus "
        "WHERE doc_date IS NOT NULL AND doc_date BETWEEN ? AND ? GROUP BY source",
        (start, end),
    ).fetchall()
    return {row["source"]: row["n"] for row in rows}


def corpus_undated(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT source, SUM(documents) AS n FROM corpus "
        "WHERE doc_date IS NULL GROUP BY source"
    ).fetchall()
    return {row["source"]: row["n"] for row in rows}


def clear_derived(conn: sqlite3.Connection) -> None:
    """Drop everything computed from raw, ahead of a --rebuild.

    Observations are written with INSERT OR IGNORE, so replaying a week over
    existing rows changes nothing: without this, a rebuild after a parser fix
    or a widened pattern returns exactly what the old code wrote. Candidate
    terms go too: they are derived from the same raw, and a widened pattern is
    exactly what stops one of them qualifying. `raw_fetch`
    and `sources`/`source_runs` are deliberately spared — the first is an
    append-only log of fetch attempts, the second is what tells the replay
    which weeks were complete.
    """
    conn.executescript(
        "DELETE FROM observations; DELETE FROM weekly_signals; "
        "DELETE FROM weekly_metrics; DELETE FROM candidate_terms; "
        "DELETE FROM corpus;"
    )
    conn.commit()


def record_raw(conn, source: str, week: str, url: str, http_status: int, path: str) -> int:
    cursor = conn.execute(
        "INSERT INTO raw_fetch (source, week, url, http_status, fetched_at, path) "
        "VALUES (?, ?, ?, ?, datetime('now'), ?)",
        (source, week, url, http_status, path),
    )
    conn.commit()
    return int(cursor.lastrowid)


def upsert_observations(conn, rows: Iterable[Any]) -> int:
    inserted = 0
    for row in rows:
        data = asdict(row)
        cursor = conn.execute(
            "INSERT OR IGNORE INTO observations "
            "(source, week, tech_id, doc_id, doc_date, title, url, entity, "
            " entity_id, amount, lat, lon, matched_pattern, raw_ref) "
            "VALUES (:source, :week, :tech_id, :doc_id, :doc_date, :title, :url, "
            " :entity, :entity_id, :amount, :lat, :lon, :matched_pattern, :raw_ref)",
            data,
        )
        inserted += cursor.rowcount
    conn.commit()
    return inserted


def max_observation_id(conn) -> int:
    """High-water mark, so a run can tell which rows it wrote itself."""
    row = conn.execute("SELECT COALESCE(MAX(id), 0) AS high FROM observations").fetchone()
    return int(row["high"])


def new_observation_counts(conn, after_id: int) -> dict[str, int]:
    """Rows written since `after_id`, counted by the week they belong to.

    Not the week they were fetched in: a run's raw routinely holds documents
    dated in an earlier week, and those weeks are the ones whose counts have
    just gone stale.
    """
    rows = conn.execute(
        "SELECT week, COUNT(*) AS total FROM observations WHERE id > ? GROUP BY week",
        (after_id,),
    ).fetchall()
    return {row["week"]: int(row["total"]) for row in rows}


def set_signal(conn, tech_id: str, week: str, signal: str, value: float) -> None:
    conn.execute(
        "INSERT INTO weekly_signals (tech_id, week, signal, value) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (tech_id, week, signal) DO UPDATE SET value = excluded.value",
        (tech_id, week, signal, value),
    )
    conn.commit()


def get_signal(conn, tech_id: str, week: str, signal: str) -> float | None:
    row = conn.execute(
        "SELECT value FROM weekly_signals WHERE tech_id = ? AND week = ? AND signal = ?",
        (tech_id, week, signal),
    ).fetchone()
    return None if row is None else row["value"]


def signal_series(conn, tech_id: str, signal: str, weeks: list[str]) -> list[float | None]:
    rows = conn.execute(
        "SELECT week, value FROM weekly_signals WHERE tech_id = ? AND signal = ?",
        (tech_id, signal),
    ).fetchall()
    by_week = {row["week"]: row["value"] for row in rows}
    return [by_week.get(week) for week in weeks]


def set_source_status(conn, name: str, week: str, status: str, note: str = "") -> None:
    conn.execute(
        "INSERT INTO sources (name, last_run_week, status, note, updated_at) "
        "VALUES (?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT (name) DO UPDATE SET last_run_week = excluded.last_run_week, "
        "status = excluded.status, note = excluded.note, updated_at = excluded.updated_at",
        (name, week, status, note),
    )
    conn.execute(
        "INSERT INTO source_runs (source, week, status, note, updated_at) "
        "VALUES (?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT (source, week) DO UPDATE SET status = excluded.status, "
        "note = excluded.note, updated_at = excluded.updated_at",
        (name, week, status, note),
    )
    conn.commit()


def source_statuses(conn) -> list[dict]:
    return [dict(row) for row in conn.execute("SELECT * FROM sources ORDER BY name")]


def ok_sources_for_runs(conn, run_weeks: Iterable[str]) -> set[str]:
    """Sources whose recorded run completed, for any of these run weeks."""
    weeks = list(run_weeks)
    if not weeks:
        return set()
    placeholders = ",".join("?" * len(weeks))
    rows = conn.execute(
        f"SELECT DISTINCT source FROM source_runs "
        f"WHERE status = 'ok' AND week IN ({placeholders})",
        weeks,
    ).fetchall()
    return {row["source"] for row in rows}


def ok_sources_for_week(conn, week: str) -> set[str]:
    """Sources whose recorded run for this week completed."""
    return ok_sources_for_runs(conn, [week])


def upsert_metrics(conn, row: dict) -> None:
    placeholders = ", ".join(f":{column}" for column in METRIC_COLUMNS)
    updates = ", ".join(
        f"{column} = excluded.{column}"
        for column in METRIC_COLUMNS
        if column not in ("tech_id", "week")
    )
    conn.execute(
        f"INSERT INTO weekly_metrics ({', '.join(METRIC_COLUMNS)}) VALUES ({placeholders}) "
        f"ON CONFLICT (tech_id, week) DO UPDATE SET {updates}",
        {column: row.get(column) for column in METRIC_COLUMNS},
    )
    conn.commit()


def metrics_for_week(conn, week: str) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM weekly_metrics WHERE week = ? ORDER BY tech_id", (week,)
        )
    ]


def observations_for(conn, week: str, tech_id: str, source: str | None = None) -> list[dict]:
    query = "SELECT * FROM observations WHERE week = ? AND tech_id = ?"
    params: list[Any] = [week, tech_id]
    if source is not None:
        query += " AND source = ?"
        params.append(source)
    return [dict(row) for row in conn.execute(query + " ORDER BY doc_date DESC", params)]


def upsert_candidates(conn, week: str, candidates, total: int | None = None) -> int:
    """A week's rows are replaced, not merged, so what is stored is always
    exactly what the current run computed. Merging keeps a term that has
    stopped qualifying forever -- above all the term the owner has just
    promoted to the watchlist, which is the point of the whole discovery loop.
    That term would go on appearing on the dashboard and in the next lexicon
    request, the week's row count would climb past `MAX_CANDIDATES`, and the
    week would hold two different `total`s, the stale one on the highest-ratio
    row that render and lexicon both read the total from. `clear_derived`
    drops the table as well, but that runs only on a --rebuild; this holds on
    an ordinary weekly run.

    `total` is how many candidates qualified before `detect_rising` capped
    the list at `MAX_CANDIDATES`; it defaults to the row count so a caller
    that doesn't yet know about truncation still gets a consistent value."""
    candidates = list(candidates)
    total = len(candidates) if total is None else total
    conn.execute("DELETE FROM candidate_terms WHERE week = ?", (week,))
    for candidate in candidates:
        conn.execute(
            "INSERT INTO candidate_terms "
            "(term, week, count, baseline, ratio, status, examples, total) "
            "VALUES (?, ?, ?, ?, ?, 'new', ?, ?)",
            (candidate.term, week, candidate.count, candidate.baseline, candidate.ratio,
             json.dumps(candidate.examples), total),
        )
    conn.commit()
    return len(candidates)


def candidates_for_week(conn, week: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM candidate_terms WHERE week = ? ORDER BY ratio DESC, term", (week,)
    ).fetchall()
    result = []
    for row in rows:
        record = dict(row)
        record["examples"] = json.loads(record.get("examples") or "[]")
        result.append(record)
    return result
