"""Orchestration and CLI.

Order is fixed: fetch every source to disk, then parse and match from disk, then
aggregate, then score, then render. A collector failure is contained to its own
source and never stops the run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config, http, matcher, metrics, normalize, render, store
from .collectors import base
from .collectors.arxiv import ArxivCollector
from .collectors.federalregister import FederalRegisterCollector
from .collectors.hn import HackerNewsCollector

COLLECTORS = (ArxivCollector(), HackerNewsCollector(), FederalRegisterCollector())


def fetch_week(conn, week: str, collectors, session) -> set[str]:
    succeeded: set[str] = set()
    for collector in collectors:
        try:
            for index, page in enumerate(collector.fetch_raw(session, week)):
                path = base.write_raw(collector.name, week, index, page)
                store.record_raw(conn, collector.name, week, page.url, page.status, str(path))
            store.set_source_status(conn, collector.name, week, "ok", "")
            succeeded.add(collector.name)
        except Exception as error:  # one bad source must not end the run
            store.set_source_status(conn, collector.name, week, "failed", str(error))
            print(f"  ! {collector.name} failed: {error}", file=sys.stderr)
    return succeeded


def sources_with_raw(week: str, collectors) -> set[str]:
    return {
        collector.name
        for collector in collectors
        if any(base.read_raw(collector.name, week))
    }


def ingest_week(conn, week: str, watchlist, collectors) -> int:
    inserted = 0
    for collector in collectors:
        for path, text in base.read_raw(collector.name, week):
            raw_ref = _raw_ref(conn, str(path))
            for document in collector.parse(text):
                inserted += store.upsert_observations(
                    conn,
                    matcher.observations_for_document(
                        watchlist, document, collector.name, week, raw_ref
                    ),
                )
    return inserted


def _raw_ref(conn, path: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM raw_fetch WHERE path = ? ORDER BY id DESC LIMIT 1", (path,)
    ).fetchone()
    return None if row is None else int(row["id"])


def score_week(conn, week: str, watchlist) -> int:
    rows = metrics.compute_week(conn, week, watchlist)
    for row in rows:
        store.upsert_metrics(conn, row)
    return len(rows)


def run_week(
    conn,
    week: str,
    watchlist,
    collectors=COLLECTORS,
    session=None,
    skip_fetch: bool = False,
    out_path: Path | None = None,
) -> Path:
    if skip_fetch:
        ok_sources = sources_with_raw(week, collectors)
        print(f"Skipping fetch; replaying raw for {sorted(ok_sources)}")
    else:
        print(f"Fetching {week}")
        ok_sources = fetch_week(conn, week, collectors, session)

    observations = ingest_week(conn, week, watchlist, collectors)
    signals = normalize.compute_signals(conn, week, watchlist, ok_sources)
    scored = score_week(conn, week, watchlist)
    path = render.render_dashboard(conn, week, watchlist, out_path)

    _append_run_log(week, ok_sources, observations, signals, scored, path)
    print(
        f"{week}: {observations} new observations, {signals} signals, "
        f"{scored} scored -> {path}"
    )
    return path


def _append_run_log(week, ok_sources, observations, signals, scored, path) -> None:
    config.RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with config.RUN_LOG_PATH.open("a") as handle:
        handle.write(json.dumps({
            "week": week,
            "ok_sources": sorted(ok_sources),
            "new_observations": observations,
            "signals_written": signals,
            "technologies_scored": scored,
            "output": str(path),
        }) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="observatory.run")
    parser.add_argument("--week", default=None, help="ISO week, e.g. 2026-W33")
    parser.add_argument("--skip-fetch", action="store_true",
                        help="recompute from raw files already on disk")
    parser.add_argument("--rebuild", action="store_true",
                        help="recompute every week that has raw data")
    parser.add_argument("--only", default=None, help="run a single collector by name")
    args = parser.parse_args(argv)

    config.load_dotenv()
    watchlist = matcher.load_watchlist()
    collectors = COLLECTORS
    if args.only:
        collectors = tuple(c for c in COLLECTORS if c.name == args.only)
        if not collectors:
            parser.error(f"unknown collector {args.only!r}")

    conn = store.connect()
    store.init_schema(conn)
    try:
        if args.rebuild:
            weeks = sorted(p.name for p in config.RAW_DIR.glob("*-W*") if p.is_dir())
            for week in weeks:
                run_week(conn, week, watchlist, collectors, skip_fetch=True)
            return 0
        week = args.week or config.current_week()
        session = None if args.skip_fetch else http.make_session()
        run_week(conn, week, watchlist, collectors, session=session,
                 skip_fetch=args.skip_fetch)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
