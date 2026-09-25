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
    "Estimates marked 'floor' are the lowest band any claim evidences, not a level the evidence "
    "holds; the placement check of 2026-09-24 found this true for most technologies under weights v1.",
)


def load_claims(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf8").splitlines():
        if line.strip():
            r = json.loads(line)
            if "claim_id" in r:
                rows.append(r)
    return rows


def _previous(directory: Path, period: str) -> dict:
    p = directory / f"estimates-{quarter.previous_period(period)}.json"
    if not p.exists():
        return {}
    data = json.loads(p.read_text())
    return data.get("estimates", data)


def build_context(period: str, claims_path: Path | None = None, as_of: dt.date | None = None) -> dict:
    claims_path = claims_path or TRL_DIR / f"claims-{period}.jsonl"
    # Estimates live beside the claims they came from, so a run on a fixture
    # never overwrites the real period's file.
    directory = claims_path.parent
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
        before = previous.get(tid, {}).get("point")
        moved = None if before is None or e.point is None else e.point - before
        t = watchlist.by_id(tid)
        techs.append({"id": tid, "name": t.name, "family": t.family, "point": e.point, "low": e.low,
                      "high": e.high, "held": e.held, "n_claims": e.n_claims,
                      "n_verified": e.n_verified, "top": e.top, "contrary": e.contrary,
                      "moved": moved})
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"estimates-{period}.json").write_text(json.dumps(
        {"as_of": as_of.isoformat(), "weights_version": w.version, "estimates": estimates}, indent=2))
    movers = {"up": [t for t in techs if (t["moved"] or 0) > 0],
              "retreated": [t for t in techs if (t["moved"] or 0) < 0 or t["contrary"]],
              "unestimated": [t for t in techs if t["point"] is None]}
    return {"period": period, "period_display": quarter.period_display(period), "as_of": as_of.isoformat(),
            "weights_version": w.version, "prompt_versions": sorted({c["prompt_version"] for c in claims}),
            "technologies": sorted(techs, key=lambda t: (-(t["point"] or 0), t["name"])),
            "movers": movers, "brand_logo": quarter.brand_logo(), "notes": list(NOTES)}


def render(period: str, claims_path: Path | None = None) -> Path:
    html = weekly_render._environment().get_template("trl.html.j2").render(
        **build_context(period, claims_path))
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = config.OUTPUT_DIR / f"trl-{period}.html"
    out.write_text(html, encoding="utf8")
    return out
