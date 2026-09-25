"""Task 6 step 3: the placement sheet, the blank verdict CSV, and the tracker's
estimates (kept out of the reader's sight). Usage: placement_sheet.py"""

import dataclasses, datetime as dt, json, sys  # noqa: E401
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from observatory.trl import placement, score  # noqa: E402

TECHS = ("supply_chain_digital_twin agentic_procurement delivery_drones cv_inspection supply_chain_llm "
         "autonomous_trucking sidewalk_delivery_robots additive_spares electric_trucks humanoid_logistics").split()
AS_OF, W = dt.date(2026, 9, 30), score.load_weights()
rows = [json.loads(line) for line in open(ROOT / "data/trl/claims-2026-Q3.jsonl", encoding="utf8")]
by_tech = {t: sorted((r for r in rows if "claim_id" in r and r["tech_id"] == t),
                     key=lambda c: -score.claim_weight(c, AS_OF, W)) for t in TECHS}
(ROOT / "docs/audit/trl-placement-sheet.md").write_text(placement.sheet(by_tech))
(ROOT / "docs/audit/trl-placement-verdicts.csv").write_text(placement.verdict_template(TECHS))
est = {t: dataclasses.asdict(score.estimate(cs, AS_OF, W)) for t, cs in by_tech.items()}
for e in est.values():  # claim ids, not whole claims, in the saved estimate
    e["top"] = [c["claim_id"] for c in e["top"]]
    e["contrary"] = e["contrary"] and e["contrary"]["claim_id"]
(ROOT / "data/trl/estimates-2026-Q3.json").write_text(json.dumps({"as_of": str(AS_OF), "weights_version": W.version,
                                                                   "estimates": est}, indent=2))
