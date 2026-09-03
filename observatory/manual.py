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

import collections
import csv
import datetime as dt
import io
import re
from pathlib import Path

import yaml

from . import config, crossref, matcher, store, supplemental

REQUIRED_META = ("source", "exported", "query", "records")
# Every field these databases disagree about the spelling of.
CSV_FIELDS = {
    "title": ("title", "document title", "article title", "ti"),
    "abstract": ("abstract", "ab"),
    "doi": ("doi", "di"),
    "year": ("year", "publication year", "py"),
    "date": ("date", "publication date", "da"),
    "url": ("url", "link"),
    "venue": ("venue", "journal", "source title", "publication title", "applicants"),
    "classifications": ("cpc classifications", "classifications", "ipcr classifications"),
    # The database's own record identifier. Without one, identity falls back to
    # a truncated title, and a real Lens export of 185 patents collapsed into
    # 183 documents that way -- a continuation and its parent share their words.
    "identifier": ("lens id", "publication number", "accession number", "eid",
                   "ut", "id", "document id"),
}


class ExportProblem(Exception):
    """A hand-made export that cannot be trusted, named rather than ingested."""


MONTHS = {name: number for number, name in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}


def _partial_date(raw: str) -> str | None:
    """A date that names less than a day, from ProQuest's slash form.

    `2026/08/27/` is a daily, `2026/08//` a monthly, `2026///Jul/Aug` a
    bimonthly issue. The first of the month, and the first month of a range,
    are visible approximations. January is a fabrication -- seventeen of
    thirty-six records landed there before this existed.
    """
    parts = [part for part in raw.split("/") if part.strip()]
    if not parts or not re.match(r"^\d{4}$", parts[0]):
        return None
    year = int(parts[0])
    for part in parts[1:]:
        cleaned = part.strip().lower()
        if re.match(r"^\d{1,2}$", cleaned) and 1 <= int(cleaned) <= 12:
            return f"{year:04d}-{int(cleaned):02d}-01"
        if cleaned[:3] in MONTHS:
            return f"{year:04d}-{MONTHS[cleaned[:3]]:02d}-01"
    return None


def _iso_date(date_text: str | None, year: str | None) -> str | None:
    raw_text = (date_text or "").strip()
    partial = _partial_date(raw_text) if "/" in raw_text else None
    for raw in (raw_text, ""):
        cleaned = raw.strip().replace("/", "-").strip("-")
        match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", cleaned)
        if match:
            year_n, month, day = (int(part) for part in match.groups())
            try:
                return dt.date(year_n, month, day).isoformat()
            except ValueError:
                break
    if partial:
        return partial
    # A record with only a year still belongs somewhere. January 1st is a
    # deliberate, visible approximation rather than a guess at a real day.
    if year and re.match(r"^\d{4}$", year.strip()):
        # A year is not a week. This is kept only so the record survives to the
        # resolver, which replaces it; `year_only` is what marks it as unplaced.
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
                   # ProQuest names things its own way: the publication is JF,
                   # and the usable date is Y1 in slash form while DA carries
                   # "2026 Aug 27", which no ISO parser will take.
                   "JF": "venue", "JO": "venue", "Y1": "issued",
                   # A trade export has no abstract. The indexer's subject terms
                   # are the only other thing saying what the article is about.
                   "KW": "keywords",
                   # Patents. TY says which kind of record this is; a patent
                   # carries two dates and they are years apart.
                   "TY": "kind", "C2": "grant_date", "PB": "assignee",
                   "ID": "identifier", "AN": "identifier", "SN": "identifier"}.get(tag)
            if key:
                separator = "; " if key == "keywords" else " "
                current[key] = (f"{current[key]}{separator}{value}".strip()
                                if key in current else value)
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
        "identifier": (record.get("identifier") or "").strip(),
        "title": (record.get("title") or "").strip(),
        "abstract": (record.get("abstract") or "").strip(),
        "venue": (record.get("venue") or "").strip(),
        "classifications": (record.get("classifications") or "").strip(),
        "keywords": (record.get("keywords") or "").strip(),
        "doi": doi,
        "date": _iso_date(record.get("issued") or record.get("date"), record.get("year")),
        # True when the only date the export gave was a bare year. Scopus RIS
        # carries nothing else, and that year is the issue year rather than the
        # publication date -- 12% of a 40-DOI sample stamped 2026 were published
        # in 2025. Left as it stands, every such record lands on January 1st.
        "year_only": (not _iso_date(record.get("issued"), None)
                      and not _iso_date(record.get("date"), None)
                      and bool(record.get("year"))),
        "url": (record.get("url") or "").strip() or (f"https://doi.org/{doi}" if doi else ""),
    }


def dois_needing_dates(records: list[dict]) -> list[str]:
    """The DOIs worth asking Crossref about: year-only records, and no others."""
    return [
        record["doi"] for record in records
        if record.get("year_only") and record.get("doi")
    ]


def with_resolved_dates(records: list[dict], dates: dict[str, str | None]) -> list[dict]:
    """Records re-dated from the resolver, dropping the ones it cannot place.

    A record whose date stays a bare year is not dropped for being unimportant.
    It is dropped because a year is not a week, and the alternative -- January
    1st -- is a fabricated spike that no downstream reader can see through.
    The count of what was dropped is reported by the caller.
    """
    placed = []
    for record in records:
        if not record.get("year_only"):
            placed.append(record)
            continue
        resolved = dates.get(record.get("doi") or "")
        if resolved:
            placed.append(dict(record, date=resolved, year_only=False))
    return placed


# Below this, an export is citation-only in practice and the matcher is reading
# subject headings rather than prose. Not zero: a handful of records legitimately
# lack an abstract in any database.
ABSTRACT_FLOOR = 0.25


def abstract_coverage(records: list[dict]) -> float | None:
    """The share of records carrying an abstract, or None for an empty export."""
    if not records:
        return None
    return sum(1 for r in records if (r.get("abstract") or "").strip()) / len(records)


def abstract_warning(source: str, filename: str, coverage: float | None) -> str | None:
    """Said at import, because nobody re-reads an export months later.

    ProQuest's RIS export defaults to citation-only -- bibliographic fields and
    the indexer's subject terms, no `AB` tag at all. Every ABI/INFORM export so
    far arrived that way, so trade press reached the matcher as about
    twenty-six words of subject headings. The keyword fallback in `haystack`
    was built around that and made it look like a property of the source rather
    than a setting on the export screen; it surfaced only as a side finding of
    the CRA feasibility test. Scopus files from the same importer carry
    abstracts, so the parser was never the problem.
    """
    if coverage is None or coverage >= ABSTRACT_FLOOR:
        return None
    return (
        f"  {source}: {filename} has abstracts on {coverage * 100:.0f}% of its "
        f"records. The matcher is reading titles and subject terms only. "
        f"Re-export choosing the option that includes the abstract "
        f"(ProQuest: 'RIS' with Citation, abstract & indexing, not Citation only)."
    )


def haystack(record: dict) -> str:
    """Everything about a record that says what it is about.

    Subject terms matter because a ProQuest trade export has no abstract at
    all. On a real 36-record export they took the match rate from 4 to 9, and
    they carry the domain words -- "Logistics", "Supply chains" -- that the
    context gate needs before a technology term in a headline can count.
    """
    return "\n".join(part for part in (
        record.get("title"), record.get("venue"),
        record.get("abstract"), record.get("keywords"),
    ) if part)


def document_id(source: str, record: dict) -> str:
    """What makes this record one document rather than another.

    The database's own identifier first, then a DOI, and a truncated title only
    as a last resort. That last resort is not safe on its own: patents carry no
    DOI, and 185 real ones produced 183 identities because two pairs shared a
    title. Two rows silently became one, which is this project's oldest failure
    mode wearing a new hat.
    """
    for key in ("identifier", "doi"):
        value = (record.get(key) or "").strip()
        if value:
            return f"{source}:{value}"
    return f"{source}:{(record.get('title') or '')[:120]}"


def classification_evidence(source: str, record: dict) -> list[str]:
    """Technologies the retrieval evidences, from the record's own classification.

    A code is a tree, so the map names a branch and matching is by prefix.
    Only sources that declare a map get anything; everything else has to earn
    its match from the text like any other document.
    """
    registry = supplemental.load()
    entry = registry.sources.get(source)
    declared = (entry.evidences or {}) if entry else {}
    if not declared:
        return []
    confirm = (entry.confirm or {}) if entry else {}
    haystack_text = f"{record.get('title') or ''} {record.get('abstract') or ''}"
    codes = [
        code.strip()
        for code in re.split(r"[;,]", record.get("classifications") or "")
        if code.strip()
    ]
    found: list[str] = []
    for prefix, tech_id in declared.items():
        if not any(code.startswith(prefix) for code in codes):
            continue
        # An enabling-technology class only counts when the document says so.
        needed = confirm.get(prefix)
        if needed and not re.search(needed, haystack_text, re.IGNORECASE):
            continue
        if tech_id not in found:
            found.append(tech_id)
    return found


def _report_missing(watchlist, directory: Path, period: str | None) -> None:
    """Say what the sheet asked for and never got, before ingesting the rest.

    An export nobody ran is the same shape as a silently truncated one: the
    quarter imports cleanly and reports a fraction as though it were the whole.
    2026-Q3 asked for twenty ABI/INFORM exports and four were run, and nothing
    in the pipeline noticed -- trade press read as a thin source rather than as
    a fifth of a source.

    Reported for every period that has a directory, because a directory means
    somebody started that quarter. Never fatal: the rows that did arrive are
    still real, and refusing them would trade an undercount for nothing.
    """
    from . import supplemental

    if period is not None:
        periods = [period]
    else:
        periods = sorted(child.name for child in directory.iterdir()
                         if child.is_dir()) if directory.exists() else []
    for name in periods:
        try:
            missing = supplemental.missing_exports(name, watchlist, root=directory)
        except Exception as error:  # a period the registry cannot parse is not fatal
            print(f"  could not check {name} for missing exports: {error}")
            continue
        if missing:
            print(f"  {name}: exports that never arrived")
            for line in supplemental.describe_missing(missing):
                print(line)


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
        retired = (supplemental.load().sources.get(str(meta["source"]))
                   or _NOT_REGISTERED).retired
        if retired:
            raise ExportProblem(
                f"{path.name} is an export from {meta['source']}, which is "
                f"retired: {retired} Move the file out of the manual directory "
                f"-- leaving it here means the next rebuild ingests it again.")
        # The filename travels with the sidecar so a warning can name the file
        # rather than the source. `read_exports` drops the path on return, and
        # both callers unpack two-tuples.
        meta["_filename"] = path.name
        found.append((meta, records, path))
    _refuse_overlapping(found)
    return [(meta, records) for meta, records, _ in found]


# How much of the whole set the largest single file may account for. Below
# this, the other files are adding real records; at or above it, they are
# copies of one result set wearing different names.
UNION_LIMIT = 0.95


# A source with no registry entry is not retired; it is simply not one of the
# human-fetched ones, and the rest of the importer already handles it.
_NOT_REGISTERED = supplemental.Source(
    id="", name="", family="", signal="", stage="", format="", query="")


def _refuse_overlapping(found) -> None:
    """Refuse a set of exports that adds nothing to its own largest file.

    Four ABI/INFORM files once arrived holding 182 records between them and 52
    distinct ones, each a superset of the last: a marked-items list exported
    repeatedly as it grew. Nothing downstream would have noticed -- the
    importer deduplicates, so it writes the 52 and reports success, leaving a
    quarter that looks four publications wide when it is one.

    The test is the union, not pairwise overlap. Pairwise refused honest work:
    a term batch slices the *query*, not the corpus, so an article carrying
    terms from two batches appears in both, and a two-record batch fully inside
    a twelve-record one is exactly what a correct export looks like. What the
    accumulation case does that batching never does is leave the union no
    bigger than the largest single file: the tolerance below is what "no
    bigger" means in practice, since a stray record picked up between exports
    is enough to lift the union above it.
    """
    by_source: dict[str, list[tuple[str, set]]] = {}
    for meta, records, path in found:
        # The guard has to mean the same thing by "the same record" as the rest
        # of the pipeline does, so identity is `document_id` and not the raw
        # accession number. Keying on `identifier` alone skipped every Scopus
        # export ever made: ProQuest writes an accession number and Scopus does
        # not, so 2,648 records across twelve files carried a blank one, `if
        # ids` was false every time, and the guard silently did not apply to
        # the largest manual source.
        source = str(meta["source"])
        ids = {document_id(source, record) for record in records
               if (record.get("identifier") or record.get("doi")
                   or record.get("title") or "").strip()}
        if ids:
            by_source.setdefault(source, []).append((path.name, ids))
    for source, files in by_source.items():
        if len(files) < 2:
            continue
        union = set().union(*(ids for _, ids in files))
        largest_name, largest = max(files, key=lambda item: len(item[1]))
        if len(largest) >= len(union) * UNION_LIMIT:
            raise ExportProblem(
                f"{len(files)} {source} exports hold {sum(len(ids) for _, ids in files)} "
                f"records between them and {len(union)} distinct -- little more than "
                f"{largest_name} holds on its own. The set adds nothing to its own "
                f"largest file, which is what a marked-items list exported again as it "
                f"grew looks like. Clear the selections between exports and re-run; "
                f"ingesting these would report a quarter far wider than it is."
            )


def import_exports(conn, watchlist, root: Path | None = None, session=None,
                   period: str | None = None) -> int:
    """Match every export under `root` and write the hits as observations."""
    directory = Path(root) if root else config.MANUAL_DIR
    _report_missing(watchlist, directory, period)
    exports = read_exports(directory)

    # One resolver pass across every export, before any of them is matched. A
    # bibliographic record that carries only a year cannot be placed in a week,
    # and placing it on January 1st is what put all 2,607 records of one Scopus
    # export into 2026-W01.
    needing = [doi for _, records in exports for doi in dois_needing_dates(records)]
    dates: dict[str, str | None] = {}
    if needing:
        print(f"  resolving {len(set(needing))} publication dates via Crossref")
        dates = crossref.resolve(
            needing, session=session,
            progress=lambda done, total: print(f"    {done} of {total}"),
        )

    # Said before anything is counted, for the same reason the missing-export
    # report is: an export that came back thin is not visible in its own
    # numbers, only in a comparison nobody runs.
    for meta, records in exports:
        line = abstract_warning(str(meta["source"]), str(meta.get("_filename") or "export"),
                                abstract_coverage(records))
        if line:
            print(line)

    written = 0
    retrieved: dict[str, dict] = collections.defaultdict(dict)
    for meta, records in exports:
        source = str(meta["source"])
        placed = with_resolved_dates(records, dates)
        # The export files are this source's retrieved corpus, and it is the
        # denominator of its rates. Accumulated across every file and written
        # once at the end: keying by the export date wiped eleven of twelve
        # Scopus files, because they shared one, and record_corpus replaces
        # what it finds under a key.
        for record in placed:
            key = (record.get("date") or "")[:10] or None
            retrieved[source][key] = retrieved[source].get(key, 0) + 1
        dropped = len(records) - len(placed)
        if dropped:
            # Silent truncation is this project's oldest failure mode, and a
            # record dropped for having no placeable date is a truncation.
            print(f"  {source}: {dropped} of {len(records)} records had no date "
                  f"beyond a year and could not be placed in a week")
        for record in placed:
            if not record["date"] or not record["title"]:
                continue
            # The abstract is the licensed asset. It is read here, decides the
            # match, and is never handed to anything that persists.
            hits = list(watchlist.match(haystack(record)))
            # The classification the record was filed under, added after the
            # text matches and skipped where the text already found it, so a
            # patent that both says the word and carries the code is still one
            # observation.
            already = {tech_id for tech_id, _ in hits}
            for tech_id in classification_evidence(source, record):
                if tech_id not in already:
                    prefix = next(
                        code for code, mapped in
                        (supplemental.load().sources[source].evidences or {}).items()
                        if mapped == tech_id
                    )
                    hits.append((tech_id, f"cpc:{prefix}"))
            if not hits:
                continue
            week = config.iso_week(dt.date.fromisoformat(record["date"]))
            doc_id = document_id(source, record)
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
    for source, counts in retrieved.items():
        store.forget_manual_corpus(conn, source)
        store.record_corpus(conn, source, store.MANUAL_KEY, counts.items())
    return written
