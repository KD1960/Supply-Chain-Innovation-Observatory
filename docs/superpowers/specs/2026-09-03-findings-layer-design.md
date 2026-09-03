# Findings layer — design

2026-09-03. Owner: Kevin Dooley. Implements §4 of
`docs/marketing-plan-2026-09-03.md`, which calls the missing findings layer
"the single largest marketing gap and it is a development task, not a
communications one."

Target period for this build: **2026-Q2** — the most recent fully scored
quarter, and the stimulus the plan's think-aloud sessions use. 2026-Q3
withholds its scores and must keep rendering; it is not what this build is
demonstrated against.

## The problem

The report opens with tiles that describe the instrument -- documents matched,
technologies seen, technologies silent -- and an "In summary" that is mostly
method. Both are true and neither is a finding. A professional reads three
findings and one chart; the findings are present in the data and buried in the
document.

## What a finding is here

One plain sentence about the world, its sample size beside it, and a link to
the row it came from. Not a statement about the instrument.

## Structure

`observatory/findings.py`, pure functions over the rows `build_context`
already assembles. No new queries and no new database reads: a finding that
cannot be computed from what the report already shows is a finding the
evidence page cannot support.

Each rule is a function `(rows, context) -> Finding | None` carrying:

- `id` -- stable, so an override can name it
- `text` -- the drafted sentence, with its n inside the sentence
- `anchor` -- the technology row it points at, or none for a whole-quarter claim

`compose()` runs the rules in a fixed order, drops the ones that return None,
applies the override file, and returns at most five.

## The rules

**Count rules** run in every period, including one whose scores are withheld:

1. `stage_frontier` -- technologies whose evidence is led by filings, the
   diffusion end. Q2: autonomous trucking, 12 documents, 8 filings, 6 companies.
2. `federal_money` -- technologies drawing federal awards, with the share of
   their evidence that is money.
3. `patent_led` -- technologies whose largest family is patents.
4. `most_evidenced` -- the most-written-about technology, stated with its
   concentration so the sentence cannot read as importance.

**Score rules** are skipped when `sai`/`lfi`/`shift` are absent:

5. `crossing` -- lab-to-field index above zero.
6. `built_versus_said` -- the substance-against-attention leaders.
7. `movers` -- the largest share shifts against the previous period.

Order above is the ranking. Five ship.

## Two guards

**Minimum evidence.** A rule may not name a technology on fewer than three
documents. 2026-Q2 has cold chain IoT monitoring sitting at diffusion on a
single SEC filing; without this guard the plan's own example sentence --
"autonomous trucking is the only technology at the diffusion stage" -- is
false. Technologies below the floor are counted in the sentence, never named.

**The finding must reach the page.** A test asserts against the rendered HTML,
not against the template context. A chart that was in the context and not on
the page shipped twice in this project; §10 of STATUS names it as the
recurring shape.

## Override

`findings/<period>.yaml`, optional. A mapping of rule id to either a
replacement `text` or `drop: true`; file order sets display order. Absent file
means the drafted sentences ship. An id in the file that no rule owns raises --
silence is what this project keeps being burned by, so an override that names
nothing is an error and not a no-op.

This is the split the marketing plan's §8 already assigns: the pipeline drafts,
Kevin has final text.

## Report changes

- New `<section id="findings">` above "In summary".
- The instrument tiles move into the "How to read this document" disclosure.
- Every technology row gains `id="tech-<id>"` so a post can link to one row
  rather than to a 14,000-pixel page.

## Out of scope

PNG post sizes, the two-page brief, and the tracked-technologies sheet. They
are the next pass and depend on this one's findings being settled.
