# observatory/trl/placement.py
"""The sheet a reader places technologies from, the CSV they hand back, and
the agreement measure. Same shape as docs/audit/sample-*.md."""

from __future__ import annotations

import csv
import io
import re

from .score import TRLEstimate

VERDICT_COLUMNS = ("tech_id", "reader_trl", "reader_note")


def _fence(*texts: str) -> str:
    longest = max((len(r) for t in texts for r in re.findall(r"`+", t or "")), default=0)
    return "`" * max(3, longest + 1)


def sheet(claims_by_tech: dict[str, list[dict]]) -> str:
    lines = ["# TRL placement sheet", "",
             "For each technology read its claims (at most twenty, heaviest first) and write ONE",
             "number, 1-9, in trl-placement-verdicts.csv: the highest level the evidence holds.",
             "Bands: 1-3 research; 4-6 prototype and pilot; 7-8 in real operation; 9 routine at scale.",
             "Do not look at the tracker's estimate first.", ""]
    for tech, claims in claims_by_tech.items():
        lines += [f"## {tech}", ""]
        for n, c in enumerate(claims[:20], start=1):
            f = _fence(c["quote"])
            lines += [f"{n}. `{c['claim_id']}` {c['claim_type']} | {c['actor_type']}: {c['actor']} | {c['setting']} | "
                      f"{c['source']} {c['doc_date'] or ''} | quote_verified: {'yes' if c.get('quote_verified') else 'no'}",
                      f"   {c.get('url') or ''}", f, c["quote"], f, ""]
    return "\n".join(lines)


def verdict_template(tech_ids) -> str:
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(VERDICT_COLUMNS))
    w.writeheader()
    for t in tech_ids:
        w.writerow({"tech_id": t, "reader_trl": "", "reader_note": ""})
    return out.getvalue()


def agreement(verdicts: list[dict], estimates: dict[str, TRLEstimate]) -> dict:
    diffs = []
    for v in verdicts:
        e = estimates.get(v["tech_id"])
        if e is None or e.point is None or not str(v.get("reader_trl", "")).strip():
            continue
        diffs.append(abs(int(v["reader_trl"]) - e.point))
    n = len(diffs)
    return {"n": n, "within_one": sum(d <= 1 for d in diffs), "exact": sum(d == 0 for d in diffs),
            "mean_abs_diff": (sum(diffs) / n) if n else None}
