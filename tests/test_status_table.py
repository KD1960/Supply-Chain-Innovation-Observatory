"""STATUS §2 is generated, and this is what stops it drifting again.

The handover table misstated the corpus by 15% when the process review checked
it: seven headline figures wrong, two rows contradicting each other, and a
by-source row summing to 2,711 against its own stated 2,130. It had been
asserted correct -- "every number in it was verified against the database" --
and nothing re-verified it afterwards.

It went wrong again on 2026-09-01, hours after that was written up: eleven
exports landed, the observations total and §5 were updated, and the by-source
row was not, so the table contradicted itself one row apart.

A row that has to be hand-edited on every import will be wrong again. These
tests read the live database, so they skip where it is absent -- CI has no
`data/`, which is gitignored -- and that is the point: they fire on the machine
where the edit happens, before the commit.
"""

import pytest

from observatory import config, status, store

pytestmark = pytest.mark.skipif(
    not config.DB_PATH.exists(),
    reason="no local database; STATUS §2 can only be checked where the data is",
)


@pytest.fixture()
def conn():
    connection = store.connect()
    yield connection
    connection.close()


def test_status_matches_the_database(conn):
    """The whole point. Fails with the corrected table, so fixing it is a
    copy-paste and not a research task."""
    from observatory import matcher

    generated = status.derived_rows(conn, matcher.load_watchlist())
    written = status.written_rows()
    wrong = {label: (written.get(label), value)
             for label, value in generated.items()
             if written.get(label) != value}
    assert not wrong, (
        "STATUS §2 disagrees with the database:\n"
        + "\n".join(f"  {label}\n    STATUS: {was}\n    actual: {now}"
                    for label, (was, now) in wrong.items())
        + "\n\nRegenerate with: python -m observatory.run --write-status"
    )


def test_the_by_source_row_sums_to_the_observations_row(conn):
    """The review's sharpest catch: the by-source row summed to 2,711 against
    a stated 2,130. Two numbers in one table that cannot both be true is the
    one error a reader can find without leaving the page."""
    written = status.written_rows()
    by_source = status.parse_by_source(written["By source"])
    total = int(written["Observations"].replace(",", "").replace("*", ""))
    assert sum(by_source.values()) == total, (
        f"by-source sums to {sum(by_source.values())}, "
        f"observations says {total}"
    )


def test_the_test_count_is_this_run(request, conn):
    """Only when the whole suite ran.

    A `-k` selection, a `-m` selection or a named file collects a subset, and
    asserting the stated total against that would replace a true number with a
    false one -- the count would read 3 after `pytest tests/test_status_table.py`.
    Silence on a partial run is correct here; the full run is the one that
    guards the file, and CI runs it that way.
    """
    subset = (request.config.option.keyword
              or request.config.option.markexpr
              or any(arg.endswith(".py") or "::" in arg
                     for arg in request.config.args))
    if subset:
        pytest.skip("a partial run collects a subset; the count would be wrong")
    collected = request.session.testscollected
    written = status.written_rows()
    stated = int(written["Tests"].replace("*", "").split()[0])
    assert stated == collected, (
        f"STATUS says {stated} tests, this run collected {collected}. "
        "Regenerate with: python -m observatory.run --write-status"
    )
