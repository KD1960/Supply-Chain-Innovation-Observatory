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
    # True when some level reached the support threshold; False when the point is
    # the fallback -- the lowest band any claim evidences -- or there is no point.
    held: bool = False


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
    n_verified = 0
    for claim in claims:
        weight = claim_weight(claim, as_of, w)
        n_verified += 1 if claim.get("quote_verified") else 0
        if weight == 0.0:
            continue
        if claim["claim_type"] == "abandons":
            # The band it contradicts is the one its setting would otherwise evidence:
            # treat it as an operation-level claim withdrawn.
            for level in range(7, 10):
                support[level] -= w.contrary_penalty * weight
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
    # Cumulative support from the top: a level is held if it, or anything above it, is evidenced enough.
    cumulative, running = {}, 0.0
    for level in reversed(LEVELS):
        running += max(0.0, support[level])
        cumulative[level] = running
    held = [level for level in LEVELS if cumulative[level] >= w.support_threshold]
    point = max(held) if held else min(schema.BAND[c["claim_type"]][0] for _, c in weighted)
    evidenced = [level for level in LEVELS if support[level] > 0]
    low, high = min(evidenced), max(evidenced)
    at_point = [(wt, c) for wt, c in weighted
                if schema.BAND[c["claim_type"]][0] <= point <= schema.BAND[c["claim_type"]][1]]
    top = [c for _, c in sorted(at_point, key=lambda x: -x[0])[:3]]
    return TRLEstimate(point, low, high, support, top, contrary[1] if contrary else None,
                       len(claims), n_verified, bool(held))
