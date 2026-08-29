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


# --- document identity -----------------------------------------------------
#
# A real Lens export of 185 patents produced 183 distinct doc_ids. Patents carry
# no DOI, so identity fell back to the first 120 characters of the title, and
# two pairs of genuinely different patents shared one -- a continuation and its
# parent are routinely filed under the same words. Two rows became one and
# nothing said so. Nineteen of the titles were longer than the truncation, so
# the collision rate was not going to stay at two.


def test_two_records_sharing_a_title_stay_two_documents():
    same_title = (
        "Title,Abstract,Publication Date,Applicants,CPC Classifications,Lens ID\n"
        '"Shelving structure","A.",2026/07/07,"A CORP","B65G1/1378",063-505-904-835-801\n'
        '"Shelving structure","B.",2026/07/14,"B CORP","B65G1/1378",151-191-575-003-57X\n'
    )
    records = manual.parse_csv(same_title)
    assert len({manual.document_id("lens", r) for r in records}) == 2


def test_a_record_identifier_is_preferred_over_the_title():
    record = {"doi": "", "title": "A patent", "identifier": "063-505-904-835-801"}
    assert manual.document_id("lens", record) == "lens:063-505-904-835-801"


def test_a_doi_is_preferred_over_a_title_when_there_is_no_identifier():
    record = {"doi": "10.1000/xyz", "title": "A paper", "identifier": ""}
    assert manual.document_id("scopus", record) == "scopus:10.1000/xyz"


def test_a_record_with_only_a_title_still_gets_an_identity():
    record = {"doi": "", "title": "A paper with no identifiers at all", "identifier": ""}
    assert manual.document_id("scopus", record).startswith("scopus:A paper")


def test_the_real_export_keeps_every_record_distinct():
    """The regression this exists to catch, measured against the actual file."""
    from pathlib import Path
    export = Path("data/manual/2026-Q3/lens-export-supplychaininnovation.csv")
    if not export.exists():
        return
    records = manual.parse_csv(export.read_text(errors="replace"))
    assert len({manual.document_id("lens", r) for r in records}) == len(records)


# --- dates a bibliographic export does not carry ---------------------------

SCOPUS_RIS = """TY  - JOUR
TI  - A paper about warehouse robotics
AB  - Autonomous mobile robots in a warehouse.
PY  - 2026
DO  - 10.1000/aaa
T2  - Journal of Operations Management
ER  -
"""


def test_a_year_only_record_takes_its_date_from_the_resolver():
    """Scopus RIS carries PY and nothing else, and PY is the issue year: 12% of
    a 40-DOI sample stamped 2026 were published in 2025. Left alone, 2,607
    records landed on January 1st."""
    records = manual.parse_ris(SCOPUS_RIS)
    enriched = manual.with_resolved_dates(records, {"10.1000/aaa": "2025-02-10"})
    assert enriched[0]["date"] == "2025-02-10"


def test_a_record_the_resolver_cannot_place_is_dropped_not_dated_to_january():
    records = manual.parse_ris(SCOPUS_RIS)
    enriched = manual.with_resolved_dates(records, {"10.1000/aaa": None})
    assert enriched == []


def test_a_record_that_already_has_a_real_date_is_left_alone():
    """A patent's grant date came from the file and needs no lookup."""
    dated = manual.parse_ris(
        "TY  - PAT\nTI  - A patent\nC2  - 2026/07/07\nDA  - 2023/01/01\nER  -\n")
    enriched = manual.with_resolved_dates(dated, {})
    assert enriched[0]["date"] == "2026-07-07"


def test_only_year_only_records_are_sent_to_the_resolver():
    """2,607 lookups is worth not making twice, and a record that already knows
    its day has nothing to gain."""
    records = manual.parse_ris(SCOPUS_RIS) + manual.parse_ris(
        "TY  - PAT\nTI  - A patent\nC2  - 2026/07/07\nDO  - 10.1000/bbb\nER  -\n")
    assert manual.dois_needing_dates(records) == ["10.1000/aaa"]


def test_a_year_only_record_with_no_doi_cannot_be_placed():
    records = manual.parse_ris("TY  - JOUR\nTI  - A paper\nPY  - 2026\nER  -\n")
    assert manual.dois_needing_dates(records) == []
    assert manual.with_resolved_dates(records, {}) == []


# --- ProQuest -------------------------------------------------------------
#
# Captured from a real ABI/INFORM export. ProQuest names its fields differently
# from every other RIS producer: the publication is JF rather than T2, the date
# is Y1 in slash form while DA carries an unparseable "2026 Aug 27", and there
# is no abstract at all -- only indexer-assigned subject terms.

PROQUEST_RIS = """TY  - JOUR
T1  - Amazon to expand drone delivery reach sixfold this year
AN  - 3379430251
JF  - Supply Chain Dive
AU  - Garland, Max
Y1  - 2026/08/27/
PY  - 2026
DA  - 2026 Aug 27
PB  - Industry Dive
KW  - Supply chains
KW  - Logistics
KW  - Postal & delivery services
UR  - https://www.proquest.com/docview/3379430251
ER  -
"""


def test_a_proquest_record_is_dated_from_its_slash_form_date():
    """DA reads "2026 Aug 27", which no ISO parser will take, so every record
    fell back to the bare year and landed on January 1st."""
    assert manual.parse_ris(PROQUEST_RIS)[0]["date"] == "2026-08-27"


def test_the_publication_becomes_the_venue():
    """ProQuest uses JF where the bibliographic databases use T2, so every
    record in a real export carried an empty publication."""
    assert manual.parse_ris(PROQUEST_RIS)[0]["venue"] == "Supply Chain Dive"


def test_subject_terms_are_kept_for_matching():
    """There is no abstract in a ProQuest trade export. The subject terms are
    the only thing besides the title that says what the article is about, and
    including them took the match rate on a real export from 4 of 36 to 9."""
    record = manual.parse_ris(PROQUEST_RIS)[0]
    assert "Logistics" in record["keywords"]
    assert "Postal & delivery services" in record["keywords"]


def test_the_haystack_includes_the_subject_terms():
    record = manual.parse_ris(PROQUEST_RIS)[0]
    assert "Logistics" in manual.haystack(record)
    assert "Amazon to expand drone delivery" in manual.haystack(record)


def test_a_proquest_record_is_not_treated_as_year_only():
    """Y1 gives a real day, so this record needs no Crossref lookup."""
    records = manual.parse_ris(PROQUEST_RIS)
    assert records[0]["year_only"] is False
    assert manual.dois_needing_dates(records) == []


def test_the_accession_number_is_the_document_identity():
    assert manual.document_id("abi_inform", manual.parse_ris(PROQUEST_RIS)[0]) == \
        "abi_inform:3379430251"


def test_a_monthly_publications_date_becomes_the_first_of_that_month():
    """Y1 of "2026/08//" is what a monthly carries. Five Modern Materials
    Handling records fell through to January on it."""
    assert manual.parse_ris(
        "TY  - JOUR\nT1  - A\nY1  - 2026/08//\nPY  - 2026\nER  -\n")[0]["date"] == "2026-08-01"


def test_a_bimonthly_issue_takes_the_first_month_of_its_range():
    """Y1 of "2026///Jul/Aug" is a two-month issue. Its first month is a
    visible approximation; January is a fabrication."""
    assert manual.parse_ris(
        "TY  - JOUR\nT1  - A\nY1  - 2026///Jul/Aug\nPY  - 2026\nER  -\n")[0]["date"] == "2026-07-01"


def test_a_year_only_y1_is_still_year_only():
    """The academic records carry Y1 of "2026" and nothing more. They need the
    resolver like any other year-only record."""
    record = manual.parse_ris(
        "TY  - JOUR\nT1  - A\nY1  - 2026\nPY  - 2026\nDO  - 10.1/x\nER  -\n")[0]
    assert record["year_only"] is True


# --- exports that are the same export ---------------------------------------
#
# Four ABI/INFORM files arrived holding 182 records between them and 52
# distinct ones: each was a superset of the last, the signature of exporting a
# marked-items list that kept growing rather than each query's own result. The
# importer deduplicates by accession number, so it would have written 52 rows
# and said nothing, leaving a quarter that looks four-publications-wide and is
# one.


def _export(tmp_path, name, ids):
    body = "".join(
        f"TY  - JOUR\nT1  - Article {i}\nAN  - {i}\nJF  - A Journal\n"
        f"Y1  - 2026/07/01/\nER  -\n" for i in ids)
    (tmp_path / name).write_text(body)
    (tmp_path / f"{name}.meta.yaml").write_text(
        f"source: abi_inform\nexported: 2026-08-29\nquery: q\nrecords: {len(ids)}\n")


def test_two_exports_of_the_same_records_are_refused(tmp_path):
    _export(tmp_path, "a.ris", range(1, 41))
    _export(tmp_path, "b.ris", range(1, 51))
    with pytest.raises(manual.ExportProblem) as raised:
        manual.read_exports(tmp_path)
    message = str(raised.value).lower()
    assert "adds nothing" in message or "one result set" in message


def test_term_batches_of_one_publication_may_overlap(tmp_path):
    """A term batch is a slice of the *query*, not of the corpus. An article
    containing terms from two batches appears in both, and with a two-record
    batch that is 100% containment -- which the first version of this guard
    refused outright."""
    _export(tmp_path, "terms1.ris", [1, 2])
    _export(tmp_path, "terms2.ris", [1, 2, 3, 4, 5, 6, 7, 8])
    _export(tmp_path, "terms3.ris", [9, 10, 11, 12])
    assert len(manual.read_exports(tmp_path)) == 3


def test_files_that_add_nothing_to_each_other_are_still_refused(tmp_path):
    """The accumulation case: every file inside the largest, so the whole set
    is worth exactly one export however many files it holds."""
    _export(tmp_path, "a.ris", range(1, 20))
    _export(tmp_path, "b.ris", range(1, 30))
    _export(tmp_path, "c.ris", range(1, 40))
    with pytest.raises(manual.ExportProblem):
        manual.read_exports(tmp_path)


def test_exports_of_genuinely_different_slices_are_accepted(tmp_path):
    _export(tmp_path, "a.ris", range(1, 41))
    _export(tmp_path, "b.ris", range(100, 140))
    assert len(manual.read_exports(tmp_path)) == 2


def test_a_little_overlap_between_slices_is_tolerated(tmp_path):
    """Two publications can carry the same syndicated story."""
    _export(tmp_path, "a.ris", range(1, 41))
    _export(tmp_path, "b.ris", range(38, 78))
    assert len(manual.read_exports(tmp_path)) == 2


def test_the_refusal_gives_the_numbers_and_names_the_largest_file(tmp_path):
    """A refusal a person cannot act on is an obstacle. It has to say how many
    files, how many records, how many distinct, and which file already held
    them all."""
    _export(tmp_path, "scd.ris", range(1, 41))
    _export(tmp_path, "mmh.ris", range(1, 51))
    with pytest.raises(manual.ExportProblem) as raised:
        manual.read_exports(tmp_path)
    message = str(raised.value)
    assert "mmh.ris" in message
    assert "90" in message and "50" in message
