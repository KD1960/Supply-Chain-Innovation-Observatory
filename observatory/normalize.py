"""Observations to weekly signals.

The only subtle rule lives here: a source that failed this week must leave its
signals absent, not zero. A zero says "nothing happened"; an absence says "we
did not look". Confusing the two invents declines that never occurred.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import config, store
from .matcher import Watchlist


@dataclass(frozen=True)
class Aggregation:
    signal: str
    source: str
    method: str  # "count" | "sum_amount" | "distinct_entities"
    entity_filter: str | None = None
    trailing_weeks: int | None = None


AGGREGATIONS: tuple[Aggregation, ...] = (
    Aggregation("arxiv_papers", "arxiv", "count"),
    Aggregation("hn_points", "hn", "sum_amount"),
    Aggregation("fedreg_docs", "federalregister", "count"),
    Aggregation("media_articles", "gdelt_doc", "count"),
    Aggregation("media_deploy", "gdelt_doc", "count", entity_filter="deployment"),
    Aggregation("fed_obligated", "usaspending", "sum_amount"),
    Aggregation("fed_awards", "usaspending", "count"),
    Aggregation("edgar_filings", "edgar", "count"),
    Aggregation("edgar_filers", "edgar", "distinct_entities",
                trailing_weeks=config.TRAILING_WEEKS),
)


def signals_for_source(source: str) -> list[Aggregation]:
    return [aggregation for aggregation in AGGREGATIONS if aggregation.source == source]


def compute_signals(conn, week: str, watchlist: Watchlist, ok_sources: set[str]) -> int:
    written = 0
    for aggregation in AGGREGATIONS:
        if aggregation.source not in ok_sources:
            continue
        totals = _totals(conn, week, aggregation)
        for tech in watchlist.active:
            store.set_signal(
                conn, tech.id, week, aggregation.signal, float(totals.get(tech.id, 0.0))
            )
            written += 1
    return written


EXPRESSIONS = {
    "count": "COUNT(*)",
    "sum_amount": "COALESCE(SUM(amount), 0)",
    "distinct_entities": "COUNT(DISTINCT entity_id)",
}


def _totals(conn, week: str, aggregation: Aggregation) -> dict[str, float]:
    expression = EXPRESSIONS[aggregation.method]
    query = f"SELECT tech_id, {expression} AS total FROM observations WHERE source = ?"
    params: list = [aggregation.source]

    if aggregation.trailing_weeks:
        window = config.trailing_weeks(week, aggregation.trailing_weeks)
        query += f" AND week IN ({','.join('?' * len(window))})"
        params += window
    else:
        query += " AND week = ?"
        params.append(week)

    if aggregation.entity_filter is not None:
        query += " AND entity = ?"
        params.append(aggregation.entity_filter)

    if aggregation.method == "distinct_entities":
        query += " AND entity_id IS NOT NULL"

    rows = conn.execute(query + " GROUP BY tech_id", params).fetchall()
    return {row["tech_id"]: float(row["total"]) for row in rows}
