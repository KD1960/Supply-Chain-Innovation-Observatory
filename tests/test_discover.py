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
