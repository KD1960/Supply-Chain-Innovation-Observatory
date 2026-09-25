"""The text behind an observation. The database stores no document text (raw
before parse); this re-parses the raw file the observation came from."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from ..collectors import base


@dataclass(frozen=True)
class DocText:
    source: str
    doc_id: str
    doc_date: str | None
    title: str | None
    url: str | None
    text: str
    observation_id: int


def texts_for(conn, tech_id: str, weeks: list[str], collectors) -> Iterator[DocText]:
    if not weeks:
        return
    by_name = {c.name: c for c in collectors}
    marks = ",".join("?" * len(weeks))
    rows = conn.execute(
        f"SELECT id, source, week, doc_id, doc_date, title, url FROM observations "
        f"WHERE tech_id = ? AND week IN ({marks}) ORDER BY doc_date DESC", [tech_id, *weeks]).fetchall()
    wanted: dict[tuple[str, str], list] = {}
    for r in rows:
        wanted.setdefault((r["source"], r["week"]), []).append(dict(r))
    for (source, week), obs in wanted.items():
        collector = by_name.get(source)
        if collector is None:
            continue
        by_doc = {o["doc_id"]: o for o in obs}
        for _, text in base.read_raw(source, week):
            for doc in collector.parse(text):
                o = by_doc.pop(doc.doc_id, None)
                if o is None:
                    continue
                body = " ".join(p for p in (doc.title, doc.text) if p)
                yield DocText(source, doc.doc_id, doc.date, doc.title, doc.url, body, o["id"])
            if not by_doc:
                break
