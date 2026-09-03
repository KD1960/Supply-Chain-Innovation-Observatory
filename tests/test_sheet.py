"""The tracked-technologies sheet: one page, for a class rather than a board."""

import pytest

from observatory import sheet
from observatory.matcher import Technology, Watchlist


def tech(tech_id, name, *patterns):
    return Technology(
        id=tech_id, name=name, family="robotics", include=patterns, exclude=(),
        status="active", added_week="2020-W01", patterns_changed_week="2020-W01")


# --- patterns read as terms -------------------------------------------------
#
# Generated from the lexicon rather than written beside it, so a definition
# cannot drift from what the entry actually matches. Appendix A prints the
# pattern with its metacharacters knocked out, which produces "warehouse robot
# s ics" -- true to the pattern and unreadable to a student.


def test_a_suffix_alternation_becomes_the_words_it_matches():
    assert sheet.expand("warehouse robot(s|ics)?") == ["warehouse robots",
                                                       "warehouse robotics"]


def test_an_optional_word_gives_both_the_long_and_the_short_form():
    expanded = sheet.expand("robotic (item |piece )?picking")
    assert "robotic picking" in expanded
    assert "robotic item picking" in expanded


def test_a_hyphen_or_space_class_reads_as_a_space():
    assert sheet.expand("general[- ]purpose humanoid") == ["general purpose humanoid"]


def test_word_boundaries_and_optional_letters_come_out_as_the_term():
    assert sheet.expand(r"\bAMRs?\b") == ["AMRs"]


def test_alternatives_inside_a_phrase_are_each_spelled_out():
    assert sheet.expand("autonomous yard (truck|tractor|spotter)(s)?") == [
        "autonomous yard trucks", "autonomous yard tractors",
        "autonomous yard spotters"]


def test_a_pattern_it_cannot_expand_is_left_as_written():
    """Guessing at a pattern is worse than showing it. A sheet that quietly
    rewrites what a technology matches is a sheet that lies about the lexicon."""
    assert sheet.expand(r"cold chain\s+\w{3,}") == [r"cold chain\s+\w{3,}"]


# --- the sheet itself -------------------------------------------------------


def watchlist():
    return Watchlist(version=10, technologies=(
        tech("a", "Warehouse robotics", "warehouse robot(s|ics)?"),
        tech("b", "Autonomous trucking", "autonomous truck(s|ing)?")))


def test_the_sheet_lists_every_active_technology():
    composed = sheet.compose(watchlist(), "2026-Q2")
    assert [entry["name"] for entry in composed["technologies"]] == [
        "Autonomous trucking", "Warehouse robotics"]
    assert "warehouse robots" in composed["technologies"][1]["terms"]


def test_the_sheet_states_the_lexicon_version_it_was_made_from():
    """A sheet handed out in a class outlives the lexicon that made it."""
    composed = sheet.compose(watchlist(), "2026-Q2")
    assert "10" in composed["provenance"]
    assert "2026 Q2" in composed["title"]


def test_the_written_sheet_is_a_one_page_pdf(tmp_path):
    path = sheet.write(watchlist(), "2026-Q2", tmp_path)
    body = path.read_bytes()
    assert path.name == "technologies-2026-Q2.pdf"
    assert body.count(b"/Type /Page\n") == 1


def test_a_sheet_that_would_need_a_second_page_says_so(tmp_path):
    """One page is the format. Forty-nine technologies that do not fit is a
    decision for a person, not something to discover on a photocopier."""
    crowded = Watchlist(version=10, technologies=tuple(
        tech(f"t{index}", f"A technology with a very long name number {index}",
             "some fairly long pattern here(s)?")
        for index in range(120)))
    with pytest.raises(sheet.SheetOverflow):
        sheet.write(crowded, "2026-Q2", tmp_path)


def test_readable_terms_come_before_a_pattern_that_cannot_be_read():
    """Seven of the forty-eight lead with a proximity pattern -- agentic ai
    within eighty characters of procurement. Printing that first hands the
    student the regex and hides the two plain terms behind it."""
    entry = tech("x", "Agentic AI for procurement",
                 r"agentic ai[^.]{0,80}(procurement|sourcing)",
                 "agentic procurement", "agentic sourcing")
    assert sheet.terms_of(entry) == "agentic procurement, agentic sourcing"


def test_a_technology_with_nothing_readable_still_shows_what_it_matches():
    """Showing the pattern is honest. Showing nothing would say the technology
    matches nothing, which is the drift this sheet exists to avoid."""
    entry = tech("y", "Domain-specific LLMs", r"llm[^.]{0,30}(warehouse|logistics)")
    assert sheet.terms_of(entry) == r"llm[^.]{0,30}(warehouse|logistics)"


def test_a_terms_line_too_wide_is_cut_at_a_term_not_mid_word():
    """Chopping characters off the end produced 'generative ai in supply chain,
    generative ai in procurement, generative ai in l', which reads as a typo
    rather than as a list that continues."""
    fits = lambda text: len(text) <= 18  # noqa: E731 - a width rule, inline
    assert sheet.trim("alpha, beta, gamma, delta", fits) == "alpha, beta…"


def test_a_terms_line_that_fits_is_left_alone():
    assert sheet.trim("alpha, beta", lambda text: True) == "alpha, beta"


def test_a_single_term_too_wide_is_cut_with_an_ellipsis():
    assert sheet.trim("supercalifragilistic", lambda text: len(text) <= 8) == "superca…"
