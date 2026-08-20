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
from pathlib import Path

from . import config, render

QUARTER_WEEKS = 13
# The six public collectors. Anything else in `observations` arrived through a
# hand-made export from a licensed database (see manual.py), which a reader
# without a subscription cannot follow -- so the report says so.
SOURCES = ("arxiv", "github", "hn", "edgar", "federalregister", "usaspending")


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
        top_source, top_count = row["by_source"].most_common(1)[0]
        rows.append({
            "id": tech.id,
            "name": tech.name,
            "family": tech.family,
            "total": row["total"],
            "filers": row["filers"],
            "by_source": {source: row["by_source"].get(source, 0) for source in SOURCES},
            "top_source": top_source,
            "concentration": round(100 * top_count / row["total"]),
            "shift": shifts.get(tech.id),
        })
    rows.sort(key=lambda item: -item["total"])
    licensed = sorted({
        source
        for row in counts.values()
        for source in row["by_source"]
        if source not in SOURCES
    })
    movers = [row for row in rows if row["shift"] is not None]
    movers.sort(key=lambda item: -item["shift"])
    return {
        "quarter": name,
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
