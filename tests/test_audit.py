"""Sampling observations so their precision can actually be judged.

Loosening the lexicon at v7 added about 1,100 observations and nobody measured
what it cost. The obstacle is that a GitHub row's stored title is
`owner/repo-name` -- the match happened on the repository description, which is
not in the database at all. Thirty-one percent of the corpus cannot be judged
from `observations`, and reading titles produced a precision estimate that was
wrong in both directions.

The evidence is on disk. Every API source wrote its untouched response body to
`raw/` before anything parsed it, and every hand-made export is still in
`data/manual`. This recovers the text that produced a match so a person can say
whether the match was right.
"""

import json

import pytest

from observatory import audit, config, store


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def test_a_sample_is_reproducible_from_its_seed():
    """A precision figure nobody can re-derive is an anecdote."""
    first = audit.pick(list(range(200)), size=20, seed=7)
    assert first == audit.pick(list(range(200)), size=20, seed=7)
    assert first != audit.pick(list(range(200)), size=20, seed=8)


def test_a_sample_smaller_than_the_population_is_drawn_without_replacement():
    drawn = audit.pick(list(range(50)), size=20, seed=1)
    assert len(drawn) == 20
    assert len(set(drawn)) == 20


def test_asking_for_more_than_exists_returns_everything():
    assert sorted(audit.pick([1, 2, 3], size=99, seed=1)) == [1, 2, 3]


def test_the_sample_is_stratified_across_sources():
    """An unstratified draw would be 30% GitHub and 30% Scopus and tell us
    nothing about the small sources, which are the ones the new work added."""
    population = [{"source": "github"}] * 800 + [{"source": "lens"}] * 80
    drawn = audit.stratify(population, per_stratum=10, key="source", seed=3)
    counts = {}
    for row in drawn:
        counts[row["source"]] = counts.get(row["source"], 0) + 1
    assert counts == {"github": 10, "lens": 10}


def test_a_stratum_smaller_than_the_quota_contributes_all_it_has():
    population = [{"source": "github"}] * 40 + [{"source": "abi_inform"}] * 3
    drawn = audit.stratify(population, per_stratum=10, key="source", seed=3)
    assert sum(1 for row in drawn if row["source"] == "abi_inform") == 3


def test_evidence_carries_the_text_the_match_was_made_on():
    """The whole point. A row whose evidence is just its title is a row nobody
    can judge."""
    record = audit.Evidence(
        source="github", doc_id="github:x/y", tech_id="erp",
        matched_pattern=r"\bERP\b", title="x/y",
        text="A postgres ERP connector for supply chain data", url="https://…")
    assert "ERP" in record.text
    assert record.shown().count("ERP") >= 1


def test_evidence_marks_where_the_pattern_fired():
    """A coder should not have to re-run the regex in their head."""
    record = audit.Evidence(
        source="github", doc_id="d", tech_id="erp", matched_pattern="ERP",
        title="a", text="an ERP migration", url="")
    assert "[[ERP]]" in record.shown()


def test_evidence_with_no_recoverable_text_says_so_rather_than_looking_empty():
    record = audit.Evidence(
        source="github", doc_id="d", tech_id="erp", matched_pattern="ERP",
        title="a", text=None, url="")
    assert "not recovered" in record.shown().lower()


# --- walking back to the raw ------------------------------------------------

def test_a_github_observation_recovers_its_repository_description(conn, tmp_path, monkeypatch):
    """The case the whole module exists for: the title is owner/repo-name and
    the match was made on the description."""
    monkeypatch.setattr(config, "RAW_DIR", tmp_path)
    raw = tmp_path / "2026-W13" / "github"
    raw.mkdir(parents=True)
    page = raw / "000.json"
    page.write_text(json.dumps({"items": [
        {"full_name": "acme/widget", "description": "An ERP connector for warehouses",
         "html_url": "https://github.com/acme/widget"},
    ]}))
    store.record_raw(conn, "github", "2026-W13", "http://x", 200, str(page))
    ref = conn.execute("SELECT id FROM raw_fetch").fetchone()[0]
    _observe(conn, "github", "github:acme/widget", "erp", r"\bERP\b", "acme/widget", ref)
    found = audit.evidence(conn, _rows(conn)[0])
    assert "ERP connector" in found.text


def test_an_arxiv_observation_recovers_its_abstract(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path)
    raw = tmp_path / "2026-W13" / "arxiv"
    raw.mkdir(parents=True)
    page = raw / "000.xml"
    page.write_text(
        '<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
        '<id>http://arxiv.org/abs/2601.001v1</id><title>A paper</title>'
        '<summary>We study digital twins for warehouse operations.</summary>'
        "</entry></feed>")
    store.record_raw(conn, "arxiv", "2026-W13", "http://x", 200, str(page))
    ref = conn.execute("SELECT id FROM raw_fetch").fetchone()[0]
    _observe(conn, "arxiv", "arxiv:http://arxiv.org/abs/2601.001v1",
             "supply_chain_digital_twin", "digital twin(s)?", "A paper", ref)
    assert "warehouse operations" in audit.evidence(conn, _rows(conn)[0]).text


def test_a_manual_observation_recovers_from_its_export(conn, tmp_path, monkeypatch):
    """Scopus, Lens and ABI/INFORM rows have no raw_ref -- their evidence is in
    data/manual, which is just as much a source of truth."""
    monkeypatch.setattr(config, "MANUAL_DIR", tmp_path)
    export = tmp_path / "scopus.ris"
    export.write_text(
        "TY  - JOUR\nTI  - A journal paper\nAB  - On control towers in logistics.\n"
        "DO  - 10.1/abc\nPY  - 2026\nER  -\n")
    (tmp_path / "scopus.ris.meta.yaml").write_text(
        "source: scopus\nexported: 2026-08-29\nquery: q\nrecords: 1\n")
    _observe(conn, "scopus", "scopus:10.1/abc", "control_tower",
             "control tower(s)?", "A journal paper", None)
    assert "control towers" in audit.evidence(conn, _rows(conn)[0]).text


def test_evidence_that_cannot_be_recovered_is_reported_not_invented(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path)
    monkeypatch.setattr(config, "MANUAL_DIR", tmp_path)
    _observe(conn, "github", "github:gone/missing", "erp", "ERP", "gone/missing", None)
    assert audit.evidence(conn, _rows(conn)[0]).text is None


def _observe(conn, source, doc_id, tech_id, pattern, title, raw_ref):
    conn.execute(
        "INSERT INTO observations (source, week, tech_id, doc_id, doc_date, title, "
        "url, entity, entity_id, amount, lat, lon, matched_pattern, raw_ref) "
        "VALUES (?, '2026-W13', ?, ?, '2026-03-25', ?, '', NULL, NULL, NULL, "
        "NULL, NULL, ?, ?)",
        (source, tech_id, doc_id, title, pattern, raw_ref))
    conn.commit()


def _rows(conn):
    return [dict(row) for row in conn.execute("SELECT * FROM observations")]
