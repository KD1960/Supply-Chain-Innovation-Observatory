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

    def shown(self, width: int = 700) -> str:
        """The evidence as a coder should see it, with the match marked.

        Marked because a coder should not have to re-run a regex in their head,
        and because a pattern that fired on something unexpected is the single
        most useful thing an audit can surface.
        """
        if self.text is None:
            return f"{self.title or ''}\n(full text not recovered from raw)"
        body = f"{self.title or ''}\n{self.text}"[:width]
        try:
            return re.sub(f"({self.matched_pattern})", r"[[\1]]", body,
                          flags=re.IGNORECASE)
        except re.error:
            return body


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


RECOVERY = {
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
