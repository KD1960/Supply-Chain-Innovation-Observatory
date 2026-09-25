# observatory/trl/report.py
"""The TRL page: one estimate per tracked technology, the claims behind it,
and what moved since last period. Reads claims and weights; calls no model."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .. import config, matcher, quarter, render as weekly_render
from . import score, tracked

TRL_DIR = config.DATA_DIR / "trl"

NOTES = (
    "Pilot-band evidence (TRL 5-8) is collected only from sources that permit mining; "
    "see the probe report for what that covers this period.",
    "A technology whose claims do not add up to the support threshold at any level is shown as "
    "'insufficient evidence' with the span of levels its claims evidence; no level is printed "
    "that the evidence does not hold. See the placement report for the period this was last checked.",
)


class ClaimsMissing(ValueError):
    """Asked for a period whose claims have not been extracted."""


def load_claims(path: Path) -> list[dict]:
    """Claim rows, one per (claim_id, claim_type), the last occurrence kept.
    The extraction appends, so a re-run of a period would otherwise count
    every claim twice."""
    rows: dict[tuple[str, str], dict] = {}
    for line in path.read_text(encoding="utf8").splitlines():
        if line.strip():
            r = json.loads(line)
            if "claim_id" in r:
                key = (r["claim_id"], r.get("claim_type"))
                rows.pop(key, None)  # re-insert so order follows the last occurrence
                rows[key] = r
    return list(rows.values())


def _previous(directory: Path, period: str) -> dict:
    p = directory / f"estimates-{quarter.previous_period(period)}.json"
    if not p.exists():
        return {}
    data = json.loads(p.read_text())
    return data.get("estimates", data)


def _order(t: dict) -> tuple:
    """Held estimates first (highest level first), then insufficient-evidence
    ones by number of claims, then technologies with no evidenced level."""
    if t["held"]:
        return (0, -t["point"], t["name"])
    if t["low"] is not None:
        return (1, -t["n_claims"], t["name"])
    return (2, 0, t["name"])


def build_context(period: str, claims_path: Path | None = None, as_of: dt.date | None = None) -> dict:
    claims_path = claims_path or TRL_DIR / f"claims-{period}.jsonl"
    # Estimates live beside the claims they came from, so a run on a fixture
    # never overwrites the real period's file.
    directory = claims_path.parent
    if not claims_path.exists():
        raise ClaimsMissing(f"no claims file at {claims_path}; extract it first with "
                            f"python -m observatory.claims.extract_trl --period {period}")
    claims = load_claims(claims_path)
    _, end = quarter.period_bounds(period)
    as_of = as_of or dt.date.fromisoformat(end)
    w = score.load_weights()
    watchlist = matcher.load_watchlist()
    previous = _previous(directory, period)
    techs, estimates = [], {}
    for tid in tracked.tracked_ids():
        mine = [c for c in claims if c["tech_id"] == tid]
        e = score.estimate(mine, as_of, w)
        estimates[tid] = {"point": e.point, "low": e.low, "high": e.high, "held": e.held}
        # A move is only a move between two held levels; "insufficient evidence"
        # in either period has no level to move from or to.
        prev = previous.get(tid, {})
        before = prev.get("point") if prev.get("held") else None
        moved = None if before is None or not e.held else e.point - before
        t = watchlist.by_id(tid)
        techs.append({"id": tid, "name": t.name, "family": t.family, "point": e.point, "low": e.low,
                      "high": e.high, "held": e.held, "n_claims": e.n_claims,
                      "n_verified": e.n_verified, "top": e.top, "contrary": e.contrary,
                      "moved": moved})
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"estimates-{period}.json").write_text(json.dumps(
        {"as_of": as_of.isoformat(), "weights_version": w.version, "estimates": estimates}, indent=2))
    movers = {"up": [t for t in techs if (t["moved"] or 0) > 0],
              "retreated": [t for t in techs if (t["moved"] or 0) < 0],
              "contrary": [t for t in techs if t["contrary"]],
              "insufficient": [t for t in techs if not t["held"] and t["low"] is not None],
              "unestimated": [t for t in techs if t["low"] is None]}
    return {"period": period, "period_display": quarter.period_display(period), "as_of": as_of.isoformat(),
            "weights_version": w.version, "prompt_versions": sorted({c["prompt_version"] for c in claims}),
            "technologies": sorted(techs, key=_order),
            "movers": movers, "brand_logo": quarter.brand_logo(), "notes": list(NOTES)}


def render(period: str, claims_path: Path | None = None) -> Path:
    html = weekly_render._environment().get_template("trl.html.j2").render(
        **build_context(period, claims_path))
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = config.OUTPUT_DIR / f"trl-{period}.html"
    out.write_text(html, encoding="utf8")
    return out
