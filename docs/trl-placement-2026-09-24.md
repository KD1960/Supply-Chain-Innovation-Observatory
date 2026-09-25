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

## Owner's reading, 2026-09-25, and the verdict

Kevin filled `docs/audit/trl-placement-verdicts.csv` on 2026-09-25, reading
`docs/audit/trl-placement-sheet.md` without looking at the tracker's estimate first. No
model call was made for this section; the computation is
`docs/experiments/trl/placement_final.py`, run against the same three files as before
(`docs/audit/trl-placement-verdicts.csv`, `docs/audit/trl-placement-model.csv`,
`data/trl/estimates-2026-Q3.json`).

| Technology | Owner | Owner's note | Model | Tracker point | Span | Held |
|---|---|---|---|---|---|---|
| supply_chain_digital_twin | 3 | "3 based on evidence but we're missing sources that would suggest 4-6" | 4 | insufficient | 1–5 | no |
| agentic_procurement | 3 | "3 based on evidence but we're missing sources that would suggest 4-6" | 4 | insufficient | 1–5 | no |
| delivery_drones | 3 | "3 based on evidence but we're missing sources that would suggest 4-9" | 3 | 2 | 1–3 | yes |
| cv_inspection | 3 | "3 based on evidence but we're missing sources that would suggest 4-6" | 5 | insufficient | 1–5 | no |
| supply_chain_llm | 2 | (blank) | 7 | insufficient | 7–8 | no |
| autonomous_trucking | 3 | "3 based on evidence but we're missing sources that would suggest 4-6" | 6 | insufficient | 2–5 | no |
| sidewalk_delivery_robots | 3 | "3 based on evidence but we're missing sources that would suggest 4-6" | 2 | insufficient | 1–2 | no |
| additive_spares | 3 | (blank) | 3 | insufficient | 1–3 | no |
| electric_trucks | 3 | "3 based on evidence but we're missing sources that would suggest 4-7" | 3 | insufficient | 1–3 | no |
| humanoid_logistics | 2–3 | "2-3 based on evidence but we're missing sources that would suggest 4-6" | 4 | insufficient | 1–5 | no |

For arithmetic, "2–3" (humanoid_logistics) is treated as 2.5.

### The three comparisons

`python3 docs/experiments/trl/placement_final.py`:

1. **Owner vs model, all 10.** n=10, within one 6/10, exact 3, mean abs diff 1.45. Misses (diff
   > 1): cv_inspection (owner 3, model 5, diff 2), supply_chain_llm (owner 2, model 7, diff 5),
   autonomous_trucking (owner 3, model 6, diff 3), humanoid_logistics (owner 2.5, model 4, diff
   1.5).
2. **Owner vs tracker point, held only.** n=1 (delivery_drones is the only held point). Within
   one 1/1, exact 0, mean abs diff 1.0 (owner 3, tracker point 2).
3. **Owner vs tracker span ± 1, all 10 — an added measure, not the plan's gate.** n=10, within
   9/10, mean abs diff 0.4. The one miss is supply_chain_llm: owner 2, span 7–8, outside the
   [low−1, high+1] window by 4 levels.

These match the controller's quick numbers (owner~model within one 6/10; owner~tracker point
within one 1/1; owner within span±1 9/10, supply_chain_llm the miss). One correction to the
task brief: the owner's note is not identical across nine rows — it appears on eight rows
(all except `supply_chain_llm` and `additive_spares`, which he left blank), each a
near-verbatim variant of "N based on evidence but we're missing sources that would suggest
4-6" (with 4-9 for delivery_drones and 4-7 for electric_trucks).

### The verdict, against the plan's gate

**On the plan's rule (STATUS §7 item 1, Task 6 Step 5), the check FAILS.** The gate is: pass
only if owner~tracker within one on ≥7 of 10 **and** owner~model within one on ≥7 of 10.
Owner~model is 6/10, short of 7. Owner~tracker point is not measurable at 7/10 at all: after
the scoring fix, only one technology (delivery_drones) has a held point, so n=1, and the gate
as written cannot be satisfied by a single comparison. Both halves of the conjunction fail (or
are unmeasurable), so the check fails on the letter of the plan.

**The reading.** The owner placed every one of the ten technologies at 2–3, and on eight of
them wrote essentially the same note: he is reading the evidence as it stands (research-band,
consistent with the claims), while flagging explicitly that the pool is missing the pilot- and
operation-band sources (4–6, and up to 4-9 for delivery_drones) that would let him place higher
if they existed. That is a *calibrated* low placement, not a shrug: he is telling the tracker
its ceiling, not guessing.

The owner and the tracker's spans agree on 9 of 10 — his number falls inside the tracker's
evidenced range (widened by one level either way) for every technology except one. The
disagreements with the model reader are all in one direction: the model reads the same claims
one or more levels *up* from where the owner does — supply_chain_llm 7 vs 2, autonomous_trucking
6 vs 3, cv_inspection 5 vs 3 — the model treats a single strong claim (or a small handful) as
sufficient to place at the top of what any one claim could support, where the owner is more
conservative given how thin the pool is.

The one span miss, supply_chain_llm, is not a new problem: it is the actor-unclear arXiv
"production-deployed" claim already flagged in STATUS §7 item 4. The tracker's span (7–8) comes
entirely from that single claim's own claim_type (`demonstrates_in_operation`) reading itself at
face value; the owner, seeing the same one claim with an unclear actor, placed it at research
band (2) instead. This is the item 4 question made concrete: should an actor-unclear
operation-band claim be allowed to set a span at all.

**What this means.** The instrument (extraction, claim typing, sheet) is consistent with a
careful human reading research-stage evidence: owner and tracker-span agree 9 of 10, and the
owner's notes show he is reading conservatively *because* the sources stop short of pilot and
operation evidence, not because the scoring or the claim extraction misled him. The gap that
fails the gate is a **source-coverage gap** (no free source reaches the pilot band — the same
finding as the probe, `docs/trl-probe-2026-09-24.md`), not a scoring problem. The probe already
found and named this; the placement check confirms it from the human side.

**Do not revise the weights.** The plan's "revise the weights table once, then recompute and
compare once more" step (Task 6 Step 5, STATUS §7 item 1) exists to correct a *scoring*
disagreement — the instrument reading claims wrong. This is a *source-coverage* disagreement:
the instrument and the owner agree on what the evidence in hand supports (9/10 span agreement);
there is no pilot- or operation-band evidence in the pool to score. Revising weights v1 would not
close the owner~model gap (the model's disagreement is about how much weight to give a single
claim, not about the weights table) and would not manufacture evidence the sources don't have.
The owner may overrule this reading and order a weights revision anyway; that is his call to
make, not this report's.

**Next steps.**

- The news mining licence (spec §6 item 1) is the probe's own reversal condition
  (`docs/trl-probe-2026-09-24.md`) and the most direct way to close the source-coverage gap
  that this check confirms.
- The owner's remaining rulings from STATUS §7: item 1 itself (accept the source-coverage
  reading above and keep weights v1, or order a revision anyway), item 2 (the
  threshold/insufficient-evidence rule), item 3 (Lens), and item 4 (whether the
  actor-unclear `supply_chain_llm` claim should be allowed to set a span, given the miss
  above).
