"""Final placement check, 2026-09-25: the owner's column is filled. Three
comparisons against docs/audit/trl-placement-verdicts.csv (no model calls):

1. Owner vs model reader (docs/audit/trl-placement-model.csv), all 10.
2. Owner vs tracker point (data/trl/estimates-2026-Q3.json), only the
   technologies with a held point (n will be 1).
3. Owner vs tracker span: owner's number within [low-1, high+1], all 10.
   This is an added measure, not the plan's gate.

"2-3" (humanoid_logistics) is treated as 2.5 for arithmetic.

Run: python3 docs/experiments/trl/placement_final.py
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _owner_value(raw: str) -> float:
    raw = raw.strip()
    m = re.match(r"^(\d+)\s*-\s*(\d+)$", raw)
    if m:
        return (int(m.group(1)) + int(m.group(2))) / 2
    return float(raw)


def load_owner() -> dict[str, dict]:
    out = {}
    with open(ROOT / "docs/audit/trl-placement-verdicts.csv") as f:
        for row in csv.DictReader(f):
            tech = row["tech_id"].strip()
            trl_raw = row["reader_trl"].strip()
            note = (row.get("reader_note") or "").strip()
            out[tech] = {
                "raw": trl_raw,
                "value": _owner_value(trl_raw) if trl_raw else None,
                "note": note,
            }
    return out


def load_model() -> dict[str, int]:
    out = {}
    with open(ROOT / "docs/audit/trl-placement-model.csv") as f:
        for row in csv.DictReader(f):
            out[row["tech_id"].strip()] = int(row["reader_trl"])
    return out


def load_tracker() -> dict[str, dict]:
    data = json.loads((ROOT / "data/trl/estimates-2026-Q3.json").read_text())
    return data["estimates"]


def summarize(diffs: list[float]) -> dict:
    n = len(diffs)
    return {
        "n": n,
        "within_one": sum(d <= 1 for d in diffs),
        "exact": sum(d == 0 for d in diffs),
        "mean_abs_diff": (sum(diffs) / n) if n else None,
    }


def owner_vs_model(owner: dict, model: dict) -> tuple[dict, list[str]]:
    diffs, misses = [], []
    for tech, o in owner.items():
        if o["value"] is None or tech not in model:
            continue
        d = abs(o["value"] - model[tech])
        diffs.append(d)
        if d > 1:
            misses.append(f"{tech}: owner {o['raw']} vs model {model[tech]} (diff {d:g})")
    return summarize(diffs), misses


def owner_vs_tracker_point(owner: dict, tracker: dict) -> tuple[dict, list[str]]:
    diffs, misses = [], []
    for tech, o in owner.items():
        e = tracker.get(tech)
        if o["value"] is None or e is None or e.get("point") is None:
            continue
        d = abs(o["value"] - e["point"])
        diffs.append(d)
        if d > 1:
            misses.append(f"{tech}: owner {o['raw']} vs tracker point {e['point']} (diff {d:g})")
    return summarize(diffs), misses


def owner_vs_tracker_span(owner: dict, tracker: dict) -> tuple[dict, list[str]]:
    diffs, misses = [], []
    for tech, o in owner.items():
        e = tracker.get(tech)
        if o["value"] is None or e is None or e.get("low") is None or e.get("high") is None:
            continue
        low, high, v = e["low"], e["high"], o["value"]
        if v < low - 1:
            d = (low - 1) - v
        elif v > high + 1:
            d = v - (high + 1)
        else:
            d = 0
        diffs.append(d)
        if d > 0:
            misses.append(f"{tech}: owner {o['raw']} vs span {low}-{high} (outside by {d:g})")
    return summarize(diffs), misses


def main() -> None:
    owner = load_owner()
    model = load_model()
    tracker = load_tracker()

    om, om_misses = owner_vs_model(owner, model)
    otp, otp_misses = owner_vs_tracker_point(owner, tracker)
    ots, ots_misses = owner_vs_tracker_span(owner, tracker)

    print("Owner vs model reader (n={n}): within_one={within_one}/{n}, exact={exact}, "
          "mean_abs_diff={mad}".format(n=om["n"], within_one=om["within_one"], exact=om["exact"],
                                        mad=round(om["mean_abs_diff"], 3) if om["mean_abs_diff"] is not None else None))
    for m in om_misses:
        print("  miss:", m)

    print("Owner vs tracker point (n={n}): within_one={within_one}/{n}, exact={exact}, "
          "mean_abs_diff={mad}".format(n=otp["n"], within_one=otp["within_one"], exact=otp["exact"],
                                        mad=round(otp["mean_abs_diff"], 3) if otp["mean_abs_diff"] is not None else None))
    for m in otp_misses:
        print("  miss:", m)

    print("Owner vs tracker span +-1 (n={n}): within={within_one}/{n}, exact={exact}, "
          "mean_abs_diff={mad}".format(n=ots["n"], within_one=ots["within_one"], exact=ots["exact"],
                                        mad=round(ots["mean_abs_diff"], 3) if ots["mean_abs_diff"] is not None else None))
    for m in ots_misses:
        print("  miss:", m)

    gate_om = om["within_one"] >= 7
    gate_otp = otp["n"] >= 7 and otp["within_one"] >= 7
    verdict = "PASS" if (gate_om and gate_otp) else "FAIL"
    print(f"\nPlan's gate: owner~model >=7/10 within one: {gate_om} "
          f"({om['within_one']}/10). owner~tracker point >=7/10 within one: {gate_otp} "
          f"(n={otp['n']}, within_one={otp['within_one']}). Verdict: {verdict}")


if __name__ == "__main__":
    main()
