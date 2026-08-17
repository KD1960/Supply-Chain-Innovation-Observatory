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
