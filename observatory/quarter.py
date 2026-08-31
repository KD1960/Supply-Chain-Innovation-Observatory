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

import collections
import datetime as dt
import json

import yaml
from pathlib import Path

from markupsafe import Markup

from . import charts, config, render, store, supplemental

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
    "regulation": "deployment",
    "trade": "deployment",
    "filings": "diffusion",
    "community": "attention",
}


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


def map_points(conn, name: str) -> list:
    """Every located award in the period, as a dot.

    An award whose dollars were not reported still gets a dot: it is a place
    where capacity is being built, and dropping it would quietly shrink the
    map. Size is the square root of the money, so a hundred-million-dollar
    award is ten times a million-dollar one rather than a hundred.
    """
    weeks = weeks_in_period(name)
    placeholders = ",".join("?" for _ in weeks)
    rows = conn.execute(
        f"SELECT title, amount, lat, lon FROM observations "
        f"WHERE week IN ({placeholders}) AND lat IS NOT NULL AND lon IS NOT NULL",
        weeks,
    ).fetchall()
    points = []
    for row in rows:
        millions = (row["amount"] or 0) / 1e6
        size = 3 + min(14, (millions ** 0.5))
        money = f" — ${millions:.1f}M" if row["amount"] else ""
        points.append(charts.Point(
            x=row["lon"], y=row["lat"], size=size,
            label=f"{row['title'] or 'award'}{money}", colour="#A85B12"))
    return points


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
    return {
        "quarter": name,
        "single_source_count": sum(1 for row in rows if row["single_source"]),
        "single_source_documents": sum(
            row["total"] for row in rows if row["single_source"]
        ),
        "single_source_share": SINGLE_SOURCE_SHARE,
        "map_points": (points := map_points(conn, name)),
        # Markup, because the environment autoescapes: without it the SVG
        # arrives in the page as text and the block renders empty.
        "build_map": Markup(charts.build_map(points)),
        "substance_rows": (sub := [
            row for row in rows if substance(row) or attention(row)
        ]),
        "substance_chart": Markup(charts.scatter(
            [charts.Point(x=attention(row), y=substance(row),
                          size=4 + min(10, row["total"] ** 0.5),
                          label=f"{row['name']} — {substance(row)} building, "
                                f"{attention(row)} talking",
                          colour="#A85B12")
             for row in sub],
            x_label="attention", y_label="substance", diagonal=True,
        )),
        "family_floor": FAMILY_FLOOR,
        "previous": previous_period(name),
        "weeks": weeks,
        "weeks_run": ran,
        "weeks_total": len(weeks),
        "period_label": "quarterly report" if "-Q" in name else "annual report",
        "period_noun": "quarter" if "-Q" in name else "year",
        "partial": partial,
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


def render_quarter(conn, name: str, watchlist, out_dir: Path | None = None) -> Path:
    template = render._environment().get_template("quarter.html.j2")
    directory = Path(out_dir) if out_dir else config.OUTPUT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"report-{name}.html"
    path.write_text(template.render(**build_context(conn, name, watchlist)))
    return path
