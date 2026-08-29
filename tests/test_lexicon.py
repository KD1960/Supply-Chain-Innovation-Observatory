import textwrap

import pytest

from observatory import lexicon, store
from observatory.discover import Candidate
from observatory.matcher import Technology, Watchlist


@pytest.fixture()
def watchlist():
    return Watchlist(
        version=4,
        technologies=(
            Technology(id="cold_chain_iot", name="Cold chain IoT", family="physical",
                       include=("cold chain monitoring",), exclude=(), status="active",
                       added_week="2020-W01", patterns_changed_week="2020-W01"),
        ),
        context=("logistics", "warehouse"),
    )


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    store.upsert_candidates(connection, "2026-W33", [
        Candidate(term="dark factory", count=7, baseline=1.0, ratio=7.0,
                  examples=[("Dark factory retrofit in Ohio warehouse", "https://x.test/1")]),
    ])
    yield connection
    connection.close()


def test_prepare_writes_a_request_naming_the_week(conn, watchlist, tmp_path):
    path = lexicon.prepare(conn, "2026-W33", watchlist, tmp_path / "req.md")
    assert path.exists()
    assert "2026-W33" in path.read_text()


def test_request_carries_the_candidates_and_their_evidence(conn, watchlist, tmp_path):
    text = lexicon.prepare(conn, "2026-W33", watchlist, tmp_path / "req.md").read_text()
    assert "dark factory" in text
    assert "Dark factory retrofit in Ohio" in text
    assert "https://x.test/1" in text


def test_request_lists_the_existing_technologies_so_duplicates_are_visible(conn, watchlist, tmp_path):
    text = lexicon.prepare(conn, "2026-W33", watchlist, tmp_path / "req.md").read_text()
    assert "cold_chain_iot" in text
    assert "Cold chain IoT" in text


def test_request_states_the_context_vocabulary(conn, watchlist, tmp_path):
    text = lexicon.prepare(conn, "2026-W33", watchlist, tmp_path / "req.md").read_text()
    assert "logistics" in text
    assert "warehouse" in text


def test_request_names_the_proposal_file_to_write(conn, watchlist, tmp_path):
    text = lexicon.prepare(conn, "2026-W33", watchlist, tmp_path / "req.md").read_text()
    assert "proposals/2026-W33.yaml" in text


def test_prepare_says_so_when_there_are_no_candidates(watchlist, tmp_path):
    connection = store.connect(":memory:")
    store.init_schema(connection)
    text = lexicon.prepare(connection, "2026-W33", watchlist, tmp_path / "req.md").read_text()
    assert "no candidate terms" in text.lower()
    connection.close()


def test_request_escapes_markdown_syntax_in_untrusted_candidate_text(watchlist, tmp_path):
    """Terms and titles are harvested from public APIs, unsanitised. A
    backtick would break the `term` code span; a `]` followed by `(` would
    splice in an attacker-chosen link destination. Both must come through
    escaped rather than parsed as Markdown structure."""
    connection = store.connect(":memory:")
    store.init_schema(connection)
    store.upsert_candidates(connection, "2026-W33", [
        Candidate(term="weird`term", count=3, baseline=1.0, ratio=3.0,
                  examples=[("Title with `backtick`, [brackets], and (parens)",
                              "https://x.test/2")]),
    ])
    text = lexicon.prepare(connection, "2026-W33", watchlist, tmp_path / "req.md").read_text()
    connection.close()
    assert "weird\\`term" in text
    assert "\\`backtick\\`" in text
    assert "\\[brackets\\]" in text
    assert "\\(parens\\)" in text


def test_request_wraps_a_url_containing_a_closing_paren_in_angle_brackets(watchlist, tmp_path):
    connection = store.connect(":memory:")
    store.init_schema(connection)
    store.upsert_candidates(connection, "2026-W33", [
        Candidate(term="dark factory", count=3, baseline=1.0, ratio=3.0,
                  examples=[("Title", "https://x.test/path(1)")]),
    ])
    text = lexicon.prepare(connection, "2026-W33", watchlist, tmp_path / "req.md").read_text()
    connection.close()
    assert "(<https://x.test/path(1)>)" in text


def test_request_warns_candidate_text_is_untrusted_and_not_instructions(conn, watchlist, tmp_path):
    text = lexicon.prepare(conn, "2026-W33", watchlist, tmp_path / "req.md").read_text()
    assert "untrusted" in text.lower()
    # It must appear before any actual candidate, not just anywhere in the file.
    assert text.index("untrusted") > text.index("## Candidate terms")
    assert text.index("untrusted") < text.index("### `dark factory`")


def write_proposal(tmp_path, body):
    path = tmp_path / "proposal.yaml"
    path.write_text(textwrap.dedent(body))
    return path


def test_check_accepts_a_sound_proposal(conn, watchlist, tmp_path):
    path = write_proposal(tmp_path, """
        technologies:
          - id: dark_factory
            name: Dark factories
            family: physical
            include: ["dark factor(y|ies)"]
            exclude: []
            needs_context: true
    """)
    problems, block = lexicon.check(conn, "2026-W33", watchlist, path)
    assert problems == []
    assert "dark_factory" in block


def test_check_rejects_a_pattern_that_does_not_compile(conn, watchlist, tmp_path):
    path = write_proposal(tmp_path, """
        technologies:
          - id: dark_factory
            name: Dark factories
            family: physical
            include: ["dark factor(y|ies"]
            exclude: []
    """)
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert any("compile" in problem.message for problem in problems)


def test_check_rejects_an_id_that_already_exists(conn, watchlist, tmp_path):
    path = write_proposal(tmp_path, """
        technologies:
          - id: cold_chain_iot
            name: Duplicate
            family: physical
            include: ["something else"]
            exclude: []
    """)
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert any("already" in problem.message for problem in problems)


def test_check_rejects_a_proposal_that_matches_none_of_its_own_evidence(conn, watchlist, tmp_path):
    """A pattern that cannot match the documents that inspired it is useless."""
    path = write_proposal(tmp_path, """
        technologies:
          - id: dark_factory
            name: Dark factories
            family: physical
            include: ["completely unrelated phrase"]
            exclude: []
    """)
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert any("evidence" in problem.message for problem in problems)


def test_check_warns_when_a_gated_pattern_can_never_pass_its_gate(watchlist, tmp_path):
    """needs_context plus evidence that contains no context word is a silent zero.

    This uses its own connection rather than the shared `conn` fixture: that
    fixture's example title now contains "warehouse" (a context word), which
    is what lets test_check_accepts_a_sound_proposal see a clean proposal for
    the same pattern. This test needs the opposite -- evidence with no context
    word at all -- so it supplies its own context-free candidate.
    """
    connection = store.connect(":memory:")
    store.init_schema(connection)
    store.upsert_candidates(connection, "2026-W33", [
        Candidate(term="dark factory", count=7, baseline=1.0, ratio=7.0,
                  examples=[("Dark factory retrofit in Ohio", "https://x.test/1")]),
    ])
    path = write_proposal(tmp_path, """
        technologies:
          - id: dark_factory
            name: Dark factories
            family: physical
            include: ["dark factor(y|ies)"]
            exclude: []
            needs_context: true
    """)
    problems, _ = lexicon.check(connection, "2026-W33", watchlist, path)
    connection.close()
    # The example title "Dark factory retrofit in Ohio" has no context word.
    assert any("context" in problem.message for problem in problems)


def test_check_reports_a_missing_proposal_file(conn, watchlist, tmp_path):
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, tmp_path / "absent.yaml")
    assert any("not found" in problem.message for problem in problems)


def test_check_rejects_a_proposal_file_that_is_not_a_mapping(conn, watchlist, tmp_path):
    """The proposals file is written by a Claude session from untrusted public-API
    text. A bare YAML list or scalar must be a Problem, never a traceback."""
    path = write_proposal(tmp_path, "- just a list\n- not a mapping\n")
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert problems and all(isinstance(p, lexicon.Problem) for p in problems)


def test_check_rejects_a_proposal_missing_the_technologies_key(conn, watchlist, tmp_path):
    path = write_proposal(tmp_path, "note: forgot the technologies key\n")
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert problems and all(isinstance(p, lexicon.Problem) for p in problems)


def test_check_rejects_a_technologies_value_that_is_not_a_list(conn, watchlist, tmp_path):
    path = write_proposal(tmp_path, "technologies: not-a-list\n")
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert problems and all(isinstance(p, lexicon.Problem) for p in problems)


def test_check_rejects_a_technology_entry_that_is_not_a_mapping(conn, watchlist, tmp_path):
    path = write_proposal(tmp_path, "technologies:\n  - just a string\n")
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert problems and all(isinstance(p, lexicon.Problem) for p in problems)


def test_check_rejects_invalid_yaml_syntax(conn, watchlist, tmp_path):
    path = write_proposal(tmp_path, "technologies: [unclosed\n")
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert problems and all(isinstance(p, lexicon.Problem) for p in problems)


def test_check_reports_a_clear_problem_when_include_is_a_bare_string(conn, watchlist, tmp_path):
    """A YAML scalar where a sequence was meant -- e.g. include: "multi[- ]agent"
    instead of include: ["multi[- ]agent"] -- must be named as a shape problem,
    not iterated character by character into a string of bogus pattern-compile
    errors."""
    path = write_proposal(tmp_path, """
        technologies:
          - id: dark_factory
            name: Dark factories
            family: physical
            include: "multi[- ]agent"
            exclude: []
    """)
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert any("include" in problem.message for problem in problems)
    assert not any("does not compile" in problem.message for problem in problems)


def test_check_reports_a_clear_problem_when_exclude_is_a_bare_string(conn, watchlist, tmp_path):
    path = write_proposal(tmp_path, """
        technologies:
          - id: dark_factory
            name: Dark factories
            family: physical
            include: ["dark factor(y|ies)"]
            exclude: "lights-out band"
    """)
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert any("exclude" in problem.message for problem in problems)
    assert not any("does not compile" in problem.message for problem in problems)


def test_check_reports_a_problem_when_name_is_missing(conn, watchlist, tmp_path):
    """`matcher.load_watchlist` reads `entry["name"]`, not `.get`, so a proposal
    missing `name` would validate cleanly here but crash the next
    `observatory.run` the moment it's pasted into watchlist.yaml and loaded --
    that is not sensible degradation, so `check` must catch it first."""
    path = write_proposal(tmp_path, """
        technologies:
          - id: dark_factory
            family: physical
            include: ["dark factor(y|ies)"]
            exclude: []
            needs_context: true
    """)
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert any("name" in problem.message for problem in problems)


def test_check_reports_a_problem_when_family_is_missing(conn, watchlist, tmp_path):
    """Same failure mode as a missing `name`: `matcher.load_watchlist` reads
    `entry["family"]` unconditionally, so this would otherwise validate
    cleanly and crash the next run after being pasted in."""
    path = write_proposal(tmp_path, """
        technologies:
          - id: dark_factory
            name: Dark factories
            include: ["dark factor(y|ies)"]
            exclude: []
            needs_context: true
    """)
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert any("family" in problem.message for problem in problems)


def test_check_reports_a_problem_when_id_is_missing(conn, watchlist, tmp_path):
    """`matcher.load_watchlist` reads `entry["id"]` unconditionally too. The
    `tech_id = entry.get("id", "(missing id)")` fallback exists only to give
    other problem messages something to label themselves with -- on its own
    it does not raise a problem, so this case needs its own check."""
    path = write_proposal(tmp_path, """
        technologies:
          - name: Dark factories
            family: physical
            include: ["dark factor(y|ies)"]
            exclude: []
            needs_context: true
    """)
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert any("id" in problem.message for problem in problems)


def test_check_does_not_penalise_an_omitted_exclude(conn, watchlist, tmp_path):
    """Omitting `exclude` is normal -- most proposals have nothing to exclude,
    and the request template does not require the key. Shape-checking it
    against the substituted default (`entry.get("exclude", [])`) would make
    every such proposal fail with a false positive."""
    path = write_proposal(tmp_path, """
        technologies:
          - id: dark_factory
            name: Dark factories
            family: physical
            include: ["dark factor(y|ies)"]
    """)
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert not any("exclude" in problem.message for problem in problems)


def test_check_rejects_an_exclude_pattern_that_does_not_compile(conn, watchlist, tmp_path):
    """`matcher.Technology.__post_init__` compiles exclude patterns as well as
    include ones, so a bad exclude that check waved through would raise in
    `load_watchlist` on the next run -- before a single fetch -- once merged.
    Exclude is where alternation and parentheses pile up, so this is the more
    likely of the two to be malformed."""
    path = write_proposal(tmp_path, """
        technologies:
          - id: dark_factory
            name: Dark factories
            family: physical
            include: ["dark factor(y|ies)"]
            exclude: ["dark factory (band|album"]
    """)
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert any("exclude" in problem.message and "compile" in problem.message
               for problem in problems)


def test_check_reports_a_problem_when_include_is_present_but_empty(conn, watchlist, tmp_path):
    """`include: []` matches nothing, exactly like an absent `include`, and a
    validator that passes it hands the owner the silent zero it exists to
    prevent."""
    path = write_proposal(tmp_path, """
        technologies:
          - id: dark_factory
            name: Dark factories
            family: physical
            include: []
            exclude: []
    """)
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert any("include" in problem.message for problem in problems)


def test_check_rejects_an_exclude_that_vetoes_the_proposals_own_evidence(conn, watchlist, tmp_path):
    """An exclude broader than its own include counts zero forever. The
    evidence test already asks whether a proposal matches the documents that
    inspired it; it must ask that of the matcher's real answer, excludes
    applied, not of the include patterns alone."""
    path = write_proposal(tmp_path, """
        technologies:
          - id: dark_factory
            name: Dark factories
            family: physical
            include: ["dark factor(y|ies)"]
            exclude: ["dark"]
    """)
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert any("evidence" in problem.message for problem in problems)


def test_check_reports_two_entries_sharing_an_id(conn, watchlist, tmp_path):
    """The id check only looked at the existing watchlist, so two proposed
    entries with the same id both passed and the second was silently swallowed
    at merge time."""
    path = write_proposal(tmp_path, """
        technologies:
          - id: dark_factory
            name: Dark factories
            family: physical
            include: ["dark factor(y|ies)"]
          - id: dark_factory
            name: Dark factories, again
            family: physical
            include: ["lights[- ]out factor(y|ies)"]
    """)
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert any("dark_factory" in problem.message and "twice" in problem.message
               for problem in problems)


def test_check_reports_a_problem_when_include_is_missing(conn, watchlist, tmp_path):
    """Unlike `exclude`, an absent `include` is a real problem: a technology
    with no patterns matches nothing."""
    path = write_proposal(tmp_path, """
        technologies:
          - id: dark_factory
            name: Dark factories
            family: physical
            exclude: []
    """)
    problems, _ = lexicon.check(conn, "2026-W33", watchlist, path)
    assert any("include" in problem.message for problem in problems)


# --- revising an entry that already exists ---------------------------------
#
# `check` was written for discovery: new technologies drawn from the week's
# candidate terms. Ten entries then needed *revising* -- their patterns carried
# the domain word while the context gate sat off -- and every one was rejected
# twice over, for existing already and for matching no candidate evidence.
# Neither is a fault in a revision, and the workflow had no other door.

REVISION = """
revisions:
  - id: supply_chain_digital_twin
    name: Supply chain digital twins
    family: digital
    include:
      - "digital twin(s)?"
    exclude: []
    needs_context: true
    because: >-
      The pattern required the domain word adjacent to the technology word, so
      an article saying "inventory management with digital twins" was missed.
"""


def test_a_revision_of_an_existing_technology_is_accepted(conn, tmp_path):
    path = tmp_path / "r.yaml"
    path.write_text(REVISION)
    problems, _ = lexicon.check(conn, "2026-W35", _watchlist(), path)
    assert problems == []


def test_a_revision_must_name_a_technology_that_exists(conn, tmp_path):
    """Revising something absent is a typo, and it would merge as a new
    technology with no `added_week` and no evidence behind it."""
    path = tmp_path / "r.yaml"
    path.write_text(REVISION.replace("supply_chain_digital_twin", "no_such_thing"))
    problems, _ = lexicon.check(conn, "2026-W35", _watchlist(), path)
    assert any("does not exist" in problem.message for problem in problems)


def test_a_revision_must_say_why(conn, tmp_path):
    """A new technology carries its evidence in the candidate terms that
    surfaced it. A revision has no such trail, so the reason is the trail."""
    path = tmp_path / "r.yaml"
    path.write_text(REVISION.replace("    because: >-", "    unused: >-"))
    problems, _ = lexicon.check(conn, "2026-W35", _watchlist(), path)
    assert any("because" in problem.message for problem in problems)


def test_a_revision_is_not_asked_for_candidate_evidence(conn, tmp_path):
    """The evidence test exists to stop a proposed technology that matches
    nothing in the week that surfaced it. A revision was not surfaced by a
    week."""
    path = tmp_path / "r.yaml"
    path.write_text(REVISION)
    problems, _ = lexicon.check(conn, "2026-W35", _watchlist(), path)
    assert not any("candidate evidence" in problem.message for problem in problems)


def test_a_revisions_patterns_still_have_to_compile(conn, tmp_path):
    path = tmp_path / "r.yaml"
    path.write_text(REVISION.replace('"digital twin(s)?"', '"digital twin(s"'))
    problems, _ = lexicon.check(conn, "2026-W35", _watchlist(), path)
    assert any("does not compile" in problem.message for problem in problems)


def test_a_revision_that_empties_its_patterns_is_refused(conn, tmp_path):
    path = tmp_path / "r.yaml"
    path.write_text(REVISION.replace('      - "digital twin(s)?"\n', ""))
    problems, _ = lexicon.check(conn, "2026-W35", _watchlist(), path)
    assert any("matches nothing" in problem.message for problem in problems)


def test_a_file_may_hold_both_new_technologies_and_revisions(conn, tmp_path):
    path = tmp_path / "r.yaml"
    path.write_text(REVISION + """
technologies:
  - id: brand_new
    name: Brand new
    family: digital
    include:
      - "vehicle routing"
    exclude: []
    needs_context: false
""")
    problems, _ = lexicon.check(conn, "2026-W35", _watchlist(), path)
    assert not any(p.term == "supply_chain_digital_twin" for p in problems)


def _watchlist():
    from observatory import matcher
    return matcher.load_watchlist()
