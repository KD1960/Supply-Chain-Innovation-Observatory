"""The denominator: how many documents each source retrieved, by their own date.

A rate is matched over retrieved. The numerator has always been dated by the
document itself; the denominator was counted by which week's directory the raw
file sat in, which is a different thing. ISO weeks and calendar quarters do not
line up -- 2026-Q4 ran to December 27th and the last four days of the year fell
out of the annual report entirely.

Counting retrieved documents by their own date makes both halves of the rate
agree, and makes a calendar period exact rather than approximate.
"""

import pytest

from observatory import store


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def test_a_documents_own_date_decides_which_period_it_counts_in(conn):
    store.record_corpus(conn, "arxiv", "2026-W39", [("2026-09-28", 3), ("2026-10-01", 5)])
    assert store.corpus_between(conn, "2026-09-01", "2026-09-30") == {"arxiv": 3}
    assert store.corpus_between(conn, "2026-10-01", "2026-12-31") == {"arxiv": 5}


def test_one_week_can_feed_two_quarters(conn):
    """The point of the change. A week straddling a quarter boundary belongs to
    both, in the proportion its documents actually fall."""
    store.record_corpus(conn, "arxiv", "2026-W40", [("2026-09-30", 2), ("2026-10-02", 8)])
    assert store.corpus_between(conn, "2026-07-01", "2026-09-30")["arxiv"] == 2
    assert store.corpus_between(conn, "2026-10-01", "2026-12-31")["arxiv"] == 8


def test_recording_a_week_again_replaces_it_rather_than_doubling(conn):
    """A rebuild replays every week. Adding would inflate the denominator by a
    factor of however many times the corpus had been rebuilt, which is a
    silently shrinking rate."""
    store.record_corpus(conn, "arxiv", "2026-W39", [("2026-09-28", 3)])
    store.record_corpus(conn, "arxiv", "2026-W39", [("2026-09-28", 3)])
    assert store.corpus_between(conn, "2026-09-01", "2026-09-30") == {"arxiv": 3}


def test_sources_are_counted_separately(conn):
    store.record_corpus(conn, "arxiv", "2026-W39", [("2026-09-28", 3)])
    store.record_corpus(conn, "github", "2026-W39", [("2026-09-28", 7)])
    assert store.corpus_between(conn, "2026-09-01", "2026-09-30") == {"arxiv": 3, "github": 7}


def test_a_period_with_nothing_retrieved_is_empty_not_missing(conn):
    assert store.corpus_between(conn, "2020-01-01", "2020-12-31") == {}


def test_an_undated_document_is_counted_but_not_placed(conn):
    """A document the parser could not date still exists. It is counted against
    the source so the total is honest, and excluded from every period so it
    cannot land in one it does not belong to."""
    store.record_corpus(conn, "arxiv", "2026-W39", [(None, 4), ("2026-09-28", 3)])
    assert store.corpus_between(conn, "2026-01-01", "2026-12-31") == {"arxiv": 3}
    assert store.corpus_undated(conn) == {"arxiv": 4}


def test_clearing_derived_tables_clears_the_corpus(conn):
    """It is derived from raw like everything else, and a stale denominator
    outlives the parser that produced it."""
    store.record_corpus(conn, "arxiv", "2026-W39", [("2026-09-28", 3)])
    store.clear_derived(conn)
    assert store.corpus_between(conn, "2026-01-01", "2026-12-31") == {}


# --- populated during ingest ------------------------------------------------

def test_ingesting_a_week_records_what_it_retrieved(conn, tmp_path, monkeypatch):
    """Every document the parser saw, matched or not. The denominator is the
    corpus, not the part of it that happened to match."""
    from observatory import config, matcher, run
    monkeypatch.setattr(config, "RAW_DIR", tmp_path)
    raw = tmp_path / "2026-W40" / "arxiv"
    raw.mkdir(parents=True)
    (raw / "000.xml").write_text(
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        '<entry><id>a</id><title>Warehouse robotics study</title>'
        '<summary>Autonomous mobile robots in a warehouse.</summary>'
        '<published>2026-09-30T00:00:00Z</published></entry>'
        '<entry><id>b</id><title>Unrelated paper</title>'
        '<summary>Nothing to do with the domain.</summary>'
        '<published>2026-10-02T00:00:00Z</published></entry></feed>')
    from observatory.collectors.arxiv import ArxivCollector
    run.ingest_week(conn, "2026-W40", matcher.load_watchlist(), [ArxivCollector()], {"arxiv"})
    september = store.corpus_between(conn, "2026-07-01", "2026-09-30")
    october = store.corpus_between(conn, "2026-10-01", "2026-12-31")
    assert september.get("arxiv") == 1
    assert october.get("arxiv") == 1


def test_a_manual_source_holds_one_set_of_counts_not_one_per_run(conn):
    """The first version keyed manual corpus rows by the export date. Fixing it
    to a fixed key left the old rows in place, so lens read 370 against an
    export of 185 -- both keys summing. A source's manual corpus is one thing
    however the counting has changed underneath it."""
    store.record_corpus(conn, "lens", "2026-08-28", [("2026-07-01", 185)])
    store.record_corpus(conn, "lens", store.MANUAL_KEY, [("2026-07-01", 185)])
    store.forget_manual_corpus(conn, "lens")
    store.record_corpus(conn, "lens", store.MANUAL_KEY, [("2026-07-01", 185)])
    assert store.corpus_between(conn, "2026-01-01", "2026-12-31") == {"lens": 185}
