"""Dashboard rendering.

One self-contained HTML file: inline CSS, inline SVG, no scripts, no network at
view time. It has to open by double-click in five years and still work.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from . import charts, config, metrics, store

TEMPLATE_DIR = Path(__file__).parent / "templates"
FAMILY_COLOURS = {
    "automation": "#5b7fa6",
    "vehicles": "#8a6fa8",
    "digital": "#3f8f7a",
    "traceability": "#b5854b",
    "physical": "#a35f6d",
    "networks": "#5f7355",
}
MOVER_COUNT = 5
MAP_MIN_RADIUS = 3.0
MAP_MAX_RADIUS = 18.0


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def evidence_filename(week: str) -> str:
    """Each dashboard links to its own week's evidence.

    `evidence.html` is overwritten every run, so an archived dashboard that
    linked to it would send a reader of week W to the latest week's evidence
    with nothing to say the two disagree.
    """
    return f"evidence-{week}.html"


RISING_LIMIT = 12


def _rising_terms(conn, week: str) -> tuple[list[dict], int]:
    """The strongest candidates, and how many there were in all.

    Both, because the page shows a capped list and silent truncation is this
    project's oldest failure mode. A NULL total belongs to a row written before
    the column existed; falling back to what is shown is honest -- it says the
    list is whole, which is all that can be known about it.
    """
    rows = [dict(row) for row in store.candidates_for_week(conn, week)]
    for row in rows:
        row["examples"] = row.get("examples") or []
    total = max((row.get("total") or 0) for row in rows) if rows else 0
    return rows[:RISING_LIMIT], total or len(rows)


def dashboard_context(conn, week: str, watchlist, ok_sources=None) -> dict:
    """The weekly page, which is a collection health view and nothing more.

    It used to carry movers, a stage board, substance against attention, lab to
    field and a build map. All of that moved to the quarterly report, because a
    week cannot support it: two thirds of technology-weeks hold no observations
    and the median is zero, so a weekly ranking mostly reported which week a
    collector happened to catch something.

    It was also wrong in a way that showed. Ranking on a trailing z-score let a
    technology with nothing at all in the week sit at the top of "This Week's
    Movers" -- on 2026-W36, seven of the top eight had no documents in the week
    they were named for, and the evidence page each linked to said so.

    What a week can answer is whether the collectors ran and what arrived. That
    is what is left.
    """
    arrivals = conn.execute(
        "SELECT source, COUNT(*) AS n FROM observations WHERE week = ? "
        "GROUP BY source ORDER BY n DESC", (week,),
    ).fetchall()
    retrieved = conn.execute(
        "SELECT source, SUM(documents) AS n FROM corpus WHERE week = ? "
        "GROUP BY source", (week,),
    ).fetchall()
    return {
        "week": week,
        "lexicon_version": watchlist.version,
        # This week's runs, not the latest state. `source_runs` was created
        # for exactly this and the strip queried `sources` instead, so every
        # re-rendered archive week was stamped with today's status.
        "sources": store.source_runs_for_week(conn, week) or store.source_statuses(conn),
        "arrivals": [(row["source"], row["n"]) for row in arrivals],
        "retrieved": {row["source"]: row["n"] for row in retrieved},
        "matched_total": sum(row["n"] for row in arrivals),
        # The key the page and its tests have always used. Rising terms are a
        # collection concern -- what the sweep is finding that the lexicon does
        # not know -- so they stay on the weekly page rather than moving.
        "rising_terms": (rising := _rising_terms(conn, week))[0],
        "rising_total": rising[1],
    }


def unplaced_award_count(conn, week: str) -> int:
    """Federal awards whose place of performance would not resolve.

    The map draws only what it can place, so a week whose places would not
    resolve looks exactly like a quiet week. Spec §8 block 6: unresolvable
    locations are counted in a footnote rather than dropped silently.

    What makes an observation a map candidate is its source, not the presence
    of an amount: `hn` puts a story's points in `amount` and never sets
    coordinates, so counting every amount without a location would report
    Hacker News stories as federal awards that could not be placed.
    """
    row = conn.execute(
        "SELECT COUNT(*) AS total FROM observations WHERE week = ? "
        "AND source = 'usaspending' AND amount IS NOT NULL "
        "AND (lat IS NULL OR lon IS NULL)",
        (week,),
    ).fetchone()
    return int(row["total"])


def signals_in_play(conn, week: str, signals: tuple[str, ...]) -> list[str]:
    """Which of these signals this week actually has values for.

    The Substance vs. Attention axes are means over whatever is present, and
    with GDELT deferred "attention" is Hacker News alone. A reader cannot see
    that from the chart, so the block says which signals it is made of.
    """
    present = {
        row["signal"]
        for row in conn.execute(
            "SELECT DISTINCT signal FROM weekly_signals WHERE week = ?", (week,)
        )
    }
    return [signal for signal in signals if signal in present]


def build_map_points(conn, week: str) -> list[charts.Point]:
    rows = conn.execute(
        "SELECT tech_id, title, entity, amount, lat, lon FROM observations "
        "WHERE week = ? AND lat IS NOT NULL AND lon IS NOT NULL",
        (week,),
    ).fetchall()
    if not rows:
        return []
    amounts = [float(row["amount"] or 0) for row in rows]
    largest = max(amounts) or 1.0
    points = []
    for row, amount in zip(rows, amounts):
        # USAspending reports negative amounts for deobligations/corrections. A
        # shrinking award isn't a bigger build, so floor at zero before sizing —
        # otherwise a negative amount reaches **0.5 as a complex number.
        share = (max(amount, 0.0) / largest) ** 0.5
        label = " · ".join(
            part for part in (row["entity"], row["title"], _money(amount)) if part
        )
        points.append(
            charts.Point(
                x=float(row["lon"]),
                y=float(row["lat"]),
                label=label,
                size=MAP_MIN_RADIUS + share * (MAP_MAX_RADIUS - MAP_MIN_RADIUS),
            )
        )
    return points


def _money(amount: float) -> str:
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:,.1f}M"
    if amount > 0:
        return f"${amount:,.0f}"
    return ""


def _lfi_history(conn, tech_id: str, week: str, weeks: int = 12) -> list[float | None]:
    wanted = set(config.trailing_weeks(week, weeks))
    rows = conn.execute(
        "SELECT week, lfi FROM weekly_metrics WHERE tech_id = ? ORDER BY week", (tech_id,)
    ).fetchall()
    by_week = {row["week"]: row["lfi"] for row in rows if row["week"] in wanted}
    return [by_week.get(w) for w in config.trailing_weeks(week, weeks)]


def evidence_context(conn, week: str, watchlist) -> dict:
    rows = conn.execute(
        "SELECT tech_id, source, doc_id, doc_date, title, url, entity, matched_pattern "
        "FROM observations WHERE week = ? ORDER BY tech_id, doc_date DESC",
        (week,),
    ).fetchall()
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["tech_id"], []).append(dict(row))
    # Every active technology gets a section and an anchor, whether or not it
    # has observations this week -- the dashboard links all of them (Movers
    # and the warming-up footer), and a link into a missing anchor is a dead
    # link. A technology with no matches renders with a count of 0, which is
    # itself the information: the system looked and found nothing.
    return {
        "week": week,
        "lexicon_version": watchlist.version,
        "groups": [
            {"tech_id": tech.id, "name": tech.name, "rows": grouped.get(tech.id, [])}
            for tech in watchlist.active
        ],
    }


def render_evidence(
    conn, week: str, watchlist, out_path: Path | None = None, latest: bool = True
) -> Path:
    context = evidence_context(conn, week, watchlist)
    html = _environment().get_template("evidence.html.j2").render(**context)
    target = Path(out_path) if out_path else config.OUTPUT_DIR / f"evidence-{week}.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html)
    if out_path is None and latest:
        (config.OUTPUT_DIR / "evidence.html").write_text(html)
    return target


def render_dashboard(
    conn, week: str, watchlist, out_path: Path | None = None, latest: bool = True
) -> Path:
    """Write this week's dashboard, and its evidence page beside it.

    `latest` is what keeps the run week in `latest.html` when a run also
    re-renders an earlier week it wrote into: only the run week refreshes the
    unversioned copies.
    """
    context = dashboard_context(conn, week, watchlist)
    html = _environment().get_template("dashboard.html.j2").render(**context)
    target = Path(out_path) if out_path else config.OUTPUT_DIR / f"dashboard-{week}.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html)
    if out_path is None and latest:
        (config.OUTPUT_DIR / "latest.html").write_text(html)
    evidence_target = (
        None if out_path is None else target.parent / evidence_filename(week)
    )
    render_evidence(conn, week, watchlist, evidence_target, latest=latest)
    return target
