"""Evidence pages, quarterly.

They followed the weekly dashboard, which is now a collection health view: a
week is too small a window to interpret and the analytical blocks moved to the
quarterly report, so the evidence behind them moved with them.

The listing also changes shape. Every active technology got a section whether
or not it had documents, which put a wall of empty headings between the reader
and the evidence. On 2026-Q3 that was 9 technologies with documents and 42
sections.
"""

import pytest

from observatory import quarter, store


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def test_only_technologies_with_documents_get_a_section(conn):
    _observe(conn, "a", "2026-08-04")
    context = quarter.evidence_context(conn, "2026-Q3", _watchlist())
    assert [group["tech_id"] for group in context["groups"]] == ["a"]


def test_the_technologies_with_nothing_are_named_at_the_bottom(conn):
    """Named rather than dropped. A technology the system looked for and did
    not find is a finding; leaving it out entirely would hide that it was
    looked for at all."""
    _observe(conn, "a", "2026-08-04")
    context = quarter.evidence_context(conn, "2026-Q3", _watchlist())
    assert [t["tech_id"] for t in context["empty"]] == ["b"]


def test_a_section_still_exists_for_every_technology_that_is_linked(conn):
    """The report links a technology from several blocks, and a link into a
    missing anchor is a dead link. An empty technology keeps its anchor in the
    list at the bottom."""
    _observe(conn, "a", "2026-08-04")
    context = quarter.evidence_context(conn, "2026-Q3", _watchlist())
    anchors = {group["tech_id"] for group in context["groups"]}
    anchors |= {t["tech_id"] for t in context["empty"]}
    assert anchors == {"a", "b"}


def test_sections_are_ordered_by_how_much_evidence_they_carry(conn):
    for day in ("04", "11", "18"):
        _observe(conn, "b", f"2026-08-{day}")
    _observe(conn, "a", "2026-08-04")
    context = quarter.evidence_context(conn, "2026-Q3", _watchlist())
    assert [group["tech_id"] for group in context["groups"]] == ["b", "a"]


def test_documents_are_selected_by_their_own_date(conn):
    """Dated in a finished quarter, so the assertion is about the quarter
    boundary rather than about today. The dates were 2026-09-30 and
    2026-10-02, both of which are now ahead of the clock, and a report counts
    what has happened."""
    _observe(conn, "a", "2025-09-30")
    _observe(conn, "a", "2025-10-02")
    context = quarter.evidence_context(conn, "2025-Q3", _watchlist())
    assert len(context["groups"][0]["rows"]) == 1


def _observe(conn, tech_id, date):
    from observatory.matcher import Observation
    store.upsert_observations(conn, [Observation(
        source="arxiv", week="2026-W32", tech_id=tech_id, doc_id=f"{tech_id}:{date}",
        doc_date=date, title=f"paper {date}", url="", entity=None, entity_id=None,
        amount=None, lat=None, lon=None, matched_pattern="x", raw_ref=None)])


def _watchlist():
    from observatory.matcher import Technology, Watchlist
    def tech(tech_id):
        return Technology(id=tech_id, name=tech_id.upper(), family="f",
                          include=("x",), exclude=(), status="active",
                          added_week="2020-W01", patterns_changed_week="2020-W01")
    return Watchlist(version=1, context=("x",), technologies=(tech("a"), tech("b")))
