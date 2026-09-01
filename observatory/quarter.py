"""Quarterly reporting.

The weekly dashboard answers "what happened this week". Across this corpus that
question is mostly unanswerable: two thirds of technology-weeks hold zero
observations and the median is zero, so a weekly ranking largely reports which
week a collector happened to catch something.

Thirteen weeks is the first interval at which a typical technology has anything
in it. This module aggregates the same stored observations to that interval. It
adds no new fetching and no new judgement -- it is a different lens on rows the
weekly run already wrote.
"""

from __future__ import annotations

import base64
import collections
import datetime as dt
import functools
import re

from pathlib import Path

from markupsafe import Markup

from . import charts, config, export, render, store, supplemental

QUARTER_WEEKS = 13
# The six public collectors. Anything else in `observations` arrived through a
# hand-made export from a licensed database (see manual.py), which a reader
# without a subscription cannot follow -- so the report says so.

# A technology drawing this much of its evidence from one source is reported as
# a count and nothing more. Measured on the real corpus at the time this was
# built: across 2026-Q1 and Q2 about half of all technologies sat at or above
# it, those technologies held 63% of every document, and four of the five
# largest were among them.
#
# 80 is a judgement rather than a derivation, which is why the report prints how
# many technologies it caught -- a threshold nobody can see is a threshold
# nobody can argue with.
SINGLE_SOURCE_SHARE = 0.80

# How many technologies the stage board and the substance chart name. Forty
# labels overlap into nothing; the point of a label is being able to read it.
BOARD_LIMIT = 14

# What kind of evidence each source produces. Diversity is counted across these
# rather than across source names, because two sources measuring the same thing
# are one piece of evidence twice.
#
# arXiv and Scopus are the case that forces this: both are research literature,
# so a technology at 6 preprints and 5 journal papers would clear a two-source
# floor while resting entirely on academic interest. Measured on 2026-Q2, five
# technologies would have cleared on a Scopus export alone -- freight
# decarbonisation, critical infrastructure security, electric heavy-duty trucks,
# warehouse robotics and humanoid logistics.
EVIDENCE_FAMILIES: dict[str, str] = {
    "arxiv": "research",
    "scopus": "research",
    "openalex": "research",
    "github": "code",
    "patentsview": "patents",
    "lens": "patents",
    "edgar": "filings",
    "abi_inform": "trade",
    "federalregister": "regulation",
    "usaspending": "money",
    # Its own family, not "money". USAspending here is infrastructure being
    # built -- ports, rail corridors, freight facilities -- and NSF is research
    # being funded. Both are federal dollars and they sit at different stages,
    # so one number would swamp the infrastructure signal under a corpus five
    # times its size: 184 documents against roughly a thousand. Not "research"
    # either: money committed to an idea is not a paper published about one.
    "nsf": "research funding",
    "hn": "community",
}

# Documents a family must supply before it counts towards diversity. One
# document from a second family is not corroboration -- on 2026-Q2, eleven of
# the eighteen technologies that passed the gate had a second source
# contributing one or two documents.
#
# Deliberately left at 1 for now. Raising it to 3 would gate 27 of 34
# technologies, but that measures how thin the corpus is today rather than where
# the threshold belongs; Scopus, ABI/INFORM and Lens are expected to change it
# substantially. The mechanism ships now and the number is set against real data
# after the first quarter that has them.

# Every source that can appear in `observations`. Written as a six-tuple before
# any human-supplied export existed, which meant Scopus and Lens vanished from
# the table the moment they arrived: a technology with 26 observations rendered
# its evidence as "[]" and one with 89 showed a breakdown summing to 18. The
# totals and the gate were right and the table was not, which is the worse way
# round.
COLLECTORS = ("arxiv", "github", "hn", "edgar", "federalregister", "usaspending")
SOURCES = COLLECTORS + tuple(
    source for source in EVIDENCE_FAMILIES if source not in COLLECTORS
)
FAMILY_FLOOR = 1

# What a family's evidence says about where a technology sits. A technology
# whose documents concentrate in one family is not a defect to be suppressed --
# it is a technology at that stage, and saying so is the finding. Freight
# decarbonisation at 88% research is a technology in the research stage.
FAMILY_STAGE = {
    "research": "idea",
    "code": "experiment",
    "patents": "experiment",
    "money": "investment",
    "research funding": "idea",
    "regulation": "deployment",
    "trade": "deployment",
    "filings": "diffusion",
    "community": "attention",
}


# The stage model, and which families speak to each stage. The inverse of
# FAMILY_STAGE, written out rather than derived, because a family can inform
# more than one stage: a filing is both an investment and a sign of diffusion.
STAGE_FAMILIES: dict[str, tuple[str, ...]] = {
    "idea": ("research", "research funding"),
    "experiment": ("code", "patents"),
    "investment": ("money", "filings"),
    "deployment": ("regulation", "trade"),
    "diffusion": ("filings", "trade", "community"),
}


def _chart(dropped: dict, printable: dict, name: str, points, **kwargs) -> str:
    """The chart for the page, and quietly the one for the file.

    They differ. The page numbers its dots, puts the name on hover and keys it
    with a table underneath; a PDF has none of those, so the exported copy
    carries printed labels and reports how many would not fit -- a chart
    missing three labels looks exactly like one that has them all.
    """
    svg = charts.scatter(points, **kwargs)
    for_file, missed = charts.scatter_with_report(
        points, **{**kwargs, "numbered": False, "labels": True})
    printable[name] = for_file
    if missed:
        dropped[name] = missed
    return svg


def _describe(tech) -> str:
    """A one-line description, from the technology's own patterns.

    Written from the lexicon rather than kept as prose beside it, so a
    description cannot drift away from what the entry actually matches -- which
    is the thing a reader of the appendix wants to know.
    """
    phrases = []
    for pattern in tech.include[:3]:
        cleaned = re.sub(r"\\b|[\\^$()\[\]{}?*+|]", " ", pattern)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned:
            phrases.append(cleaned)
    return "matches " + "; ".join(phrases) if phrases else "no patterns"


def _summary(name: str, rows, counts, ran: int, total_weeks: int,
             partial: bool = False, short_history: bool = False,
             window_collected: int = 0, window_total: int = 0) -> list[str]:
    """The quarter as points, for a reader who reads nothing else.

    A list rather than a paragraph: prose is read start to finish or not at
    all, and a summary exists to be scanned.
    """
    documents = sum(row["total"] for row in rows)
    # Sorted by the thing the sentence claims to rank by. `rows` arrives
    # ordered by document count, and saying "ranked by substance" over that
    # order would be a sentence that is simply not true.
    top = sorted((row for row in rows if row.get("sai") is not None),
                 key=lambda row: -row["sai"])[:3]
    concentrated = [row for row in rows if row["single_source"]]
    silent = [row for row in rows if not row["total"]]
    families = collections.Counter()
    for row in rows:
        for family, count in (row["by_family"] or {}).items():
            if count:
                families[family] += count
    leading = ", ".join(f"{family} {count}" for family, count in families.most_common(3))
    stage_counts = collections.Counter(row["stage"] for row in rows if row.get("stage"))
    stage_text = ", ".join(f"{count} at {stage}" for stage, count in stage_counts.most_common(3))
    parts = [
        f"{name} holds {documents} matched documents across {len(rows)} technologies, "
        f"collected over {ran} of {total_weeks} weeks.",
        f"The evidence is led by {leading}." if leading else "",
        f"By the family supplying most of their evidence, the quarter reads {stage_text}."
        if stage_text else "",
    ]
    if not top and partial:
        parts.append(
            f"Scores are withheld: this period has run {ran} of {total_weeks} weeks, "
            f"and a score compares a period against periods that are complete. The "
            f"counts stand -- they are observations, and only the scores are inferences."
        )
    elif not top and short_history:
        # Named rather than left blank. The period is whole, so nothing above
        # tells the reader why the movement section is missing, and a missing
        # section reads as nothing moved rather than as we cannot yet say.
        parts.append(
            f"Scores are withheld: {window_collected} of the {window_total} quarters "
            f"a score is computed over were collected, and a score compares a period "
            f"against periods that exist. The counts stand -- they are observations, "
            f"and only the scores are inferences."
        )
    if top:
        names = ", ".join(row["name"] for row in top)
        parts.append(
            f"Ranked by substance against attention \u2014 what is being built "
            f"rather than said \u2014 the quarter's leaders are {names}."
        )
    if concentrated:
        parts.append(
            f"{len(concentrated)} of {len(rows)} technologies draw "
            f"{int(SINGLE_SOURCE_SHARE * 100)}% or more of their evidence from one "
            f"kind. That is reported rather than suppressed: a technology whose "
            f"documents sit almost entirely in research is a technology at the "
            f"research stage. It is also the thing most likely to mislead, because "
            f"one source's coverage can look like a technology's trajectory."
        )
    crossing = [row for row in rows if (row.get("lfi") or 0) > 0]
    if crossing:
        names = ", ".join(row["name"] for row in crossing[:3])
        parts.append(
            f"{len(crossing)} technologies show more evidence from the investment "
            f"and deployment stages than from research and experimentation, which is "
            f"what moving out of the laboratory looks like in this data: {names}."
        )
    located = [row for row in rows if row.get("by_family", {}).get("money")]
    if located:
        parts.append(
            f"{len(located)} technologies drew federal money this quarter, and the "
            f"awards that name a place of performance are plotted on the build map."
        )
    if silent:
        parts.append(
            f"{len(silent)} technologies produced no documents at all this quarter. "
            f"Absence here means absence from these sources, not from the world."
        )
    parts.append(
        "Counts are documents matched rather than mentions, and every rate is a "
        "share of what its own family retrieved, so a figure can be compared with "
        "the same figure a quarter earlier. Small corpora move by whole "
        "percentage points on a single document."
    )
    return [part for part in parts if part]


def family_rates(row, retrieved: dict[str, int]) -> dict[str, float]:
    """Matched over retrieved, per family, as a percentage.

    100 means every document in that family's supply chain corpus mentioned the
    technology. Nothing comes near it, and that is the true magnitude: vehicle
    routing appears in 0.52% of supply chain research. The percentile index this
    replaces reported that as 93.

    A rate can also move. A percentile cannot -- if every technology doubles,
    every percentile stays exactly where it was, which is fatal for a tool whose
    purpose is detecting movement.
    """
    return {
        family: 100 * count / retrieved[family]
        for family, count in (row["by_family"] or {}).items()
        if count and retrieved.get(family)
    }


def family_of(source: str) -> str:
    """An unregistered source is its own family. Folding an unknown export in
    with something else would invent corroboration that nobody checked."""
    return EVIDENCE_FAMILIES.get(source, source)


def by_family(by_source) -> collections.Counter:
    totals: collections.Counter = collections.Counter()
    for source, count in (by_source or {}).items():
        totals[family_of(source)] += count
    return totals


def is_single_source(row: dict) -> bool:
    """Whether this technology's evidence is really one source's coverage.

    A stage score, a pipeline position or a share shift computed from one
    source is arithmetically a restatement of what that source happened to
    index. Reporting it beside a caveat is not enough: this project has already
    shipped one wrong ranking that way, and a number printed next to a warning
    is still read as a number.
    """
    total = row.get("total") or 0
    if total <= 0:
        return True
    families = by_family(row.get("by_source"))
    if len([n for n in families.values() if n >= FAMILY_FLOOR]) < 2:
        return True
    return max(families.values()) / total >= SINGLE_SOURCE_SHARE


def quarter_of(week: str) -> str:
    year, number = week.split("-W")
    # A long ISO year has 53 weeks. The 53rd belongs to Q4 rather than opening
    # a fifth quarter that no other year has.
    index = min((int(number) - 1) // QUARTER_WEEKS + 1, 4)
    return f"{year}-Q{index}"


def weeks_in_quarter(name: str) -> list[str]:
    year, number = name.split("-Q")
    first = (int(number) - 1) * QUARTER_WEEKS + 1
    return [f"{year}-W{week:02d}" for week in range(first, first + QUARTER_WEEKS)]


def weeks_in_year(year: str) -> list[str]:
    # December 28th always falls in the last ISO week of its year, which is 53
    # in a long year. Hard-coding 52 would drop the annual report's own final
    # week in 2020, 2026 and every other long year.
    last = dt.date(int(year), 12, 28).isocalendar().week
    return [f"{year}-W{week:02d}" for week in range(1, last + 1)]


def period_bounds(name: str) -> tuple[str, str]:
    """The calendar dates a period covers.

    Calendar, not ISO. The two do not line up: 2026-Q1 used to begin on
    December 29th 2025 and the ISO year ended on December 27th, so the last four
    days of every December were in no report at all. Every observation carries
    its own date, so the exact boundary costs nothing.

    Collection is untouched and stays on ISO weeks. A wider fetch window
    silently truncates four of six sources (STATUS section 6); the cadence of
    the fetch and the boundaries of the report are separate things.
    """
    if "-Q" in name:
        year, number = name.split("-Q")
        first = 3 * (int(number) - 1) + 1
        start = dt.date(int(year), first, 1)
        end = dt.date(int(year) + (first + 3 > 12), (first + 3 - 1) % 12 + 1, 1) - dt.timedelta(days=1)
        return start.isoformat(), end.isoformat()
    return f"{int(name):04d}-01-01", f"{int(name):04d}-12-31"


def weeks_in_period(name: str) -> list[str]:
    """A period is a quarter (`2026-Q2`) or a whole year (`2026`)."""
    return weeks_in_quarter(name) if "-Q" in name else weeks_in_year(name)


def previous_period(name: str) -> str:
    return previous_quarter(name) if "-Q" in name else str(int(name) - 1)


def previous_quarter(name: str) -> str:
    year, number = name.split("-Q")
    if int(number) == 1:
        return f"{int(year) - 1}-Q4"
    return f"{year}-Q{int(number) - 1}"


def totals(conn, name: str) -> dict[str, dict]:
    # Selected by the document's own date, which is the rule the rest of the
    # pipeline already follows. A paper dated September 30th belongs to Q3
    # whether or not its ISO week runs into October.
    start, end = period_bounds(name)
    rows = conn.execute(
        "SELECT tech_id, source, COUNT(*) AS n FROM observations "
        "WHERE doc_date BETWEEN ? AND ? GROUP BY tech_id, source",
        (start, end),
    ).fetchall()
    filers = conn.execute(
        "SELECT tech_id, COUNT(DISTINCT entity_id) AS n FROM observations "
        "WHERE doc_date BETWEEN ? AND ? AND source = 'edgar' "
        "AND entity_id IS NOT NULL GROUP BY tech_id",
        (start, end),
    ).fetchall()
    by_tech: dict[str, dict] = collections.defaultdict(
        lambda: {"total": 0, "by_source": collections.Counter(), "filers": 0}
    )
    for row in rows:
        by_tech[row["tech_id"]]["total"] += row["n"]
        by_tech[row["tech_id"]]["by_source"][row["source"]] = row["n"]
    for row in filers:
        by_tech[row["tech_id"]]["filers"] = row["n"]
    return dict(by_tech)


def share_shift(conn, name: str) -> dict[str, float | None]:
    """Each technology's share of the quarter, against its share of the last one.

    Reported in place of raw counts because the corpus itself is not stable:
    between the two halves of the first year every source returned more
    material than before, arXiv by 35% and GitHub by 79%. Against that
    background almost everything "rose", and the rise meant nothing.
    """
    now, before = totals(conn, name), totals(conn, previous_period(name))
    now_total = sum(row["total"] for row in now.values())
    before_total = sum(row["total"] for row in before.values())
    if not before_total:
        # Nothing to have moved against. A share computed from an empty
        # quarter would read as a jump from zero for every technology at once.
        return {tech_id: None for tech_id in now}
    shifts: dict[str, float | None] = {}
    for tech_id in set(now) | set(before):
        share_now = 100 * now.get(tech_id, {"total": 0})["total"] / now_total if now_total else 0.0
        share_before = 100 * before.get(tech_id, {"total": 0})["total"] / before_total
        shifts[tech_id] = share_now - share_before
    return shifts


def weeks_run(conn, name: str) -> int:
    """Weeks of this quarter the pipeline actually ran.

    Taken from source_runs rather than from the observations, because a week
    that ran and found nothing is observed; a week that never ran is not.
    """
    weeks = weeks_in_period(name)
    placeholders = ",".join("?" for _ in weeks)
    row = conn.execute(
        f"SELECT COUNT(DISTINCT week) AS n FROM source_runs WHERE week IN ({placeholders})",
        weeks,
    ).fetchone()
    return row["n"] if row else 0


# Building versus talking, at the family level. Research is in neither: a
# preprint is not a built thing and it is not hype, and the weekly index leaves
# arXiv out of both halves for the same reason. Folding nine hundred research
# documents into either side would drown the distinction the block exists to
# draw.
SUBSTANCE_FAMILIES = ("code", "patents", "filings", "money", "regulation")
ATTENTION_FAMILIES = ("community", "trade")


def substance(row) -> int:
    return sum((row["by_family"] or {}).get(f, 0) for f in SUBSTANCE_FAMILIES)


def attention(row) -> int:
    return sum((row["by_family"] or {}).get(f, 0) for f in ATTENTION_FAMILIES)


def locations(conn, name: str) -> list[dict]:
    """Where federal money went in the period, by state, with its evidence.

    A table rather than a map. `build_map` drew dots on a blank rectangle with
    no coastline -- its own docstring admitted as much -- and a scatter with no
    map under it is not a map. The places and the dollars are what the block
    was ever for, and a table says them without pretending to cartography.
    """
    start, end = period_bounds(name)
    rows = conn.execute(
        "SELECT title, amount, lat, lon, url, tech_id FROM observations "
        "WHERE doc_date BETWEEN ? AND ? AND lat IS NOT NULL",
        (start, end),
    ).fetchall()
    from . import geo
    by_state: dict[str, dict] = {}
    for row in rows:
        # Nearest centroid rather than an exact match. The coordinates were
        # written from a centroid, but rounding and any future source that
        # geocodes more precisely would both miss an equality test.
        state = min(
            geo.STATE_CENTROIDS,
            key=lambda code: (geo.STATE_CENTROIDS[code][0] - row["lat"]) ** 2
            + (geo.STATE_CENTROIDS[code][1] - row["lon"]) ** 2,
        )
        entry = by_state.setdefault(state, {
            "state": state, "awards": 0, "dollars": 0.0, "awards_list": [],
            "technologies": set(),
        })
        entry["awards"] += 1
        entry["dollars"] += row["amount"] or 0
        entry["technologies"].add(row["tech_id"])
        entry["awards_list"].append({
            "title": row["title"], "amount": row["amount"], "url": row["url"],
            "tech_id": row["tech_id"],
        })
    for entry in by_state.values():
        entry["technologies"] = sorted(entry["technologies"])
        entry["awards_list"].sort(key=lambda award: -(award["amount"] or 0))
    return sorted(by_state.values(), key=lambda entry: -entry["dollars"])


def retrieved_by_family(conn, name: str) -> dict[str, int]:
    """The denominator, from the corpus table, by each document's own date.

    Counted at ingest and stored rather than recomputed, so a report does not
    have to walk fifty thousand raw files, and so the denominator agrees with
    the numerator: both are placed by the document's own date.
    """
    start, end = period_bounds(name)
    families: collections.Counter = collections.Counter()
    for source, count in store.corpus_between(conn, start, end).items():
        family = EVIDENCE_FAMILIES.get(source)
        if family:
            families[family] += count
    return dict(families)


ASSET_DIR = Path(__file__).resolve().parent / "assets"


@functools.lru_cache(maxsize=1)
def brand_logo() -> str:
    """The W. P. Carey / NASPO lockup as a data URI.

    Embedded rather than linked. A report is one file that gets emailed and
    opened out of a download folder, and a linked image would be a broken box
    everywhere but the machine that made it -- the same reason the charts are
    inline SVG. Cached because it is the same 45K on every render.
    """
    return "data:image/png;base64," + base64.b64encode(
        (ASSET_DIR / "naspo-logo.png").read_bytes()).decode("ascii")


def period_display(name: str) -> str:
    """`2026-Q2` is a filename. `2026 Q2` is a title."""
    return name.replace("-Q", " Q")


def build_context(conn, name: str, watchlist) -> dict:
    counts = totals(conn, name)
    weeks = weeks_in_period(name)
    ran = weeks_run(conn, name)
    partial = ran < len(weeks)
    # Eight weeks of share against a full thirteen is not a comparison, it is a
    # shortfall wearing a percentage sign. A quarter still filling up reports
    # its counts and withholds its movement.
    shifts = {} if partial else share_shift(conn, name)
    rows = []
    for tech in watchlist.active:
        row = counts.get(tech.id)
        if not row:
            continue
        concentrated = is_single_source(row)
        families = by_family(row["by_source"])
        # The family, not the top source. Showing the source's share beside a
        # verdict reached on the family's produced rows reading "48% arxiv"
        # next to a GATED mark, which a reader can only take as a mistake.
        top_family, top_count = families.most_common(1)[0]
        rows.append({
            "single_source": concentrated,
            "stage": FAMILY_STAGE.get(top_family, ""),
            "families": len([n for n in families.values() if n >= FAMILY_FLOOR]),
            "top_family": top_family,
            "id": tech.id,
            "name": tech.name,
            "family": tech.family,
            "total": row["total"],
            "filers": row["filers"],
            "by_source": {source: row["by_source"].get(source, 0) for source in SOURCES},
            "by_family": dict(families),
            "top_source": row["by_source"].most_common(1)[0][0],
            "concentration": round(100 * top_count / row["total"]),
            # Kept, not withheld. Concentration in one family is a statement
            # about which stage a technology is in, which is the question this
            # project asks; suppressing it deleted the finding along with the
            # risk. What remains of the original concern -- that a source's
            # coverage can masquerade as a technology's trajectory -- is handled
            # by naming the family and its share beside every number.
            "shift": shifts.get(tech.id),
        })
    # Quarterly metrics: substance against attention, lab to field, and where
    # in the pipeline a technology sits, each over the trailing four quarters.
    # A technology with no documents this quarter is left unscored, which is
    # what the weekly version got wrong.
    from . import metrics
    scores = {row["tech_id"]: row for row in metrics.compute_quarter(conn, name, watchlist)}
    # The second reason a score can be absent. `partial` asks whether this
    # period finished; this asks whether the periods it is scored against were
    # ever collected. 2025-Q4 ran all thirteen of its weeks and still could not
    # be scored, because only one quarter of its trailing four had been
    # collected -- and the page said nothing, because every withholding notice
    # was gated on `partial`.
    window = metrics.trailing_quarters(name)
    window_collected = len(metrics.collected_quarters(conn, window))
    short_history = window_collected < metrics.MIN_HISTORY_QUARTERS
    for row in rows:
        score = scores.get(row["id"], {})
        row["sai"] = score.get("sai")
        row["lfi"] = score.get("lfi")
        row["position"] = score.get("position")

    # The index needs every row's family breakdown, so it is a second pass.
    retrieved = retrieved_by_family(conn, name)
    for row in rows:
        row["rates"] = family_rates(row, retrieved)
    rows.sort(key=lambda item: -item["total"])
    # Sources a reader without a subscription cannot follow. Defined by what
    # they are rather than by absence from a hardcoded list: once supplemental
    # sources became first-class columns, "not in SOURCES" named nothing.
    human_fetched = set(supplemental.load().sources)
    licensed = sorted({
        source
        for row in counts.values()
        for source in row["by_source"]
        if source in human_fetched
    })
    movers = [row for row in rows if row["shift"] is not None]
    movers.sort(key=lambda item: -item["shift"])
    scored = sorted((row for row in rows if row.get("sai") is not None),
                    key=lambda row: -row["total"])[:BOARD_LIMIT]
    labels_dropped: dict[str, int] = {}
    printable: dict[str, str] = {}

    def legend(entries):
        """The key a numbered chart is unreadable without.

        Carries the figures as well as the name, so the table answers the
        questions the chart raises without a reader going back to the main
        listing.
        """
        return [
            {"n": index, "id": row["id"], "name": row["name"],
             "documents": row["total"], "stage": row.get("stage", ""),
             "sai": row.get("sai"), "position": row.get("position"),
             "concentration": row["concentration"], "top_family": row["top_family"]}
            for index, row in enumerate(entries, start=1)
        ]
    stage_points = [
        charts.Point(x=row["position"], y=row["sai"],
                     size=4 + min(10, row["total"] ** 0.5),
                     label=f"{row['name']} \u2014 {row['total']} documents",
                     colour="#A85B12")
        for row in scored if row.get("position") is not None
    ]

    return {
        "quarter": name,
        "period_display": period_display(name),
        "brand_logo": brand_logo(),
        "stage_points": stage_points,
        "stage_board": Markup(_chart(
            labels_dropped, printable, "stage board", stage_points,
            x_label="pipeline position (idea \u2192 diffusion)",
            y_label="substance minus attention", numbered=True,
        )) if stage_points else None,
        "summary": _summary(name, rows, counts, ran, len(weeks), partial,
                            short_history, window_collected, len(window)),
        "appendix_technologies": [
            {"id": tech.id, "name": tech.name, "family": tech.family,
             "description": _describe(tech)}
            for tech in watchlist.active
        ],
        "appendix_stages": [
            {"stage": stage, "sources": sorted(
                source for source, family in EVIDENCE_FAMILIES.items()
                if family in families_for_stage)}
            for stage, families_for_stage in STAGE_FAMILIES.items()
        ],
        "single_source_count": sum(1 for row in rows if row["single_source"]),
        "single_source_documents": sum(
            row["total"] for row in rows if row["single_source"]
        ),
        "single_source_share": SINGLE_SOURCE_SHARE,
        # A table of places, not a map. build_map drew dots on a blank
        # rectangle with no coastline, and a scatter with nothing under it is
        # not a map -- the places and the dollars were what the block was ever
        # for.
        "locations": locations(conn, name),
        "substance_rows": (sub := sorted(
            (row for row in rows if substance(row) or attention(row)),
            key=lambda row: -row["total"])[:BOARD_LIMIT]),
        "substance_chart": Markup(_chart(
            labels_dropped, printable, "substance and attention",
            [charts.Point(x=attention(row), y=substance(row),
                          size=4 + min(10, row["total"] ** 0.5),
                          label=f"{row['name']} — {substance(row)} building, "
                                f"{attention(row)} talking",
                          colour="#A85B12")
             for row in sub],
            x_label="attention", y_label="substance", diagonal=True, numbered=True,
            above="above: more built than said",
            below="below: more said than built",
        )),
        "labels_dropped": labels_dropped,
        "printable_charts": printable,
        "stage_legend": legend(scored),
        "substance_legend": legend(sub),
        "family_floor": FAMILY_FLOOR,
        "previous": previous_period(name),
        "weeks": weeks,
        "weeks_run": ran,
        "weeks_total": len(weeks),
        "period_label": "quarterly report" if "-Q" in name else "annual report",
        "period_noun": "quarter" if "-Q" in name else "year",
        "partial": partial,
        "short_history": short_history,
        "window_collected": window_collected,
        "window_total": len(window),
        "documents": sum(row["total"] for row in counts.values()),
        "rows": rows,
        "risers": movers[:8],
        "fallers": list(reversed(movers[-8:])) if movers else [],
        "silent": [
            {"id": tech.id, "name": tech.name}
            for tech in watchlist.active if tech.id not in counts
        ],
        "licensed": licensed,
        "filers_total": sum(row["filers"] for row in counts.values()),
        "lexicon_version": watchlist.version,
    }


def evidence_context(conn, name: str, watchlist) -> dict:
    """Every document behind a period's counts, by technology.

    Only technologies with documents get a section. Giving every active
    technology one put a wall of empty headings between the reader and the
    evidence -- on 2026-Q3, nine technologies with documents and forty-two
    sections.

    The ones with nothing are named at the bottom rather than dropped. A
    technology the system looked for and did not find is a finding, and it also
    keeps an anchor, so a link from the report is never dead.
    """
    start, end = period_bounds(name)
    rows = conn.execute(
        "SELECT tech_id, source, doc_id, doc_date, title, url, entity, matched_pattern "
        "FROM observations WHERE doc_date BETWEEN ? AND ? ORDER BY doc_date DESC",
        (start, end),
    ).fetchall()
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["tech_id"], []).append(dict(row))
    groups = [
        {"tech_id": tech.id, "name": tech.name, "rows": grouped[tech.id]}
        for tech in watchlist.active if grouped.get(tech.id)
    ]
    groups.sort(key=lambda group: -len(group["rows"]))
    return {
        "quarter": name,
        "period_noun": "quarter" if "-Q" in name else "year",
        "start": start,
        "end": end,
        "lexicon_version": watchlist.version,
        "groups": groups,
        "empty": [
            {"tech_id": tech.id, "name": tech.name}
            for tech in watchlist.active if not grouped.get(tech.id)
        ],
    }


def render_quarter(conn, name: str, watchlist, out_dir: Path | None = None) -> Path:
    template = render._environment().get_template("quarter.html.j2")
    directory = Path(out_dir) if out_dir else config.OUTPUT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"report-{name}.html"
    context = build_context(conn, name, watchlist)
    path.write_text(template.render(**context))
    # The charts again, on their own, for a slide or a paper. Inline SVG is
    # right for reading the report and useless for anything else.
    evidence = render._environment().get_template("evidence.html.j2")
    (directory / f"evidence-{name}.html").write_text(
        evidence.render(**evidence_context(conn, name, watchlist)))
    # The printable variants, not what the page shows. The page numbers its
    # dots, puts the name on hover and keys it with a table underneath; a file
    # has none of those, so the exported copy carries printed labels.
    export.write_charts(directory, name, {
        "substance-attention": context["printable_charts"].get("substance and attention"),
        "stage-board": context["printable_charts"].get("stage board"),
    })
    return path
