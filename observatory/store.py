"""SQLite persistence. The database is a derived artifact: everything in it can
be rebuilt from the raw files on disk, so the schema is free to change."""

from __future__ import annotations

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
    momentum REAL,
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

CREATE TABLE IF NOT EXISTS candidate_terms (
    term TEXT NOT NULL,
    week TEXT NOT NULL,
    count INTEGER,
    baseline REAL,
    ratio REAL,
    status TEXT,
    PRIMARY KEY (term, week)
);
"""

METRIC_COLUMNS = [
    "tech_id", "week", "momentum", "sai", "lfi", "adoption", "adoption_new",
    "stage_idea", "stage_experiment", "stage_investment", "stage_deployment",
    "stage_diffusion", "position", "lexicon_version",
]


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    target = str(path or config.DB_PATH)
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
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
    conn.commit()


def source_statuses(conn) -> list[dict]:
    return [dict(row) for row in conn.execute("SELECT * FROM sources ORDER BY name")]


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
