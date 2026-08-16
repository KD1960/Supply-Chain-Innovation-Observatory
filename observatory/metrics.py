"""Scoring.

Every function here is pure and takes plain lists, so the maths can be tested
against series with known answers. Nothing in this module touches the network,
the clock, or a model.
"""

from __future__ import annotations

import statistics

from . import config

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


def zscore(series: list[float | None], min_periods: int = config.MIN_HISTORY_WEEKS) -> float | None:
    filled = [value for value in carry_forward(series) if value is not None]
    if len(filled) < min_periods:
        return None
    spread = statistics.pstdev(filled)
    if spread == 0:
        return 0.0
    return (filled[-1] - statistics.fmean(filled)) / spread


def trailing_mean(series: list[float], window: int) -> float:
    return statistics.fmean(series[-window:])


def acceleration(series: list[float | None]) -> float | None:
    """Change in the four-week slope: is growth itself speeding up?"""
    filled = [value for value in carry_forward(series) if value is not None]
    if len(filled) < config.MIN_HISTORY_WEEKS:
        return None
    now = trailing_mean(filled, 4)
    four_back = trailing_mean(filled[:-4], 4)
    eight_back = trailing_mean(filled[:-8], 4)
    return (now - four_back) - (four_back - eight_back)


def cross_sectional_z(values: dict[str, float | None]) -> dict[str, float | None]:
    present = [value for value in values.values() if value is not None]
    if len(present) < 2:
        return {key: None for key in values}
    centre = statistics.fmean(present)
    spread = statistics.pstdev(present)
    if spread == 0:
        return {key: (None if value is None else 0.0) for key, value in values.items()}
    return {
        key: (None if value is None else (value - centre) / spread)
        for key, value in values.items()
    }
