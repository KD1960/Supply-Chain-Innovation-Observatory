"""The human-fetched half of the corpus.

Nobody reads a document and decides whether it counts. A person pastes a query
into a database and exports the result; the matcher decides relevance. These
tests cover the part that makes that reproducible -- the query the person
pastes, generated from the same watchlist the pipeline scores against.
"""

import pytest

from observatory import quarter, supplemental


def test_the_registry_loads_every_declared_source():
    registry = supplemental.load()
    assert set(registry.sources) >= {"lens", "scopus", "abi_inform"}


def test_every_source_declares_a_known_evidence_family():
    """A source whose family is not in the gate's map would be counted as its
    own family, silently inventing corroboration."""
    for source_id, source in supplemental.load().sources.items():
        assert quarter.EVIDENCE_FAMILIES.get(source_id) == source.family, source_id


def test_lens_is_patents_and_scopus_is_research():
    registry = supplemental.load()
    assert registry.sources["lens"].family == "patents"
    assert registry.sources["scopus"].family == "research"


def test_a_query_carries_the_periods_own_dates():
    query = supplemental.build_query("lens", "2026-Q2", _watchlist())
    assert "2026-04-01" in query or "2026-03-30" in query
    assert "{start}" not in query and "{end}" not in query


def test_the_lens_query_names_the_classification_codes():
    """Filtering by CPC is the container filter for patents, the same move as
    ISSNs for journals. Fifty technology keyword searches is the thing it
    replaces."""
    query = supplemental.build_query("lens", "2026-Q2", _watchlist())
    assert "G06Q10/08" in query
    assert "B65G" in query


def test_the_scopus_query_names_issns_rather_than_journal_titles():
    """Titles are entered inconsistently and change; ISSNs do not."""
    query = supplemental.build_query("scopus", "2026-Q2", _watchlist())
    assert "ISSN" in query
    assert "0272-6963" in query


def test_the_trade_press_query_is_built_from_the_live_watchlist():
    """Publication alone yields thousands of stories a quarter, so this source
    carries a term filter -- and it must track the lexicon rather than drift out
    of step with it."""
    query = supplemental.build_query("abi_inform", "2026-Q2", _watchlist())
    assert '"warehouse robot"' in query.lower()


def test_changing_the_watchlist_changes_the_trade_press_query():
    before = supplemental.build_query("abi_inform", "2026-Q2", _watchlist())
    after = supplemental.build_query("abi_inform", "2026-Q2", _watchlist(extra="zeppelin freight"))
    assert before != after
    assert "zeppelin freight" in after


def test_a_query_referring_to_an_unknown_list_is_an_error_not_a_broken_string():
    """A half-substituted query pasted into a database returns something. That
    something is not what anybody asked for."""
    with pytest.raises(supplemental.RegistryProblem):
        supplemental.render("{nonexistent} AND x", {}, "2026-Q2")


def test_export_queries_returns_one_entry_per_source():
    entries = supplemental.export_queries("2026-Q2", _watchlist())
    assert {entry["source"] for entry in entries} == set(supplemental.load().sources)
    for entry in entries:
        assert entry["query"].strip()
        assert entry["format"] in ("ris", "csv")


def test_export_queries_states_the_period_each_query_covers():
    for entry in supplemental.export_queries("2026-Q2", _watchlist()):
        assert entry["period"] == "2026-Q2"
        assert entry["start"] == "2026-03-30"


def test_the_query_template_lives_in_config_not_code():
    """Lens's exact search syntax is unverified until somebody runs it. Fixing
    it must not require a code change."""
    text = (supplemental.REGISTRY_PATH).read_text()
    assert "date_published" in text or "{start}" in text


def _watchlist(extra=None):
    from observatory import matcher
    loaded = matcher.load_watchlist()
    if extra is None:
        return loaded
    technologies = loaded.technologies + (matcher.Technology(
        id="zeppelin", name="Zeppelin freight", family="vehicles",
        include=(extra,), exclude=(), status="active",
        added_week="2026-W35", patterns_changed_week="2026-W35",
    ),)
    return matcher.Watchlist(version=loaded.version, context=loaded.context,
                             technologies=technologies)


# --- the printed sheet -----------------------------------------------------

def test_the_sheet_shows_the_query_for_every_source(capsys):
    supplemental.print_queries("2026-Q2", _watchlist())
    printed = capsys.readouterr().out
    for source in supplemental.load().sources.values():
        assert source.name in printed
    assert "G06Q10/08" in printed


def test_the_sheet_records_what_the_sidecar_needs(capsys):
    """An export nobody can reproduce is not evidence. Everything the sidecar
    requires has to be on the sheet the person is looking at."""
    from observatory import manual
    supplemental.print_queries("2026-Q2", _watchlist())
    printed = capsys.readouterr().out.lower()
    for field in manual.REQUIRED_META:
        assert field in printed, f"sidecar needs {field} but the sheet never says so"


def test_the_sheet_names_where_the_export_goes(capsys):
    supplemental.print_queries("2026-Q2", _watchlist())
    assert "data/manual/2026-Q2" in capsys.readouterr().out


def test_the_sheet_says_the_lens_syntax_is_unverified(capsys):
    """Shipping an unverified query silently is how a wrong number gets a
    plausible provenance."""
    supplemental.print_queries("2026-Q2", _watchlist())
    printed = capsys.readouterr().out.lower()
    assert "unverified" in printed or "verify" in printed


def test_the_cli_flag_prints_the_sheet(capsys):
    from observatory import run
    run.main(["--export-queries", "2026-Q2"])
    assert "Lens.org" in capsys.readouterr().out


def test_the_cli_flag_rejects_a_period_that_is_not_one(capsys):
    from observatory import run
    with pytest.raises((SystemExit, ValueError, supplemental.RegistryProblem)):
        run.main(["--export-queries", "not-a-quarter"])


# --- turning patterns into phrases -----------------------------------------
#
# A watchlist pattern is a regex; a bibliographic database wants a phrase.
# Stripping the punctuation out of `warehouse robot(s|ics)?` yields
# "warehouse robot s ics", which is not a phrase, matches nothing, and looks
# entirely plausible sitting in a query string. The alternations have to be
# expanded, and the patterns that cannot be expanded have to be dropped rather
# than mangled.


def test_an_optional_alternation_expands_to_every_real_phrase():
    assert supplemental.phrases_for("warehouse robot(s|ics)?") == [
        "warehouse robot", "warehouse robots", "warehouse robotics",
    ]


def test_a_character_class_of_separators_expands_to_both_spellings():
    assert set(supplemental.phrases_for("piece[- ]picking")) == {
        "piece-picking", "piece picking",
    }


def test_word_boundaries_are_dropped_and_the_optional_plural_kept():
    assert set(supplemental.phrases_for(r"\bAMRs?\b")) == {"AMR", "AMRs"}


def test_a_proximity_pattern_is_dropped_rather_than_mangled():
    """`.{0,80}` has no phrase equivalent. Stripping it leaves the digits
    behind, which is how "ai 0,30 route optimisation" got into a query."""
    assert supplemental.phrases_for("(computer|machine) vision.{0,80}(warehouse|freight)") == []


def test_a_lookbehind_is_dropped_rather_than_mangled():
    assert supplemental.phrases_for("(?<!data )warehouse(s|ing)?") == []


def test_no_emitted_phrase_carries_regex_punctuation():
    for tech in _watchlist().active:
        for pattern in tech.include:
            for phrase in supplemental.phrases_for(pattern):
                assert not set(phrase) & set("\\()[]{}|?*+^$"), (pattern, phrase)


def test_no_emitted_phrase_has_a_doubled_or_leading_space():
    for tech in _watchlist().active:
        for pattern in tech.include:
            for phrase in supplemental.phrases_for(pattern):
                assert phrase == " ".join(phrase.split()), (pattern, phrase)


def test_the_term_list_is_capped():
    """ProQuest will not take a query of unbounded length, and 150 terms is not
    the ~30 the spec costed."""
    terms = supplemental.watchlist_terms(_watchlist())
    assert terms.count(" OR ") + 1 <= supplemental.MAX_TERMS


def test_the_sheet_states_how_many_phrases_the_query_carries(capsys):
    """Silent truncation is this project's oldest failure mode, so the sheet
    states the count, the total and the cap whether or not the cap bit."""
    watchlist = _watchlist()
    supplemental.print_queries("2026-Q2", watchlist)
    printed = capsys.readouterr().out
    total = len(supplemental.watchlist_phrases(watchlist))
    carried = min(total, supplemental.MAX_TERMS)
    assert f"{carried} of {total} phrases" in printed
    assert f"capped at {supplemental.MAX_TERMS}" in printed


def test_a_cap_that_bites_says_how_many_it_dropped(capsys, monkeypatch):
    monkeypatch.setattr(supplemental, "MAX_TERMS", 5)
    supplemental.print_queries("2026-Q2", _watchlist())
    printed = capsys.readouterr().out
    assert "were dropped by the cap" in printed
    assert "5 of" in printed


def test_every_technology_gets_at_most_one_phrase():
    """Ranking by length kept 'optimisation' and 'optimization' as two of the
    forty slots while warehouse robotics fell out at rank 193. One phrase per
    technology spends the budget on coverage instead of spelling."""
    watchlist = _watchlist()
    phrases = supplemental.watchlist_phrases(watchlist)
    assert len(phrases) <= len(watchlist.active)
    assert len(set(phrases)) == len(phrases)


def test_the_phrase_chosen_is_the_most_specific_one_available():
    """'warehouse robotics' discriminates; 'warehouse robot' is a prefix of it
    and retrieves more noise."""
    assert "warehouse robotics" in supplemental.watchlist_phrases(_watchlist())


def test_technologies_with_no_phrasable_pattern_are_named_not_dropped(capsys):
    """A technology defined only by a proximity pattern cannot be searched as a
    phrase. That is a hole in trade press coverage and the sheet has to say
    which technologies are in it."""
    watchlist = _watchlist()
    supplemental.print_queries("2026-Q2", watchlist)
    printed = capsys.readouterr().out
    for tech_id in supplemental.unphrasable(watchlist):
        assert tech_id in printed, f"{tech_id} is unsearchable and the sheet never says so"


def test_a_proximity_only_technology_is_reported_as_unphrasable():
    """Constructed rather than drawn from the live lexicon, so this keeps
    testing the behaviour after the watchlist changes."""
    from observatory import matcher
    tech = matcher.Technology(
        id="proximity_only", name="Proximity only", family="digital",
        include=(r"llm[^.]{0,30}(warehouse|logistics)",), exclude=(),
        status="active", added_week="2026-W35", patterns_changed_week="2026-W35",
    )
    watchlist = matcher.Watchlist(version=1, context=("logistics",), technologies=(tech,))
    assert supplemental.unphrasable(watchlist) == ["proximity_only"]
    assert supplemental.watchlist_phrases(watchlist) == []


def test_the_sheet_can_be_narrowed_to_one_source(capsys):
    """Three long queries on one sheet is how the ABI/INFORM query ended up
    pasted into Lens, where PUB() and pd() mean nothing and the result was a
    clean, believable zero."""
    supplemental.print_queries("2026-Q2", _watchlist(), only="lens")
    printed = capsys.readouterr().out
    assert "Lens.org" in printed
    assert "ProQuest" not in printed
    assert "PUB(" not in printed


def test_narrowing_to_an_unknown_source_is_an_error():
    with pytest.raises(supplemental.RegistryProblem):
        supplemental.print_queries("2026-Q2", _watchlist(), only="nope")


def test_the_cli_passes_the_source_through(capsys):
    from observatory import run
    run.main(["--export-queries", "2026-Q2", "--source", "lens"])
    printed = capsys.readouterr().out
    assert "Lens.org" in printed and "ProQuest" not in printed


def test_scopus_filters_by_publication_year_not_a_date_range():
    """PUBDATETXT(a TO b) was a guess and Scopus rejected it. PUBYEAR is a
    documented field code; the quarter is narrowed with the interface's own
    date limiter, which is a mechanical setting rather than a judgement about
    relevance, and the pipeline files each paper by its own date anyway."""
    query = supplemental.build_query("scopus", "2026-Q2", _watchlist())
    assert "PUBYEAR" in query
    assert "PUBDATETXT" not in query
    assert "2026" in query


def test_a_period_spanning_two_years_asks_for_both():
    """An ISO quarter's first Monday can fall in the previous December."""
    years = supplemental.years_in(("2025-12-29", "2026-03-29"))
    assert years == ["2025", "2026"]
    assert supplemental.pubyear_clause(("2025-12-29", "2026-03-29")) == (
        "( PUBYEAR = 2025 OR PUBYEAR = 2026 )"
    )


def test_a_single_year_period_asks_for_one_year():
    assert supplemental.pubyear_clause(("2026-04-01", "2026-06-30")) == "PUBYEAR = 2026"


# --- splitting an export that will not fit ---------------------------------
#
# Scopus returned 2,607 documents for one year of twelve journals against a
# 1,000-record export limit. Splitting by hand is how a quarter goes half
# collected while every file still looks complete.


def test_splitting_scopus_gives_one_query_per_journal():
    entries = supplemental.export_queries("2026-Q2", _watchlist(), split=True)
    issns = supplemental.load().lists["issn"]["items"]
    scopus = [e for e in entries if e["source"] == "scopus"]
    assert len(scopus) == len(issns)


def test_each_split_query_names_exactly_one_journal():
    for entry in supplemental.export_queries("2026-Q2", _watchlist(), split=True):
        if entry["source"] == "scopus":
            assert entry["query"].count("ISSN(") == 1


def test_each_split_query_gets_its_own_filename():
    entries = [e for e in supplemental.export_queries("2026-Q2", _watchlist(), split=True)
               if e["source"] == "scopus"]
    names = [e["filename"] for e in entries]
    assert len(set(names)) == len(names)
    assert all(name.endswith(".ris") for name in names)


def test_a_split_query_still_carries_the_period():
    for entry in supplemental.export_queries("2026-Q2", _watchlist(), split=True):
        assert "PUBYEAR" in entry["query"] or "date_published" in entry["query"] or "pd(" in entry["query"]


def test_without_splitting_there_is_one_query_per_source():
    entries = supplemental.export_queries("2026-Q2", _watchlist())
    assert len(entries) == len(supplemental.load().sources)


def test_trade_press_splits_by_publication():
    """One outlet returns 3,460 records for a quarter against a 1,000 export
    limit, so the whole set cannot come out in one file."""
    entries = [e for e in supplemental.export_queries("2026-Q2", _watchlist(), split=True)
               if e["source"] == "abi_inform"]
    assert len(entries) == len(supplemental.load().lists["publications"]["items"])
    for entry in entries:
        assert entry["query"].count("PUB.EXACT(") == 1


def test_a_source_with_nothing_to_split_on_is_left_whole():
    entries = supplemental.export_queries("2026-Q2", _watchlist(), split=True)
    assert len([e for e in entries if e["source"] == "lens"]) == 1


def test_the_sheet_says_how_many_files_a_split_expects(capsys):
    supplemental.print_queries("2026-Q2", _watchlist(), only="scopus", split=True)
    printed = capsys.readouterr().out
    count = len(supplemental.load().lists["issn"]["items"])
    assert f"{count} separate exports" in printed


# --- phrases for a corpus that is already on-topic --------------------------
#
# A real ABI/INFORM export returned 36 records where publication-only returns
# 3,460 for one outlet. The 50 formal phrases were fighting a filter already
# applied: PUB() constrains to supply chain trade press, so "digital twin" in
# Supply Chain Dive is the technology and "supply chain digital twins" is a
# phrase no headline writes.


def test_a_trade_phrase_is_the_shortest_distinctive_one():
    tech = _tech("supply_chain_digital_twin",
                 ("supply chain digital twin(s)?", "digital twin of the supply chain"))
    assert supplemental.trade_phrase(tech) == "supply chain digital twin"


def test_a_trade_phrase_drops_a_leading_domain_word():
    """The publication filter already said "supply chain". Repeating it in the
    term costs recall and buys nothing."""
    assert supplemental.strip_domain("supply chain digital twin") == "digital twin"
    assert supplemental.strip_domain("warehouse robotics") == "warehouse robotics"


def test_a_phrase_that_is_only_a_domain_word_is_kept_whole():
    """Stripping "supply chain" from "supply chain" leaves nothing to search."""
    assert supplemental.strip_domain("supply chain") == "supply chain"


def test_trade_phrases_are_shorter_than_the_general_ones():
    watchlist = _watchlist()
    general = supplemental.watchlist_phrases(watchlist)
    trade = supplemental.trade_phrases(watchlist)
    assert sum(len(p) for p in trade) < sum(len(p) for p in general)


def test_the_trade_query_uses_the_trade_phrases():
    query = supplemental.build_query("abi_inform", "2026-Q2", _watchlist())
    assert '"digital twin"' in query


def test_the_trade_query_matches_publications_exactly():
    """PUB("Logistics Management") matched the International Journal of
    Physical Distribution & Logistics Management -- an academic journal already
    covered by Scopus. Counted as trade, it would fake family diversity, which
    is the one thing the gate exists to prevent."""
    query = supplemental.build_query("abi_inform", "2026-Q2", _watchlist())
    assert "PUB.EXACT(" in query
    assert 'PUB("' not in query


def test_publications_absent_from_the_database_are_not_asked_for():
    """DC Velocity returns nothing under PUB.EXACT. Asking anyway makes a query
    longer and a reader think it was covered."""
    items = supplemental.load().lists["publications"]["items"]
    for absent in ("DC Velocity", "FreightWaves", "Material Handling & Logistics"):
        assert absent not in items


def _tech(tech_id, include):
    from observatory import matcher
    return matcher.Technology(
        id=tech_id, name=tech_id, family="f", include=include, exclude=(),
        status="active", added_week="2026-W01", patterns_changed_week="2026-W01")


def test_stripping_never_leaves_a_single_generic_word():
    """"warehouse management system" became "system", which would have matched
    nearly every article in a trade publication and drowned the export it was
    meant to narrow."""
    assert supplemental.strip_domain("warehouse management system") == \
        "warehouse management system"


def test_stripping_still_works_where_the_remainder_is_distinctive():
    assert supplemental.strip_domain("supply chain digital twin") == "digital twin"
    assert supplemental.strip_domain("supply chain control tower") == "control tower"


def test_no_trade_term_is_a_single_common_word():
    """One term of two characters or one common word makes the whole query
    useless, and the query is what a person pastes without checking."""
    for phrase in supplemental.trade_phrases(_watchlist()):
        assert " " in phrase or len(phrase) >= 8, phrase


def test_the_term_wrapper_is_configurable_rather_than_assumed():
    """An unfielded term returned 19 articles for Supply Chain Dive in
    2026-Q3; the same terms in FT() returned 13. Two guesses at ProQuest's
    scope, both wrong, is enough: the wrapper is config and the answer comes
    from measurement."""
    registry = supplemental.load()
    each = registry.lists["trade_terms"]["each"]
    assert "{}" in each
    query = supplemental.build_query("abi_inform", "2026-Q2", _watchlist())
    assert each.replace("{}", "digital twin") in query
