"""Recovering the evidence behind an observation, so precision can be judged.

Loosening the lexicon at v7 added about 1,100 observations and nothing measured
what it cost. The obstacle was never sampling -- it was that the database does
not hold the text a match was made on. A GitHub row's title is
`owner/repo-name`; the match happened on the repository description. Reading
titles gave a precision estimate that was wrong in both directions, across 31%
of the corpus.

The text is on disk. Every API collector writes its untouched response body to
`raw/` before anything parses it, and every hand-made export stays in
`data/manual`. This module walks back from an observation to the words that
produced it.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path

from . import config


def pick(population: list, size: int, seed: int) -> list:
    """A reproducible sample. A precision figure nobody can re-derive is an
    anecdote, so the seed is part of the result rather than a convenience."""
    if size >= len(population):
        return list(population)
    return random.Random(seed).sample(list(population), size)


def stratify(population: list, per_stratum: int, key: str, seed: int) -> list:
    """An equal quota from each stratum, not a proportional draw.

    Proportionally, a sample would be a third GitHub and a third Scopus and
    would say nothing about the small sources -- which are exactly the ones the
    recent work added, and the ones whose precision is unknown.
    """
    groups: dict[str, list] = {}
    for row in population:
        groups.setdefault(row[key], []).append(row)
    drawn: list = []
    for index, (_, rows) in enumerate(sorted(groups.items())):
        drawn.extend(pick(rows, per_stratum, seed + index))
    return drawn


@dataclass(frozen=True)
class Evidence:
    source: str
    doc_id: str
    tech_id: str
    matched_pattern: str
    title: str | None
    text: str | None
    url: str | None

    def shown(self, width: int = 4000) -> str:
        """The evidence as a coder should see it, with the match marked.

        Marked because a coder should not have to re-run a regex in their head,
        and because a pattern that fired on something unexpected is the single
        most useful thing an audit can surface.

        This used to cut at a fixed 700 and say nothing. Measured against a
        sample drawn like the published one: 62 of 108 items ran past the cut,
        24 had the matched pattern beyond it and 13 had the only context word
        that opened the gate beyond it, against a median evidence length of 886
        characters. Coders were asked whether a match was justified while the
        text that justified it sat outside the window -- the owner found it by
        looking for "procurement" on an item matched as `agentic_procurement`
        and not seeing it. It was at character 1693.

        So: the cap is wide enough for ninety per cent of the corpus, the match
        is kept in view when it falls beyond the cap, and what was removed is
        counted out loud.
        """
        if self.text is None:
            return f"{self.title or ''}\n(full text not recovered from raw)"
        body = f"{self.title or ''}\n{self.text}"
        if len(body) > width:
            body = self._window(body, width)
        try:
            marked = re.sub(f"({self.matched_pattern})", r"[[\1]]", body,
                            flags=re.IGNORECASE)
        except re.error:
            return body
        if "[[" not in marked:
            # Said out loud rather than left for the coder to wonder about. On
            # EDGAR this is structural and not a bug: filing bodies are
            # megabytes and are never fetched, so an observation is attributed
            # by the query term that retrieved it and the stored text is the
            # filer's name. A coder shown a company name and asked whether it
            # supports a technology is being asked to guess.
            marked += (
                "\n\n[the matched text is not in the stored evidence — this "
                "observation was attributed by the query that retrieved it. "
                "Open the link to judge it, or code it `x`.]"
            )
        return marked

    def _window(self, body: str, width: int) -> str:
        """Keep the head, and the match with room around it if it falls outside.

        A head-only cut is what hid the evidence. Taking a window around the
        match instead means the one span a coder has to see is always in front
        of them, whatever the length of what precedes it.
        """
        try:
            found = re.search(self.matched_pattern, body, re.IGNORECASE)
        except re.error:
            found = None
        if found is None or found.end() <= width:
            return f"{body[:width]}\n[{len(body) - width} characters not shown]"
        margin = 600
        start = max(0, found.start() - margin)
        end = min(len(body), found.end() + margin)
        return (f"{body[:width - (end - start)]}\n"
                f"[{start - (width - (end - start))} characters not shown]\n"
                f"{body[start:end]}"
                + (f"\n[{len(body) - end} characters not shown]" if end < len(body) else ""))


def _github_text(page: str, doc_id: str) -> str | None:
    wanted = doc_id.split(":", 1)[1]
    for item in (json.loads(page).get("items") or []):
        if item.get("full_name") == wanted:
            return item.get("description") or ""
    return None


def _arxiv_text(page: str, doc_id: str) -> str | None:
    wanted = doc_id.split(":", 1)[1]
    for block in re.findall(r"(?s)<entry>.*?</entry>", page):
        if wanted in block:
            summary = re.search(r"(?s)<summary>(.*?)</summary>", block)
            return " ".join(summary.group(1).split()) if summary else ""
    return None


def _json_text(page: str, doc_id: str, keys: tuple[str, ...],
               fields: tuple[str, ...]) -> str | None:
    """Any collector whose raw is a flat list of objects.

    Matched by substring rather than by an exact id field, because each
    collector builds its doc_id its own way and the parsers already own that
    logic; this only has to find the right object again.
    """
    wanted = doc_id.split(":", 1)[1]
    payload = json.loads(page or "{}")
    items = []
    for key in keys:
        found = payload.get(key)
        if isinstance(found, dict):
            found = found.get("hits")
        if isinstance(found, list):
            items = found
            break
    for item in items:
        if wanted and wanted in json.dumps(item):
            source = item.get("_source", item)
            return " ".join(str(source.get(field) or "") for field in fields).strip()
    return None


def _nsf_text(page: str, doc_id: str) -> str | None:
    wanted = doc_id.split(":", 1)[1]
    for award in (json.loads(page or "{}").get("response") or {}).get("award") or []:
        if str(award.get("id")) == wanted:
            return f"{award.get('title') or ''}\n{award.get('abstractText') or ''}".strip()
    return None


def _openalex_text(page: str, doc_id: str) -> str | None:
    """Rebuilt from the inverted index, the same way the collector does it --
    OpenAlex ships abstracts as a word-to-positions map, not as prose."""
    from .collectors.openalex import OpenAlexCollector
    wanted = doc_id.split(":", 1)[1]
    for work in json.loads(page or "{}").get("results") or []:
        if (work.get("id") or "").rsplit("/", 1)[-1] == wanted:
            body = OpenAlexCollector().abstract(work.get("abstract_inverted_index"))
            return f"{work.get('title') or ''}\n{body or ''}".strip()
    return None


# Every source that can be walked back to words. NSF and OpenAlex were added as
# collectors in August 2026 and never added here, so 24 of 132 sample items
# reached a coder as "(full text not recovered from raw)" -- unjudgeable, and
# silently so.
RECOVERY = {
    "nsf": lambda page, doc_id: _nsf_text(page, doc_id),
    "openalex": lambda page, doc_id: _openalex_text(page, doc_id),
    "github": lambda page, doc_id: _github_text(page, doc_id),
    "arxiv": lambda page, doc_id: _arxiv_text(page, doc_id),
    "hn": lambda page, doc_id: _json_text(page, doc_id, ("hits",), ("title", "story_text")),
    "edgar": lambda page, doc_id: _json_text(page, doc_id, ("hits",), ("display_names", "file_type")),
    "federalregister": lambda page, doc_id: _json_text(
        page, doc_id, ("results",), ("title", "abstract")),
    "usaspending": lambda page, doc_id: _json_text(
        page, doc_id, ("results",), ("Description",)),
}


def _from_raw(conn, row: dict) -> str | None:
    paths = []
    if row.get("raw_ref"):
        found = conn.execute("SELECT path FROM raw_fetch WHERE id = ?",
                             (row["raw_ref"],)).fetchone()
        if found:
            paths.append(Path(found[0]))
    # A rebuild can leave raw_ref behind, so fall back to the week's whole
    # directory rather than reporting evidence as unrecoverable when it is
    # sitting on disk.
    directory = config.RAW_DIR / row["week"] / row["source"]
    if directory.exists():
        paths.extend(sorted(directory.iterdir()))
    recover = RECOVERY.get(row["source"])
    if not recover:
        return None
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            text = recover(path.read_text(errors="replace"), row["doc_id"])
        except Exception:
            continue
        if text is not None:
            return text
    return None


def _from_manual(row: dict) -> str | None:
    from . import manual
    try:
        exports = manual.read_exports(config.MANUAL_DIR)
    except Exception:
        return None
    for meta, records in exports:
        if str(meta["source"]) != row["source"]:
            continue
        for record in records:
            if manual.document_id(row["source"], record) == row["doc_id"]:
                return " ".join(part for part in (
                    record.get("abstract"), record.get("keywords"),
                    record.get("venue")) if part)
    return None


def evidence(conn, row: dict) -> Evidence:
    text = _from_raw(conn, row)
    if text is None:
        text = _from_manual(row)
    return Evidence(
        source=row["source"], doc_id=row["doc_id"], tech_id=row["tech_id"],
        matched_pattern=row["matched_pattern"] or "", title=row["title"],
        text=text, url=row["url"],
    )


def sheet(conn, per_stratum: int = 12, seed: int = 20260830) -> list[dict]:
    """A stratified sample with its evidence recovered, ready to be coded."""
    rows = [dict(row) for row in conn.execute("SELECT * FROM observations")]
    drawn = stratify(rows, per_stratum=per_stratum, key="source", seed=seed)
    return [
        {"n": index, "source": row["source"], "tech_id": row["tech_id"],
         "pattern": row["matched_pattern"], "url": row["url"],
         "shown": evidence(conn, row).shown()}
        for index, row in enumerate(sorted(drawn, key=lambda r: (r["source"], r["tech_id"])), 1)
    ]


LENS_PATENT_URL = "https://www.lens.org/lens/patent/{}"

WITHHELD = (
    "(excerpt withheld — this record came from a licensed database, and the\n"
    "abstract is the part the publisher licenses. Open the link above to read\n"
    "it; the coding is against the full document, not against this file.)"
)


def coding_url(row: dict) -> str | None:
    """A link a coder can actually open.

    The blocker on the first pass was that a third of the sheet had no text and
    no way to reach any: the owner coded 33 items `x` because the excerpt was
    withheld and nothing on the page said where to find the document. Scopus
    and ABI/INFORM already store a URL -- ABI's goes through the ASU proxy, so
    it resolves straight to the record. Lens stores none, but its document ids
    are Lens.org's own, so the link is reconstructible.
    """
    url = (row.get("url") or "").strip()
    if url:
        return url
    doc_id = row.get("doc_id") or ""
    if row.get("source") == "lens" and ":" in doc_id:
        return LENS_PATENT_URL.format(doc_id.split(":", 1)[1])
    return None


def markdown(conn, rows: list[dict], seed: int, lexicon_version: int,
             licensed: set[str] | None = None) -> str:
    """The sheet a coder works from.

    Every item carries its link, whether or not its text can be shown, so an
    item nobody can read is still an item somebody can go and read.
    """
    licensed = licensed if licensed is not None else set()
    shown = sum(1 for row in rows if row["source"] not in licensed)
    out = [
        f"# Precision audit sample — lexicon v{lexicon_version}",
        "",
        f"{len(rows)} observations, stratified by source, seed {seed}.",
        "",
        "The match is marked [[like this]]. For each, the question is only:",
        "**does this document support counting it under that technology?**",
        "",
        f"**{len(rows) - shown} of {len(rows)} excerpts are withheld** — they came from",
        "licensed databases, and the abstract is the part the publisher licenses.",
        "Every one carries its link, so it can be opened and coded rather than",
        "skipped. Code an item you cannot reach as `x`, not as a guess.",
        "",
        "Excerpts are no longer cut at a fixed width. The previous sheet was, and",
        "said nothing about it: 24 of 108 items had the matched pattern outside",
        "the window, so coders were asked to judge a match they could not see.",
        "Where a long document is still trimmed, the window follows the match and",
        "the number of characters removed is printed.",
        "",
    ]
    for index, row in enumerate(rows, start=1):
        url = coding_url(row)
        out.append(f"## {index}. {row['tech_id']}  ({row['source']})")
        out.append(f"pattern: `{row['matched_pattern']}`")
        out.append(f"link: {url}" if url else "link: (none recorded)")
        out.append("```")
        if row["source"] in licensed:
            out.append(WITHHELD)
        else:
            out.append(evidence(conn, row).shown())
        out.append("```")
        out.append("")
    return "\n".join(out)


def draw(conn, per_stratum: int = 12, seed: int = 20260830) -> list[dict]:
    """The sampled observation rows themselves, ordered as the sheet numbers
    them. `sheet` returns rendered rows; this returns what they were made from,
    which is what `markdown` and any re-coding need."""
    rows = [dict(row) for row in conn.execute("SELECT * FROM observations")]
    drawn = stratify(rows, per_stratum=per_stratum, key="source", seed=seed)
    return sorted(drawn, key=lambda r: (r["source"], r["tech_id"]))
