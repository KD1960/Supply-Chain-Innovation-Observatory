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

import collections
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import config, quarter

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "sources.yaml"

# Placeholders every query may use, on top of the lists declared in the file.
PERIOD_KEYS = ("start", "end", "pubyear")
# Built from watchlist.yaml rather than from the registry, so a lexicon edit
# reaches the trade press query without anybody remembering to copy it across.
WATCHLIST_KEY = "watchlist_terms"
TRADE_KEY = "trade_terms"


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
    # Classification prefix -> technology. Where a source's retrieval is
    # specific enough to stand as evidence without the text agreeing.
    evidences: dict | None = None
    # Classification prefix -> a pattern the text must also match. For classes
    # that name an enabling component rather than a mechanism.
    confirm: dict | None = None
    # The list to break this source's query up by when one export will not fit.
    split_by: str | None = None
    # Terms per query, where the whole list is too long for the database to
    # parse. None means one query carries them all.
    max_terms: int | None = None


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
MAX_TERMS = 100

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


# Words the publication filter has already said. A trade query is confined to
# supply chain outlets, so repeating the domain inside every term costs recall
# and buys nothing: no headline writes "supply chain digital twins".
DOMAIN_PREFIXES = ("supply chain", "logistics", "freight", "warehouse management")


def strip_domain(phrase: str) -> str:
    """A phrase with its leading domain word removed, where one remains.

    Kept whole when the domain word is the whole phrase -- there would be
    nothing left to search for.
    """
    lowered = phrase.lower()
    for prefix in DOMAIN_PREFIXES:
        if lowered.startswith(prefix + " "):
            remainder = phrase[len(prefix):].strip()
            # Only when what is left still says something on its own. Stripping
            # "warehouse management" off "warehouse management system" left
            # "system", which matches nearly every article in a trade
            # publication -- drowning the export the term was narrowing.
            if " " in remainder and len(remainder) >= 6:
                return remainder
    return phrase


def trade_phrase(tech) -> str | None:
    """The phrase to look for in trade press.

    The shortest distinctive expansion rather than the longest. Trade headlines
    are short and informal, and the publication filter has already done the
    domain work that a long formal phrase was carrying.
    """
    for pattern in tech.include:
        candidates = phrases_for(pattern)
        if candidates:
            return min(candidates, key=lambda phrase: (len(phrase), phrase))
    return None


# An acronym: a short run of capitals, optionally pluralised, optionally with a
# slash. AMR, AMRs, AS/RS, ERP, S/4HANA.
ACRONYM = re.compile(r"^[A-Z][A-Z0-9]{1,6}(/[A-Z0-9]{1,6})?s?$")


def acronyms_for(tech) -> list[str]:
    """The acronyms this technology's own patterns already contain.

    Taken from the lexicon rather than invented: an acronym the matcher does
    not recognise would retrieve documents that nothing can then match, which
    is work for a person and evidence for nobody.
    """
    found: list[str] = []
    for pattern in tech.include:
        for phrase in phrases_for(pattern):
            if ACRONYM.match(phrase) and phrase not in found:
                found.append(phrase)
    return found


def trade_phrases(watchlist) -> list[str]:
    phrases: list[str] = []
    for tech in watchlist.active:
        phrase = trade_phrase(tech)
        candidates = ([strip_domain(phrase)] if phrase else []) + acronyms_for(tech)
        for candidate in candidates:
            # An acronym is ambiguous in a general corpus and unambiguous
            # inside a supply chain trade publication, which the publication
            # filter has already guaranteed. "ERP transition" is how a headline
            # writes what a paper calls enterprise resource planning.
            if candidate and candidate.lower() not in {p.lower() for p in phrases}:
                phrases.append(candidate)
    return phrases


def trade_terms(watchlist, join: str = " OR ", registry: Registry | None = None) -> str:
    spec = (registry or load()).lists.get("trade_terms") or {}
    each = spec.get("each", '"{}"')
    return spec.get("join", join).join(
        each.replace("{}", phrase) for phrase in trade_phrases(watchlist)[:MAX_TERMS]
    )


def watchlist_terms(watchlist, join: str = " OR ") -> str:
    kept = watchlist_phrases(watchlist)[:MAX_TERMS]
    return join.join(f'"{phrase}"' for phrase in kept)


def years_in(bounds: tuple[str, str]) -> list[str]:
    start, end = bounds
    return [str(year) for year in range(int(start[:4]), int(end[:4]) + 1)]


def pubyear_clause(bounds: tuple[str, str]) -> str:
    """Scopus's date filter, as a year rather than a range.

    `PUBDATETXT(a TO b)` was a guess and Scopus rejected the query outright.
    PUBYEAR is documented. A year is wider than the quarter asked for, which
    costs nothing: the pipeline files every document by its own date, so a wide
    export lands in the right weeks and a narrow one loses papers. The quarter
    is narrowed in the interface's date limiter when the export is too large --
    a mechanical setting, not a judgement about relevance.
    """
    years = years_in(bounds)
    if len(years) == 1:
        return f"PUBYEAR = {years[0]}"
    return "( " + " OR ".join(f"PUBYEAR = {year}" for year in years) + " )"


def render(template: str, values: dict[str, str], period: str) -> str:
    """Substitute every placeholder, or refuse.

    A half-substituted query pasted into a database still returns something,
    and that something is not what anybody asked for.
    """
    start, end = period_bounds(period)
    available = dict(values, start=start, end=end,
                     pubyear=pubyear_clause((start, end)))
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
    values[TRADE_KEY] = trade_terms(watchlist, registry=registry)
    return render(registry.sources[source_id].query, values, period)


def _split_values(registry: Registry, source: Source) -> list[tuple[str, dict[str, str]]]:
    """One (label, list-values) pair per piece of a split query.

    A source with nothing to split on is one piece, which keeps the caller from
    needing to care whether splitting applied.
    """
    base = _rendered_lists(registry)
    spec = registry.lists.get(source.split_by or "")
    if not spec:
        return [("", base)]
    return [
        (str(item), dict(base, **{
            source.split_by: spec.get("each", "{}").replace("{}", str(item))
        }))
        for item in spec.get("items", [])
    ]


def _term_batches(source: Source, watchlist, registry: Registry) -> list[tuple[str, str]]:
    """The term list in pieces small enough for the database to read.

    Every term appears in exactly one batch. A term dropped between batches is
    a technology that silently stops being looked for.
    """
    if not source.max_terms:
        return [("", trade_terms(watchlist, registry=registry))]
    spec = registry.lists.get("trade_terms") or {}
    each, join = spec.get("each", '"{}"'), spec.get("join", " OR ")
    phrases = trade_phrases(watchlist)[:MAX_TERMS]
    # Spread evenly rather than chunk. Chunking 61 terms into fifteens leaves a
    # fifth batch holding one term, which is a whole export and a whole round
    # trip for a person to ask about "SCADA" on its own.
    count = -(-len(phrases) // source.max_terms) or 1
    batches = [phrases[index::count] for index in range(count)]
    return [
        (f"terms{index}", join.join(each.replace("{}", phrase) for phrase in batch))
        for index, batch in enumerate(batches, start=1)
    ]


def export_queries(period: str, watchlist, registry: Registry | None = None,
                   only: str | None = None, split: bool = False) -> list[dict]:
    registry = registry or load()
    if only and only not in registry.sources:
        raise RegistryProblem(
            f"unknown source {only!r}; the registry holds "
            f"{', '.join(sorted(registry.sources))}"
        )
    wanted = [registry.sources[only]] if only else list(registry.sources.values())
    start, end = period_bounds(period)
    entries = []
    for source in wanted:
        pieces = _split_values(registry, source) if split else [("", None)]
        batches = _term_batches(source, watchlist, registry) if split else [
            ("", trade_terms(watchlist, registry=registry))]
        for label, values in pieces:
          for batch_label, terms in batches:
            if values is None:
                values = _rendered_lists(registry)
            values = dict(values)
            values[WATCHLIST_KEY] = watchlist_terms(watchlist)
            values[TRADE_KEY] = terms
            parts = [part for part in (label, batch_label) if part]
            suffix = ("-" + "-".join(re.sub(r'[^A-Za-z0-9]+', '', part) for part in parts)
                      if parts else "")
            entries.append({
                "source": source.id, "name": source.name, "family": source.family,
                "format": source.format, "note": " ".join((source.note or "").split()),
                "period": period, "start": start, "end": end, "piece": label,
                "filename": f"{source.id}{suffix}.{source.format}",
                "registry_version": registry.version,
                "lexicon_version": watchlist.version,
                "query": render(source.query, values, period),
            })
    return entries


def print_queries(period: str, watchlist, registry: Registry | None = None,
                  only: str | None = None, split: bool = False) -> None:
    """The sheet a person works from.

    It carries everything the sidecar will demand, because an export whose
    query nobody recorded cannot be reproduced, and an export that cannot be
    reproduced is not evidence.
    """
    entries = export_queries(period, watchlist, registry, only, split)
    print(f"\nSupplemental exports for {period}  "
          f"(registry v{entries[0]['registry_version']}, "
          f"lexicon v{entries[0]['lexicon_version']})")
    print(f"Covering {entries[0]['start']} to {entries[0]['end']}, "
          f"by ISO week rather than calendar month.")
    by_source = collections.Counter(entry["source"] for entry in entries)
    for source_id, pieces in by_source.items():
        if pieces > 1:
            print(f"{source_id}: split into {pieces} separate exports, because one "
                  f"would exceed the database's export limit. All {pieces} are "
                  f"needed; a missing one is a missing slice that still looks whole.")
    print()
    seen_note: set[str] = set()
    for entry in entries:
        print("=" * 78)
        piece = f"  ({entry['piece']})" if entry.get("piece") else ""
        print(f"{entry['name']}{piece}   "
              f"[{entry['family']} evidence, export as {entry['format'].upper()}]")
        # Once per source. Repeating a paragraph of caveats above each of twelve
        # queries buries the queries.
        if entry["note"] and entry["source"] not in seen_note:
            print(f"  {entry['note']}")
            seen_note.add(entry["source"])
        print(f"\n  QUERY -- paste verbatim:\n\n{entry['query']}\n")
        print(f"  Save the export to: data/manual/{period}/{entry['filename']}")
        print(f"  Beside it write:    data/manual/{period}/{entry['filename']}.meta.yaml\n")
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
