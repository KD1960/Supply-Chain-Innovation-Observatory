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


def observe(conn, tech_id, week, source, doc_id, entity_id=None, doc_date=None):
    """Dated from its week unless a date is given.

    Reports select by the document's own date now, so an undated observation is
    in no period at all -- which is correct behaviour and useless test data.
    """
    if doc_date is None:
        import datetime as dt

        from observatory import config
        # Mid-week. A week straddling a quarter boundary now falls in whichever
        # quarter holds the day, and Monday would put 2026-W14 in March -- true,
        # but it makes the fixture about the boundary rather than about what the
        # test is checking. A test that cares about the boundary states a date.
        doc_date = (config.week_bounds(week)[0] + dt.timedelta(days=3)).isoformat()
    store.upsert_observations(conn, [Observation(
        source=source, week=week, tech_id=tech_id, doc_id=doc_id, doc_date=doc_date,
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


def test_a_concentrated_technology_is_labelled_rather_than_silenced(conn):
    """Reversed on the owner's ruling, 2026-08-30. If 88% of a technology's
    documents are research, that is an indicator it sits at the research stage,
    not a defect. Withholding the movement deleted the finding along with the
    risk; the concentration column carries the caution instead."""
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    concentrated = [row for row in context["rows"] if row["single_source"]]
    assert concentrated
    for row in concentrated:
        assert row["shift"] is not None
        assert row["stage"], "the dominant family has to name a stage instead"


def test_counts_survive_the_gate(conn):
    """Document counts are observations, not inferences. Suppressing them would
    hide that the evidence exists at all."""
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    gated = [row for row in context["rows"] if row["single_source"]]
    assert gated
    assert all(row["total"] > 0 for row in gated)


def test_a_concentrated_technology_is_not_kept_off_the_movers_list(conn):
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    listed = {row["id"] for row in context["risers"] + context["fallers"]}
    concentrated = {row["id"] for row in context["rows"] if row["single_source"]}
    assert listed & concentrated


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







# --- Where the money went ---------------------------------------------------
#
# A table, not a map. The map drew dots on a blank rectangle with no coastline
# -- its own docstring said so -- and a scatter with nothing under it is not a
# map. The places, the dollars and the awards behind them are what the block
# was ever for.







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


# --- rates instead of a percentile index ------------------------------------
#
# The percentile index reported vehicle routing at 93 when it appears in 0.52%
# of supply chain research. Worse, a percentile cannot move: if every
# technology doubles, every percentile stays where it was, which is fatal for a
# tool whose purpose is detecting movement.
#
# A rate is matched over retrieved, so 100 means every document in that
# family's supply chain corpus mentioned the technology. Nothing is near it,
# and that is the true magnitude rather than a defect of the scale.


def test_a_rate_is_matched_over_retrieved():
    rates = quarter.family_rates({"by_family": {"patents": 27}}, {"patents": 185})
    assert round(rates["patents"], 2) == 14.59


def test_a_rate_of_one_hundred_means_every_document():
    rates = quarter.family_rates({"by_family": {"trade": 30}}, {"trade": 30})
    assert rates["trade"] == 100.0


def test_a_family_that_retrieved_nothing_yields_no_rate():
    """Dividing by a corpus nobody collected would invent a number."""
    assert quarter.family_rates({"by_family": {"trade": 3}}, {"trade": 0}) == {}


def test_rates_cover_only_families_the_technology_appears_in():
    rates = quarter.family_rates({"by_family": {"code": 5, "patents": 0}},
                                 {"code": 100, "patents": 185})
    assert set(rates) == {"code"}


# --- concentration labels a stage rather than withholding it ----------------
#
# The owner's ruling: if 88% of freight decarbonisation's documents are
# research, that is an indicator the technology is at that stage, not a defect.
# Suppressing it deleted exactly the finding the project exists to detect.


def test_a_concentrated_technology_keeps_its_movement(conn):
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    solo = next(r for r in context["rows"] if r["id"] == "solo")
    assert solo["families"] == 1
    assert solo["shift"] is not None, "concentration is a finding, not a reason to withhold"


def test_a_concentrated_technology_reaches_the_movers_list(conn):
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    listed = {row["id"] for row in context["risers"] + context["fallers"]}
    assert "solo" in listed


def test_the_dominant_family_names_a_stage(conn):
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    solo = next(r for r in context["rows"] if r["id"] == "solo")
    assert solo["top_family"] == "code"
    assert solo["stage"] == "experiment"


def test_every_family_maps_to_a_stage():
    for family in set(quarter.EVIDENCE_FAMILIES.values()):
        assert family in quarter.FAMILY_STAGE, family


# --- calendar periods -------------------------------------------------------
#
# ISO weeks and calendar quarters do not line up. 2026-Q1 ran from December
# 29th 2025, 2026-Q3 ended September 27th, and the ISO year stopped on December
# 27th -- so the last four days of every year fell out of the annual report.
# The owner asked for a calendar-year schedule, which the data supports exactly:
# every observation carries its own date.


def test_a_quarter_covers_its_calendar_dates():
    assert quarter.period_bounds("2026-Q1") == ("2026-01-01", "2026-03-31")
    assert quarter.period_bounds("2026-Q3") == ("2026-07-01", "2026-09-30")
    assert quarter.period_bounds("2026-Q4") == ("2026-10-01", "2026-12-31")


def test_a_year_covers_all_of_it_including_the_end_of_december():
    """The ISO year ended on the 27th. Four days of every December were in no
    report at all."""
    assert quarter.period_bounds("2026") == ("2026-01-01", "2026-12-31")


def test_a_leap_year_february_is_handled():
    assert quarter.period_bounds("2028-Q1") == ("2028-01-01", "2028-03-31")


def test_the_previous_period_is_still_the_one_before():
    assert quarter.previous_period("2026-Q1") == "2025-Q4"
    assert quarter.previous_period("2026") == "2025"


def test_totals_select_documents_by_their_own_date(conn):
    """A document dated September 30th belongs to Q3 even though its ISO week
    runs into October."""
    _dated(conn, "a", "2026-W40", "2026-09-30", "in Q3")
    _dated(conn, "a", "2026-W40", "2026-10-02", "in Q4")
    assert quarter.totals(conn, "2026-Q3")["a"]["total"] == 1
    assert quarter.totals(conn, "2026-Q4")["a"]["total"] == 1


def _dated(conn, tech_id, week, doc_date, doc_id):
    conn.execute(
        "INSERT INTO observations (source, week, tech_id, doc_id, doc_date, title, "
        "url, entity, entity_id, amount, lat, lon, matched_pattern, raw_ref) VALUES "
        "('arxiv', ?, ?, ?, ?, ?, '', NULL, NULL, NULL, NULL, NULL, 'x', NULL)",
        (week, tech_id, doc_id, doc_date, doc_id))
    conn.commit()


def test_research_funding_is_its_own_family():
    """NSF funds ideas; USAspending here funds ports and rail corridors being
    built. Both are federal dollars and they sit at different stages, so
    counting them as one number would swamp the infrastructure signal under a
    corpus five times its size -- 184 documents against roughly a thousand."""
    assert quarter.EVIDENCE_FAMILIES["nsf"] == "research funding"
    assert quarter.EVIDENCE_FAMILIES["usaspending"] == "money"
    assert quarter.FAMILY_STAGE["research funding"] == "idea"
    assert quarter.FAMILY_STAGE["money"] == "investment"


def test_research_funding_is_not_folded_into_research():
    """An NSF award is money committed, not a paper published. Folding it in
    with arXiv and Scopus would count the funding of an idea and the publishing
    of one as the same evidence."""
    assert quarter.EVIDENCE_FAMILIES["nsf"] != quarter.EVIDENCE_FAMILIES["arxiv"]


# --- the report's blocks ----------------------------------------------------

def test_the_stage_board_is_limited_so_its_labels_stay_readable(conn):
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    assert len(context["stage_points"]) <= quarter.BOARD_LIMIT


def test_the_stage_board_keeps_the_technologies_with_the_most_evidence(conn):
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    if context["stage_points"]:
        names = [p.label for p in context["stage_points"]]
        assert any("solo" in n or "broad" in n for n in names)




def test_the_appendix_describes_every_tracked_technology(conn):
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    listed = {row["id"] for row in context["appendix_technologies"]}
    assert listed == {tech.id for tech in watchlist.active}
    for row in context["appendix_technologies"]:
        assert row["description"], f"{row['id']} has no description"


def test_the_appendix_maps_every_stage_to_its_sources(conn):
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    stages = {row["stage"] for row in context["appendix_stages"]}
    assert stages == {"idea", "experiment", "investment", "deployment", "diffusion"}
    for row in context["appendix_stages"]:
        assert row["sources"], f"{row['stage']} lists no sources"


def test_the_summary_is_a_list_of_points(conn):
    """Prose in a summary is read as prose -- start to finish or not at all.
    Bullets can be scanned, which is what a summary is for."""
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    assert isinstance(context["summary"], list)
    assert all(isinstance(point, str) and point for point in context["summary"])
    assert 4 <= len(context["summary"]) <= 10


def test_the_summary_still_names_the_quarter_and_its_size(conn):
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    joined = " ".join(context["summary"])
    assert "2026-Q2" in joined
    assert str(context["documents"]) in joined


def test_locations_are_a_table_rather_than_a_map(conn):
    """The map drew dots on a blank rectangle with no coastline. A scatter with
    no map under it is not a map, and a table of places says the same thing
    without pretending to be cartography."""
    _locate(conn, "solo", "2026-W20", 33.4, -112.0, 5_000_000, "Phoenix port work")
    _locate(conn, "solo", "2026-W21", 33.4, -112.0, 1_000_000, "Second Arizona award")
    _locate(conn, "solo", "2026-W22", 47.6, -122.3, 2_000_000, "Seattle award")
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    assert "build_map" not in context
    places = {row["state"]: row for row in context["locations"]}
    assert places["AZ"]["awards"] == 2
    assert places["AZ"]["dollars"] == 6_000_000
    assert places["WA"]["awards"] == 1


def test_locations_are_ordered_by_money(conn):
    _locate(conn, "solo", "2026-W20", 33.4, -112.0, 1_000_000, "small")
    _locate(conn, "solo", "2026-W21", 47.6, -122.3, 9_000_000, "large")
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    assert [row["state"] for row in context["locations"]] == ["WA", "AZ"]


def test_each_location_carries_its_evidence(conn):
    _locate(conn, "solo", "2026-W20", 33.4, -112.0, 5_000_000, "Phoenix port work")
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    row = context["locations"][0]
    assert "Phoenix port work" in [award["title"] for award in row["awards_list"]]


def test_no_locations_means_no_block(conn):
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    assert context["locations"] == []


def test_a_chart_says_how_many_labels_would_not_fit(conn):
    """Silent thinning is this project's oldest failure mode. A chart missing
    three of its labels looks exactly like a chart that has them all."""
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    assert "labels_dropped" in context
    assert isinstance(context["labels_dropped"], dict)


def test_the_charts_carry_a_legend_keyed_to_their_numbers(conn):
    """A number on a dot is meaningless without the key, and the key is what
    lets the chart be read on paper as well as on the page."""
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    legend = context["stage_legend"]
    assert legend
    assert [row["n"] for row in legend] == list(range(1, len(legend) + 1))
    for row in legend:
        assert row["name"] and row["documents"] is not None


def test_the_legend_matches_the_points_it_keys(conn):
    watchlist = _seed_two_quarters(conn)
    context = quarter.build_context(conn, "2026-Q2", watchlist)
    assert len(context["stage_legend"]) == len(context["stage_points"])
    assert [row["name"] for row in context["stage_legend"]] == \
challenge if False else [point.label.split(" — ")[0] for point in context["stage_points"]]
