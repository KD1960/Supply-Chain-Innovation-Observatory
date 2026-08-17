from observatory import discover


def test_normalise_lowercases_and_splits_on_non_letters():
    assert discover.normalise("Autonomous-Trucking, at scale!") == [
        "autonomous", "trucking", "at", "scale"
    ]


def test_extract_phrases_returns_two_to_four_word_windows():
    phrases = discover.extract_phrases("humanoid warehouse picking robots")
    assert "humanoid warehouse" in phrases
    assert "humanoid warehouse picking" in phrases
    assert "humanoid warehouse picking robots" in phrases
    assert "humanoid" not in phrases, "single words are too noisy to be candidates"


def test_extract_phrases_rejects_windows_containing_a_stopword():
    phrases = discover.extract_phrases("robots in the warehouse")
    assert phrases == [], "every window here spans a stopword"


def test_extract_phrases_spans_stopwords_without_bridging_them():
    phrases = discover.extract_phrases("cold chain for frozen goods")
    assert "cold chain" in phrases
    assert "frozen goods" in phrases
    assert "chain frozen" not in phrases, "a phrase must not bridge a stopword"


def test_extract_phrases_drops_pure_numbers():
    assert discover.extract_phrases("2026 2027 forecast") == []


def test_extract_phrases_is_deterministic():
    text = "automated storage and retrieval systems for cold chain logistics"
    assert discover.extract_phrases(text) == discover.extract_phrases(text)


def test_extract_phrases_handles_empty_and_none():
    assert discover.extract_phrases("") == []
    assert discover.extract_phrases(None) == []


def test_stopwords_cover_the_obvious_connectives():
    for word in ("the", "a", "of", "for", "and", "in", "on", "with", "to"):
        assert word in discover.STOPWORDS


import json
from collections import Counter

import pytest

from observatory.collectors.base import BaseCollector, Document, RawPage
from observatory.matcher import Technology, Watchlist


class FakeCollector(BaseCollector):
    """Serves canned documents per week without touching the network or disk."""

    name = "fake"

    def __init__(self, by_week):
        self._by_week = by_week

    def documents_for(self, week):
        return self._by_week.get(week, [])


@pytest.fixture()
def watchlist():
    return Watchlist(
        version=1,
        technologies=(
            Technology(id="cold_chain_iot", name="Cold chain IoT", family="physical",
                       include=("cold chain monitoring",), exclude=(), status="active",
                       added_week="2020-W01", patterns_changed_week="2020-W01"),
        ),
        context=("logistics",),
    )


def documents(*titles):
    return [Document(doc_id=f"d{i}", date="2026-08-12", title=title, text="",
                     url=f"https://x.test/{i}") for i, title in enumerate(titles)]


def test_detect_rising_surfaces_a_term_that_spikes(monkeypatch, watchlist):
    weeks = {"2026-W33": documents(*["dark factory retrofit"] * 6)}
    for week in config_weeks_before("2026-W33", 12):
        weeks[week] = documents("unrelated shipping news")
    collector = FakeCollector(weeks)
    monkeypatch.setattr(discover, "_documents_for_week", lambda week, collectors: collector.documents_for(week))

    rising = discover.detect_rising("2026-W33", [collector], watchlist)
    terms = {candidate.term for candidate in rising.candidates}
    assert "dark factory" in terms


def test_detect_rising_ignores_a_term_the_watchlist_already_matches(monkeypatch, watchlist):
    weeks = {"2026-W33": documents(*["cold chain monitoring rollout"] * 8)}
    for week in config_weeks_before("2026-W33", 12):
        weeks[week] = []
    collector = FakeCollector(weeks)
    monkeypatch.setattr(discover, "_documents_for_week", lambda week, collectors: collector.documents_for(week))

    terms = {c.term for c in discover.detect_rising("2026-W33", [collector], watchlist).candidates}
    assert "cold chain monitoring" not in terms


def test_detect_rising_requires_the_minimum_count(monkeypatch, watchlist):
    weeks = {"2026-W33": documents(*["dark factory retrofit"] * 2)}
    for week in config_weeks_before("2026-W33", 12):
        weeks[week] = []
    collector = FakeCollector(weeks)
    monkeypatch.setattr(discover, "_documents_for_week", lambda week, collectors: collector.documents_for(week))
    rising = discover.detect_rising("2026-W33", [collector], watchlist)
    assert rising.candidates == []
    assert rising.total == 0


def test_detect_rising_requires_the_minimum_ratio(monkeypatch, watchlist):
    weeks = {"2026-W33": documents(*["dark factory retrofit"] * 6)}
    for week in config_weeks_before("2026-W33", 12):
        weeks[week] = documents(*["dark factory retrofit"] * 6)
    collector = FakeCollector(weeks)
    monkeypatch.setattr(discover, "_documents_for_week", lambda week, collectors: collector.documents_for(week))
    rising = discover.detect_rising("2026-W33", [collector], watchlist)
    assert rising.candidates == []
    assert rising.total == 0


def test_candidates_carry_example_documents(monkeypatch, watchlist):
    weeks = {"2026-W33": documents(*[f"dark factory retrofit {n}" for n in range(6)])}
    for week in config_weeks_before("2026-W33", 12):
        weeks[week] = []
    collector = FakeCollector(weeks)
    monkeypatch.setattr(discover, "_documents_for_week", lambda week, collectors: collector.documents_for(week))

    rising = {c.term: c for c in discover.detect_rising("2026-W33", [collector], watchlist).candidates}
    examples = rising["dark factory"].examples
    assert 1 <= len(examples) <= discover.MAX_EXAMPLES
    assert all(title and url for title, url in examples)


def test_detect_rising_caps_the_result_and_reports_the_full_total(monkeypatch, watchlist):
    """40 distinct terms qualify; only MAX_CANDIDATES may come back, and they
    must be the highest-ratio ones, with `total` disclosing the true count."""
    term_count = discover.MAX_CANDIDATES + 15
    titles = []
    for index in range(term_count):
        titles.extend([f"widget{index:02d} spike"] * (discover.MIN_COUNT + index))
    weeks = {"2026-W33": documents(*titles)}
    for week in config_weeks_before("2026-W33", 12):
        weeks[week] = []
    collector = FakeCollector(weeks)
    monkeypatch.setattr(discover, "_documents_for_week", lambda week, collectors: collector.documents_for(week))

    rising = discover.detect_rising("2026-W33", [collector], watchlist)

    assert rising.total == term_count
    assert len(rising.candidates) == discover.MAX_CANDIDATES
    expected_top_terms = {
        f"widget{index:02d} spike"
        for index in range(term_count - discover.MAX_CANDIDATES, term_count)
    }
    assert {c.term for c in rising.candidates} == expected_top_terms


def config_weeks_before(week, count):
    from observatory import config
    return config.trailing_weeks(config.week_offset(week, -1), count)
