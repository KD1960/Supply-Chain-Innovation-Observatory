import collections

import pytest

from observatory import quarter, store
from observatory.matcher import Observation, Technology, Watchlist


def tech(tech_id, name=None, family="f"):
    return Technology(
        id=tech_id, name=name or tech_id, family=family, include=("x",), exclude=(),
        status="active", added_week="2020-W01", patterns_changed_week="2020-W01",
    )


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def observe(conn, tech_id, week, source, doc_id, entity_id=None):
    store.upsert_observations(conn, [Observation(
        source=source, week=week, tech_id=tech_id, doc_id=doc_id, doc_date=None,
        title=doc_id, url=f"https://example.test/{doc_id}", entity=None,
        entity_id=entity_id, amount=None, lat=None, lon=None,
        matched_pattern="x", raw_ref=None,
    )])


def test_quarter_of_maps_a_week_to_its_calendar_quarter():
    assert quarter.quarter_of("2026-W01") == "2026-Q1"
    assert quarter.quarter_of("2026-W13") == "2026-Q1"
    assert quarter.quarter_of("2026-W14") == "2026-Q2"
    assert quarter.quarter_of("2026-W52") == "2026-Q4"


def test_a_fifty_third_week_belongs_to_the_fourth_quarter():
    """A long ISO year has 53 weeks. W53 must not fall off the end into Q5."""
    assert quarter.quarter_of("2020-W53") == "2020-Q4"


def test_weeks_in_quarter_returns_thirteen_weeks_oldest_first():
    weeks = quarter.weeks_in_quarter("2026-Q2")
    assert weeks[0] == "2026-W14"
    assert weeks[-1] == "2026-W26"
    assert len(weeks) == 13


def test_previous_quarter_crosses_the_year_boundary():
    assert quarter.previous_quarter("2026-Q1") == "2025-Q4"
    assert quarter.previous_quarter("2026-Q3") == "2026-Q2"


def test_totals_count_documents_per_technology_in_the_quarter(conn):
    observe(conn, "a", "2026-W14", "arxiv", "d1")
    observe(conn, "a", "2026-W20", "arxiv", "d2")
    observe(conn, "b", "2026-W15", "github", "d3")
    totals = quarter.totals(conn, "2026-Q2")
    assert totals["a"]["total"] == 2
    assert totals["b"]["total"] == 1


def test_totals_exclude_weeks_outside_the_quarter(conn):
    observe(conn, "a", "2026-W13", "arxiv", "before")
    observe(conn, "a", "2026-W14", "arxiv", "inside")
    observe(conn, "a", "2026-W27", "arxiv", "after")
    assert quarter.totals(conn, "2026-Q2")["a"]["total"] == 1


def test_totals_break_the_count_down_by_source(conn):
    observe(conn, "a", "2026-W14", "arxiv", "d1")
    observe(conn, "a", "2026-W15", "github", "d2")
    observe(conn, "a", "2026-W16", "github", "d3")
    by_source = quarter.totals(conn, "2026-Q2")["a"]["by_source"]
    assert by_source["arxiv"] == 1
    assert by_source["github"] == 2


def test_adoption_counts_distinct_companies_not_filings(conn):
    observe(conn, "a", "2026-W14", "edgar", "f1", entity_id="0001")
    observe(conn, "a", "2026-W18", "edgar", "f2", entity_id="0001")
    observe(conn, "a", "2026-W20", "edgar", "f3", entity_id="0002")
    assert quarter.totals(conn, "2026-Q2")["a"]["filers"] == 2


def test_share_shift_compares_against_the_previous_quarter(conn):
    # Q1: a is 1 of 2 documents (50%). Q2: a is 3 of 4 (75%). Shift +25 points.
    observe(conn, "a", "2026-W02", "arxiv", "q1a")
    observe(conn, "b", "2026-W03", "arxiv", "q1b")
    for i, week in enumerate(["2026-W14", "2026-W15", "2026-W16"]):
        observe(conn, "a", week, "arxiv", f"q2a{i}")
    observe(conn, "b", "2026-W17", "arxiv", "q2b")
    rows = quarter.share_shift(conn, "2026-Q2")
    assert rows["a"] == pytest.approx(25.0)
    assert rows["b"] == pytest.approx(-25.0)


def test_share_shift_is_none_when_the_previous_quarter_is_empty(conn):
    """A technology cannot have moved against a quarter that was never observed."""
    observe(conn, "a", "2026-W14", "arxiv", "d1")
    assert quarter.share_shift(conn, "2026-Q2")["a"] is None


def test_build_context_names_the_silent_technologies(conn):
    watchlist = Watchlist(version=1, technologies=(tech("seen"), tech("silent")))
    observe(conn, "seen", "2026-W14", "arxiv", "d1")
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    assert [t["name"] for t in context["silent"]] == ["silent"]
    assert context["quarter"] == "2026-Q2"
    assert context["documents"] == 1


def test_render_writes_a_page_naming_the_quarter(conn, tmp_path):
    watchlist = Watchlist(version=1, technologies=(tech("a", name="Alpha tech"),))
    observe(conn, "a", "2026-W14", "arxiv", "d1")
    path = quarter.render_quarter(conn, "2026-Q2", watchlist, out_dir=tmp_path)
    html = path.read_text()
    assert path.name == "report-2026-Q2.html"
    assert "2026-Q2" in html
    assert "Alpha tech" in html


def test_a_quarter_with_every_week_run_is_not_partial(conn):
    for week in quarter.weeks_in_quarter("2026-Q2"):
        store.set_source_status(conn, "arxiv", week, "ok")
    observe(conn, "a", "2026-W14", "arxiv", "d1")
    context = quarter.build_context(conn, "2026-Q2", Watchlist(1, (tech("a"),)))
    assert context["weeks_run"] == 13
    assert context["partial"] is False


def test_a_quarter_missing_weeks_is_flagged_partial(conn):
    """2026-Q3 held eight weeks of data and looked like a collapse against Q2's
    thirteen. A quarter still in progress must say so on its own face."""
    for week in quarter.weeks_in_quarter("2026-Q3")[:8]:
        store.set_source_status(conn, "arxiv", week, "ok")
    observe(conn, "a", "2026-W27", "arxiv", "d1")
    context = quarter.build_context(conn, "2026-Q3", Watchlist(1, (tech("a"),)))
    assert context["weeks_run"] == 8
    assert context["partial"] is True


def test_a_partial_quarter_reports_no_share_shift(conn):
    """Eight weeks of share against thirteen is not a comparison, it is a
    shortfall wearing a percentage sign."""
    for week in quarter.weeks_in_quarter("2026-Q2"):
        store.set_source_status(conn, "arxiv", week, "ok")
    for week in quarter.weeks_in_quarter("2026-Q3")[:8]:
        store.set_source_status(conn, "arxiv", week, "ok")
    observe(conn, "a", "2026-W14", "arxiv", "q2a")
    observe(conn, "b", "2026-W15", "arxiv", "q2b")
    observe(conn, "a", "2026-W27", "arxiv", "q3a")
    context = quarter.build_context(conn, "2026-Q3", Watchlist(1, (tech("a"), tech("b"))))
    assert context["risers"] == []
    assert all(row["shift"] is None for row in context["rows"])


def test_the_partial_page_says_how_many_weeks_are_missing(conn, tmp_path):
    for week in quarter.weeks_in_quarter("2026-Q3")[:8]:
        store.set_source_status(conn, "arxiv", week, "ok")
    observe(conn, "a", "2026-W27", "arxiv", "d1")
    path = quarter.render_quarter(conn, "2026-Q3", Watchlist(1, (tech("a"),)), out_dir=tmp_path)
    assert "8 of 13" in path.read_text()


def test_weeks_in_period_accepts_a_bare_year():
    weeks = quarter.weeks_in_period("2025")
    assert weeks[0] == "2025-W01"
    assert weeks[-1] == "2025-W52"
    assert len(weeks) == 52


def test_a_long_iso_year_has_fifty_three_weeks():
    """2026 is a 53-week ISO year. Assuming 52 would silently drop its last
    week from the annual report -- the deliverable's own final week."""
    weeks = quarter.weeks_in_period("2026")
    assert weeks[-1] == "2026-W53"
    assert len(weeks) == 53


def test_weeks_in_period_still_accepts_a_quarter():
    assert quarter.weeks_in_period("2026-Q2") == quarter.weeks_in_quarter("2026-Q2")


def test_previous_period_of_a_year_is_the_year_before():
    assert quarter.previous_period("2026") == "2025"
    assert quarter.previous_period("2026-Q1") == "2025-Q4"


def test_totals_cover_the_whole_year(conn):
    observe(conn, "a", "2026-W02", "arxiv", "q1")
    observe(conn, "a", "2026-W20", "arxiv", "q2")
    observe(conn, "a", "2026-W40", "arxiv", "q4")
    observe(conn, "a", "2025-W40", "arxiv", "lastyear")
    assert quarter.totals(conn, "2026")["a"]["total"] == 3


def test_an_annual_report_is_partial_until_every_week_has_run(conn):
    for week in quarter.weeks_in_period("2026")[:40]:
        store.set_source_status(conn, "arxiv", week, "ok")
    observe(conn, "a", "2026-W02", "arxiv", "d1")
    context = quarter.build_context(conn, "2026", Watchlist(1, (tech("a"),)))
    assert context["weeks_total"] == 53
    assert context["weeks_run"] == 40
    assert context["partial"] is True


def test_render_writes_an_annual_report(conn, tmp_path):
    watchlist = Watchlist(version=1, technologies=(tech("a", name="Alpha tech"),))
    observe(conn, "a", "2026-W02", "arxiv", "d1")
    path = quarter.render_quarter(conn, "2026", watchlist, out_dir=tmp_path)
    assert path.name == "report-2026.html"
    assert "Alpha tech" in path.read_text()


def test_an_annual_page_calls_itself_annual(conn, tmp_path):
    observe(conn, "a", "2026-W02", "arxiv", "d1")
    html = quarter.render_quarter(conn, "2026", Watchlist(1, (tech("a"),)), out_dir=tmp_path).read_text()
    assert "annual report" in html.lower()
    assert "quarterly report" not in html.lower()


def test_a_quarterly_page_still_calls_itself_quarterly(conn, tmp_path):
    observe(conn, "a", "2026-W14", "arxiv", "d1")
    html = quarter.render_quarter(conn, "2026-Q2", Watchlist(1, (tech("a"),)), out_dir=tmp_path).read_text()
    assert "quarterly report" in html.lower()


def test_a_licensed_source_is_named_on_the_report(conn, tmp_path):
    """A reader without a subscription cannot follow a Scopus citation. That
    should be stated on the page, not discovered."""
    observe(conn, "a", "2026-W14", "scopus", "d1")
    observe(conn, "a", "2026-W15", "arxiv", "d2")
    context = quarter.build_context(conn, "2026-Q2", Watchlist(1, (tech("a"),)))
    assert context["licensed"] == ["scopus"]
    html = quarter.render_quarter(conn, "2026-Q2", Watchlist(1, (tech("a"),)), out_dir=tmp_path).read_text()
    assert "scopus" in html.lower()
    assert "subscription" in html.lower()


def test_a_report_from_public_sources_alone_says_nothing_about_licensing(conn, tmp_path):
    observe(conn, "a", "2026-W14", "arxiv", "d1")
    context = quarter.build_context(conn, "2026-Q2", Watchlist(1, (tech("a"),)))
    assert context["licensed"] == []
    html = quarter.render_quarter(conn, "2026-Q2", Watchlist(1, (tech("a"),)), out_dir=tmp_path).read_text()
    assert "subscription" not in html.lower()


# --- the source diversity gate ---------------------------------------------
#
# Measured on the real corpus before this was built: across 2026-Q1 and Q2,
# about half of all technologies drew 80% or more of their evidence from one
# source, those technologies held 63% of every document, and four of the five
# largest were among them. The two largest movers in both quarters -- ERP
# platforms and ML demand forecasting -- were 87-97% GitHub, where 78% of
# matched repositories have a single star and a 60-repo sample gained none in
# nine months. "ERP is rising fastest" was really "GitHub indexed more one-star
# ERP repositories".


def _row(counts, filers=0):
    return {"total": sum(counts.values()), "by_source": collections.Counter(counts),
            "filers": filers}


def _seed_two_quarters(conn):
    """Q1 and Q2 both populated, so share shifts exist to be withheld.

    `solo` is one source throughout; `broad` is spread across four. Both grow,
    so a gate that merely dropped small technologies would not pass these."""
    for quarter_weeks, span in (("2026-W0%d", range(1, 10)), ("2026-W%d", range(14, 27))):
        pass
    for n in range(1, 10):                      # Q1
        observe(conn, "solo", f"2026-W{n:02d}", "github", f"s-q1-{n}")
    for n in range(1, 9):
        observe(conn, "broad", f"2026-W{n:02d}",
                ("arxiv", "github", "edgar", "hn")[n % 4], f"b-q1-{n}")
    for n in range(14, 27):                     # Q2
        observe(conn, "solo", f"2026-W{n:02d}", "github", f"s-q2-{n}")
    for n in range(14, 26):
        observe(conn, "broad", f"2026-W{n:02d}",
                ("arxiv", "github", "edgar", "hn")[n % 4], f"b-q2-{n}")
    for week in quarter.weeks_in_quarter("2026-Q1") + quarter.weeks_in_quarter("2026-Q2"):
        conn.execute("INSERT OR IGNORE INTO source_runs (source, week, status) "
                     "VALUES ('arxiv', ?, 'ok')", (week,))
    conn.commit()
    return Watchlist(version=1, context=("x",), technologies=(tech("solo"), tech("broad")))


def test_a_technology_from_one_source_is_flagged():
    assert quarter.is_single_source(_row({"github": 100})) is True


def test_the_threshold_bites_at_eighty_percent():
    """80 is a judgement, not a derivation, so it is pinned by a test that
    fails if anybody moves it quietly."""
    assert quarter.is_single_source(_row({"github": 79, "arxiv": 21})) is False
    assert quarter.is_single_source(_row({"github": 80, "arxiv": 20})) is True


def test_two_sources_are_not_enough_if_one_dominates():
    assert quarter.is_single_source(_row({"github": 95, "arxiv": 5})) is True


def test_a_broadly_evidenced_technology_passes():
    assert quarter.is_single_source(_row({"github": 30, "arxiv": 30, "edgar": 25, "hn": 15})) is False


def test_a_technology_with_no_documents_is_not_scored_as_diverse():
    assert quarter.is_single_source(_row({})) is True


def test_share_shift_is_withheld_for_a_single_source_technology(conn):
    """The report's only inference is the share shift, so that is what the gate
    has to take away. A shift in a 97%-GitHub technology's share is a shift in
    GitHub's coverage wearing the technology's name."""
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    for row in context["rows"]:
        if row["single_source"]:
            assert row["shift"] is None, f"{row['id']} kept a shift it cannot support"


def test_counts_survive_the_gate(conn):
    """Document counts are observations, not inferences. Suppressing them would
    hide that the evidence exists at all."""
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    gated = [row for row in context["rows"] if row["single_source"]]
    assert gated
    assert all(row["total"] > 0 for row in gated)


def test_no_gated_technology_reaches_the_movers_list(conn):
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    listed = {row["id"] for row in context["risers"] + context["fallers"]}
    gated = {row["id"] for row in context["rows"] if row["single_source"]}
    assert not (listed & gated)


def test_the_report_says_how_many_it_gated(conn):
    """A threshold nobody can see is a threshold nobody can argue with."""
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    assert context["single_source_count"] == sum(
        1 for row in context["rows"] if row["single_source"]
    )
    assert context["single_source_documents"] == sum(
        row["total"] for row in context["rows"] if row["single_source"]
    )


# --- evidence families -----------------------------------------------------
#
# Counting source names overstates diversity when two sources measure the same
# thing. arXiv and Scopus are both research literature: a technology at 6 arXiv
# plus 5 Scopus papers would clear a two-source floor while resting entirely on
# academic interest. Measured on 2026-Q2 before this was built, five
# technologies would have cleared on a Scopus export alone -- freight
# decarbonisation, critical infrastructure security, electric heavy-duty trucks,
# warehouse robotics and humanoid logistics.


def test_arxiv_and_scopus_are_the_same_kind_of_evidence():
    assert quarter.family_of("arxiv") == quarter.family_of("scopus")


def test_code_patents_filings_and_trade_press_are_all_distinct():
    families = {quarter.family_of(s)
                for s in ("github", "lens", "edgar", "abi_inform", "federalregister")}
    assert len(families) == 5


def test_an_unregistered_source_gets_its_own_family():
    """A hand-made export under an unknown name must not be silently folded in
    with something else; that would invent corroboration."""
    assert quarter.family_of("some_new_export") == "some_new_export"
    assert quarter.family_of("some_new_export") != quarter.family_of("arxiv")


def test_two_research_sources_do_not_make_a_technology_diverse():
    assert quarter.is_single_source(_row({"arxiv": 6, "scopus": 5})) is True


def test_research_plus_patents_does_make_it_diverse():
    assert quarter.is_single_source(_row({"arxiv": 6, "lens": 5})) is False


def test_concentration_is_measured_across_families_not_sources():
    """Split across two research sources, the evidence is still 100% research."""
    assert quarter.is_single_source(_row({"arxiv": 50, "scopus": 45, "github": 5})) is True


def test_the_floor_is_one_until_the_new_sources_land():
    """Calibrating a threshold against a corpus about to triple is backwards.
    The mechanism ships now; the number is set once there is data to set it
    against."""
    assert quarter.FAMILY_FLOOR == 1


def test_a_source_below_the_floor_does_not_count_towards_diversity(monkeypatch):
    """Both cases sit under the 80% concentration rule, so only the floor can
    decide them -- otherwise this would pass without the floor existing."""
    monkeypatch.setattr(quarter, "FAMILY_FLOOR", 3)
    assert quarter.is_single_source(_row({"arxiv": 7, "github": 2})) is True
    assert quarter.is_single_source(_row({"arxiv": 7, "github": 3})) is False


def test_the_api_collectors_are_each_their_own_family():
    """Each of the six is a distinct kind of evidence, so introducing families
    changed no verdict on the corpus as it stood. The supplemental sources are
    what families exist for: arXiv and Scopus share one."""
    families = {quarter.family_of(s) for s in quarter.COLLECTORS}
    assert len(families) == len(quarter.COLLECTORS)
    assert quarter.family_of("scopus") == quarter.family_of("arxiv")


def test_the_report_states_the_floor_and_the_family_requirement(conn):
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    assert context["family_floor"] == quarter.FAMILY_FLOOR
    assert context["single_source_share"] == quarter.SINGLE_SOURCE_SHARE


def test_rows_report_how_many_families_back_them(conn):
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    solo = next(r for r in context["rows"] if r["id"] == "solo")
    broad = next(r for r in context["rows"] if r["id"] == "broad")
    assert solo["families"] == 1
    assert broad["families"] >= 2


# --- showing every source ---------------------------------------------------
#
# SOURCES was a hardcoded six-tuple written before any human-supplied export
# existed. After Scopus and Lens landed, a technology with 26 observations
# rendered its evidence breakdown as "[]" and one with 89 showed a breakdown
# summing to 18. The totals and the gate were right; the table was not.


def test_the_source_list_covers_every_registered_supplemental_source():
    from observatory import supplemental
    for source_id in supplemental.load().sources:
        assert source_id in quarter.SOURCES, f"{source_id} would vanish from the table"


def test_the_source_list_still_covers_the_api_collectors():
    for source_id in ("arxiv", "github", "hn", "edgar", "federalregister", "usaspending"):
        assert source_id in quarter.SOURCES


def test_a_rows_breakdown_accounts_for_every_document(conn):
    """The breakdown is the evidence for the total. If they disagree, one of
    them is wrong and the reader cannot tell which."""
    observe(conn, "a", "2026-W14", "arxiv", "d1")
    observe(conn, "a", "2026-W15", "scopus", "d2")
    observe(conn, "a", "2026-W16", "lens", "d3")
    for week in quarter.weeks_in_quarter("2026-Q2"):
        conn.execute("INSERT OR IGNORE INTO source_runs (source, week, status) "
                     "VALUES ('arxiv', ?, 'ok')", (week,))
    watchlist = Watchlist(version=1, context=("x",), technologies=(tech("a"),))
    row = quarter.build_context(conn, "2026-Q2", watchlist)["rows"][0]
    assert sum(row["by_source"].values()) == row["total"]


def test_rows_carry_a_family_breakdown_for_display(conn):
    """Eight source columns will not fit a table. Families are the unit the
    gate already uses, and there are fewer of them."""
    observe(conn, "a", "2026-W14", "arxiv", "d1")
    observe(conn, "a", "2026-W15", "scopus", "d2")
    observe(conn, "a", "2026-W16", "lens", "d3")
    for week in quarter.weeks_in_quarter("2026-Q2"):
        conn.execute("INSERT OR IGNORE INTO source_runs (source, week, status) "
                     "VALUES ('arxiv', ?, 'ok')", (week,))
    watchlist = Watchlist(version=1, context=("x",), technologies=(tech("a"),))
    row = quarter.build_context(conn, "2026-Q2", watchlist)["rows"][0]
    assert row["by_family"]["research"] == 2      # arxiv and scopus together
    assert row["by_family"]["patents"] == 1
    assert sum(row["by_family"].values()) == row["total"]


def test_the_concentration_shown_is_the_one_the_gate_used(conn):
    """Vehicle routing rendered "48% arxiv" beside a GATED mark, because the
    number came from the top source while the verdict came from the family --
    arXiv and Scopus together were 97% of its evidence. A reader cannot
    reconcile those, and would conclude the gate was wrong."""
    for n in range(1, 8):
        observe(conn, "a", f"2026-W1{n}", "arxiv", f"x{n}")
    for n in range(1, 10):
        observe(conn, "a", f"2026-W2{n%6}", "scopus", f"s{n}")
    observe(conn, "a", "2026-W14", "github", "g1")
    for week in quarter.weeks_in_quarter("2026-Q2"):
        conn.execute("INSERT OR IGNORE INTO source_runs (source, week, status) "
                     "VALUES ('arxiv', ?, 'ok')", (week,))
    watchlist = Watchlist(version=1, context=("x",), technologies=(tech("a"),))
    row = quarter.build_context(conn, "2026-Q2", watchlist)["rows"][0]
    assert row["top_family"] == "research"
    assert row["concentration"] == round(100 * row["by_family"]["research"] / row["total"])
    assert row["single_source"] is (row["concentration"] >= 80)


# --- the 0-100 index --------------------------------------------------------
#
# Counts are not comparable across sources: GitHub retrieved 30,459 documents
# in 2026-Q3 against Hacker News's 2,304. The index expresses a technology's
# standing *within each family* and averages those, weighted by how much
# evidence each family actually supplied.
#
# It is computed only for technologies that pass the diversity gate. A naive
# version scored rail intermodal technology 90 on one document, because one
# document is a high percentile inside a family that holds six.


def test_the_index_runs_from_zero_to_one_hundred(conn):
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    for row in context["rows"]:
        if row["index"] is not None:
            assert 0 <= row["index"] <= 100


def test_a_gated_technology_has_no_index(conn):
    """The index is an inference. The gate withholds inferences, and it is what
    keeps a one-document technology out of the top of the ranking."""
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    for row in context["rows"]:
        if row["single_source"]:
            assert row["index"] is None


def test_more_evidence_in_a_family_pulls_the_index_towards_that_family():
    """Volume weighting: a family that supplied 27 documents should count for
    more than one that supplied 1. Breadth-equal weighting says three
    documents across three families is worth thirty across three, which is more
    confidence than the evidence carries."""
    scale = {"code": {0: 0.0, 1: 50.0, 27: 100.0},
             "patents": {0: 0.0, 1: 10.0, 27: 20.0}}
    heavy = quarter.index_for({"by_family": {"code": 27, "patents": 1}}, scale)
    light = quarter.index_for({"by_family": {"code": 1, "patents": 27}}, scale)
    assert heavy > light


def test_the_index_is_none_when_no_family_supplied_anything():
    assert quarter.index_for({"by_family": {}}, {}) is None


def test_percentiles_are_computed_within_a_family_not_across_all():
    """Six Federal Register documents and eight hundred GitHub ones are not the
    same scale, which is the whole reason this exists."""
    rows = [{"by_family": {"code": 800, "regulation": 1}},
            {"by_family": {"code": 1, "regulation": 6}}]
    scale = quarter.family_scale(rows)
    assert scale["regulation"][6] > scale["regulation"][1]
    assert scale["code"][800] > scale["code"][1]


# --- Build Map --------------------------------------------------------------
#
# In the design spec since the beginning and never plotted a point, because
# USAspending returned nothing usable for a year. It has 33 geocoded awards
# now, which is the whole reason that collector was fixed.


def test_the_build_map_takes_its_points_from_located_observations(conn):
    _locate(conn, "a", "2026-W14", 33.4, -112.0, 5_000_000, "Phoenix award")
    _locate(conn, "a", "2026-W15", 47.6, -122.3, 1_000_000, "Seattle award")
    points = quarter.map_points(conn, "2026-Q2")
    assert len(points) == 2
    assert {round(p.y, 1) for p in points} == {33.4, 47.6}


def test_a_bigger_award_gets_a_bigger_dot(conn):
    _locate(conn, "a", "2026-W14", 33.4, -112.0, 100_000_000, "large")
    _locate(conn, "a", "2026-W15", 47.6, -122.3, 100_000, "small")
    points = {p.label.split(" ")[0]: p for p in quarter.map_points(conn, "2026-Q2")}
    assert points["large"].size > points["small"].size


def test_an_award_with_no_amount_still_gets_a_dot(conn):
    """A grant whose dollars were not reported is still a place where capacity
    is being built. Dropping it would silently shrink the map."""
    _locate(conn, "a", "2026-W14", 33.4, -112.0, None, "unpriced")
    assert len(quarter.map_points(conn, "2026-Q2")) == 1


def test_observations_outside_the_period_are_not_plotted(conn):
    _locate(conn, "a", "2026-W02", 33.4, -112.0, 1000, "last quarter")
    assert quarter.map_points(conn, "2026-Q2") == []


def test_the_map_label_names_the_technology_and_the_money(conn):
    _locate(conn, "a", "2026-W14", 33.4, -112.0, 2_500_000, "Port project")
    label = quarter.map_points(conn, "2026-Q2")[0].label
    assert "Port project" in label and "2.5" in label


# --- Substance vs Attention -------------------------------------------------


def test_substance_counts_building_and_attention_counts_talking():
    row = {"by_family": {"code": 4, "patents": 3, "filings": 2, "money": 1,
                         "regulation": 1, "community": 5, "trade": 2,
                         "research": 9}}
    assert quarter.substance(row) == 11
    assert quarter.attention(row) == 7


def test_research_counts_as_neither():
    """A preprint is not a built thing and it is not hype. The weekly index
    leaves arXiv out of both halves for the same reason, and folding nine
    hundred research documents into either would drown the distinction."""
    assert quarter.substance({"by_family": {"research": 900}}) == 0
    assert quarter.attention({"by_family": {"research": 900}}) == 0


def test_a_technology_with_no_evidence_either_way_is_left_off_the_chart(conn):
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    for row in context["substance_rows"]:
        assert quarter.substance(row) or quarter.attention(row)


def _locate(conn, tech_id, week, lat, lon, amount, title):
    conn.execute(
        "INSERT INTO observations (source, week, tech_id, doc_id, doc_date, title, "
        "url, entity, entity_id, amount, lat, lon, matched_pattern, raw_ref) VALUES "
        "('usaspending', ?, ?, ?, '2026-04-01', ?, '', NULL, NULL, ?, ?, ?, 'x', NULL)",
        (week, tech_id, f"d-{title}-{week}", title, amount, lat, lon))
    conn.commit()


def test_the_rendered_report_actually_contains_its_charts(tmp_path, conn):
    """The context held the SVG and the page did not: Jinja autoescapes, so the
    markup arrived as text. Checking the context is not checking the report."""
    _locate(conn, "a", "2026-W14", 33.4, -112.0, 5_000_000, "Phoenix award")
    watchlist = _seed_two_quarters(conn)
    path = quarter.render_quarter(conn, "2026-Q2", watchlist, tmp_path)
    page = path.read_text()
    assert "<svg" in page
    assert "&lt;svg" not in page
