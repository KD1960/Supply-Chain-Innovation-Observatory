# Pre-practice technology tracker: design (DRAFT for owner review)

Date: 2026-09-23, revised 2026-09-24 from Kevin Dooley's spec comments.
Author: assistant, from his eight-point direction. **Status: draft pending
Kevin's final approval.**
It supersedes the Disclosed Adoption Index spec of 2026-09-04 as the project's
direction; that spec and the `phase0` branch are parked, not deleted (§9).

## 1. Decision recorded

Stakeholders want supply chain **technology tracking**, not company disclosure
ranking. The project returns to technologies as the unit of analysis, but with
three changes to the 2026-08-16 design that the 2026-09-04 assessment showed
were necessary:

1. Stage is **inferred**, not read off the source type (§4).
2. Only **pre-practice** technologies are tracked here (§3). In-practice
   technologies, if tracked at all, get a separate dashboard with a
   third-party evidence base (§8).
3. The estimand is a **Technology Readiness Level (TRL)**, as a point or range
   estimate with evidence behind it, not a count of documents (§5).

Kevin confirmed on 2026-09-24 that "TLR" in the direction means TRL.

## 2. Design constraints

- **C1. No dependence on ASU Library downloads.** No collector, export, or
  reported number may require a manual export from a library-licensed database
  (Scopus, ProQuest, Lens via library, ABI/INFORM). Existing library-derived
  observations are excluded from anything published until replaced by a
  source that permits mining (§6). The `sources.yaml` entries marked
  `format: ris` from library databases are frozen, not run.
- **C2. Paid content is allowed**, within the licence's mining terms. This
  reverses the 2026-08 "free sources only" rule. **Phase 1 runs on free
  sources only**; funds are planned but not yet allocated, and paid sources
  are added when they arrive, opportunistically. The raw-before-parse rule
  makes that safe: a new source is added and history is rebuilt, never
  rescored by hand. Each paid source must have a
  written licence note in `sources.yaml` stating what the terms permit
  (mining, internal analysis, quoting, redistribution) and the report may use
  only what they permit. Links to paid content are not required in the report;
  a citation (title, date, source) is.
- **C3. Source and stage are decoupled** (§4).
- **C4. Every published estimate is traceable** to the claims that produced it,
  each with a quote or extract and a source citation.
- **C5. No LLM in the weekly collection run.** The offline, quarterly,
  pinned-model claim extraction is the sanctioned exception, as in the DAI
  spec. Standing rules 1, 3, 4 and 5 from STATUS §8 stay in force.
- **C6. Membership is the owner's ruling.** A technology is tracked only
  because Kevin ruled it pre-practice on the sort sheet
  (`docs/audit/tech-practice-sort-2026-09-23.xlsx`, all 51 rows ruled
  2026-09-24). There is no numeric adoption screen; the sheet is the rule.

## 3. Pre-practice versus in-practice

**Pre-practice:** a technology Kevin judges not yet in routine commercial
operation across the population it applies to. The working sign is a
best-evidenced TRL of 8 or below, but the ruling is his, made on the sort
sheet, and no adoption percentage is computed or required.

**In-practice:** proven in routine, widespread commercial operation (TRL 9)
by his judgment. Not tracked here.

**Graduation:** when the tracker's estimate reaches TRL 9 and holds for two
quarters, the technology is flagged for Kevin's ruling; he decides whether
it leaves the tracker and, if the in-practice dashboard exists, enters it.
Graduation is itself a reported event. **Stall and retreat** are
also events: a technology can move down a level (Nikola, Takeoff, TradeLens).

**Sort of the current 51 lexicon entries:** Kevin confirmed every assistant
call on 2026-09-24, with the two "redefine or split" rows ruled plain retires.
Tracked list: the 24 rows marked pre-practice or pre-practice (borderline),
plus the pre-practice half of `tms_ai`, plus any additions from §7.

## 4. Theory: decoupling source from stage

The 2026-08 design mapped each source to a stage (arXiv = idea, patents =
experiment, filings = investment, trade press = diffusion) and averaged
z-scores. That is why ERP read as "research" and blockchain as "experiment":
a mature technology still generates papers, and the stage was the source's,
not the technology's.

The replacement: **an observation is evidence about maturity only through what
it says, who says it, and when.** Source type is one feature among several,
never the label.

Each claim extracted from a document carries:

| Feature | Values | Bearing on TRL |
|---|---|---|
| `claim_type` | proposes, simulates, prototypes, pilots, demonstrates-in-operation, sells, buys, operates-at-scale, abandons | strongest: each maps to a TRL band |
| `actor_type` | university, startup, incumbent vendor, user firm, government, analyst | user firm operating > vendor selling > startup announcing > university proposing |
| `setting` | lab, test site, one site, multiple sites, network-wide | scale of proof |
| `quantities` | units, sites, revenue, customers, if stated | direct adoption evidence |
| `source_type` | paper, patent, filing, press release, trade article, job posting, analyst note, funding record | reliability and self-interest prior |
| `date` | document date | recency weighting |
| `quote` | verbatim span | traceability (C4) |

**TRL bands for supply chain technology** (adapted from the NASA/DoD scale):

| TRL | Meaning here | Typical claim evidence |
|---|---|---|
| 1–3 | concept, analysis, lab proof | papers, patents, simulations |
| 4–6 | prototype validated, then piloted in a relevant environment | pilot announcements, startup funding, test-site reports |
| 7–8 | demonstrated in an operational environment; system complete and qualified | first commercial sites, user-firm case studies, regulatory approvals |
| 9 | proven in routine commercial operation | multi-site operation, purchase disclosures, installed-base figures |

**Inference.** For each technology and quarter, the estimate is a distribution
over TRL 1–9 formed from the claims in a trailing window (default 8 quarters,
recency-weighted). The first version is deliberately simple and deterministic:
each claim votes for its TRL band with a weight from `actor_type` ×
`source_type` × recency; the point estimate is the highest level with
sufficient weighted support (a "best-evidenced TRL" rule, since maturity is a
ceiling reached, not an average); the range is the interval that holds most of
the weight. Weights are a published table Kevin owns, like the lexicon.
Averaging across sources, the flaw named in the assessment, is gone: a hundred
papers cannot raise a TRL above 3 and one verified multi-site operation can
set it to 8 or 9.

**Why this is "more sophisticated" without a black box:** the model reads
(offline, quarterly, pinned) and the scoring is a lookup. The report shows the
top-weighted claims behind each estimate. A reader can disagree with the
weights table and see what changes.

## 5. What the dashboard shows

Per tracked technology: TRL point and range now, the trajectory over the last
eight quarters, the three claims that most support the current level, the
strongest contrary claim, and the date of the last level change. Across
technologies: which moved up, which stalled, which retreated, which graduated.
The narrative section that the assessment said the deterministic version could
not produce is written by the model offline from the claim ledger, once a
quarter, with every sentence citing a claim id (same sanction as extraction).

## 6. Sources: what changes

Keep running, as claim inputs rather than stage labels: arXiv, OpenAlex,
GitHub, EDGAR full-text, Federal Register, NSF, USAspending, HN.
Freeze (C1): Scopus, ProQuest trade, Lens-via-library exports.

**Top five paid additions, ranked for this tracker** (prices are the
assistant's rough recollection and need quotes; all five sell licences that
permit internal analysis and mining, which the ASU library licences do not):

1. **A text-and-data-mining licence for news and trade press: LexisNexis
   Nexis Data Lab or Dow Jones Factiva Analytics.** Replaces ProQuest trade
   press, the frozen "diffusion" source, with the same content under terms
   that allow mining. Nexis Data Lab has an academic offering. This is the one
   purchase that removes the library dependency outright. Order of $10–25k/yr.
2. **Crunchbase (data licence or API) or PitchBook.** Funding rounds by
   startup and category give the TRL 4–6 band its evidence: who is funded to
   pilot what. Crunchbase academic access is cheap ($1–5k/yr); PitchBook is
   the deeper, costlier option ($20k+).
3. **Interact Analysis, with LogisticsIQ as a second opinion.** Installed
   base and shipment figures for warehouse automation, AMRs, mobile robots,
   electrification. These are the hard numbers behind the TRL 9 test and
   the graduation flag. Bought per report ($5–15k each) or as a subscription.
4. **Gartner for Supply Chain Leaders (Hype Cycle and Magic Quadrant
   reports).** Not for mining; for calibration. Gartner's "years to
   mainstream" and hype-cycle position are an independent expert estimate to
   compare the tracker against, and the comparison itself is a finding.
   Licence permits internal use and limited quotation with attribution.
   Expensive ($30k+/yr); a single-report purchase or ASU's existing Gartner
   seat, if any, may suffice.
5. **Dimensions (Digital Science) API, or a direct Elsevier Scopus API
   agreement.** Publications, grants, patents, clinical and policy documents
   under a research-use API licence, with abstracts, replacing the library
   Scopus exports. Dimensions has free search and a paid API for mining
   ($10–20k/yr academic). This restores the TRL 1–3 band's coverage.

Near misses: PatSnap or Derwent (patents; Lens's own institutional plan is
cheaper), Statista (secondary, weak provenance), IDC or ARC Advisory (like
Gartner, narrower).

Vendors are named as options, not endorsed. Kevin's order (2026-09-24):
Crunchbase first, because it is cheap and can be bought soon; the news
mining licence next. Note on item 1: trade press is not mainly in-practice
evidence. Pilots, first customer sites and product launches are reported
there and almost nowhere else, so it is the main source for the TRL 5–8
band. Its in-practice reporting is simply not used here.

**Rough costs of the in-practice candidates in §8**, all needing quotes:
Enlyft $5–15k/yr; Lightcast academic $10–30k/yr; HG Insights $25–50k+/yr;
6sense and Revelio Labs $50k+/yr.

## 7. Candidates to add (Kevin decides)

From the 2026 landscape in Kevin's own assessment: multi-agent systems for
planning and execution, physical AI or polyfunctional robots (as distinct from
AMRs, which are in-practice), intelligent simulation (the successor framing of
digital twins), AI-native transportation management (the pre-practice half of
the `tms_ai` split), and autonomous rail vehicles (the concrete item under the
vague `rail_intermodal_tech`).

**Measurability gate (Kevin, 2026-09-24):** a candidate is added only after a
one-quarter probe on the current sources shows it produces claims reliably,
with a floor Kevin sets once the first probe reports (the assistant's opening
proposal is ten distinct claims per quarter from at least two source types).
A candidate that fails the probe is logged with the count, not added.

## 8. The in-practice dashboard (separate, conditional)

Only if a reliable, easy, third-party source of in-practice evidence exists.
Candidates: technographic install-base data (HG Insights, Enlyft, 6sense: which
WMS or ERP each company runs, inferred from job postings and web traces), job
posting data (Lightcast or Revelio Labs, skills demanded as an adoption proxy),
and the market-analyst installed-base figures in §6 item 3. Self-disclosure
(the DAI's 10-K evidence) is not the base; it may be a cross-check. Scope it
only after this tracker has produced one quarter.

## 9. What happens to the existing work

Status 2026-09-24: Phase 1 built on branch `trl`; see STATUS.md.

- The count-based Observatory keeps collecting weekly from `main`; its
  reports stop being the deliverable. Its collectors and raw store are the
  input layer for §4.
- The DAI `phase0` branch is parked: the claim extractor, quote verifier and
  windowing are reusable for §4 (they already extract role and stance from
  text with verified quotes). Kevin's pending hand-coding of
  `phase0-verdicts.csv` is **no longer required**. Do not merge or delete the
  branch until Kevin decides.
- `metrics.py` stage mapping (`SIGNALS_BY_STAGE`) is retired from the
  deliverable, not from the code, until the new scoring exists.

## 10. Assistant's suggestions on the plan

1. **TRL is a maturity scale, not an adoption scale.** With no adoption
   screen, the tracker says how proven a technology is, not how widely it is
   used. Say so plainly in the report so readers do not confuse the two.
2. **The value case, per Kevin:** not everyone can spend $25k on Gartner, and
   a tracker run for a while may catch Gartner's blind spots. Report the
   Gartner comparison when a Gartner source is available; do not wait for it.
3. **Measure first, again.** Before any code: hand-place ten technologies on
   the TRL scale from 20 claims each, using the parked extractor, and see if
   two readers agree within one level. If they cannot, no weights table will.
4. **Start on free sources now; add paid later** (Kevin, 2026-09-24; see C2).
5. **The list is cut.** Done on the sort sheet.
6. **Keep stall and retreat as first-class outcomes.** The surprise readers
   want is as often "this went backwards" as "this arrived".
7. **Before the next push, decide what becomes public.** The repository is
   public and `main` has not been pushed since 2026-09-04. The unpushed
   commits include the DAI brainstorm and spec, this spec and the sort sheet,
   all of which quote or summarize Kevin's 09-04 assessment. A push publishes
   them. Options: push as is, or move the assessment quotations and the
   parked DAI documents to `correspondence/` (gitignored) first.

## 11. Decisions taken 2026-09-24

- Budget: planned, not allocated; proceed on free sources, add paid
  opportunistically.
- Borderline rows: ruled on the sheet.
- Quarterly offline model narrative (§5): **approved** under rule 1.
- Publication: Kevin ruled on 2026-09-24 that everything may be pushed; main was pushed the same day.
