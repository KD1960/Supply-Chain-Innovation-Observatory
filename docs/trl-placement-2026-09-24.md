# TRL placement check, 2026-09-24 (PRELIMINARY)

Task 6 of the TRL tracker phase 1 plan (spec §10 item 3). The question: do two readers,
given the same claims, place a technology within one TRL level of each other and of the
tracker? If not, the weights table is decorating noise.

**Status: preliminary. No pass or fail verdict is given here.** Reader 1 (Kevin) has not
yet filled `docs/audit/trl-placement-verdicts.csv`. See "Waiting on the owner" below.

## What was run

- Extraction: `python -m observatory.claims.extract_trl --period 2026-Q3 --tech <id> --limit 20 --max-dollars 15`,
  once per technology, model `claude-sonnet-5`, prompt `trl-1`. 71 documents read, 43 claims,
  0 errors, 0 refusals, 43 of 43 quotes verified.
- Sheet: `docs/experiments/trl/placement_sheet.py` wrote `docs/audit/trl-placement-sheet.md`
  (claims per technology, heaviest first by `score.claim_weight`) and the blank
  `docs/audit/trl-placement-verdicts.csv`. Tracker estimates: `score.estimate`,
  `as_of = 2026-09-30`, weights version 1, saved to `data/trl/estimates-2026-Q3.json` (not in the repo).
- Reader 2: `docs/experiments/trl/placement_model.py`, `claude-opus-5-5`, effort `medium`, one
  call per technology, fixed system prompt, the technology's sheet section as the user message,
  JSON `{"trl": n}` by structured output. 10 of 10 returned `end_turn`, no refusals. Result:
  `docs/audit/trl-placement-model.csv`.

## Cost

| Step | Tokens (in / out / cache read / cache write) | Dollars |
|---|---|---|
| Extraction, `claude-sonnet-5` (71 requests; `data/trl/usage-2026-Q3-claude-sonnet-5.json`) | 40,437 / 8,642 / 94,359 / 15,466 | $0.22 |
| Model reader, `claude-opus-5-5` (10 calls + 1 smoke call) | 10,576 + 1,690 / 740 + 109 / 0 / 0 | $0.07 |
| **Total** | | **$0.29** |

Dollars are computed at list price ($2 / $10 per MTok for Sonnet 5, $4 / $20 for Opus 5.5;
cache read 0.1x, cache write 1.25x of input). The pre-run estimates printed by the command
summed to $0.33 for extraction and $0.82 for the reader (both deliberately high).

## The table

| Technology | Kevin | Model | Tracker point | Tracker range | Claims | Verified |
|---|---|---|---|---|---|---|
| supply_chain_digital_twin | | 4 | 2 | 1-5 | 9 | 9 |
| agentic_procurement | | 4 | 1 | 1-5 | 8 | 8 |
| delivery_drones | | 3 | 2 | 1-3 | 7 | 7 |
| cv_inspection | | 5 | 1 | 1-5 | 3 | 3 |
| supply_chain_llm | | 7 | 7 | 7-8 | 1 | 1 |
| autonomous_trucking | | 6 | 2 | 2-5 | 2 | 2 |
| sidewalk_delivery_robots | | 2 | 1 | 1-2 | 2 | 2 |
| additive_spares | | 3 | 1 | 1-3 | 3 | 3 |
| electric_trucks | | 3 | 1 | 1-3 | 4 | 4 |
| humanoid_logistics | | 4 | 1 | 1-5 | 4 | 4 |

## Agreement

| Pair | n | within one | exact | mean abs diff |
|---|---|---|---|---|
| Model vs tracker | 10 | 3 | 1 | 2.2 |
| Kevin vs tracker | pending | | | |
| Kevin vs model | pending | | | |

Model vs tracker is 3 of 10 within one level. That is not the gate (the gate is about Kevin),
but it is below the 7-of-10 bar the gate uses.

Why they differ, as observed: the model places each technology at about the top of the
tracker's own evidenced range (|model - range high| is 0 or 1 for all ten), while the tracker's
point sits at the bottom. The support threshold is 0.5; after the source, actor, setting and
recency multipliers, every claim here weighs between 0.015 and 0.186, so only three technologies reach 0.5 at
any level (supply_chain_digital_twin and delivery_drones held at 2, agentic_procurement held
at 1). The other seven get the fallback point, the lowest band floor among their claims. So the
tracker is reporting "no level is held" as a low number, and a reader reading the same claims
reports the highest level any claim reaches. supply_chain_llm agrees at 7 only because it has
one claim; its weight is 0.077, far below the threshold.

## Claims per technology

| Technology | Documents read | Claims | By claim type | By source type |
|---|---|---|---|---|
| supply_chain_digital_twin | 20 | 9 | proposes 7, simulates 1, prototypes 1 | code_repository 4, paper 3, government_record 2 |
| agentic_procurement | 11 | 8 | proposes 3, simulates 1, prototypes 4 | code_repository 5, paper 3 |
| delivery_drones | 6 | 7 | proposes 6, simulates 1 | government_record 5, paper 2 |
| cv_inspection | 5 | 3 | proposes 1, prototypes 2 | code_repository 2, government_record 1 |
| supply_chain_llm | 3 | 1 | demonstrates_in_operation 1 | paper 1 |
| autonomous_trucking | 7 | 2 | simulates 1, prototypes 1 | paper 2 |
| sidewalk_delivery_robots | 3 | 2 | proposes 2 | government_record 2 |
| additive_spares | 7 | 3 | proposes 2, simulates 1 | government_record 2, paper 1 |
| electric_trucks | 3 | 4 | proposes 2, simulates 2 | paper 4 |
| humanoid_logistics | 6 | 4 | proposes 2, simulates 1, prototypes 1 | government_record 2, code_repository 1, paper 1 |

**The claims are thin.** 43 claims across ten technologies; five technologies have three or
fewer. The "at most twenty" in the plan was never reached: the most any technology had was
nine. 33 of 43 are `proposes` or `simulates` (bands 1-3); 9 are `prototypes`; none are
`pilots`, `sells`, `buys` or `operates_at_scale`; the single operation-band claim is an arXiv
paper describing its own system. Every claim comes from a paper, an NSF award or a GitHub
repository; no press release, trade article or filing produced a claim (the five EDGAR
documents for autonomous_trucking yielded none). Actors: university 26, unclear 9, startup 7,
analyst 1. Settings: lab 30, unclear 10, test_site 2, multiple_sites 1. This is consistent with
`docs/trl-probe-2026-09-24.md` (no probed free news source cleared the pilot-band bar, so
Task 5 ran on the existing collectors): the sources in the database reach the research band and
little else, so any placement from this pass is mostly a placement of academic activity.

## Waiting on the owner

The verdict cannot be given until Kevin fills `reader_trl` in
`docs/audit/trl-placement-verdicts.csv`, reading `docs/audit/trl-placement-sheet.md` without
looking at the tracker's estimate first.

The pass line, from the plan: **Pass** if Kevin and the tracker are within one level on at
least 7 of 10, **and** Kevin and the model are within one level on at least 7 of 10. **Fail**
on anything less; then the weights table is revised once with the reasons written into the
yaml comments, the estimates recomputed (no new extraction), and the comparison re-run once.
A second fail stops the plan at this task.

To finish: fill the CSV, then run `placement.agreement()` on it against
`data/trl/estimates-2026-Q3.json` and against `docs/audit/trl-placement-model.csv` (read as
estimates with `point = reader_trl`), and replace the two "pending" rows above.

## Revision after the scoring fix (2026-09-24)

Everything above is the original record and is left as it was. The final branch review found
that the scorer counted a claim once **per level of its band** when adding up cumulative
support, so a `proposes` claim (band 1-2) was counted twice at level 1 and every two-level
claim type (`proposes`, `simulates`, `prototypes`, `pilots`, `sells`, `buys`,
`demonstrates_in_operation`) was favoured over `operates_at_scale` (band 9 only). Cumulative
support at level L is now the sum of the weights of the claims whose band reaches L or higher,
each claim counted once. At the same time the fallback changed: when no level reaches the
threshold there is **no point**; the page says "insufficient evidence (claims span L-H)"
instead of printing the lowest band as "TRL n (floor)". This is the new default and the owner
may reverse it (STATUS §7 item 2).

No new extraction: the same 43 claims (`data/trl/claims-2026-Q3.jsonl`, committed as
`docs/audit/trl-claims-2026-Q3.jsonl`), weights version 1, `as_of = 2026-09-30`, re-scored by
`python -m observatory.run --trl-report 2026-Q3`, which rewrote
`data/trl/estimates-2026-Q3.json`. "Max support" is the cumulative support at the lowest
evidenced level, i.e. the sum of the weights of all the technology's claims, against the
threshold of 0.5.

| Technology | Model | Tracker point | Tracker range | Held | Max support | Before the fix |
|---|---|---|---|---|---|---|
| supply_chain_digital_twin | 4 | insufficient | 1-5 | no | 0.466 | 2, held |
| agentic_procurement | 4 | insufficient | 1-5 | no | 0.270 | 1, held |
| delivery_drones | 3 | 2 | 1-3 | yes | 0.513 | 2, held |
| cv_inspection | 5 | insufficient | 1-5 | no | 0.233 | 1 (floor) |
| supply_chain_llm | 7 | insufficient | 7-8 | no | 0.077 | 7 (floor) |
| autonomous_trucking | 6 | insufficient | 2-5 | no | 0.093 | 2 (floor) |
| sidewalk_delivery_robots | 2 | insufficient | 1-2 | no | 0.162 | 1 (floor) |
| additive_spares | 3 | insufficient | 1-3 | no | 0.199 | 1 (floor) |
| electric_trucks | 3 | insufficient | 1-3 | no | 0.154 | 1 (floor) |
| humanoid_logistics | 4 | insufficient | 1-5 | no | 0.218 | 1 (floor) |

**One of ten holds a level** (delivery_drones, TRL 2); nine are insufficient evidence; the other
14 tracked technologies have no claims and are not estimated. Two of the three levels held
before the fix (digital twin 2, agentic procurement 1) were held only because the double count
inflated them.

### Agreement, revised

`placement.agreement()` on `data/trl/placement-model.csv` (identical to
`docs/audit/trl-placement-model.csv`) against the new estimates. The measure skips a technology
with no tracker point, so the insufficient-evidence ones drop out:

| Pair | n | within one | exact | mean abs diff |
|---|---|---|---|---|
| Model vs tracker | 1 | 1 | 0 | 1.0 |
| Kevin vs tracker | pending | | | |
| Kevin vs model | pending | | | |

Model vs tracker is now 1 of 1 within one, which says nothing: with nine of ten technologies
reported as insufficient evidence there is almost nothing to compare. The model reader placed
all ten at a number; the tracker now declines to for nine of them. Whether "insufficient
evidence" against a reader's number counts as a disagreement for the gate (the plan's gate is
"within one level on at least 7 of 10") is the owner's ruling; counted as disagreements, model
vs tracker is 1 of 10 within one.
