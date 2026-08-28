"""Licensed exports, fetched by a human.

Web of Science, Scopus, ABI/INFORM and their neighbours hold the material this
project most conspicuously cannot see -- journal articles rather than
preprints, and trade press rather than none. None of them can be automated:
they sit behind institutional authentication and their licences forbid
systematic download. What they do allow is a person running a search and
exporting the result.

So the fetch has a human in the middle, and everything after it is the same as
any other source: the same matcher, the same observations table, the same
document-week rule. Three things make a hand-made export as accountable as an
API call.

**A sidecar.** Every export file needs a `<file>.meta.yaml` naming the source,
the export date, the exact query string, and the number of records the database
said it returned. An export nobody can reproduce is not evidence.

**A count check.** Scopus caps an export at 2,000 records and mentions it only
in the interface. A truncated file ingested quietly is a smaller number wearing
the same clothes as a real one, which is this project's oldest failure mode.
The declared count and the parsed count must agree.

**Abstracts are matched and then dropped.** The abstract is the part of the
record the publisher licenses. It decides whether a document matches and is
then discarded; what persists is bibliographic metadata and a DOI, which any
reader with access can follow. Nothing licensed is ever written to the database
or to a published report.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
from pathlib import Path

import yaml

from . import config, matcher, store

REQUIRED_META = ("source", "exported", "query", "records")
# Every field these databases disagree about the spelling of.
CSV_FIELDS = {
    "title": ("title", "document title", "article title", "ti"),
    "abstract": ("abstract", "ab"),
    "doi": ("doi", "di"),
    "year": ("year", "publication year", "py"),
    "date": ("date", "publication date", "da"),
    "url": ("url", "link"),
}


class ExportProblem(Exception):
    """A hand-made export that cannot be trusted, named rather than ingested."""


def _iso_date(date_text: str | None, year: str | None) -> str | None:
    for raw in (date_text or "", ""):
        cleaned = raw.strip().replace("/", "-").strip("-")
        match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", cleaned)
        if match:
            year_n, month, day = (int(part) for part in match.groups())
            try:
                return dt.date(year_n, month, day).isoformat()
            except ValueError:
                break
    # A record with only a year still belongs somewhere. January 1st is a
    # deliberate, visible approximation rather than a guess at a real day.
    if year and re.match(r"^\d{4}$", year.strip()):
        return f"{year.strip()}-01-01"
    return None


def parse_ris(text: str) -> list[dict]:
    records: list[dict] = []
    current: dict[str, str] = {}
    last_tag: str | None = None
    for line in text.splitlines():
        match = re.match(r"^([A-Z][A-Z0-9])  - ?(.*)$", line)
        if match:
            tag, value = match.group(1), match.group(2).strip()
            if tag == "ER":
                if current:
                    records.append(current)
                current, last_tag = {}, None
                continue
            key = {"TI": "title", "T1": "title", "AB": "abstract", "DO": "doi",
                   "PY": "year", "DA": "date", "UR": "url", "T2": "venue",
                   # Patents. TY says which kind of record this is; a patent
                   # carries two dates and they are years apart.
                   "TY": "kind", "C2": "grant_date", "PB": "assignee"}.get(tag)
            if key:
                current[key] = f"{current[key]} {value}".strip() if key in current else value
                last_tag = key
            else:
                last_tag = None
        elif line.strip() and last_tag:
            # A wrapped continuation line, indented under its tag.
            current[last_tag] = f"{current[last_tag]} {line.strip()}".strip()
    if current:
        records.append(current)
    return [_normalise(record) for record in records]


def parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    mapping = {}
    for field, aliases in CSV_FIELDS.items():
        for column in reader.fieldnames or ():
            if column.strip().lower() in aliases:
                mapping[field] = column
                break
    return [
        _normalise({field: (row.get(column) or "").strip()
                    for field, column in mapping.items()})
        for row in reader
    ]


def _normalise(record: dict) -> dict:
    # A patent's event is its grant. `DA` on a patent record is the filing
    # date, which across a real Lens export ran from 2017 to 2025 for patents
    # all granted inside one quarter -- keying on it files every one of them
    # into a week the query never asked about. `TY - PAT` is what distinguishes
    # the two, and a bibliographic record is left alone.
    if (record.get("kind") or "").strip().upper() == "PAT":
        if record.get("grant_date"):
            record = dict(record, date=record["grant_date"])
        if record.get("assignee") and not record.get("venue"):
            record = dict(record, venue=record["assignee"])
    doi = (record.get("doi") or "").strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    return {
        "title": (record.get("title") or "").strip(),
        "abstract": (record.get("abstract") or "").strip(),
        "venue": (record.get("venue") or "").strip(),
        "doi": doi,
        "date": _iso_date(record.get("date"), record.get("year")),
        "url": (record.get("url") or "").strip() or (f"https://doi.org/{doi}" if doi else ""),
    }


def read_exports(root: Path) -> list[tuple[dict, list[dict]]]:
    """Every export under `root`, paired with its sidecar. Raises rather than
    skipping: a silently ignored export is a silently missing quarter."""
    root = Path(root)
    if not root.exists():
        return []
    found = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in (".ris", ".csv", ".txt"):
            continue
        sidecar = path.with_name(f"{path.name}.meta.yaml")
        if not sidecar.exists():
            raise ExportProblem(f"{path} has no {sidecar.name} beside it")
        meta = yaml.safe_load(sidecar.read_text()) or {}
        missing = [key for key in REQUIRED_META if key not in meta]
        if missing:
            raise ExportProblem(f"{sidecar} is missing {', '.join(missing)}")
        text = path.read_text(errors="replace")
        records = parse_csv(text) if path.suffix.lower() == ".csv" else parse_ris(text)
        declared = int(meta["records"])
        if len(records) != declared:
            raise ExportProblem(
                f"{path} parsed {len(records)} records but {sidecar.name} declares "
                f"{declared}. An export capped by the database looks exactly like a "
                f"complete one; fix the count or re-export before ingesting."
            )
        found.append((meta, records))
    return found


def import_exports(conn, watchlist, root: Path | None = None) -> int:
    """Match every export under `root` and write the hits as observations."""
    written = 0
    for meta, records in read_exports(Path(root) if root else config.MANUAL_DIR):
        source = str(meta["source"])
        for record in records:
            if not record["date"] or not record["title"]:
                continue
            # The abstract is the licensed asset. It is read here, decides the
            # match, and is never handed to anything that persists.
            haystack = f"{record['title']}\n{record['venue']}\n{record['abstract']}"
            hits = watchlist.match(haystack)
            if not hits:
                continue
            week = config.iso_week(dt.date.fromisoformat(record["date"]))
            doc_id = f"{source}:{record['doi'] or record['title'][:120]}"
            written += store.upsert_observations(conn, [
                matcher.Observation(
                    source=source, week=week, tech_id=tech_id, doc_id=doc_id,
                    doc_date=record["date"], title=record["title"],
                    url=record["url"] or None, entity=record["venue"] or None,
                    entity_id=None, amount=None, lat=None, lon=None,
                    matched_pattern=pattern, raw_ref=None,
                )
                for tech_id, pattern in hits
            ])
    return written
