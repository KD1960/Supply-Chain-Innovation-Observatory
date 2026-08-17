"""Finding the vocabulary the watchlist is missing.

Discovery reads raw files back through each collector's parser rather than
reading the observations table, because the observations table only holds
documents that already matched something. The interesting terms are in the
documents that matched nothing.

Everything here is deterministic: no model, no randomness, no clock.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass

from . import config
from .collectors import base

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


MIN_COUNT = 5
MIN_RATIO = 3.0
BASELINE_WEEKS = 12
MAX_EXAMPLES = 3
MAX_CANDIDATES = 25


@dataclass(frozen=True)
class Candidate:
    term: str
    count: int
    baseline: float
    ratio: float
    examples: list[tuple[str, str]]


@dataclass(frozen=True)
class RisingTerms:
    """A review queue, not a data dump: `candidates` is capped at
    `MAX_CANDIDATES` so a human can actually read it. `total` discloses how
    many qualified before the cap, so a truncated list never quietly passes
    itself off as the whole picture."""
    candidates: list[Candidate]
    total: int


def _documents_for_week(week: str, collectors) -> list:
    """Every document fetched for a week, matched or not, re-parsed from raw."""
    documents = []
    for collector in collectors:
        for path, text in base.read_raw(collector.name, week):
            try:
                documents.extend(collector.parse(text))
            except Exception as error:  # a poisoned raw file must not stop discovery
                print(f"  ! discover: {collector.name} failed to parse {path}: {error}",
                      file=sys.stderr)
                continue
    return documents


def week_phrase_counts(week: str, collectors) -> Counter:
    counts: Counter = Counter()
    for document in _documents_for_week(week, collectors):
        counts.update(set(extract_phrases(document.title)))
    return counts


def _already_covered(watchlist, term: str) -> bool:
    """Whether an active technology's own pattern already covers this term.

    Deliberately bypasses `Watchlist.match`'s `needs_context` gate. That gate
    answers a different question — whether a *document* counts, given its
    full text may or may not mention the field this project cares about — and
    a short 2-to-4 word candidate phrase essentially never carries both a
    technology's vocabulary and a separate context word in the same string.
    Routing through `match` would make this check silently fail for every
    context-gated technology, so it goes straight to the compiled include and
    exclude patterns instead.
    """
    for tech in watchlist.active:
        if any(pattern.search(term) for pattern in tech.exclude_res):
            continue
        if any(pattern.search(term) for pattern in tech.include_res):
            return True
    return False


def detect_rising(week: str, collectors, watchlist) -> RisingTerms:
    """Phrases spiking against their own trailing baseline that nothing matches yet.

    Capped at `MAX_CANDIDATES`, ratio descending, with the full qualifying
    count carried alongside so a truncated list is visibly truncated.
    """
    current = week_phrase_counts(week, collectors)
    if not current:
        return RisingTerms(candidates=[], total=0)

    history: Counter = Counter()
    baseline_weeks = config.trailing_weeks(config.week_offset(week, -1), BASELINE_WEEKS)
    for past in baseline_weeks:
        history.update(week_phrase_counts(past, collectors))

    qualifying = []
    for term, count in current.items():
        if count < MIN_COUNT:
            continue
        baseline = history[term] / len(baseline_weeks)
        ratio = count / baseline if baseline else float(count)
        if ratio < MIN_RATIO:
            continue
        if _already_covered(watchlist, term):
            continue
        qualifying.append((term, count, round(baseline, 3), round(ratio, 2)))

    # Rank and cut first, then look up examples. Finding a term's examples
    # re-phrases every document in the week, and on live data all but the
    # twenty-five surviving terms' examples were thrown away -- about ten
    # times the work for the same answer.
    qualifying.sort(key=lambda row: (-row[3], row[0]))
    documents = _documents_for_week(week, collectors)
    candidates = [
        Candidate(term=term, count=count, baseline=baseline, ratio=ratio,
                  examples=_examples(documents, term))
        for term, count, baseline, ratio in qualifying[:MAX_CANDIDATES]
    ]
    return RisingTerms(candidates=candidates, total=len(qualifying))


def _examples(documents, term: str) -> list[tuple[str, str]]:
    found = []
    for document in documents:
        if term in extract_phrases(document.title):
            found.append((document.title, document.url))
            if len(found) == MAX_EXAMPLES:
                break
    return found
