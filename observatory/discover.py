"""Finding the vocabulary the watchlist is missing.

Discovery reads raw files back through each collector's parser rather than
reading the observations table, because the observations table only holds
documents that already matched something. The interesting terms are in the
documents that matched nothing.

Everything here is deterministic: no model, no randomness, no clock.
"""

from __future__ import annotations

import re

MIN_TOKENS = 2
MAX_TOKENS = 4

STOPWORDS = frozenset("""
a an and are as at be been but by for from has have how in into is it its of on
or over that the their there these this to under up via was were what when
where which who will with without you your our we they he she
""".split())


def normalise(text: str | None) -> list[str]:
    return [token for token in re.split(r"[^0-9a-z]+", (text or "").lower()) if token]


def extract_phrases(text: str | None) -> list[str]:
    """Every 2-to-4 word window that contains no stopword and no bare number.

    Windows never bridge a stopword: "cold chain for frozen goods" yields
    "cold chain" and "frozen goods" but never "chain frozen", which would be a
    phrase no human wrote.
    """
    phrases: list[str] = []
    for run_of_words in _runs(normalise(text)):
        for size in range(MIN_TOKENS, MAX_TOKENS + 1):
            for start in range(len(run_of_words) - size + 1):
                phrases.append(" ".join(run_of_words[start:start + size]))
    return phrases


def _runs(tokens: list[str]) -> list[list[str]]:
    """Split a token list into stretches uninterrupted by stopwords or numbers."""
    runs: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in STOPWORDS or token.isdigit():
            if current:
                runs.append(current)
            current = []
        else:
            current.append(token)
    if current:
        runs.append(current)
    return runs
