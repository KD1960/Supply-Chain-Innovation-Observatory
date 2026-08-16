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


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def build_context(conn, week: str, watchlist) -> dict:
    names = {tech.id: tech.name for tech in watchlist.technologies}
    families = {tech.id: tech.family for tech in watchlist.technologies}
    rows = store.metrics_for_week(conn, week)

    scored = [row for row in rows if row.get("momentum") is not None]
    warming = [names.get(row["tech_id"], row["tech_id"]) for row in rows
               if row.get("momentum") is None]
    scored.sort(key=lambda row: row["momentum"], reverse=True)

    movers = [
        {
            "name": names.get(row["tech_id"], row["tech_id"]),
            "family": families.get(row["tech_id"], ""),
            "momentum": row["momentum"],
            "sai": row["sai"],
            "lfi": row["lfi"],
            "adoption": row["adoption"] or 0,
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
        "warming_up": sorted(warming),
    }


def _lfi_history(conn, tech_id: str, week: str, weeks: int = 12) -> list[float | None]:
    wanted = set(config.trailing_weeks(week, weeks))
    rows = conn.execute(
        "SELECT week, lfi FROM weekly_metrics WHERE tech_id = ? ORDER BY week", (tech_id,)
    ).fetchall()
    by_week = {row["week"]: row["lfi"] for row in rows if row["week"] in wanted}
    return [by_week.get(w) for w in config.trailing_weeks(week, weeks)]


def render_dashboard(conn, week: str, watchlist, out_path: Path | None = None) -> Path:
    context = build_context(conn, week, watchlist)
    html = _environment().get_template("dashboard.html.j2").render(**context)
    target = Path(out_path) if out_path else config.OUTPUT_DIR / f"dashboard-{week}.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html)
    if out_path is None:
        (config.OUTPUT_DIR / "latest.html").write_text(html)
    return target
