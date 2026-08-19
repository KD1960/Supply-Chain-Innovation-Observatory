"""Scoring.

Every function here is pure and takes plain lists, so the maths can be tested
against series with known answers. Nothing in this module touches the network,
the clock, or a model. The one exception is `compute_week`, which reads from
the store to assemble those plain lists — but it still writes nothing.
"""

from __future__ import annotations

import math
import statistics

from . import config, normalize, store

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


def normalize_series(
    series: list[float | None], min_periods: int = config.MIN_HISTORY_WEEKS
) -> list[float | None]:
    """Put one signal's values on a unit scale.

    Signals differ wildly in magnitude — HN points run to the hundreds,
    arXiv papers to the dozens. Averaging them raw would let the loudest
    unit decide the ranking, so each series is centred and scaled against
    its own trailing window before it joins the composite.

    `min_periods` is a parameter because the momentum composite is now
    quarterly: four points, not fifty-two, so the weekly floor would blank it.
    """
    if observed(series) < min_periods:
        return [None] * len(series)
    filled = carry_forward(series)
    present = [value for value in filled if value is not None]
    centre = statistics.fmean(present)
    spread = statistics.pstdev(present)
    if spread == 0:
        return [None if value is None else 0.0 for value in filled]
    return [None if value is None else (value - centre) / spread for value in filled]


def trailing_mean(series: list[float], window: int) -> float:
    return statistics.fmean(series[-window:])


def acceleration(series: list[float | None]) -> float | None:
    """Change in the four-week slope: is growth itself speeding up?"""
    if observed(series) < config.MIN_HISTORY_WEEKS:
        return None
    filled = [value for value in carry_forward(series) if value is not None]
    now = trailing_mean(filled, 4)
    four_back = trailing_mean(filled[:-4], 4)
    eight_back = trailing_mean(filled[:-8], 4)
    return (now - four_back) - (four_back - eight_back)


QUARTER_WEEKS = 13
MIN_HISTORY_QUARTERS = 3
MIN_NONZERO_QUARTERS = 2
MIN_QUARTER_VOLUME = 12


def to_quarters(
    series: list[float | None], size: int = QUARTER_WEEKS, how: str = "sum"
) -> list[float | None]:
    """Fold a weekly series into quarters, oldest first.

    Cut from the most recent week backwards, so a short leading remainder
    cannot shift every later boundary by a week. A quarter in which no week was
    observed stays None -- the hole rule one level up: a quarter we never saw
    is not a quarter in which nothing happened.

    `how` distinguishes a flow from a stock. Papers and repositories are flows:
    thirteen weeks of them add up. `edgar_filers` is a stock -- distinct
    companies over a trailing window -- so the same companies reappear in it
    every week, and adding thirteen weeks of it multiplies them.
    """
    quarters: list[float | None] = []
    end = len(series)
    while end > 0:
        start = max(0, end - size)
        present = [value for value in series[start:end] if value is not None]
        if not present:
            quarters.append(None)
        elif how == "last":
            quarters.append(float(present[-1]))
        else:
            quarters.append(float(sum(present)))
        end = start
    quarters.reverse()
    return quarters


def has_trend_support(quarters: list[float | None]) -> bool:
    """Whether a signal has enough presence for its shape to mean anything.

    Most of `weekly_signals` is observed zeros, so a technology seen once in a
    year still has a full, mostly-flat series. Normalising that divides by a
    near-zero spread and hands the single document a large z-score: three
    documents in a year is how manufacturing execution systems came to rank
    first. Two present quarters are the fewest from which a trend can be read.

    A fall to zero still qualifies, on two non-zero quarters out of three. The
    guard is against absence, not against bad news.

    The volume floor is the same argument by magnitude. Below twelve across
    three quarters at least one quarter averages under four a week, and the
    second difference is then decided by which quarter a single document landed
    in rather than by any trend.
    """
    recent = quarters[-MIN_HISTORY_QUARTERS:]
    present = [value for value in recent if value]
    if len(present) < MIN_NONZERO_QUARTERS:
        return False
    return sum(present) >= MIN_QUARTER_VOLUME


def quarterly_acceleration(quarters: list[float | None]) -> float | None:
    """Second difference of the last three quarters: is growth speeding up?

    The weekly version averages 4-week windows because a single week is mostly
    noise. At quarterly resolution each point is already an aggregate of
    thirteen weeks, so the plain second difference is the whole measurement.

    All three must be present. Bridging a missing quarter with the one before
    it would invent a trend across the gap.
    """
    if len(quarters) < MIN_HISTORY_QUARTERS:
        return None
    recent = quarters[-MIN_HISTORY_QUARTERS:]
    if any(value is None for value in recent):
        return None
    older, middle, newest = recent
    return (newest - middle) - (middle - older)


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
STOCK_SIGNALS = frozenset(
    aggregation.signal
    for aggregation in normalize.AGGREGATIONS
    if aggregation.trailing_weeks is not None
)
SOFT_SIGNALS = ("media_articles", "hn_points")

STAGE_INDEX = {stage: position for position, stage in enumerate(STAGES, start=1)}
MOMENTUM_SUPPRESSION_WEEKS = 8


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


def momentum_suppressed(tech, week: str) -> bool:
    """A widened pattern looks exactly like real acceleration. Do not report it."""
    cutoff = config.week_offset(week, -MOMENTUM_SUPPRESSION_WEEKS)
    return tech.patterns_changed_week > cutoff


def compute_week(conn, week: str, watchlist) -> list[dict]:
    weeks = config.trailing_weeks(week, config.TRAILING_WEEKS)
    raw_accelerations: dict[str, float | None] = {}
    partial: dict[str, dict] = {}

    for tech in watchlist.active:
        z_by_signal: dict[str, float | None] = {}
        composite_inputs: list[list[float | None]] = []
        for signal in ALL_SIGNALS:
            series = store.signal_series(conn, tech.id, signal, weeks)
            # Stages, SAI and LFI stay weekly: they describe where a technology
            # sits, and the latest week is the honest answer to that.
            z_by_signal[signal] = zscore(series)
            # Momentum does not. Two thirds of technology-weeks in this corpus
            # hold zero observations, so a weekly slope is mostly measuring
            # which week a collector happened to catch something. Raw counts
            # are summed into quarters first, then normalised.
            quarters = to_quarters(
                series, how="last" if signal in STOCK_SIGNALS else "sum"
            )
            if has_trend_support(quarters):
                composite_inputs.append(
                    normalize_series(quarters, min_periods=MIN_HISTORY_QUARTERS)
                )

        stages = stage_scores(z_by_signal)
        composite = _composite_series(composite_inputs)
        raw = quarterly_acceleration(composite)
        raw_accelerations[tech.id] = None if momentum_suppressed(tech, week) else raw

        partial[tech.id] = {
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
        }

    momentum_by_tech = cross_sectional_z(raw_accelerations)
    for tech_id, row in partial.items():
        row["momentum"] = momentum_by_tech[tech_id]
    return [partial[tech.id] for tech in watchlist.active]


def _adoption(filers: float | None) -> int | None:
    """An absent edgar_filers signal is not zero adopters.

    weekly_signals leaves the row out on a week EDGAR failed, and folding that
    into 0 would print a hard "0 adopters" for every technology on the week we
    happened not to look — the fabricated decline the hole rule exists to
    prevent, wearing the most authoritative number on the page.
    """
    return None if filers is None else int(filers)


def _composite_series(series_list: list[list[float | None]]) -> list[float | None]:
    """Mean across signals, week by week, of whatever is present."""
    if not series_list:
        return []
    length = len(series_list[0])
    return [
        mean_of_present([series[index] for series in series_list])
        for index in range(length)
    ]


def _exp(value: float) -> float:
    """Clamped exponential — softmax weights must not overflow on an outlier."""
    return math.exp(max(min(value, 20.0), -20.0))
