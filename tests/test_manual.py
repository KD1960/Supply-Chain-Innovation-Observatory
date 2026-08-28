import textwrap

import pytest

from observatory import manual, store
from observatory.matcher import Technology, Watchlist


def tech(tech_id="wr", pattern="warehouse robot(s|ics)?"):
    return Technology(
        id=tech_id, name=tech_id, family="f", include=(pattern,), exclude=(),
        status="active", added_week="2020-W01", patterns_changed_week="2020-W01",
    )


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


RIS = textwrap.dedent("""\
    TY  - JOUR
    TI  - Warehouse robotics adoption in mid-market distribution
    AB  - A survey of warehouse robots across 40 distribution centres.
    PY  - 2026
    DA  - 2026/04/15
    DO  - 10.1000/abc123
    T2  - International Journal of Production Research
    ER  -

    TY  - JOUR
    TI  - Unrelated paper about protein folding
    AB  - Nothing to do with this domain.
    PY  - 2026
    DA  - 2026/04/20
    DO  - 10.1000/xyz789
    ER  -
    """)

META = textwrap.dedent("""\
    source: scopus
    exported: 2026-08-20
    query: TITLE-ABS-KEY("warehouse robot")
    records: 2
    redistributable: false
    """)


def write_export(tmp_path, name="scopus-2026.ris", body=RIS, meta=META):
    directory = tmp_path / "scopus"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(body)
    (directory / f"{name}.meta.yaml").write_text(meta)
    return directory


def test_ris_parses_one_record_per_entry():
    records = manual.parse_ris(RIS)
    assert len(records) == 2
    assert records[0]["title"].startswith("Warehouse robotics adoption")
    assert records[0]["doi"] == "10.1000/abc123"
    assert records[0]["date"] == "2026-04-15"


def test_ris_falls_back_to_the_year_when_there_is_no_full_date():
    records = manual.parse_ris("TY  - JOUR\nTI  - A title\nPY  - 2026\nER  -\n")
    assert records[0]["date"] == "2026-01-01"


def test_ris_joins_a_wrapped_field():
    body = "TY  - JOUR\nTI  - A very long title that\n          continues here\nPY  - 2026\nER  -\n"
    assert manual.parse_ris(body)[0]["title"] == "A very long title that continues here"


def test_csv_maps_columns_by_name():
    body = 'Title,Abstract,DOI,Year\n"Warehouse robots","In warehouses","10.1/a",2026\n'
    records = manual.parse_csv(body)
    assert records[0]["title"] == "Warehouse robots"
    assert records[0]["doi"] == "10.1/a"
    assert records[0]["date"] == "2026-01-01"


def test_reading_an_export_requires_its_sidecar(tmp_path):
    directory = tmp_path / "scopus"
    directory.mkdir(parents=True)
    (directory / "x.ris").write_text(RIS)
    with pytest.raises(manual.ExportProblem, match="meta.yaml"):
        list(manual.read_exports(tmp_path))


def test_a_short_export_is_refused_rather_than_counted(tmp_path):
    """Scopus caps an export at 2,000 records and says so only in the UI.
    A truncated file that is silently ingested is a smaller number that looks
    exactly like a real one."""
    write_export(tmp_path, meta=META.replace("records: 2", "records: 2000"))
    with pytest.raises(manual.ExportProblem, match="2000"):
        list(manual.read_exports(tmp_path))


def test_import_writes_observations_for_matching_records_only(tmp_path, conn):
    write_export(tmp_path)
    watchlist = Watchlist(version=1, technologies=(tech(),))
    written = manual.import_exports(conn, watchlist, root=tmp_path)
    assert written == 1
    rows = conn.execute("SELECT * FROM observations").fetchall()
    assert len(rows) == 1
    assert rows[0]["source"] == "scopus"
    assert rows[0]["url"] == "https://doi.org/10.1000/abc123"


def test_the_observation_lands_in_the_documents_own_week(tmp_path, conn):
    """A bulk export is backdated by nature: 2026-04-15 is 2026-W16, whatever
    week the export was taken in."""
    write_export(tmp_path)
    manual.import_exports(conn, Watchlist(version=1, technologies=(tech(),)), root=tmp_path)
    assert conn.execute("SELECT week FROM observations").fetchone()["week"] == "2026-W16"


def test_a_licensed_abstract_is_matched_but_never_stored(tmp_path, conn):
    """The abstract is the licensed asset. It decides the match and is then
    dropped: what persists is bibliographic metadata and a DOI."""
    write_export(tmp_path)
    watchlist = Watchlist(version=1, technologies=(tech("dc", "distribution cent(er|re)s?"),))
    assert manual.import_exports(conn, watchlist, root=tmp_path) == 1
    stored = " ".join(
        str(value) for row in conn.execute("SELECT * FROM observations").fetchall()
        for value in tuple(row)
    )
    assert "40 distribution centres" not in stored


def test_importing_twice_does_not_double_count(tmp_path, conn):
    write_export(tmp_path)
    watchlist = Watchlist(version=1, technologies=(tech(),))
    manual.import_exports(conn, watchlist, root=tmp_path)
    manual.import_exports(conn, watchlist, root=tmp_path)
    assert conn.execute("SELECT COUNT(*) AS n FROM observations").fetchone()["n"] == 1


def test_a_missing_root_is_not_an_error(tmp_path, conn):
    assert manual.import_exports(conn, Watchlist(1, (tech(),)), root=tmp_path / "nope") == 0


# --- patents ---------------------------------------------------------------
#
# Captured from a real Lens.org RIS export of 185 US patents granted in
# 2026-Q3. Written against the file rather than the documentation, because a
# fixture built from documentation tests the documentation.

LENS_RIS = """TY  - PAT
CY  - US
M3  - B1
SN  - US 12673822 B1
ID  - 063-505-904-835-801
C2  - 2026/07/07
PY  - 2026
M1  - US 202318339727 A
DA  - 2023/06/22
C1  - 2023/06/22
UR  - https://lens.org/063-505-904-835-801
TI  - Package storage space optimization systems and methods using reconfigurable racks
AU  - MALSHE ROHIT
PB  - AMAZON TECH INC
ER  -
"""


def test_a_patent_is_dated_by_its_grant_not_its_filing():
    """DA is the filing date and runs years before the window that retrieved
    the record -- across a real export it spanned 2017 to 2025 for patents
    granted in one quarter. Keying on it files every patent into a week the
    query never asked about, which is the USAspending failure exactly."""
    record = manual.parse_ris(LENS_RIS)[0]
    assert record["date"] == "2026-07-07"


def test_a_patents_assignee_becomes_its_entity():
    """Who was granted it is the interesting half of a patent."""
    assert manual.parse_ris(LENS_RIS)[0]["venue"] == "AMAZON TECH INC"


def test_a_non_patent_record_still_uses_its_own_date():
    """RIS is shared with the bibliographic databases, where DA is the
    publication date and means what it says."""
    article = manual.parse_ris(
        "TY  - JOUR\nTI  - A paper\nDA  - 2026/05/04\nPY  - 2026\nER  -\n"
    )[0]
    assert article["date"] == "2026-05-04"


# --- patent classification as evidence -------------------------------------
#
# Measured on a real 185-patent export: text matching reached 2 records, and
# reached 11 even with the context gate switched off. Patents describe
# mechanisms while the watchlist speaks trade vocabulary -- an abstract about
# "reconfigurable racks for standardized packages" is warehouse automation and
# never says so. The classification the patent was filed under does say so.

LENS_CSV_HEADER = "Title,Abstract,Publication Date,Applicants,CPC Classifications\n"


def _lens_row(title, abstract, codes, applicant="ACME CORP", date="2026/07/07"):
    return LENS_CSV_HEADER + f'"{title}","{abstract}",{date},"{applicant}","{codes}"\n'


def test_a_specific_classification_attributes_without_the_words():
    """B65G1/137 is storage devices with indicating or control means -- an
    AS/RS. The patent is warehouse automation whether or not it says so."""
    text = _lens_row("Reconfigurable rack system",
                     "Racks may be configured based on expected package mix.",
                     "B65G1/1378; G06Q10/087")
    records = manual.parse_csv(text)
    assert "warehouse_robotics" in manual.classification_evidence("lens", records[0])


def test_a_broad_classification_attributes_nothing():
    """G06Q10/087 is inventory management -- a business domain, not a
    technology. It covered 135 of 185 patents including 'Material conveying
    method' and 'Automated chain of custody tracking'."""
    text = _lens_row("Chain of custody tracking", "Tracking techniques.",
                     "G06Q10/087; G06Q10/083")
    assert manual.classification_evidence("lens", manual.parse_csv(text)[0]) == []


def test_classification_matching_is_by_prefix():
    """A code is a tree. G06K7/10 is a kind of G06K7, and the map names the
    branch rather than every leaf."""
    text = _lens_row("Tag reader", "A reader.", "G06K7/10297")
    assert "item_level_rfid" in manual.classification_evidence("lens", manual.parse_csv(text)[0])


def test_a_source_with_no_classification_map_attributes_nothing():
    assert manual.classification_evidence("scopus", {"classifications": "B65G1/1378"}) == []


def test_every_mapped_technology_exists_in_the_watchlist():
    from observatory import matcher, supplemental
    known = {tech.id for tech in matcher.load_watchlist().active}
    for source in supplemental.load().sources.values():
        for code, tech_id in (source.evidences or {}).items():
            assert tech_id in known, f"{code} maps to unknown {tech_id}"


def test_the_applicant_becomes_the_entity():
    text = _lens_row("A patent", "An abstract.", "B65G1/1378", applicant="AMAZON TECH INC")
    assert manual.parse_csv(text)[0]["venue"] == "AMAZON TECH INC"


def test_classification_evidence_is_recorded_as_the_matched_pattern(tmp_path):
    """A count has to be traceable to what produced it. Here that is a
    classification code, not a regex."""
    export = tmp_path / "lens.csv"
    export.write_text(_lens_row("Rack system", "Racks.", "B65G1/1378"))
    (tmp_path / "lens.csv.meta.yaml").write_text(
        "source: lens\nexported: 2026-08-28\nquery: test\nrecords: 1\n")
    from observatory import matcher, store
    conn = store.connect(":memory:")
    store.init_schema(conn)
    manual.import_exports(conn, matcher.load_watchlist(), tmp_path)
    rows = conn.execute("SELECT tech_id, matched_pattern FROM observations").fetchall()
    assert ("warehouse_robotics", "cpc:B65G1/137") in [(r[0], r[1]) for r in rows]


def test_text_and_classification_evidence_do_not_double_count(tmp_path):
    export = tmp_path / "lens.csv"
    export.write_text(_lens_row(
        "Automated storage and retrieval for a warehouse",
        "An automated storage and retrieval system in a warehouse.", "B65G1/1378"))
    (tmp_path / "lens.csv.meta.yaml").write_text(
        "source: lens\nexported: 2026-08-28\nquery: test\nrecords: 1\n")
    from observatory import matcher, store
    conn = store.connect(":memory:")
    store.init_schema(conn)
    manual.import_exports(conn, matcher.load_watchlist(), tmp_path)
    rows = conn.execute(
        "SELECT COUNT(*) FROM observations WHERE tech_id='warehouse_robotics'").fetchone()
    assert rows[0] == 1
