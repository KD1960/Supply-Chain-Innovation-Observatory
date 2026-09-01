"""A report about a period that has not happened.

Risk 4 of the process review. Scopus issue dates run ahead of publication --
`PUBYEAR = 2026` returns records dated to December -- so the store holds 62
observations dated after today and 2,911 corpus documents in weeks that have
not occurred. `quarter.build_context(conn, "2026-Q4", watchlist)` therefore
returned twelve technologies for a quarter that has not begun, every one at
100% research concentration because Scopus is the only source that can see the
future, and `output/` held dashboards for 2026-W40, W44 and W49.

Two separate fixes, because they are two separate errors. A period that has not
begun should not render at all. A period that is running should count what has
happened in it and not what is dated ahead of it -- the annual report's total
included those 62 rows.

The document's own date still decides its period; that rule is untouched. A
December paper belongs to Q4. It just cannot be counted before December.
"""

import datetime as dt

import pytest

from observatory import quarter, store
from observatory.matcher import Observation, Technology, Watchlist


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def _watchlist():
    return Watchlist(version=1, context=("supply chain",), technologies=(Technology(
        id="a", name="A", family="f", include=("widget",), exclude=(),
        status="active", added_week="2020-W01", patterns_changed_week="2020-W01"),))


def _observe(conn, date, doc_id):
    store.upsert_observations(conn, [Observation(
        source="scopus", week="2026-W20", tech_id="a", doc_id=doc_id,
        doc_date=date, title="widget", url="u", entity=None, entity_id=None,
        amount=None, lat=None, lon=None, matched_pattern="widget", raw_ref=None)])


def _next_quarter():
    today = dt.date.today()
    return f"{today.year + 1}-Q1"


# --- a period that has not begun --------------------------------------------


def test_a_period_that_has_not_begun_is_refused(conn):
    with pytest.raises(quarter.PeriodNotStarted):
        quarter.build_context(conn, _next_quarter(), _watchlist())


def test_rendering_one_is_refused_too(conn, tmp_path):
    with pytest.raises(quarter.PeriodNotStarted):
        quarter.render_quarter(conn, _next_quarter(), _watchlist(), tmp_path)


def test_the_current_period_still_renders(conn, tmp_path):
    """The guard is about periods that have not started, not about unfinished
    ones. A running quarter reports its counts and withholds its scores, which
    is a different mechanism and has to keep working."""
    today = dt.date.today()
    name = f"{today.year}-Q{(today.month - 1) // 3 + 1}"
    assert quarter.render_quarter(conn, name, _watchlist(), tmp_path).exists()


# --- documents dated ahead of today -----------------------------------------


def test_a_period_counts_what_has_happened_in_it(conn):
    """The annual total carried 62 rows from a quarter that had not begun."""
    today = dt.date.today()
    name = str(today.year)
    _observe(conn, today.isoformat(), "now")
    _observe(conn, f"{today.year}-12-31", "ahead")

    context = quarter.build_context(conn, name, _watchlist())
    assert context["documents"] == 1, "a document dated ahead of today was counted"


def test_counting_bounds_stop_at_today_but_period_bounds_do_not(conn):
    """`period_bounds` is what the export sheet asks a human for, and it must
    keep naming the whole period; clamping it would ask for a short window. Only
    the counting is clamped."""
    today = dt.date.today()
    name = str(today.year)
    assert quarter.period_bounds(name) == (f"{today.year}-01-01", f"{today.year}-12-31")
    assert quarter.counting_bounds(name) == (f"{today.year}-01-01", today.isoformat())


def test_a_finished_period_is_not_clamped(conn):
    """Yesterday's quarters count their whole selves."""
    assert quarter.counting_bounds("2025-Q4") == quarter.period_bounds("2025-Q4")


# --- weekly pages for weeks that have not happened ---------------------------


def test_a_future_week_is_never_queued_for_rendering(conn, monkeypatch):
    """The three that existed -- 2026-W40, W44 and W49 -- came from Scopus
    issue dates running months ahead of publication. `--import-manual`
    re-rendered every week holding an observation, so pages appeared for weeks
    that had not occurred, and because the loop runs ascending the last one
    drawn took `latest.html`."""
    from observatory import config, run

    monkeypatch.setattr(config, "current_week", lambda: "2026-W36")
    _observe(conn, "2026-05-13", "now")      # 2026-W20, in the past
    _observe(conn, "2026-12-01", "ahead")    # 2026-W49, not yet

    queued = run.weeks_to_render(conn)
    assert queued == ["2026-W20"], queued
