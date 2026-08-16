"""Observations to weekly signals.

The only subtle rule lives here: a source that failed this week must leave its
signals absent, not zero. A zero says "nothing happened"; an absence says "we
did not look". Confusing the two invents declines that never occurred.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import store
from .matcher import Watchlist


@dataclass(frozen=True)
class Aggregation:
    signal: str
    source: str
    method: str  # "count" | "sum_amount"


AGGREGATIONS: tuple[Aggregation, ...] = (
    Aggregation("arxiv_papers", "arxiv", "count"),
    Aggregation("hn_points", "hn", "sum_amount"),
    Aggregation("fedreg_docs", "federalregister", "count"),
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


def _totals(conn, week: str, aggregation: Aggregation) -> dict[str, float]:
    expression = "COUNT(*)" if aggregation.method == "count" else "COALESCE(SUM(amount), 0)"
    rows = conn.execute(
        f"SELECT tech_id, {expression} AS total FROM observations "
        "WHERE week = ? AND source = ? GROUP BY tech_id",
        (week, aggregation.source),
    ).fetchall()
    return {row["tech_id"]: float(row["total"]) for row in rows}
