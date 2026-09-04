"""Orchestration and CLI.

Order is fixed: fetch every source to disk, then parse and match from disk, then
aggregate, then score, then render. A collector failure is contained to its own
source and never stops the run.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import sys
from pathlib import Path

from . import (config, discover, http, manual, matcher, metrics, normalize,
               quarter, render, store, supplemental)
from .collectors import base
from .collectors.arxiv import ArxivCollector
from .collectors.edgar import EdgarCollector
from .collectors.federalregister import FederalRegisterCollector
from .collectors.github import GithubCollector
from .collectors.hn import HackerNewsCollector
from .collectors.nsf import NsfCollector
from .collectors.openalex import OpenAlexCollector
from .collectors.usaspending import UsaspendingCollector

COLLECTORS = (
    ArxivCollector(),
    HackerNewsCollector(),
    OpenAlexCollector(),
    NsfCollector(),
    FederalRegisterCollector(),
    UsaspendingCollector(),
    EdgarCollector(),
    GithubCollector(),
)


def fetch_week(conn, week: str, collectors, session) -> set[str]:
    succeeded: set[str] = set()
    for collector in collectors:
        try:
            pages = 0
            for index, page in enumerate(collector.fetch_raw(session, week)):
                path = base.write_raw(collector.name, week, index, page)
                store.record_raw(conn, collector.name, week, page.url, page.status, str(path))
                pages += 1
            # A run that yielded nothing at all. Recorded as its own status
            # rather than as ok, because an API that quietly starts returning
            # nothing is indistinguishable from a technology nobody is working
            # on, and four collectors warn about the opposite condition while
            # nothing checked this floor.
            store.set_source_status(
                conn, collector.name, week,
                "ok" if pages else "empty",
                "" if pages else "fetch returned no pages")
            # `empty` still counts as collected. A real zero and a broken API
            # look identical in one response and NSF's seasonal gap is a real
            # zero, so this is surfaced for a human and never folded into a
            # hole automatically.
            succeeded.add(collector.name)
        except Exception as error:  # one bad source must not end the run
            store.set_source_status(conn, collector.name, week, "failed", str(error))
            # The attempt reaches raw_fetch even though no body was written,
            # with the status if the error carried one and NULL if there was no
            # response to have one.
            store.record_raw(conn, collector.name, week,
                             getattr(error, "url", None) or f"{collector.name}:{week}",
                             getattr(error, "status", None), None)
            print(f"  ! {collector.name} failed: {error}", file=sys.stderr)
    return succeeded


def collectors_needing_fetch(conn, week: str, collectors) -> list:
    """The collectors that have not recorded a successful run for this week.

    Resumability is per collector, not per week. A source that fails
    systematically on historical weeks would otherwise keep its week pending
    forever, and every restart would repeat the other four sources' requests
    for it -- arXiv's among them, at three seconds apiece.
    """
    recorded = store.ok_sources_for_week(conn, week)
    return [collector for collector in collectors if collector.name not in recorded]


def weeks_needing_fetch(conn, weeks: list[str], collectors) -> list[str]:
    """Weeks where some collector has not yet recorded a successful run.

    This is what makes backfill resumable: a year of history is hours of
    polite fetching, and it must survive being interrupted and restarted
    without re-downloading what it already has.
    """
    return [week for week in weeks if collectors_needing_fetch(conn, week, collectors)]


def backfill(conn, weeks_back: int, collectors=COLLECTORS, session=None) -> list[str]:
    if weeks_back < 1:
        raise ValueError(f"weeks_back must be at least 1, got {weeks_back}")

    weeks = config.trailing_weeks(config.current_week(), weeks_back)
    pending = weeks_needing_fetch(conn, weeks, collectors)
    if not pending:
        print(f"Backfill: all {len(weeks)} weeks already fetched")
        return []

    print(f"Backfill: {len(pending)} of {len(weeks)} weeks to fetch, oldest first")
    for position, week in enumerate(pending, start=1):
        missing = collectors_needing_fetch(conn, week, collectors)
        print(f"  [{position}/{len(pending)}] {week}: "
              f"{', '.join(collector.name for collector in missing)}")
        fetch_week(conn, week, missing, session)
    return pending


def weeks_swept_by(week: str) -> list[str]:
    """Every ISO week a run for `week` actually looked at.

    Each collector's query window opens LOOKBACK_DAYS before the Monday of the
    week being processed, so the run sweeps the preceding week in full as well
    as its own. Those are the weeks whose counts a run may legitimately move.
    """
    monday, _ = config.week_bounds(week)
    earliest = config.iso_week(monday - dt.timedelta(days=config.LOOKBACK_DAYS))
    return config.week_range(earliest, week)


def runs_sweeping(week: str) -> list[str]:
    """The inverse of `weeks_swept_by`: runs whose window covered this week."""
    reach = len(weeks_swept_by(week)) - 1
    return [config.week_offset(week, ahead) for ahead in range(reach + 1)]


def scoring_sources(conn, week: str, collectors) -> set[str]:
    """Which sources may be counted for this week.

    A different question from `sources_ok_for_week`, which asks whether a
    week's own raw is complete enough to replay. The lookback means the
    following week's run swept this week in full, so a source that completed
    there has looked at this week too — that is what lets a late-arriving
    document reach a count. A source that failed in every run covering this
    week is still absent here, so the hole rule holds per week.
    """
    recorded = store.ok_sources_for_runs(conn, runs_sweeping(week))
    return {collector.name for collector in collectors if collector.name in recorded}


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
            found = _ingest_source(conn, week, watchlist, collector)
            inserted += found
            # The other shape of nothing: pages arrived and parsed to an empty
            # corpus. Recorded, not acted on -- see fetch_week.
            if collector.name in ok_sources:
                store.set_source_status(
                    conn, collector.name, week,
                    "ok" if found else "empty",
                    "" if found else "parsed no documents")
        except Exception as error:  # one bad parse must not end the run
            store.set_source_status(conn, collector.name, week, "failed", str(error))
            still_ok.discard(collector.name)
            print(f"  ! {collector.name} ingest failed: {error}", file=sys.stderr)
    return inserted, still_ok


def _ingest_source(conn, week: str, watchlist, collector) -> int:
    inserted = 0
    # Every document the parser saw, matched or not: the denominator of a rate
    # is the corpus, not the part of it that happened to match. Dated by the
    # document itself, so a week straddling a quarter boundary contributes to
    # both in the proportion its documents actually fall.
    retrieved: collections.Counter = collections.Counter()
    for path, text in base.read_raw(collector.name, week):
        raw_ref = _raw_ref(conn, str(path))
        for document in collector.parse(text):
            retrieved[document.date[:10] if document.date else None] += 1
            inserted += store.upsert_observations(
                conn,
                matcher.observations_for_document(
                    watchlist, document, collector.name,
                    _document_week(document, week), raw_ref
                ),
            )
    store.record_corpus(conn, collector.name, week, retrieved.items())
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

    mark = store.max_observation_id(conn)
    _, ok_sources = ingest_week(conn, week, watchlist, collectors, ok_sources)
    new_by_week = store.new_observation_counts(conn, mark)

    # Documents are keyed to their own week (see `_document_week`), and with a
    # seven-day lookback that is routinely the week before this one — the
    # majority case for EDGAR, whose filings trail their index date. Counting
    # only the run week would leave those rows in `observations` forever
    # without ever reaching a signal, the evidence list and the number above it
    # disagreeing permanently. So every other week this run wrote into is
    # recomputed and re-archived too, each with its own sources, before the run
    # week is rendered last and takes `latest.html`.
    swept = set(weeks_swept_by(week))
    for other in sorted((set(new_by_week) & swept) - {week}):
        _score_and_render(
            conn, other, watchlist, scoring_sources(conn, other, collectors),
            new_by_week[other], collectors, latest=False,
        )

    return _score_and_render(
        conn, week, watchlist, ok_sources, new_by_week.get(week, 0), collectors, out_path
    )


def weeks_to_render(conn) -> list[str]:
    """Every week holding an observation, that has actually happened.

    Scopus issue dates run months ahead of publication, so the store holds
    2026-W40, W44 and W49. Rendering them produced dashboards for weeks that
    did not exist, and because the loop runs ascending, the last one drawn took
    `latest.html`. A page about a week is a claim that the week occurred.
    """
    return sorted(week for week in store.new_observation_counts(conn, 0)
                  if week <= config.current_week())


def _score_and_render(
    conn, week: str, watchlist, ok_sources: set[str], observations: int, collectors,
    out_path: Path | None = None, latest: bool = True,
) -> Path:
    # A page called `latest` is a claim about now, and a week after this one
    # cannot be it. `--import-manual` re-renders every week holding an
    # observation, ascending, and the last one rendered takes the file; Scopus
    # issue dates run months ahead, so an import in September pointed
    # latest.html at 2026-W49. Whatever order the loop runs in, the claim has
    # to stay true.
    if latest and week > config.current_week():
        latest = False
    signals = normalize.compute_signals(conn, week, watchlist, ok_sources)
    scored = score_week(conn, week, watchlist)
    rising = discover.detect_rising(week, collectors, watchlist)
    store.upsert_candidates(conn, week, rising.candidates, rising.total)
    path = render.render_dashboard(conn, week, watchlist, out_path, latest=latest)

    by_status = store.sources_by_status(conn, week)
    failed = by_status.get("failed", set())
    empty = by_status.get("empty", set())
    _append_run_log(week, ok_sources, observations, signals, scored, rising, path,
                    failed_sources=failed, empty_sources=empty)
    print(
        f"{week}: {observations} new observations, {signals} signals, "
        f"{scored} scored, {len(rising.candidates)} of {rising.total} rising "
        f"candidates -> {path}"
    )
    # Said out loud on the run that produced it, not left to whoever later
    # reads the log. Silence is what let "no source run has ever failed" stand.
    if failed:
        print(f"  ! failed: {', '.join(sorted(failed))}", file=sys.stderr)
    if empty:
        print(f"  ~ returned nothing: {', '.join(sorted(empty))}", file=sys.stderr)
    return path


def rebuild(conn, watchlist, collectors=COLLECTORS) -> list[Path]:
    """Recompute every week that has raw data, under the current lexicon.

    The derived tables are dropped first. Observations are inserted with
    INSERT OR IGNORE, so replaying over the existing rows would otherwise
    leave every one of them exactly as the old parser or the old patterns
    wrote it, and the only working rebuild would be deleting the database.

    Two passes, and the order is the point. Each week's query window reaches
    seven days back, so week W's raw routinely holds documents belonging to
    W-1. Ingesting and scoring one week at a time would compute W-1's signals
    before W's raw had been read, and the late documents would sit in
    `observations` forever without ever reaching a count — the evidence list
    and the number above it disagreeing permanently. So every week's raw is
    ingested first, and only then is anything counted.

    Scoring is not limited to the weeks that have raw either. A week reached
    only through a neighbour's lookback has no raw directory of its own, and
    counting directories alone would leave it uncounted for the same reason.
    """
    store.clear_derived(conn)
    raw_weeks = sorted(path.name for path in config.RAW_DIR.glob("*-W*") if path.is_dir())

    # Licensed exports live outside data/raw and clear_derived has just wiped
    # their observations. Replaying them here is what keeps a rebuild from
    # quietly deleting a source, and it happens before any scoring so their
    # backdated documents reach the counts of the weeks they belong to.
    restored = manual.import_exports(conn, watchlist)
    if restored:
        print(f"Rebuilding: restored {restored} observations from manual exports")

    for week in raw_weeks:
        print(f"Rebuilding {week}: reading raw")
        ingest_week(
            conn, week, watchlist, collectors,
            sources_ok_for_week(conn, week, collectors),
        )

    swept = {week for raw_week in raw_weeks for week in weeks_swept_by(raw_week)}
    new_by_week = store.new_observation_counts(conn, 0)
    weeks = sorted(set(raw_weeks) | (set(new_by_week) & swept))

    # Ascending, so the newest week is rendered last and takes `latest.html`.
    return [
        _score_and_render(conn, week, watchlist,
                          scoring_sources(conn, week, collectors),
                          new_by_week.get(week, 0), collectors)
        for week in weeks
    ]


def _append_run_log(week, ok_sources, observations, signals, scored, rising, path,
                    failed_sources=(), empty_sources=()) -> None:
    """One line per run. It carried `ok_sources` and nothing else across 1,823
    lines -- not one failure field -- so a week whose first line read `["hn"]`
    and whose later lines read three sources could not say what had failed."""
    config.RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with config.RUN_LOG_PATH.open("a") as handle:
        handle.write(json.dumps({
            "week": week,
            "ok_sources": sorted(ok_sources),
            "failed_sources": sorted(failed_sources),
            "empty_sources": sorted(empty_sources),
            "new_observations": observations,
            "signals_written": signals,
            "technologies_scored": scored,
            "rising_candidates_shown": len(rising.candidates),
            "rising_candidates_total": rising.total,
            "output": str(path),
        }) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="observatory.run")
    parser.add_argument("--week", default=None, help="ISO week, e.g. 2026-W33")
    parser.add_argument("--skip-fetch", action="store_true",
                        help="recompute from raw files already on disk")
    parser.add_argument("--rebuild", action="store_true",
                        help="recompute every week that has raw data")
    parser.add_argument("--backfill", type=int, default=None, metavar="WEEKS",
                        help="fetch this many trailing weeks of history, then rebuild")
    parser.add_argument("--only", default=None, help="run a single collector by name")
    parser.add_argument("--quarter", default=None, metavar="YYYY-Qn",
                        help="write the quarterly report for a quarter, e.g. 2026-Q2")
    parser.add_argument("--annual", default=None, metavar="YYYY",
                        help="write the annual report for a calendar year, e.g. 2026")
    parser.add_argument("--import-manual", action="store_true",
                        help="ingest licensed exports from data/manual, then rescore")
    parser.add_argument("--audit-sheet", nargs="?", const=20260902, type=int,
                        metavar="SEED",
                        help="draw a precision-audit sample and write the coding "
                             "sheet, then exit")
    parser.add_argument("--write-status", action="store_true",
                        help="rewrite STATUS section 2 from the database, then exit")
    parser.add_argument("--export-queries", default=None, metavar="YYYY-Qn",
                        help="print the queries a human pastes into the "
                             "human-fetched databases for a period, then exit")
    parser.add_argument("--source", default=None, metavar="NAME",
                        help="with --export-queries, print only this source's "
                             "query, e.g. lens or scopus")
    parser.add_argument("--split", action="store_true",
                        help="with --export-queries, break a source's query into "
                             "one export per journal or code, for when a single "
                             "export would exceed the database's limit")
    args = parser.parse_args(argv)
    if args.rebuild and args.only:
        # Clearing the derived tables and then replaying one collector would
        # delete every other source's rows and never rewrite them, leaving a
        # hole on a week that actually succeeded. Scoping the delete to the
        # replayed source is worse: the derived tables would then disagree
        # across sources about which lexicon produced them.
        parser.error("--rebuild always replays every source; it cannot be combined with --only")
    if args.backfill is not None and args.only:
        # --backfill ends in the same rebuild(), so it hits the same hole.
        parser.error("backfill always fetches every source because it ends in a full rebuild; "
                      "it cannot be combined with --only")

    config.load_dotenv()
    watchlist = matcher.load_watchlist()
    collectors = COLLECTORS
    if args.only:
        collectors = tuple(c for c in COLLECTORS if c.name == args.only)
        if not collectors:
            parser.error(f"unknown collector {args.only!r}")

    # Before the database is even opened: this reads the watchlist and the
    # source registry and touches nothing else.
    if args.export_queries:
        supplemental.print_queries(args.export_queries, watchlist,
                                   only=args.source, split=args.split)
        return 0

    conn = store.connect()
    store.init_schema(conn)
    try:
        if args.audit_sheet:
            from . import audit
            drawn = audit.draw(conn, seed=args.audit_sheet)
            licensed = set(supplemental.load().sources)
            text = audit.markdown(conn, drawn, args.audit_sheet,
                                  watchlist.version, licensed)
            out = config.ROOT / "docs" / "audit" / f"sample-{args.audit_sheet}.md"
            out.write_text(text)
            withheld = sum(1 for row in drawn if row["source"] in licensed)
            print(f"{out}: {len(drawn)} items, {withheld} withheld but linked")
            return 0

        # Before anything that fetches or renders: this reads counts and
        # rewrites four rows of one markdown file.
        if args.write_status:
            from . import status
            changed = status.write(conn, watchlist, status.count_tests())
            print(f"STATUS: {', '.join(changed)} updated" if changed
                  else "STATUS: already current")
            return 0
        # Before anything that could open a session: the quarterly report is a
        # lens on stored rows, so it must never fetch.
        if args.import_manual:
            written = manual.import_exports(conn, watchlist)
            print(f"manual: {written} observations")
            for week in weeks_to_render(conn):
                _score_and_render(conn, week, watchlist,
                                  scoring_sources(conn, week, collectors), 0, collectors)
            return 0
        period = args.annual or args.quarter
        if period:
            try:
                path = quarter.render_quarter(conn, period, watchlist)
            except quarter.PeriodNotStarted as error:
                # A message, not a traceback. Asking for next quarter's report
                # is an ordinary mistake, and the answer is a sentence.
                print(f"refusing: {error}", file=sys.stderr)
                return 1
            print(f"{period}: {path}")
            return 0
        if args.backfill is not None:
            session = http.make_session()
            backfill(conn, args.backfill, collectors, session)
            rebuild(conn, watchlist, collectors)
            return 0
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
