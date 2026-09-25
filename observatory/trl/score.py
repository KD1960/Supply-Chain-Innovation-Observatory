# observatory/trl/score.py
"""Claims in, a TRL estimate out. Deterministic, and every number traceable
to the weights table and the claims listed in the result (spec §4, C4)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import schema

WEIGHTS_PATH = Path(__file__).with_name("weights.yaml")
LEVELS = tuple(range(1, 10))
UNDATED_AGE_DAYS = 365 * 2  # an undated document is treated as two years old
CONTRARY_LEVELS = (7, 8, 9)  # the levels an "abandons" claim dents, whatever its setting


@dataclass(frozen=True)
class Weights:
    version: int
    half_life_days: int
    support_threshold: float
    contrary_penalty: float
    actor: dict
    source: dict
    setting: dict


@dataclass(frozen=True)
class TRLEstimate:
    point: int | None
    low: int | None
    high: int | None
    support: dict = field(default_factory=dict)
    top: list = field(default_factory=list)
    contrary: dict | None = None
    n_claims: int = 0
    n_verified: int = 0
    # True when some level reached the support threshold. When False, `point` is
    # None ("insufficient evidence") and `low`/`high` still give the span of
    # levels the claims evidence; no level is printed that the evidence does not hold.
    held: bool = False
    # Cumulative support per level, as the threshold sees it (each claim once).
    cumulative: dict = field(default_factory=dict)


def load_weights(path: Path | None = None) -> Weights:
    raw = yaml.safe_load((path or WEIGHTS_PATH).read_text())
    return Weights(**{k: raw[k] for k in ("version", "half_life_days", "support_threshold",
                                          "contrary_penalty", "actor", "source", "setting")})


def _days_old(claim: dict, as_of: dt.date) -> int:
    try:
        return max(0, (as_of - dt.date.fromisoformat(str(claim.get("doc_date"))[:10])).days)
    except (TypeError, ValueError):
        return UNDATED_AGE_DAYS


def claim_weight(claim: dict, as_of: dt.date, w: Weights) -> float:
    if not claim.get("quote_verified"):
        return 0.0
    recency = 0.5 ** (_days_old(claim, as_of) / w.half_life_days)
    return (w.actor[claim["actor_type"]] * w.source[claim["source_type"]]
            * w.setting[claim["setting"]] * recency)


def estimate(claims: list[dict], as_of: dt.date, w: Weights) -> TRLEstimate:
    support = {level: 0.0 for level in LEVELS}
    weighted: list[tuple[float, dict]] = []
    contrary: tuple[float, dict] | None = None
    contrary_total = 0.0
    n_verified = 0
    for claim in claims:
        weight = claim_weight(claim, as_of, w)
        n_verified += 1 if claim.get("quote_verified") else 0
        if weight == 0.0:
            continue
        if claim["claim_type"] == "abandons":
            # An "abandons" claim always dents levels 7-9, whatever its own setting:
            # contrary_penalty * its weight comes off the displayed support at each of
            # 7, 8 and 9, and off the cumulative support at 7, 8 and 9 (below).
            for level in CONTRARY_LEVELS:
                support[level] -= w.contrary_penalty * weight
            contrary_total += w.contrary_penalty * weight
            if contrary is None or weight > contrary[0]:
                contrary = (weight, claim)
            continue
        lo, hi = schema.BAND[claim["claim_type"]]
        for level in range(lo, hi + 1):
            support[level] += weight
        weighted.append((weight, claim))
    if not weighted:
        return TRLEstimate(None, None, None, support, [], contrary[1] if contrary else None,
                           len(claims), n_verified)
    # Cumulative support at level L: the weights of the claims whose band reaches
    # L or higher, each claim counted ONCE however many levels its band spans,
    # less the contrary weight at levels 7-9. `support` (per level) is for display.
    cumulative = {}
    for level in LEVELS:
        total = sum(wt for wt, c in weighted if schema.BAND[c["claim_type"]][1] >= level)
        if level in CONTRARY_LEVELS:
            total -= contrary_total
        cumulative[level] = max(0.0, total)
    held = [level for level in LEVELS if cumulative[level] >= w.support_threshold]
    point = max(held) if held else None
    evidenced = [level for level in LEVELS if support[level] > 0]
    if evidenced:
        low, high = min(evidenced), max(evidenced)
    else:  # every positive level was cancelled by contrary claims
        low = min(schema.BAND[c["claim_type"]][0] for _, c in weighted)
        high = max(schema.BAND[c["claim_type"]][1] for _, c in weighted)
    # The claims shown: the heaviest at the held point, or, with no level held,
    # the heaviest overall.
    shown = weighted if point is None else [
        (wt, c) for wt, c in weighted
        if schema.BAND[c["claim_type"]][0] <= point <= schema.BAND[c["claim_type"]][1]]
    shown = shown or weighted  # a point reached only below contrary-dented levels
    top = [c for _, c in sorted(shown, key=lambda x: -x[0])[:3]]
    return TRLEstimate(point, low, high, support, top, contrary[1] if contrary else None,
                       len(claims), n_verified, bool(held), cumulative)
