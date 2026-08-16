import textwrap

import pytest

from observatory import matcher


@pytest.fixture()
def watchlist(tmp_path):
    path = tmp_path / "watchlist.yaml"
    path.write_text(textwrap.dedent("""
        lexicon_version: 1
        technologies:
          - id: autonomous_trucking
            name: Autonomous trucking
            family: vehicles
            include:
              - "autonomous truck(s|ing)?"
              - "driverless truck"
            exclude:
              - "autonomous trucking bill"
            status: active
            added_week: 2026-W33
            patterns_changed_week: 2026-W33
          - id: warehouse_robotics
            name: Warehouse robotics
            family: automation
            include:
              - "warehouse robot(s|ics)?"
            exclude: []
            status: active
            added_week: 2026-W33
            patterns_changed_week: 2026-W33
          - id: retired_thing
            name: Retired thing
            family: automation
            include:
              - "retired thing"
            exclude: []
            status: retired
            added_week: 2026-W33
            patterns_changed_week: 2026-W33
    """))
    return matcher.load_watchlist(path)


class FakeDocument:
    def __init__(self, title, text=""):
        self.doc_id = "doc-1"
        self.date = "2026-08-12"
        self.title = title
        self.text = text
        self.url = "https://example.test/doc-1"
        self.entity = None
        self.entity_id = None
        self.amount = None
        self.lat = None
        self.lon = None


def test_load_watchlist_reads_version_and_active_entries(watchlist):
    assert watchlist.version == 1
    assert [tech.id for tech in watchlist.active] == [
        "autonomous_trucking", "warehouse_robotics"
    ]


def test_include_pattern_matches_case_insensitively(watchlist):
    assert watchlist.match("Autonomous Trucking pilot expands") == [
        ("autonomous_trucking", "autonomous truck(s|ing)?")
    ]


def test_exclude_pattern_vetoes_the_document(watchlist):
    assert watchlist.match("The autonomous trucking bill passed the senate") == []


def test_word_boundaries_prevent_substring_matches(watchlist):
    assert watchlist.match("semiautonomous truckload brokerage") == []


def test_one_document_can_match_two_technologies(watchlist):
    hits = watchlist.match("Warehouse robots meet driverless truck yards")
    assert sorted(tech_id for tech_id, _ in hits) == [
        "autonomous_trucking", "warehouse_robotics"
    ]


def test_a_technology_matches_at_most_once_per_document(watchlist):
    hits = watchlist.match("autonomous truck and autonomous trucking and driverless truck")
    assert len(hits) == 1


def test_retired_technologies_never_match(watchlist):
    assert watchlist.match("a retired thing appeared") == []


def test_observations_carry_document_fields_and_matched_pattern(watchlist):
    document = FakeDocument("Warehouse robotics rollout")
    rows = matcher.observations_for_document(
        watchlist, document, source="arxiv", week="2026-W33", raw_ref=7
    )
    assert len(rows) == 1
    observation = rows[0]
    assert observation.tech_id == "warehouse_robotics"
    assert observation.source == "arxiv"
    assert observation.week == "2026-W33"
    assert observation.doc_date == "2026-08-12"
    assert observation.url == "https://example.test/doc-1"
    assert observation.matched_pattern == "warehouse robot(s|ics)?"
    assert observation.raw_ref == 7


def test_matching_searches_title_and_body(watchlist):
    document = FakeDocument("An unrelated title", "buried mention of driverless truck fleets")
    rows = matcher.observations_for_document(
        watchlist, document, source="arxiv", week="2026-W33", raw_ref=1
    )
    assert [row.tech_id for row in rows] == ["autonomous_trucking"]


def test_shipped_watchlist_loads_and_every_pattern_compiles():
    real = matcher.load_watchlist()
    assert real.version >= 1
    assert len(real.active) >= 30
    assert len({tech.id for tech in real.technologies}) == len(real.technologies)
    for tech in real.technologies:
        assert tech.include, f"{tech.id} has no include patterns"
        assert len(tech.include_res) == len(tech.include)
        assert len(tech.exclude_res) == len(tech.exclude)


def test_shipped_watchlist_matches_an_obvious_headline():
    real = matcher.load_watchlist()
    hits = dict(real.match("Aurora expands its driverless truck lanes in Texas"))
    assert "autonomous_trucking" in hits
