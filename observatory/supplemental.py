"""Queries for the sources a human fetches.

Four of this project's sources cannot be automated: they sit behind
institutional authentication and their licences forbid systematic download.
What they allow is a person running a search and exporting the result.

That leaves a judgement in the loop unless the query itself is generated. This
module generates it. The person copies a string and clicks export; they never
decide whether a document is relevant, because the matcher does that afterwards
exactly as it does for every API source.

The registry lives in `sources.yaml` rather than here because the query syntax
is the one thing nobody can verify without an account, and correcting a
template should not need a code change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import config, quarter

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "sources.yaml"

# Placeholders every query may use, on top of the lists declared in the file.
PERIOD_KEYS = ("start", "end")
# Built from watchlist.yaml rather than from the registry, so a lexicon edit
# reaches the trade press query without anybody remembering to copy it across.
WATCHLIST_KEY = "watchlist_terms"


class RegistryProblem(Exception):
    """A registry that would emit a query nobody asked for."""


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    family: str
    signal: str
    stage: str
    format: str
    query: str
    note: str = ""


@dataclass(frozen=True)
class Registry:
    version: int
    sources: dict[str, Source]
    lists: dict[str, dict]


def load(path: Path | None = None) -> Registry:
    raw = yaml.safe_load((path or REGISTRY_PATH).read_text()) or {}
    sources = {
        source_id: Source(id=source_id, **entry)
        for source_id, entry in (raw.get("sources") or {}).items()
    }
    return Registry(version=int(raw.get("version", 0)), sources=sources,
                    lists=raw.get("lists") or {})


def _rendered_lists(registry: Registry) -> dict[str, str]:
    return {
        name: spec.get("join", " OR ").join(
            spec.get("each", "{}").replace("{}", str(item)) for item in spec.get("items", [])
        )
        for name, spec in registry.lists.items()
    }


# A query has to fit in the database's search box. The first attempt emitted 150
# terms, which is both too long and mostly spelling variants. One phrase per
# technology is 50 today; this cap is a guard against a lexicon that grows past
# what ProQuest will accept, and print_queries says out loud when it bites.
MAX_TERMS = 60

# Constructs with no phrase equivalent. A pattern containing one is dropped
# whole rather than stripped, because stripping leaves the debris behind --
# `.{0,80}` becomes "0,80", which reads as part of the phrase and matches
# nothing.
UNEXPANDABLE = re.compile(
    r"\{\d"        # any brace quantifier, including `[^.]{0,30}` proximity
    r"|\[\^"       # a negated character class
    r"|\(\?"       # lookarounds and other extension groups
    r"|\.\*|\.\+|\."   # a wildcard has no phrase equivalent
    r"|\\d|\\w|\\s"
)

# One pattern must not become a hundred phrases.
MAX_EXPANSIONS = 8


def _expand(pattern: str) -> list[str]:
    """Every literal string a simple pattern can match.

    Handles the three constructs the lexicon actually uses -- an alternation
    group, an optional suffix, and a character class of separators -- and
    nothing else. Anything richer is the caller's problem to reject.
    """
    results = [""]
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "(":
            depth, close = 1, index + 1
            while close < len(pattern) and depth:
                depth += (pattern[close] == "(") - (pattern[close] == ")")
                close += 1
            close -= 1
            options = _split_alternatives(pattern[index + 1:close])
            optional = close + 1 < len(pattern) and pattern[close + 1] == "?"
            branches = [b for option in options for b in _expand(option)]
            if optional:
                branches = [""] + branches
            results = [prefix + branch for prefix in results for branch in branches]
            index = close + 2 if optional else close + 1
        elif char == "[":
            close = pattern.index("]", index)
            options = list(pattern[index + 1:close].replace("-", "-"))
            optional = close + 1 < len(pattern) and pattern[close + 1] == "?"
            if optional:
                options = [""] + options
            results = [prefix + option for prefix in results for option in options]
            index = close + 2 if optional else close + 1
        elif char == "\\":
            index += 2                      # \b and friends contribute nothing
        elif index + 1 < len(pattern) and pattern[index + 1] == "?":
            results = [prefix + suffix for prefix in results for suffix in ("", char)]
            index += 2
        else:
            results = [prefix + char for prefix in results]
            index += 1
        if len(results) > MAX_EXPANSIONS:
            return []
    return results


def _split_alternatives(body: str) -> list[str]:
    parts, depth, current = [], 0, ""
    for char in body:
        if char == "|" and depth == 0:
            parts.append(current); current = ""; continue
        depth += (char == "(") - (char == ")")
        current += char
    parts.append(current)
    return parts


def phrases_for(pattern: str) -> list[str]:
    """The literal phrases a watchlist pattern stands for, or nothing.

    Nothing is the right answer for a pattern built around proximity or a
    lookbehind: those say something a phrase search cannot say, and a phrase
    that pretends otherwise is worse than a missing one.
    """
    if UNEXPANDABLE.search(pattern.replace("\\b", "")):
        return []
    seen: list[str] = []
    for candidate in _expand(pattern):
        phrase = " ".join(candidate.split())
        if len(phrase) >= 3 and phrase not in seen:
            seen.append(phrase)
    return seen


def _best_phrase(tech) -> str | None:
    """The one phrase that stands for this technology.

    The first `include` pattern that yields anything wins, because the lexicon
    author writes the canonical term first and the rest are synonyms. Within
    that pattern the longest expansion wins: "warehouse robot" is a prefix of
    "warehouse robotics" and retrieves everything it does plus a good deal it
    should not.

    Taking the longest across every pattern instead gave warehouse robotics the
    phrase "automated storage and retrieval" -- a real term, for a different
    thing.
    """
    for pattern in tech.include:
        candidates = phrases_for(pattern)
        if candidates:
            return max(candidates, key=lambda phrase: (len(phrase), phrase))
    return None


def watchlist_phrases(watchlist) -> list[str]:
    """One phrase per technology, in watchlist order.

    Ranking all expansions by length spent the budget on spelling variants --
    "optimisation" and "optimization" taking two of forty slots while warehouse
    robotics fell out at rank 193. Coverage of the watchlist is worth more than
    coverage of a technology's synonyms.
    """
    phrases: list[str] = []
    for tech in watchlist.active:
        phrase = _best_phrase(tech)
        if phrase and phrase.lower() not in {p.lower() for p in phrases}:
            phrases.append(phrase)
    return phrases


def unphrasable(watchlist) -> list[str]:
    """Technologies no phrase search can reach.

    A technology defined only by proximity -- computer vision within eighty
    characters of a warehouse word -- says something a phrase cannot say. It is
    absent from the trade press query, and that is a hole in coverage rather
    than a rounding error, so the sheet names it.
    """
    return [tech.id for tech in watchlist.active if _best_phrase(tech) is None]


def watchlist_terms(watchlist, join: str = " OR ") -> str:
    kept = watchlist_phrases(watchlist)[:MAX_TERMS]
    return join.join(f'"{phrase}"' for phrase in kept)


def render(template: str, values: dict[str, str], period: str) -> str:
    """Substitute every placeholder, or refuse.

    A half-substituted query pasted into a database still returns something,
    and that something is not what anybody asked for.
    """
    start, end = period_bounds(period)
    available = dict(values, start=start, end=end)
    missing = [
        name for name in re.findall(r"\{(\w+)\}", template) if name not in available
    ]
    if missing:
        raise RegistryProblem(
            f"query references {', '.join(sorted(set(missing)))}, which is neither "
            f"a list in {REGISTRY_PATH.name} nor a period date"
        )
    for name, value in available.items():
        template = template.replace("{" + name + "}", value)
    return " ".join(template.split())


def period_bounds(period: str) -> tuple[str, str]:
    """The calendar dates a period covers, taken from its ISO weeks.

    The weeks are the authority, not the calendar quarter, because that is what
    the rest of the pipeline files documents into. A quarter's first Monday can
    fall in the previous month, and an export cut to calendar month boundaries
    would miss the days between.
    """
    weeks = quarter.weeks_in_period(period)
    start, _ = config.week_bounds(weeks[0])
    _, end = config.week_bounds(weeks[-1])
    return start.isoformat(), end.isoformat()


def build_query(source_id: str, period: str, watchlist, registry: Registry | None = None) -> str:
    registry = registry or load()
    if source_id not in registry.sources:
        raise RegistryProblem(f"unknown source {source_id!r}")
    values = _rendered_lists(registry)
    values[WATCHLIST_KEY] = watchlist_terms(watchlist)
    return render(registry.sources[source_id].query, values, period)


def export_queries(period: str, watchlist, registry: Registry | None = None,
                   only: str | None = None) -> list[dict]:
    registry = registry or load()
    if only and only not in registry.sources:
        raise RegistryProblem(
            f"unknown source {only!r}; the registry holds "
            f"{', '.join(sorted(registry.sources))}"
        )
    wanted = [registry.sources[only]] if only else list(registry.sources.values())
    start, end = period_bounds(period)
    return [
        {
            "source": source.id, "name": source.name, "family": source.family,
            "format": source.format, "note": " ".join((source.note or "").split()),
            "period": period, "start": start, "end": end,
            "registry_version": registry.version,
            "lexicon_version": watchlist.version,
            "query": build_query(source.id, period, watchlist, registry),
        }
        for source in wanted
    ]


def print_queries(period: str, watchlist, registry: Registry | None = None,
                  only: str | None = None) -> None:
    """The sheet a person works from.

    It carries everything the sidecar will demand, because an export whose
    query nobody recorded cannot be reproduced, and an export that cannot be
    reproduced is not evidence.
    """
    entries = export_queries(period, watchlist, registry, only)
    print(f"\nSupplemental exports for {period}  "
          f"(registry v{entries[0]['registry_version']}, "
          f"lexicon v{entries[0]['lexicon_version']})")
    print(f"Covering {entries[0]['start']} to {entries[0]['end']}, "
          f"by ISO week rather than calendar month.\n")
    for entry in entries:
        print("=" * 78)
        print(f"{entry['name']}   [{entry['family']} evidence, export as {entry['format'].upper()}]")
        if entry["note"]:
            print(f"  {entry['note']}")
        print(f"\n  QUERY -- paste verbatim:\n\n{entry['query']}\n")
        print(f"  Save the export to: data/manual/{period}/{entry['source']}.{entry['format']}")
        print(f"  Beside it write:    data/manual/{period}/{entry['source']}."
              f"{entry['format']}.meta.yaml\n")
        print(f"      source: {entry['source']}")
        print(f"      exported: <the date you ran it>")
        print(f"      query: <paste the same string>")
        print(f"      records: <the count the database reported>")
        print()
    print("=" * 78)
    print("The record count matters. An export capped by the database looks exactly")
    print("like a complete one, and the import refuses any file whose parsed count")
    print("disagrees with what you declare here.\n")
    if any(entry["source"] == "abi_inform" for entry in entries):
        _print_term_note(watchlist)
    print("Lens.org's search syntax and its CPC set are UNVERIFIED -- nobody has run")
    print("them yet. Check the first result set by hand before trusting it, and")
    print("correct sources.yaml rather than the code if the syntax is wrong.\n")


def _print_term_note(watchlist) -> None:
    phrases = watchlist_phrases(watchlist)
    missing = unphrasable(watchlist)
    print(f"The trade press query carries {min(len(phrases), MAX_TERMS)} of "
          f"{len(phrases)} phrases, one per technology, capped at {MAX_TERMS}.")
    if len(phrases) > MAX_TERMS:
        print(f"  {len(phrases) - MAX_TERMS} were dropped by the cap.")
    if missing:
        print(f"  {len(missing)} technologies cannot be searched as a phrase at all,")
        print(f"  because their patterns are proximity-based. They are absent from")
        print(f"  the trade press slice entirely:")
        print(f"      {', '.join(missing)}")
    print()
