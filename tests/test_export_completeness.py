"""An export that was never run has to be as loud as one that failed.

`read_exports` raises rather than skipping, because "a silently ignored export
is a silently missing quarter" -- but it can only refuse the files it can see.
Nothing compared what came back against what was asked for, so a quarter where
most of the sheet was never run imported cleanly and reported its fraction as
though it were the whole.

2026-Q3 is the case that prompted this. The sheet asks for **20** ABI/INFORM
exports -- four publications by five term batches -- and **four** were ever run,
all of them Supply Chain Dive. Modern Materials Handling, Supply Chain
Management Review and the Journal of Commerce were never exported at all. Trade
press holds 9 observations from 30 retrieved documents, which is not a thin
source: it is a fifth of a source. Its match rate, 30%, is the second best of
any source in the project.
"""


from observatory import matcher, supplemental
from observatory.matcher import Technology, Watchlist


def _watchlist():
    return Watchlist(version=1, context=("supply chain",), technologies=(Technology(
        id="a", name="A", family="f", include=("widget",), exclude=(),
        status="active", added_week="2020-W01", patterns_changed_week="2020-W01"),))


def test_missing_exports_names_every_file_the_sheet_asked_for(tmp_path):
    watchlist = _watchlist()
    expected = supplemental.export_queries("2026-Q3", watchlist, split=True)
    assert expected, "the sheet asks for nothing; the fixture is wrong"

    missing = supplemental.missing_exports("2026-Q3", watchlist, root=tmp_path)
    assert len(missing) == len(expected)
    assert {row["filename"] for row in missing} == {row["filename"] for row in expected}


def test_a_file_that_arrived_is_not_reported_missing(tmp_path):
    watchlist = _watchlist()
    expected = supplemental.export_queries("2026-Q3", watchlist, split=True)
    landed = expected[0]["filename"]
    directory = tmp_path / "2026-Q3"
    directory.mkdir(parents=True)
    (directory / landed).write_text("")

    missing = {row["filename"] for row in
               supplemental.missing_exports("2026-Q3", watchlist, root=tmp_path)}
    assert landed not in missing
    assert len(missing) == len(expected) - 1


# A test that read the real export directory used to sit here, asserting that
# most of 2026-Q3 was missing. It was passing for the wrong reason: `conftest`
# points `config.MANUAL_DIR` at an empty temporary directory for every test, on
# purpose and for good reasons it states, so the test saw nothing on disk and
# would have reported every export missing whatever the truth was. It could not
# have failed while the isolation held.
#
# The finding it claimed to pin was real -- verified by running
# `missing_exports` against the live directory by hand -- but a test is not
# where that belongs. What is worth asserting in a test is the behaviour of the
# check, which the fixtures above do, and the configuration it reads, which is
# below.


def test_journal_of_commerce_is_not_asked_for():
    """Removed 2026-09-01 on measurement, and this pins the reason.

    It is not the DC Velocity case of a title that does not resolve:
    `PUB.EXACT("Journal of Commerce")` returns 133,243 records and 4,487 of
    them fall in 2020-2026. ABI/INFORM's holding stops at 2022-12-31, and this
    corpus begins 2024-W12 -- more than a year after the coverage ends, so the
    publication could never have contributed a single document. Five term
    batches were exported against it and all five were correctly empty.

    Re-adding it needs ABI/INFORM to resume coverage, not a better query.
    """
    watchlist = matcher.load_watchlist("watchlist.yaml")
    asked = supplemental.export_queries("2026-Q3", watchlist, split=True)
    assert not [row for row in asked if "JournalofCommerce" in row["filename"]]
    assert not [row for row in asked
                if "Journal of Commerce" in row["query"]]


def test_import_says_what_never_arrived(tmp_path, capsys):
    """Said out loud on the run that ingests them, not left in a file nobody
    opens. Silent truncation is this project's oldest failure mode, and an
    export nobody ran is the same shape."""
    from observatory import store

    conn = store.connect(":memory:")
    store.init_schema(conn)
    try:
        (tmp_path / "2026-Q3").mkdir(parents=True)
        manual_import = __import__("observatory.manual", fromlist=["manual"])
        manual_import.import_exports(conn, _watchlist(), root=tmp_path,
                                     period="2026-Q3")
        printed = capsys.readouterr().out
        assert "never arrived" in printed
        assert "scopus" in printed
        # Not the retired source. Asking a person for an export the licence
        # forbids is worse than not asking, and a standing reminder for it
        # would outlive anyone's memory of why it stopped.
        assert "abi_inform" not in printed
    finally:
        conn.close()


def test_a_source_that_arrived_under_its_own_name_is_not_reported_missing(tmp_path):
    """Lens exports as `lens-export-supplychaininnovation.csv`, because that is
    what the database hands you. Matching on the generated filename reported a
    file sitting on disk as never having arrived -- a false positive, which in a
    report about absence is the worst possible kind."""
    watchlist = _watchlist()
    directory = tmp_path / "2026-Q3"
    directory.mkdir(parents=True)
    (directory / "lens-export-whatever-the-site-called-it.csv").write_text("")
    (directory / "lens-export-whatever-the-site-called-it.csv.meta.yaml").write_text(
        "source: lens\nexported: 2026-08-29\nquery: x\nrecords: 1\n")

    missing = supplemental.missing_exports("2026-Q3", watchlist, root=tmp_path)
    assert not [row for row in missing if row["source"] == "lens"]


def test_a_split_source_is_still_checked_piece_by_piece(tmp_path):
    """The other half. One Scopus journal arriving must not vouch for the other
    eleven, or the check would be satisfied by any single file."""
    watchlist = _watchlist()
    directory = tmp_path / "2026-Q3"
    directory.mkdir(parents=True)
    expected = [e for e in supplemental.export_queries("2026-Q3", watchlist, split=True)
                if e["source"] == "scopus"]
    (directory / expected[0]["filename"]).write_text("")
    (directory / f"{expected[0]['filename']}.meta.yaml").write_text(
        "source: scopus\nexported: 2026-08-29\nquery: x\nrecords: 1\n")

    missing = [row for row in supplemental.missing_exports("2026-Q3", watchlist, root=tmp_path)
               if row["source"] == "scopus"]
    assert len(missing) == len(expected) - 1
