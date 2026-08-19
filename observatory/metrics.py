"""Scoring.

Every function here is pure and takes plain lists, so the maths can be tested
against series with known answers. Nothing in this module touches the network,
the clock, or a model. The one exception is `compute_week`, which reads from
the store to assemble those plain lists — but it still writes nothing.
"""

from __future__ import annotations

import math
import statistics

from . import config, store

STAGES = ("idea", "experiment", "investment", "deployment", "diffusion")


def carry_forward(series: list[float | None]) -> list[float | None]:
    filled: list[float | None] = []
    last: float | None = None
    for value in series:
        if value is None:
            filled.append(last)
        else:
            filled.append(value)
            last = value
    return filled


def mean_of_present(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return statistics.fmean(present) if present else None


def observed(series: list[float | None]) -> int:
    """Weeks we actually saw, counted before any carry-forward.

    The history gate has to count these and not the carried series. A
    five-week source outage pads ten identical values into the window; those
    duplicates would pass a length check while shrinking the spread, which
    inflates every z-score computed from them.
    """
    return sum(1 for value in series if value is not None)


def zscore(series: list[float | None], min_periods: int = config.MIN_HISTORY_WEEKS) -> float | None:
    if observed(series) < min_periods:
        return None
    filled = [value for value in carry_forward(series) if value is not None]
    spread = statistics.pstdev(filled)
    if spread == 0:
        return 0.0
    return (filled[-1] - statistics.fmean(filled)) / spread


SIGNALS_BY_STAGE: dict[str, tuple[str, ...]] = {
    "idea": ("arxiv_papers", "hn_points"),
    "experiment": ("patents", "gh_repos_new", "gh_commits", "gh_stars_delta"),
    "investment": ("fed_obligated", "edgar_filings"),
    "deployment": ("fed_awards", "fedreg_docs", "media_deploy"),
    "diffusion": ("edgar_filers", "media_articles"),
}

ALL_SIGNALS = tuple(
    signal for signals in SIGNALS_BY_STAGE.values() for signal in signals
)

HARD_SIGNALS = ("patents", "gh_repos_new", "gh_commits", "fed_awards", "edgar_filers")
# A signal aggregated over its own trailing window is a stock, not a flow.
SOFT_SIGNALS = ("media_articles", "hn_points")

STAGE_INDEX = {stage: position for position, stage in enumerate(STAGES, start=1)}


def stage_scores(z_by_signal: dict[str, float | None]) -> dict[str, float | None]:
    return {
        stage: mean_of_present([z_by_signal.get(signal) for signal in signals])
        for stage, signals in SIGNALS_BY_STAGE.items()
    }


def pipeline_position(stages: dict[str, float | None]) -> float | None:
    present = {stage: value for stage, value in stages.items() if value is not None}
    if not present:
        return None
    weights = {stage: _exp(value) for stage, value in present.items()}
    total = sum(weights.values())
    return sum(STAGE_INDEX[stage] * weight for stage, weight in weights.items()) / total


def substance_index(z_by_signal: dict[str, float | None]) -> float | None:
    hard = mean_of_present([z_by_signal.get(signal) for signal in HARD_SIGNALS])
    soft = mean_of_present([z_by_signal.get(signal) for signal in SOFT_SIGNALS])
    if hard is None or soft is None:
        return None
    return hard - soft


def lab_to_field(stages: dict[str, float | None]) -> float | None:
    late = mean_of_present([stages.get("investment"), stages.get("deployment")])
    early = mean_of_present([stages.get("idea"), stages.get("experiment")])
    if late is None or early is None:
        return None
    return late - early


def compute_week(conn, week: str, watchlist) -> list[dict]:
    weeks = config.trailing_weeks(week, config.TRAILING_WEEKS)
    rows: list[dict] = []
    for tech in watchlist.active:
        z_by_signal = {
            signal: zscore(store.signal_series(conn, tech.id, signal, weeks))
            for signal in ALL_SIGNALS
        }
        stages = stage_scores(z_by_signal)
        rows.append({
            "tech_id": tech.id,
            "week": week,
            "sai": substance_index(z_by_signal),
            "lfi": lab_to_field(stages),
            "adoption": _adoption(store.get_signal(conn, tech.id, week, "edgar_filers")),
            "adoption_new": 0,
            "stage_idea": stages["idea"],
            "stage_experiment": stages["experiment"],
            "stage_investment": stages["investment"],
            "stage_deployment": stages["deployment"],
            "stage_diffusion": stages["diffusion"],
            "position": pipeline_position(stages),
            "lexicon_version": watchlist.version,
        })
    return rows


def _adoption(filers: float | None) -> int | None:
    """An absent edgar_filers signal is not zero adopters.

    weekly_signals leaves the row out on a week EDGAR failed, and folding that
    into 0 would print a hard "0 adopters" for every technology on the week we
    happened not to look — the fabricated decline the hole rule exists to
    prevent, wearing the most authoritative number on the page.
    """
    return None if filers is None else int(filers)


def _exp(value: float) -> float:
    """Clamped exponential — softmax weights must not overflow on an outlier."""
    return math.exp(max(min(value, 20.0), -20.0))
