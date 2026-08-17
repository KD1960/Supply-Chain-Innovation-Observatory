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
                  examples=[("Dark factory retrofit in Ohio", "https://x.test/1")]),
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
