"""Deterministic term matching.

This module is the reason the pipeline is reproducible. No model, no scoring,
no randomness: a document either matches a compiled pattern or it does not, and
the pattern that fired is recorded on every observation so any number on the
dashboard can be traced back to its evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import config


@dataclass(frozen=True)
class Observation:
    source: str
    week: str
    tech_id: str
    doc_id: str
    doc_date: str | None
    title: str | None
    url: str | None
    entity: str | None
    entity_id: str | None
    amount: float | None
    lat: float | None
    lon: float | None
    matched_pattern: str
    raw_ref: int | None


@dataclass(frozen=True)
class Technology:
    id: str
    name: str
    family: str
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    status: str
    added_week: str
    patterns_changed_week: str
    needs_context: bool = False
    include_res: tuple[re.Pattern, ...] = field(repr=False, default=())
    exclude_res: tuple[re.Pattern, ...] = field(repr=False, default=())

    def __post_init__(self) -> None:
        # Frozen dataclass: patterns are compiled here rather than trusted from
        # the caller, so a Technology can never exist with an include pattern
        # that silently fails to match anything.
        object.__setattr__(self, "include_res", tuple(compile_pattern(p) for p in self.include))
        object.__setattr__(self, "exclude_res", tuple(compile_pattern(p) for p in self.exclude))


@dataclass(frozen=True)
class Watchlist:
    version: int
    technologies: tuple[Technology, ...]
    context: tuple[str, ...] = ()
    context_res: tuple[re.Pattern, ...] = field(repr=False, default=())

    def __post_init__(self) -> None:
        object.__setattr__(self, "context_res", tuple(compile_pattern(p) for p in self.context))

    @property
    def active(self) -> tuple[Technology, ...]:
        return tuple(tech for tech in self.technologies if tech.status == "active")

    def by_id(self, tech_id: str) -> Technology:
        for tech in self.technologies:
            if tech.id == tech_id:
                return tech
        raise KeyError(tech_id)

    def match(self, text: str) -> list[tuple[str, str]]:
        """Return one (tech_id, matched_pattern) per matching active technology."""
        hits: list[tuple[str, str]] = []
        # Terms like "humanoid robot" or "additive manufacturing" belong to every
        # field, not ours. Those entries are marked needs_context and only count
        # when the document also speaks our language somewhere.
        has_context = any(pattern.search(text) for pattern in self.context_res)
        for tech in self.active:
            if tech.needs_context and not has_context:
                continue
            if any(pattern.search(text) for pattern in tech.exclude_res):
                continue
            for source_pattern, compiled in zip(tech.include, tech.include_res):
                if compiled.search(text):
                    hits.append((tech.id, source_pattern))
                    break
        return hits


def compile_pattern(pattern: str) -> re.Pattern:
    return re.compile(rf"\b(?:{pattern})\b", re.IGNORECASE)


def load_watchlist(path: str | Path | None = None) -> Watchlist:
    raw = yaml.safe_load(Path(path or config.WATCHLIST_PATH).read_text())
    technologies = []
    for entry in raw["technologies"]:
        include = tuple(entry.get("include", ()))
        exclude = tuple(entry.get("exclude", ()) or ())
        technologies.append(
            Technology(
                id=entry["id"],
                name=entry["name"],
                family=entry["family"],
                include=include,
                exclude=exclude,
                status=entry.get("status", "active"),
                added_week=entry["added_week"],
                patterns_changed_week=entry.get("patterns_changed_week", entry["added_week"]),
                needs_context=bool(entry.get("needs_context", False)),
            )
        )
    return Watchlist(
        version=int(raw["lexicon_version"]),
        technologies=tuple(technologies),
        context=tuple(raw.get("context", ()) or ()),
    )


def observations_for_document(
    watchlist: Watchlist, document, source: str, week: str, raw_ref: int | None
) -> list[Observation]:
    haystack = f"{document.title or ''}\n{document.text or ''}"
    hits = list(watchlist.match(haystack))
    # Evidence the retrieval carries in its own right. Added after the text
    # matches and skipped where the text already found it, so an award that both
    # says the word and came from a declaring source is still one observation.
    already = {tech_id for tech_id, _ in hits}
    note = getattr(document, "evidence_note", None) or "declared"
    hits.extend(
        (tech_id, note)
        for tech_id in getattr(document, "evidences", ())
        if tech_id not in already
    )
    return [
        Observation(
            source=source,
            week=week,
            tech_id=tech_id,
            doc_id=document.doc_id,
            doc_date=document.date,
            title=document.title,
            url=document.url,
            entity=document.entity,
            entity_id=document.entity_id,
            amount=document.amount,
            lat=document.lat,
            lon=document.lon,
            matched_pattern=pattern,
            raw_ref=raw_ref,
        )
        for tech_id, pattern in hits
    ]
