"""Orchestration and CLI.

Order is fixed: fetch every source to disk, then parse and match from disk, then
aggregate, then score, then render. A collector failure is contained to its own
source and never stops the run.
"""

from __future__ import annotations

import argparse
import datetime as dt
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


def sources_ok_for_week(conn, week: str, collectors) -> set[str]:
    """Which sources may be replayed for this week.

    Having raw on disk is not the same as having complete raw. A source that
    dies on its second sweep leaves the pages it already wrote behind, and
    counting those files would let a later --skip-fetch write signals for a
    truncated week as though it were whole — fabricating exactly the dip the
    hole rule exists to prevent. Only the recorded status knows.
    """
    recorded = store.ok_sources_for_week(conn, week)
    return {collector.name for collector in collectors if collector.name in recorded}


def ingest_week(conn, week: str, watchlist, collectors, ok_sources: set[str]) -> tuple[int, set[str]]:
    """Parse and match every source's raw files, one source at a time.

    Isolated like `fetch_week` is: a raw file holding an HTML error body saved
    as .xml raises on parse, and without this the whole run dies before
    signals, scoring or render — every later run of that week included, since
    the poisoned file stays on disk. A source that fails here drops out of
    ok_sources, so `normalize.compute_signals` leaves a hole rather than a zero.
    """
    inserted = 0
    still_ok = set(ok_sources)
    for collector in collectors:
        try:
            inserted += _ingest_source(conn, week, watchlist, collector)
        except Exception as error:  # one bad parse must not end the run
            store.set_source_status(conn, collector.name, week, "failed", str(error))
            still_ok.discard(collector.name)
            print(f"  ! {collector.name} ingest failed: {error}", file=sys.stderr)
    return inserted, still_ok


def _ingest_source(conn, week: str, watchlist, collector) -> int:
    inserted = 0
    for path, text in base.read_raw(collector.name, week):
        raw_ref = _raw_ref(conn, str(path))
        for document in collector.parse(text):
            inserted += store.upsert_observations(
                conn,
                matcher.observations_for_document(
                    watchlist, document, collector.name,
                    _document_week(document, week), raw_ref
                ),
            )
    return inserted


def _document_week(document, fallback: str) -> str:
    """The week a document belongs to, not the week we happened to fetch it.

    With a lookback overlap in the query windows a run routinely sees last
    week's documents; keying them to the run week would file them under when
    we looked rather than when they happened.
    """
    if not document.date:
        return fallback
    try:
        return config.iso_week(dt.date.fromisoformat(document.date[:10]))
    except ValueError:
        return fallback


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
        ok_sources = sources_ok_for_week(conn, week, collectors)
        print(f"Skipping fetch; replaying raw for {sorted(ok_sources)}")
    else:
        print(f"Fetching {week}")
        ok_sources = fetch_week(conn, week, collectors, session)

    observations, ok_sources = ingest_week(conn, week, watchlist, collectors, ok_sources)
    signals = normalize.compute_signals(conn, week, watchlist, ok_sources)
    scored = score_week(conn, week, watchlist)
    path = render.render_dashboard(conn, week, watchlist, out_path)

    _append_run_log(week, ok_sources, observations, signals, scored, path)
    print(
        f"{week}: {observations} new observations, {signals} signals, "
        f"{scored} scored -> {path}"
    )
    return path


def rebuild(conn, watchlist, collectors=COLLECTORS) -> list[Path]:
    """Recompute every week that has raw data, under the current lexicon.

    The derived tables are dropped first. Observations are inserted with
    INSERT OR IGNORE, so replaying over the existing rows would otherwise
    leave every one of them exactly as the old parser or the old patterns
    wrote it, and the only working rebuild would be deleting the database.
    """
    store.clear_derived(conn)
    weeks = sorted(path.name for path in config.RAW_DIR.glob("*-W*") if path.is_dir())
    return [
        run_week(conn, week, watchlist, collectors, skip_fetch=True) for week in weeks
    ]


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
            rebuild(conn, watchlist, collectors)
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
