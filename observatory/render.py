"""Dashboard rendering.

One self-contained HTML file: inline CSS, inline SVG, no scripts, no network at
view time. It has to open by double-click in five years and still work.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from . import charts, config, store

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


def build_context(conn, week: str, watchlist) -> dict:
    names = {tech.id: tech.name for tech in watchlist.technologies}
    families = {tech.id: tech.family for tech in watchlist.technologies}
    rows = store.metrics_for_week(conn, week)

    scored = [row for row in rows if row.get("momentum") is not None]
    warming = [
        {"tech_id": row["tech_id"], "name": names.get(row["tech_id"], row["tech_id"])}
        for row in rows if row.get("momentum") is None
    ]
    scored.sort(key=lambda row: row["momentum"], reverse=True)

    movers = [
        {
            "tech_id": row["tech_id"],
            "name": names.get(row["tech_id"], row["tech_id"]),
            "family": families.get(row["tech_id"], ""),
            "momentum": row["momentum"],
            "sai": row["sai"],
            "lfi": row["lfi"],
            "adoption": row["adoption"],
        }
        for row in scored[:MOVER_COUNT]
    ]

    stage_points = [
        charts.Point(
            x=row["position"], y=row["momentum"],
            label=f"{names.get(row['tech_id'], row['tech_id'])} "
                  f"(position {row['position']:.1f}, momentum {row['momentum']:+.2f})",
            colour=FAMILY_COLOURS.get(families.get(row["tech_id"], ""), "#5b7fa6"),
        )
        for row in scored if row.get("position") is not None
    ]

    substance_points = [
        charts.Point(
            x=row["sai"], y=row["lfi"],
            label=f"{names.get(row['tech_id'], row['tech_id'])} "
                  f"(substance {row['sai']:+.2f}, lab-to-field {row['lfi']:+.2f})",
            colour=FAMILY_COLOURS.get(families.get(row["tech_id"], ""), "#5b7fa6"),
        )
        for row in rows if row.get("sai") is not None and row.get("lfi") is not None
    ]

    crossovers = [
        {
            "name": names.get(row["tech_id"], row["tech_id"]),
            "lfi": row["lfi"],
            "spark": Markup(charts.sparkline(_lfi_history(conn, row["tech_id"], week))),
        }
        for row in rows if (row.get("lfi") or 0) > 0
    ]
    crossovers.sort(key=lambda row: row["lfi"], reverse=True)

    return {
        "week": week,
        "evidence_href": evidence_filename(week),
        "generated_for": dt.date.today().isoformat(),
        "lexicon_version": watchlist.version,
        "sources": store.source_statuses(conn),
        "movers": movers,
        "stage_board_svg": Markup(
            charts.scatter(stage_points, x_label="Pipeline position", y_label="Momentum")
        ),
        "substance_svg": Markup(
            charts.scatter(substance_points, x_label="Substance minus attention",
                           y_label="Lab to field")
        ),
        "crossovers": crossovers,
        "warming_up": sorted(warming, key=lambda tech: tech["name"]),
        "build_map_svg": Markup(charts.build_map(build_map_points(conn, week))),
    }


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
    context = build_context(conn, week, watchlist)
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
