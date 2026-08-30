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
import math
from pathlib import Path

from markupsafe import Markup

from . import charts, config, render, supplemental

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
    weeks = weeks_in_period(name)
    placeholders = ",".join("?" for _ in weeks)
    rows = conn.execute(
        f"SELECT tech_id, source, COUNT(*) AS n FROM observations "
        f"WHERE week IN ({placeholders}) GROUP BY tech_id, source",
        weeks,
    ).fetchall()
    filers = conn.execute(
        f"SELECT tech_id, COUNT(DISTINCT entity_id) AS n FROM observations "
        f"WHERE week IN ({placeholders}) AND source = 'edgar' "
        f"AND entity_id IS NOT NULL GROUP BY tech_id",
        weeks,
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


def family_scale(rows) -> dict[str, dict[int, float]]:
    """Where each document count sits within its own family, 0-100.

    Within the family, because the families are not the same size and never
    will be: GitHub retrieved 30,459 documents in 2026-Q3 against Hacker
    News's 2,304, and six Federal Register notices is a lot of Federal
    Register. A raw count says which source is large; a percentile within the
    family says how a technology stands in the evidence that family produced.
    """
    families = {family for row in rows for family in row["by_family"]}
    scale: dict[str, dict[int, float]] = {}
    for family in families:
        counts = sorted(row["by_family"].get(family, 0) for row in rows)
        span = max(len(counts) - 1, 1)
        scale[family] = {
            count: 100 * sum(1 for other in counts if other < count) / span
            for count in set(counts)
        }
    return scale


def index_for(row, scale: dict[str, dict[int, float]]) -> float | None:
    """A technology's standing across families, 0-100, weighted by evidence.

    Weighted by `log1p` of each family's document count, so a family that
    supplied twenty-seven documents counts for more than one that supplied
    one -- but not twenty-seven times more. Weighting families equally instead
    says three documents spread across three families are worth thirty spread
    across three, which is more confidence than the evidence carries.
    """
    pairs = [
        (scale.get(family, {}).get(count, 0.0), math.log1p(count))
        for family, count in (row["by_family"] or {}).items() if count
    ]
    total = sum(weight for _, weight in pairs)
    if not total:
        return None
    return round(sum(value * weight for value, weight in pairs) / total, 1)


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
        gated = is_single_source(row)
        families = by_family(row["by_source"])
        # The family, not the top source. Showing the source's share beside a
        # verdict reached on the family's produced rows reading "48% arxiv"
        # next to a GATED mark, which a reader can only take as a mistake.
        top_family, top_count = families.most_common(1)[0]
        rows.append({
            "single_source": gated,
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
            # Withheld rather than annotated. The counts stay -- they are
            # observations, and hiding them would hide that the evidence exists.
            "shift": None if gated else shifts.get(tech.id),
        })
    # The index needs every row's family breakdown, so it is a second pass.
    scale = family_scale(rows)
    for row in rows:
        # Withheld for a gated technology, like every other inference here: a
        # single-family index is that family's coverage wearing a score.
        row["index"] = None if row["single_source"] else index_for(row, scale)
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
