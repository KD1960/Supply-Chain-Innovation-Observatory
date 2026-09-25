# STATUS

Supply Chain Innovation Observatory — state of the project, written for someone
picking it up cold. Last updated 2026-09-25, on branch `pressroom`.

Owner: Kevin Dooley, ASU W. P. Carey.

**Read this, then `docs/trl-placement-2026-09-24.md`, then
`docs/process-review-2026-09-23.md`, then `docs/process-review-2026-08-31.md`.**
The placement report is the measurement that decides whether the new tracker's
scoring means anything, and it is waiting on the owner (§5, §7). The 09-23
review is an independent project-management audit of everything from 09-04 to
09-23, commissioned from a reviewer with no prior contact with the project. It
lives on branch `phase0` only, at that path, and arrives on `main` when that
branch is merged or the file is cherry-picked; read it there
(`git show phase0:docs/process-review-2026-09-23.md`). Its risk register (§8
there) is still the current one for everything but the TRL work. The 08-31
review is the other independent document; the 09-03 and 09-04 reviews are
self-assessments and say so.

**The direction changed again on 2026-09-23.** Stakeholders want supply chain
technology tracking, not a ranking of companies by what they disclose. The
project goes back to technologies as the unit, and the deliverable is now a
tracker of pre-practice technologies with a Technology Readiness Level (TRL)
estimate for each, backed by quoted claims. The spec is
`docs/superpowers/specs/2026-09-23-pre-practice-trl-tracker-design.md`. Which
technologies are tracked is the owner's ruling on the sort sheet,
`docs/audit/tech-practice-sort-2026-09-23.xlsx`: he ruled all 51 rows on
2026-09-24, and 24 are pre-practice.

**The Disclosed Adoption Index and branch `phase0` are parked, not deleted.**
The owner's Phase 0 hand-coding (`phase0-verdicts.csv`, the attestation sheet)
is **no longer required**. Do not merge or delete `phase0` until the owner
decides. The claims package from it (`observatory/claims/`: prompt rules,
schema helpers, quote verification) was copied onto `trl` as its first commit
and extended there.

**Phase 1 of the tracker is built on branch `trl`**, in the worktree
`.worktrees/trl/`, 10 commits ahead of `main` before this one, a fast-forward,
unmerged and unpushed. Two measurements ran on it. One gave a verdict (no free
source reaches the pilot band). The other is preliminary and its gate is not
decided, because the owner's column is blank. Both are in §5.

**Do not re-fix the closed risks.** Six of the original twelve were closed by
2026-09-03 and a seventh (the 256 hole) on 2026-09-03; each was rechecked by
behaviour rather than by grep. The 09-23 register carries the open ones
forward and adds eleven.

**Where the parked work is.** Branch `phase0`, worktree `.worktrees/phase0/`,
33 commits ahead of `main` and 4 behind it (the TRL spec, sort sheet and plan
landed on `main` after it branched), so its merge is no longer a fast-forward,
and `observatory/claims/` now differs on both sides. Its data (`data/phase0/`,
210 MB) and ledger are gitignored and were copied on 2026-09-23 to
`data/phase0-backup-2026-09-23/` in the main checkout, with a `git bundle` of
the branch beside them. Removing that worktree deletes the originals.

---

## 1. What this is

Two things now, one collecting and one being built.

**The count-based Observatory** still collects weekly and unattended from the
`main` checkout. It detects supply chain technologies in publicly accessible
data (papers, code, filings, grants, regulation, forum posts) by lexicon match
and counts documents. On 2026-09-04 the owner judged its report low value:
thin data, a statistic nobody cares about, stage read off the source type, no
surprise. Its reports are no longer the deliverable. Its collectors and raw
store are now the input layer for the tracker. It has not been retired, and it
has not been watched: see §2.

**The pre-practice TRL tracker** is the deliverable. For each technology the
owner ruled pre-practice, it gives a TRL (1 to 9) as a point and a range, with
the claims behind it. How stage is inferred:

- Once a quarter, offline, a pinned model reads the documents the collectors
  already matched to a tracked technology and extracts **claims**. Each claim
  has a `claim_type` (proposes, simulates, prototypes, pilots,
  demonstrates_in_operation, sells, buys, operates_at_scale, abandons), an
  `actor_type`, a `setting`, a `source_type`, the document date and a verbatim
  quote. The quote is checked against the document text locally; an
  unverified claim weighs nothing.
- Each claim type maps to a TRL band (1–3 research; 4–6 prototype and pilot;
  7–8 demonstrated in an operational environment; 9 routine commercial
  operation).
- Scoring is deterministic: each claim's weight is actor × source × setting ×
  recency, from a published table the owner edits
  (`observatory/trl/weights.yaml`, version 1). The **point is the highest level
  whose cumulative support reaches the threshold**, 0.5; cumulative support at
  a level is the weight of every claim whose band reaches that level or
  higher, each claim counted once. It is
  never an average: a hundred papers that only propose or simulate cannot
  lift a technology past 3 (a paper describing a prototype reaches the 4–5
  band), and one verified multi-site operation can set it at 8.
- When no level reaches the threshold there is no point: the page says
  "insufficient evidence" and shows the span of levels the claims evidence.
  That is 9 of the 10 technologies with claims today (§5). It replaced a
  "(floor)" fallback on 2026-09-24; the owner may reverse it (§7 item 2).

Source and stage are decoupled: source type is one feature of a claim, never
the label. **TRL is a maturity scale, not an adoption scale.** The tracker says
how proven a technology is, not how widely it is used; the page says so.

Collection runs weekly; reporting is quarterly, on calendar quarters. The two
cadences are deliberately different (§6).

## 2. Current state

| | |
|---|---|
| Tests | **844 passing** |
| Lexicon | version **10**, 48 active technologies |
| Observations | **2,385** |
| Sources | 11, across 9 evidence families |
| By source | github 828, arxiv 530, scopus 421, openalex 250, edgar 132, hn 67, lens 64, nsf 40, usaspending 29, federalregister 21, pressroom 3 |
| Precision | **70%** at lexicon v9, one model coder, 120 of 132 judged (`docs/precision-audit-2026-09-02.md`) — not comparable with the earlier 51%; the count lexicon's, not the tracker's |
| Deliverable | the TRL page, below. The count report (`output/report-<period>.html`) still builds and is no longer the deliverable |
| TRL tracked set | 24 technologies, the rows the owner ruled pre-practice on `docs/audit/tech-practice-sort-2026-09-23.xlsx` |
| TRL claims 2026-Q3 | 43 claims over 10 technologies, 43 of 43 quotes verified, from 71 documents; model spend $0.29 with the placement reader (`docs/trl-placement-2026-09-24.md`); a copy of the claims file is committed as `docs/audit/trl-claims-2026-Q3.jsonl` |
| TRL page | `output/trl-2026-Q3.html`: 1 of 24 holds a level (delivery drones, TRL 2); 9 "insufficient evidence" with their claims' span; 14 "not estimated" (after the scoring fix, `docs/trl-placement-2026-09-24.md`, last section) |
| TRL placement check | complete 2026-09-25, owner's column filled; gate **FAIL** on the plan's rule (owner~model 6/10 within one, owner~tracker point n=1); owner~tracker span agrees **9/10**; read as source-coverage, not scoring — `docs/trl-placement-2026-09-24.md` §"Owner's reading, 2026-09-25, and the verdict" |
| TRL weights | version **1**, `observatory/trl/weights.yaml`, threshold 0.5 |
| TRL prompt | `trl-1` (`observatory/claims/trl_prompt.py`), model `claude-sonnet-5` |
| Weekly page | collection health only — did the collectors run, what arrived, rising terms |
| Repository | https://github.com/KD1960/Supply-Chain-Innovation-Observatory (public) |
| Phase 0 (DAI) | parked 2026-09-23; instrument built, data collected, never coded, coding no longer required |

**The first four rows and the by-source row are generated.**
`python -m observatory.run --write-status` rewrites them from the database and
a test count, and `tests/test_status_table.py` fails when they drift. Do not
hand-edit them. The other rows are claims rather than counts and are written
by hand; each names the file it came from. In the `trl` worktree
`data/observatory.db` is a symlink to the main checkout's live database, so the
drift test runs here too, and a Monday cron run can make it fail again until
`--write-status` is re-run.

**2026-Q3 closes on 2026-09-30.** Count scores for it are withheld until the
quarter is complete and collected. The TRL claims for 2026-Q3 were extracted on
2026-09-24, before the quarter closed; a final Q3 read would delete the claims
file and re-run after 09-30 (§3). 2026-Q2 is the most recent fully scored
period. The Q3 manual exports on disk
(`data/manual/2026-Q3/`) were taken 08-28 and 09-01 and stop there, and Scopus
and Lens are now frozen (§4), so they cannot be re-run.

**The weekly run has kept running, unwatched, and two weeks are damaged.**
arXiv returned 429 on the 09-14 run and 2026-W37 has no arXiv observations; the
failure is recorded durably and was not backfilled. EDGAR full-text search
returned 500 on the 09-21 run. Both are absent, not zero, in scoring. For the
tracker this means the Q3 claims were read from a corpus with an arXiv hole in
it. 63 Scopus observations carry journal issue dates in weeks that have not
happened (W40, W44, W49) and are excluded from counts until their week arrives,
as designed.

**Phase 0 of the index, in numbers** (2026-09-04, `data/phase0/` on the parked
branch), kept for when it resumes: 50 of 50 sampled 10-Ks fetched raw; 80
lexicon-v10 windows, 22 filings with none; Opus 5 read the windows (57 claims)
and Items 1, 2 and 7 in full (564 claims); Sonnet 5 read the windows (56
claims); 672 of 677 quotes verified; model spend about $13. The verdicts CSV
(647 rows) and the attestation CSV (30) are blank, and no longer need filling.

## 3. How to run it

    python -m observatory.run --write-status         # regenerate section 2 from the database
    python -m observatory.run                        # the weekly run; this is what cron does
    python -m observatory.run --quarter 2026-Q4      # the count report (no longer the deliverable)
    python -m observatory.run --annual 2026
    python -m observatory.run --rebuild              # replay all raw under the current lexicon
    python -m observatory.run --backfill 52          # fetch N trailing weeks, then rebuild
    python -m observatory.run --export-queries 2026-Q4 --split   # prints nothing to run now
    python -m observatory.run --import-manual        # refuses frozen sources' files

**The weekly run includes the press rooms** (collector `pressroom`, since
2026-09-25). The newsrooms it reads are `pressrooms.yaml` at the repo root;
adding or dropping one is an edit there, not in code, and the file lists the
ones that could not be read and why. `--only pressroom` runs it alone for one
week.

**`--export-queries` now produces no queries.** Every manual source is frozen
(Scopus, Lens) or retired (ABI/INFORM); the sheet names each one as NOT
OFFERED with its reason. `--import-manual` refuses their files.

**The tracker**, from the `trl` worktree until the branch merges:

    python -m observatory.claims.extract_trl --period 2026-Q3 [--tech id] [--limit N] [--max-dollars D]
    python -m observatory.run --trl-report 2026-Q3

`extract_trl` is **offline and paid**: it calls the model API. It prints an
estimate first and refuses to start above `--max-dollars` (default 20). Default
model `claude-sonnet-5`, prompt `trl-1`. `--tech` reads one technology;
`--limit N` takes the first N documents per technology in raw-file order (not
the newest), for smoke runs. It reads only documents from the automated
collectors, so frozen library sources never reach a claim. It **appends** to
`data/trl/claims-<period>.jsonl` and says so; to re-read a period, delete that
file (and `data/trl/raw-<period>-<model>/`) first, or the claims double. It
also writes each raw model response and a cumulative usage file beside it.
All of `data/trl/` is gitignored.

`--trl-report` makes no model call. It reads the claims file, scores it with
the weights table, writes `output/trl-<period>.html` and
`data/trl/estimates-<period>.json` (next quarter's "what moved" reads it), and
refuses with one sentence if the claims file is missing.

The placement check's tools are throwaway scripts under
`docs/experiments/trl/` (`probe.py`, `placement_sheet.py`, `placement_model.py`);
`placement_model.py` also calls the model.

Installed cron, Monday 07:00 local, from the main checkout:

    0 7 * * MON cd '/Users/kevindooley/Claude/Projects/Supply chain innovation' && /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m observatory.run >> data/cron.log 2>&1

The interpreter path matters: `/usr/bin/python3` is macOS's 3.9 and has none of
the dependencies. Keys live in `.env`; `GITHUB_TOKEN`, `SEC_CONTACT_EMAIL` and
`ANTHROPIC_API_KEY` are set and working. Only the offline extraction and the
placement reader use the last. Each worktree carries its own copy of `.env`.
The `trl` worktree's `data/observatory.db`, `data/raw` and `data/manual` are
symlinks into the main checkout's `data/`; `data/trl/` is local to the
worktree and is lost if the worktree is removed before merging and copying it.

**The parked index work runs from `.worktrees/phase0/`.** Its scripts are under
`docs/experiments/phase0/` on that branch and are described in its own STATUS.
`data/phase0-backup-2026-09-23/` in the main checkout holds the backup;
refresh it before removing that worktree.

**A number read without a rebuild is the old lexicon's number.** Observations
insert with `INSERT OR IGNORE`, so rows written under old patterns survive until
`--rebuild` drops the derived tables. This has produced a wrong figure in a
report to the owner twice.

## 4. The rules this project runs on

These were each learned by shipping a wrong number, and they are why the code
looks the way it does.

- **A missing week is not a zero week.** A source that failed leaves its signals
  absent, not zero. Folding absence into zero invents declines.
- **Raw before parse.** Collectors write untouched response bodies to
  `data/raw/<week>/<source>/` before anything parses them. The database is a
  derived artifact and can always be rebuilt.
- **The document's own date decides its week**, not the run week. A run rescores
  every week it wrote into.
- **Context gating.** Terms that belong to every field (`ERP`, `humanoid robot`,
  `computer vision`) count only when the document also uses supply chain
  language. The gate is per technology and document-level.
- **Say it out loud when a cap bites.** Silent truncation is this project's
  oldest failure mode.
- **Measure before building, and record the rejection with its reversal
  condition.** Both TRL measurements in §5 carry one.
- **Check the artifact, not the code that makes it** (§10).
- **Standing instruction from the owner:** plain correctness bugs inherited from
  the plan get fixed without asking and reported in the summary; genuine
  judgment calls go to the owner.
- **Stage what you mean to commit. Never `git add -A`.** Name the paths you
  changed. On 2026-09-03 `git add -A` published the owner's marketing and
  distribution plan to the public repository because it happened to be
  untracked, and on 2026-09-04 it did the same to a `.docx` assessment saved
  into `docs/` that morning — in the commit that wrote the review describing the
  first incident. The owner elected to leave both up and set this rule. The
  repository is public: a commit is a publication, and staging everything is not
  the same as choosing what to publish. An untracked file you notice gets
  mentioned to the owner, not committed. The 09-23 audit found three files that
  had been swept in earlier, before the rule existed: the MHI *2026 Annual
  Industry Report* PDF (a third-party publication, public since 08-28), a
  terminal transcript, and the Q2 technologies sheet.

**Rules the tracker added (spec §2; each enforced in code or by a test):**

- **C1. No library exports.** No collector, export or reported number may
  require a manual export from a library-licensed database. `scopus`, `lens`
  and `abi_inform` are frozen in `sources.yaml`, each with its reason and its
  reversal condition: a licence or API agreement that permits mining, recorded
  there. The spec also says existing library-derived observations are excluded
  from anything published; the tracker never reads them, but the count report
  still counts them (§5).
- **C3. Source and stage are decoupled.** Source type is one feature of a
  claim, with a weight; it is never the stage.
- **C4. Every estimate is traceable** to claims, each with a verified quote and
  a citation. The page shows the top three claims behind each estimate and the
  strongest contrary one.
- **C5. A model only offline.** The model is called in exactly two places: the
  quarterly claim extraction (`observatory/claims/extract_trl.py`) and the
  placement check's model reader (`docs/experiments/trl/placement_model.py`),
  both by explicit command. `tests/test_claims_isolation.py` fails if any
  module in `observatory/` outside `claims/` imports `anthropic` or
  `observatory.claims`, or if `observatory/trl/` imports either. It scans only
  the `observatory` package, so the scripts under `docs/experiments/` are not
  covered.
- **Pinned model, recorded on every claim**, with the prompt version. A change
  to the prompt string is a change to the instrument and bumps the version
  (`trl-1` now). No fallback model on a refusal; refusals are recorded as rows.
- **A spend ceiling before every paid run**, printed as an estimate; the run
  refuses above it.
- **Document text is untrusted.** The system prompt says so; output is
  schema-constrained and technology ids are bounded to the tracked set.
- **C6. Membership is the owner's ruling** on the sort sheet. There is no
  numeric adoption screen.

**The index's rules (on `phase0`) still hold for its code** if it resumes:
quotes verified locally, raw model responses kept before parsing, filing text
untrusted. The audit's note that Phase 0 bent "measure before building" (it
built `universe.py` and the `claims/` package as durable modules before
measuring) is recorded in its STATUS.

## 4a. What the library can and cannot license (2026-09-03)

ASU Library answered a set of questions about text and data mining of licensed
resources; the business librarian replied with the electronic-resources and
licensing librarians copied. **Read this before adding any source that sits
behind a subscription.** The full record, including the exact clauses, is in
`docs/abi-inform-retired-2026-09-03.md`; the reply and the open questions are in
`correspondence/` (gitignored — email is not method).

The general answer: **ASU's business database licences forbid text and data
mining.** The Economist Intelligence Unit is the only business-related exception
the librarian knew of, and avoiding this restriction is a large part of why ASU
subscribes to TDM Studio at all. Most licences forbid automated retrieval even
of metadata alone.

| Source | Answer | What it meant here |
|---|---|---|
| **ProQuest / ABI/INFORM** | No TDM, and the librarian reads the clause as covering metadata. TDM Studio is the only sanctioned route, and ABI/INFORM is in it (not the Financial Times) | **Retired.** 13 observations removed, trade press gone as a family |
| **Scopus** | Elsevier gives academic researchers free API keys; the library is not involved. Quotas and throttling at dev.elsevier.com. Anything outside the API violates the terms | **Frozen** under C1 since 2026-09-24. The API route is spec §6 item 5 |
| **Web of Science** | ASU terminated the subscription 2020-12-31. No access at all | Closed |
| **Factiva** | ASU does not subscribe | Closed. A Factiva Analytics mining licence is a paid option (spec §6 item 1) |
| **NexisUni** | Programmatic access prohibited without written permission; no API subscription. Even manual downloading can get ASU cut off if the vendor deems it excessive | Closed. Nexis Data Lab is a paid option (spec §6 item 1) |
| **Lightcast** | Not a library resource — ask career services | Open, and not a library question |

**Lens is not a library resource and is frozen anyway.** Lens.org is free, but
the spec's C1 names "Lens via library", and Task 1 froze the `lens` entry with
the others. It is the only patent source. The owner has to rule (§7, item 3).

**Still open with the library**, in the reply draft, now mostly moot because
the tracker does not depend on library sources: whether a human-run Scopus
export is acceptable; whether the API key covers retrieve-match-publish;
whether TDM Studio can serve a recurring pull; whether publishing aggregate
counts with titles and links is acceptable for a licensed source.

**The standing rule this produces:** a subscription source is not added until
its licence has been checked, and the answer is written down with the condition
that would change it. Since 2026-09-24 paid sources are allowed (§8), and each
must carry a written licence note in `sources.yaml` saying what its terms permit.

## 4b. What changed recently

Full reasoning is in the commit messages, which are long on purpose, in the
SDD ledger (`.superpowers/sdd/2026-09-24-trl-tracker-phase1/progress.md`,
gitignored), and in the two measurement reports.

**2026-09-24 (TRL Phase 1)** — the owner ruled all 51 rows of the sort sheet,
commented on the spec, and approved free-sources-first. The spec was revised
from his comments and a plan written
(`docs/superpowers/plans/2026-09-24-trl-tracker-phase1.md`, eight tasks with
two measurement gates). Tasks 1–7 were executed on branch `trl` through a
fresh-implementer-per-task loop with a review after each task; two tasks needed
one fix round each. In order:

1. Library sources frozen (C1): no export sheets, no imports; `print_queries`
   no longer crashes on an empty sheet.
2. TRL claim schema, band map, and the tracked set read from the sort sheet.
3. The scorer: weighted support per level, highest held level as the point,
   the weights table.
4. The pilot-band probe: measured, verdict negative, no GDELT collector built.
5. Document text behind observations; prompt `trl-1`; the offline extraction
   command with a cost ceiling; raw responses kept.
6. The placement check: sheet, model reader and tracker on ten technologies.
   Preliminary.
7. The report page, `--trl-report`.

**2026-09-23** — the direction changed (above). The 09-23 audit was written on
`phase0` and that branch's STATUS rewritten around the DAI pivot, §2
regenerated there, and Phase 0's data and ledger backed up. That same day the
tracker spec and sort sheet were drafted on `main`. Between 09-07 and 09-23 no
work was done; the weekly run ran three more times (§2).

**2026-09-07** — the owner asked to see what the Phase 0 data said before
coding. `docs/phase0-precoding-2026-09-07.md` (on `phase0`) computed every
figure the stored claims support without a coder, then an attestation sheet
and a fifteen-category draft followed. The audit qualified both. All of it is
parked.

**2026-09-04 (the first pivot)** — the owner's assessment
(`docs/KD project assessment 20260904.docx`), a brainstorm of eight
alternatives, the Disclosed Adoption Index spec
(`docs/superpowers/specs/2026-09-04-disclosed-adoption-index-design.md`),
approved the same day, and Phase 0 built and collected on `phase0` (32
commits, about $13 of model spend). The assessment's diagnosis still stands and
is why the tracker infers stage instead of reading it off the source.

**2026-09-04** — the README was rewritten. It had described a weekly dashboard
built from six sources with an annual report, and walked a reader through
exporting from Web of Science and ABI/INFORM: the first is gone since 2020 and
the second is prohibited. A test now fails if the CLI's own help names a
retired source.

**2026-09-03 (licence)** — **ABI/INFORM is retired.** Thirteen observations
removed, trade press gone as an evidence family. Full record in
`docs/abi-inform-retired-2026-09-03.md`.

**2026-09-03** — the count report gained a findings layer
(`observatory/findings.py`), post cards (`observatory/cards.py`, Pillow), a
two-page brief (`observatory/brief.py`) and a tracked-technologies sheet
(`observatory/sheet.py`), all written by `--quarter` and all failing soft. The
overlap guard now enforces its 5% tolerance and, for the first time, applies to
Scopus. These are the count report's and are not used by the tracker.

**2026-09-01 to 09-03** — 29 commits, assessed in
`docs/process-review-2026-09-03.md`: withholding on short windows,
`source_attempts`, future periods refused, `ruff` in a pre-commit hook and CI,
STATUS §2 generated, lexicon v9 → v10, the precision instrument fixed.

**2026-08-27 to 08-31** — USAspending fixed; Scopus, Lens, ABI/INFORM,
OpenAlex and NSF added; lexicon v6 → v9; reporting moved to calendar quarters
and a four-quarter window; the weekly page became a collection-health view.

## 5. What is broken or missing

### The tracker: two measurements

**(a) The pilot-band probe — verdict: no free source reaches the pilot band**
(`docs/trl-probe-2026-09-24.md`). Trade press was the only source for TRL 5–8
evidence (pilots, first sites, purchases) and it is frozen. Three free
candidates were probed over five technologies and eight weeks, pass line three
pilot-band documents per technology: **GDELT 1 of 5** (delivery drones only,
and its nine titles are four underlying events), **GlobeNewswire 0 of 5, PR
Newswire 0 of 5**. No GDELT collector was built. The page carries the note
"Pilot-band evidence (TRL 5-8) is collected only from sources that permit
mining; see the probe report for what that covers this period."
(`observatory/trl/report.py`). GDELT gives titles only, never text, and 429'd twice during the
probe; the press-release sites take no date parameter. The `humanoid_logistics`
and `gs1_2d` queries probably undercounted.
**Reversal condition** (the probe report's own): re-run the probe with
phrase-anchored queries for `humanoid_logistics` and `gs1_2d`, and with either
a licensed news source (spec §6 item 1) or a genuinely date-filtered
press-release search. If a source then clears three or more pilot-band
documents per technology over a trailing eight weeks for at least three of the
five technologies, add its collector.

**(b) The placement check — complete 2026-09-25; gate FAILS on the plan's rule**
(`docs/trl-placement-2026-09-24.md`). The question is whether two readers,
given the same claims, place a technology within one TRL level of each other
and of the tracker. Ten technologies were read for 2026-Q3: **43 claims, none
above prototypes** except one; 33 of 43 are proposes or simulates, 9
prototypes, none pilots, sells, buys or operates at scale. **All 43 come from
papers, NSF awards or GitHub**; no filing, press release or trade article
produced a claim. Every claim weighs between 0.015 and 0.186 against a
threshold of 0.5. As first run the tracker printed **the floor for 7 of 10**
and was **within one level of the model reader (`claude-opus-5-5`) on 3 of
10**. The final branch review then found the scorer counting a two-level-band
claim twice (fixed, below); re-scored, **only delivery drones holds a level
(TRL 2, total support 0.513)**; the other nine are "insufficient evidence"
(total support 0.077 to 0.466). `placement.agreement()` skips a technology with
no point, so model vs tracker is now **1 of 1 within one** (n = 1, mean abs
diff 1.0), or 1 of 10 if "insufficient" counts as disagreement, which is the
owner's to rule. The report's last section has the table.
**The owner's column was filled 2026-09-25** and the check is complete
(`docs/experiments/trl/placement_final.py`,
`docs/trl-placement-2026-09-24.md` §"Owner's reading, 2026-09-25, and the
verdict"). The pass line, set in the plan: the owner and the tracker within
one level on at least 7 of 10, **and** the owner and the model within one
level on at least 7 of 10. **Result: FAIL.** Owner vs model is 6 of 10 within
one (misses: cv_inspection, supply_chain_llm, autonomous_trucking,
humanoid_logistics, all the model reading a level or more above the owner).
Owner vs tracker point is not measurable at the gate's 7-of-10 bar: only one
technology (delivery_drones) has a held point after the scoring fix, so n=1
(within one). An added measure not in the plan's gate — owner's number
against the tracker's span, widened by one level either side — agrees on 9 of
10; the one miss is `supply_chain_llm` (owner 2, span 7-8), the same
actor-unclear arXiv claim already flagged in item 4 below. The owner placed
every technology at 2-3 and wrote, on eight of the ten rows, a version of "based
on evidence but we're missing sources that would suggest 4-6": a calibrated
low placement, naming the missing pilot/operation evidence himself. Read this
way the failure is a **source-coverage gap** (no free source reaches the pilot
band, the same finding as the probe above), not a scoring defect, so the
report recommends **not** revising the weights and leaves the ruling to the
owner (§7 item 1).

**What the placement exposed about the weights table** (the owner's to rule,
§7 item 2): no single research-setting claim comes near the 0.5 threshold (the
observed maximum is 0.186), so a level is held only when many claims add up.
With each claim counted once, that happens for one technology (delivery drones,
level 2); at levels 4 and above it rarely will on free sources. The threshold
may need to scale with the band.

**Scoring fix at the final branch review (2026-09-24).** Cumulative support
counted a claim once per level of its band, so every two-level claim type was
counted twice and was favoured over `operates_at_scale`; that double count is
what held digital twin at 2 and agentic procurement at 1. Cumulative support at
level L is now the sum of the weights of the claims whose band reaches L or
higher, each counted once (`observatory/trl/score.py`, tests in
`tests/test_trl_score.py`). The floor fallback is gone: with no level held
there is no point and the page says "insufficient evidence (claims span L–H)";
held estimates sort first, then insufficient ones by number of claims, then
unestimated; "what moved" compares only two held levels. `supply_chain_llm`
(one arXiv claim, actor unclear, weight 0.077) no longer tops the page; it is
insufficient evidence, span 7–8.

**A rebuild drops the frozen library observations, by decision.** `--rebuild`
and `--backfill` clear the derived tables and replay raw plus manual exports;
the replay refuses frozen sources (C1), so the 421 Scopus and 64 Lens
observations in §2 do not come back. The rebuild prints one line per frozen
source ("Rebuilding: scopus is frozen (spec C1), not replayed; N observations
dropped"); `tests/test_run.py::test_rebuild_drops_frozen_sources_and_says_so`.
This is C1 applied, not a regression; it also removes the library-derived
observations the count report is not supposed to publish (below).

**Deferred minors from the Phase 1 ledger**, all harmless today: `abi_inform`
carries both `retired` and `frozen`; `tests/fixtures/trl/sort-sheet.csv` is
unused; `score.claim_weight` has no guard for keys outside the closed sets
(relies on `schema.validate`); an `abandons` claim dents levels 7–9 whatever
its own setting; the probe's release-page fetch helper was never committed;
the extraction's price table is above list (sonnet $3 against $2, so it refuses
early) and its estimate counts input tokens only; `claim_id` collides for the
same quote with a different claim type in one document; an unparseable raw
file stops the command; `placement_model.py` marks a sub-1,024-token prompt
for caching (no cache hits) and its smoke-call usage was overwritten; the TRL
report tests read the real sort sheet and watchlist because `tracked_ids()` and
`load_watchlist()` are not injectable.

**Not built in Phase 1, by design:** the eight-quarter trajectory (one period
of estimates exists; `estimates-<period>.json` is written each run so it can
be drawn later); the quarterly model narrative (spec §5, approved); the
measurability gate for candidates (spec §7); any paid source.

**(c) The press rooms — a new free source, first run 2026-09-25**
(`docs/pressroom-first-run-2026-09-25.md`). Collector `pressroom` reads 16
vendor newsrooms listed in `pressrooms.yaml` (listing plus up to 15 in-window
item pages each, one request every 2 s) and hands title and opening text to
the same matcher; family `press`, stage `deployment`. Probe 2
(`docs/trl-probe2-2026-09-25.md`) ranked it first among free sources for the
pilot band. **Licence:** press releases are issued for redistribution; the
report quotes with attribution and links the release. **Robots:** read once
per host per run and obeyed; a 403, a disallow or a JavaScript shell is
recorded in the raw envelope, never evaded. **First run** (2026-W39 only, no
rebuild): 16 of 16 newsrooms answered, 0 notes, 26 item pages, **19
documents and 3 observations**, all autonomous trucking: one pilot-band
(Kodiak and DTL's first deliveries under the California permit), one passing
mention, one false positive (Aurora's investor-day notice, matched on the
company's description of itself). 9 of 16 newsrooms had an in-window item.
That is the weekly flow, and the list is small. A first pass had parsed
every dated item on each listing (780 documents back to 2002, 131
observations, 128 of them in weeks with no `pressroom` run, and a `corpus`
row every later week would have repeated); `parse()` now keeps only items
inside the envelope's own window, and that pass was purged and replayed from
the saved raw. History on a listing is not collected. That fixed the history
repetition, not the lookback double-count (see "The count pipeline" below).
Fixed after the first run, not yet exercised on a live fetch: Wing's pages came
through as mojibake (UTF-8 read as Latin-1; `http.py` now decodes by the
page's own `<meta charset>` when the header names none, for every collector;
the W39 raw keeps the mojibake); Volvo's month-only sitemap URLs
(`/2026/september/`) are now fetched when their month meets the window and
dated from the page, not the 1st; item pages and robots.txt get one retry, not
three. **Reversal
condition:** retire the source if two consecutive quarters yield under 10
matched observations.

### The count pipeline

**The corpus double-counts across the 7-day lookback.** A document dated in
the overlap is fetched by two consecutive weekly runs and recorded in both
weeks' `corpus` rows; `corpus_between` sums `documents` by `doc_date` across
weeks, so it counts that document twice. Pre-existing for github and arxiv;
`pressroom` shares it. The fix belongs in `record_corpus` / `corpus_between`:
count distinct doc_ids, not per-week sums.

**C1 is not enforced on the count report.** 421 Scopus and 64 Lens
observations are still in the database and in any count report
`--quarter` builds. The spec excludes library-derived observations from
anything published. Nothing currently filters them. Harmless while the count
report is not published; fix before it is.

**Precision is unsettled.** The last figure, **70%**, was measured at lexicon
v9 against a corpus that no longer exists; two corpus changes separate it from
what the count report publishes. Every coder so far has been the same model.
EDGAR cannot be audited at all (filing bodies are never fetched; 129
observations, precision unknown). `docs/precision-audit-2026-09-02.md`.

**GitHub measures the wrong population.** 78% of matched repositories have
exactly one star. It is a third of the corpus, and for the tracker it supplies
code-repository claims that weigh 0.3.

**Diffusion is the thinnest stage.** With trade press gone the count report's
diffusion rests on SEC filings and Hacker News. The tracker's equivalent is the
pilot-band verdict above.

**Not built:** PatentsView (declared, never existed; `search.patentsview.org`
had no DNS record on 2026-09-03). Semantic Scholar (429s unauthenticated).

### Known defects, unfixed

- **The suite writes into the run log.**
  `test_a_future_week_never_takes_latest_html` (`tests/test_failures_durable.py`)
  redirects `OUTPUT_DIR` but not `RUN_LOG_PATH`, so every full suite run in the
  main checkout appends two fake rows to the production `data/run_log.jsonl`;
  the audit counted 140. In the `trl` worktree only `observatory.db`, `raw` and
  `manual` are symlinks; `data/run_log.jsonl` is a local file, so suite runs
  here do not touch the production log.
- `collected_quarters` counts a week as collected if any `source_runs` row
  exists, without `store.COLLECTED_STATUSES`.
- `adoption_new` is hardcoded to 0 (`metrics.py`); `media_articles` and
  `media_deploy` are declared for a GDELT collector that has never existed.
- `missing_exports` detects absence, not staleness (moot while every manual
  source is frozen).
- `patentsview` is declared in `EVIDENCE_FAMILIES` and has never existed.
- Two findings can name the same technology (2026-Q2 names autonomous trucking
  twice).
- Post cards need a font the CI box lacks; a quarter can ship with no cards and
  one line saying why.
- Carry-forward items in the plan docs: clone-cohort policy, `gh_commits` /
  `gh_stars_delta`, `fed_obligated` semantics, discovery baseline denominator.

### Phase 0 (parked): what the audit found

Kept because it is true and matters if the index resumes; none of it blocks the
tracker. Full detail in `phase0`'s STATUS §5 and in the 09-23 audit.

- Nothing was coded, so spec §7's gates were never measured except tokens per
  windowed filing (6,706 against 8,000, go).
- "Lexicon v10 reaches 5% of what the open read found" is overstated in size;
  on the auditor's read of forty labels it is nearer 15% of supply chain
  claims. Under the spec's own breadth rule, lexicon v10 leaves 43 of 50 filers
  tied at zero once ERP and WMS are set aside.
- The category draft is in-sample and counts pattern hits: 134 of 564 claims
  within its boundaries, not 183.
- The model comparison is keyed wrongly: `claim_id` omits model, role and
  stance, and 8 of the 30 shared ids carry different labels.
- The sampling frame (SIC ranges) was never put to the owner.
- The spend estimator read about a quarter low on the open run.

## 6. Decisions that reversed the spec

**Momentum was dropped entirely** (commit `5b1c4f4`), along with `acceleration`,
`cross_sectional_z`, `normalize_series`, `trailing_mean` and the quarter-folding
helpers built for it. It was the only metric needing a time series, and it kept
reporting noise as trend in three separate ways — each found by looking at what it
*ranked*, not by reading the code:

1. 95% of `weekly_signals` is observed zeros, so normalising a technology seen
   once divided by a near-zero spread and handed its single document a large
   z-score. Manufacturing execution systems, three documents in a year, ranked
   first.
2. `edgar_filers` is a stock (distinct companies over a trailing window), not a
   flow. Summing thirteen weeks of it turned two filers into twenty-six.
3. Every guard added to fix those cut the scored set further — 50 of 50 down to
   17 of 50. A metric that on inspection was mostly not measuring anything.

**Reporting moved to quarterly; collection stayed weekly.** Two thirds of
technology-weeks hold zero observations and the median is zero, so a weekly
ranking mostly reported which week a collector caught something. Zero cells fall
from 68% weekly to 46% monthly to 34% quarterly.

Collection did **not** move, and this is the part most likely to be
well-meaningly undone. A wider fetch window silently truncates four of six
sources: per 13-week quarter arXiv would ask for ~15,800 documents against a
2,000-per-sweep cap, GitHub ~6,460 against a **hard 1,000-result API limit that
cannot be raised at all**, Federal Register ~3,400 against 2,000, Hacker News
~2,200 against 1,000. The weekly window is the only one where every query stays
under its cap. Cadence and window are separable: an annual *run* that loops over
52 weekly *queries* is fine; a single wide query is not.

**The no-LLM rule is narrower than it looks.** It was justified by repeatability
of a *recurring* process. The weekly run must stay deterministic; offline,
pinned, audited model reads are allowed (C5).

**The first pivot (2026-09-04)** chose the Disclosed Adoption Index and
reversed three standing rules for it: direct model calls offline, filing bodies
fetched and read, the company as the unit. **The second (2026-09-23)** returned
to technologies as the unit, kept the offline model read, replaced
source-as-stage with inferred TRL, dropped the library sources (C1) and
allowed paid sources (C2).

**Plan deviations in Phase 1, on the assistant's ruling** (each recorded in the
task reports): `frozen_sources()` lives in `observatory/supplemental.py`, not
the chart module the plan named; an explicitly named frozen source can still
print its query (as retired `abi_inform` could), only the default sheet drops
it; the estimates file is written beside the claims file; `TRLEstimate` gained
a `held` flag (at the final review it became the switch between a point and
"insufficient evidence", and gained `cumulative`).

## 7. Where to pick up

In value order, the owner's items first because nothing else moves until they
do.

1. **Done, 2026-09-25.** The owner filled `docs/audit/trl-placement-verdicts.csv`;
   the check ran (`docs/experiments/trl/placement_final.py`,
   `docs/trl-placement-2026-09-24.md` §"Owner's reading, 2026-09-25, and the
   verdict"; §5 above has the numbers). **Result: FAIL** on the plan's rule
   (owner~model 6/10 within one; owner~tracker point n=1, not measurable at
   7/10), but owner~tracker span agrees 9/10, and the owner's own notes read as
   a calibrated low placement flagging missing pilot/operation evidence, not
   disagreement with the scoring. **Owner ruled 2026-09-25: keep weights v1.**
   His words: "the problem is lack of content, we're even missing evidence
   that might change a 1 into a 2 or 3." So the gap is not only the pilot
   band (TRL 5–8, the probe's finding); the research band is thin too, with
   at most 9 claims per technology from the free sources. The next step was
   sources: probe 2 (`docs/trl-probe2-2026-09-25.md`) ranked vendor press
   rooms first, the owner said "build the press-room collector", and it was
   built and run once on branch `pressroom` the same day (§5 (c)): 16 of 16
   newsrooms answered, 19 in-window documents, 3 observations (one
   pilot-band, all autonomous trucking). Next: merge `pressroom` after the
   owner's look, then judge the yield over a quarter (the reversal condition
   in §5 (c)); fix Wing's mojibake; and look at why the three humanoid
   newsrooms and Avery Dennison answered and matched nothing (Agility's
   "Digit 5 Humanoid Robot" release was in window: a lexicon question, not
   a collector one). Branch `trl` merged to `main` on his instruction the
   same day.
2. **Owner: the weights and threshold question the placement exposed.**
   No single research-setting claim comes near 0.5 (maximum 0.186), so a level
   is held only when many claims add up, which at levels 4 and above rarely
   happens on free sources; after the scoring fix one technology of ten holds a
   level. Options: a threshold per band, or re-weighted research sources.
   **"Insufficient evidence" instead of a floor is now the default**
   (2026-09-24, at the final branch review): the page prints no level the
   evidence does not hold and shows the claims' span instead. The owner may
   reverse it; reversing means restoring a fallback point in `score.estimate`
   and the "(floor)" label in `observatory/templates/trl.html.j2`. This
   interacts with item 1: the one permitted revision after a fail should
   address the threshold, and the owner should rule whether "insufficient"
   against a reader's number counts as a disagreement for the gate.
3. **Owner: rule on Lens.** It is free, not a library resource, and the only
   patent source; it is frozen because C1's wording names "Lens via library".
   Unfreezing needs its licence checked and written into `sources.yaml`. The
   `lens` entry's `frozen_reason` says "Library licence forbids text mining",
   which is not true of Lens; its wording waits on this ruling.
4. **Owner: actor-unclear claims.** `supply_chain_llm` rests on one arXiv
   claim, actor unclear; it no longer tops the page (held estimates now sort
   first, and it is "insufficient evidence"). Still open: whether
   actor-unclear operation-band claims should count at all.
5. **Merge `trl` into `main` after the owner's go**, not before. It is a
   fast-forward today. Copy `data/trl/` into the main checkout's `data/` first;
   it is local to the worktree. `phase0` stays parked; merging it later will
   conflict in `observatory/claims/`.
6. **Paid sources when funds arrive, Crunchbase first** (the owner's order,
   spec §6), then a news mining licence, which is also what reverses the probe
   verdict. Each needs a licence note in `sources.yaml` and a rebuild of
   history, never a hand rescore.
7. **Phase 2:** the quarterly model narrative (spec §5, approved) and the
   measurability gate for candidates (spec §7: multi-agent systems, physical
   AI, intelligent simulation, AI-native TMS, autonomous rail). Both need the
   extraction command, which now exists. A final 2026-Q3 read after 09-30.
8. **The deferred minors** in §5: the price table and output-token estimate,
   the `claim_id` collision, the unparseable-raw stop, `abandons` bluntness,
   the unused fixture, the redundant `abi_inform` flag, the uncached reader
   prompt, the non-injectable test inputs.

**Still open from before the TRL work, lower priority:**

9. **Before 2026-Q3 closes on 09-30, fill the arXiv W37 hole and recheck
   EDGAR** from the `main` checkout (`--backfill 3`, then check
   `source_attempts`). It matters to the tracker now: a final Q3 read would
   otherwise miss a week of arXiv. **Know what it does first:** `--backfill`
   ends in a full rebuild, and a rebuild does not replay frozen sources (C1),
   so the 421 Scopus and 64 Lens observations leave the database for good and
   the rebuild prints a line saying so for each (§5). That is intended; the
   count report's Q2 and earlier numbers that used them will change on the
   next `--quarter`. Back up `data/observatory.db` first if the old counts
   must stay reproducible.
10. **Stop the suite writing into `data/run_log.jsonl`** (one `monkeypatch` in
    `test_a_future_week_never_takes_latest_html`), then mark or strip the fake
    rows in the main checkout's log. Runs in the `trl` worktree write to a
    local log and add none.
11. **Enforce C1 on the count report**, or retire the count report, before any
    count report is published again (§5).
12. **Owner: the calendar.** The marketing plan's positioning, findings layer,
    example sentence and December freeze were written for the count report.
    Decide what January launches.
13. **What to do about the MHI report PDF and the prompts transcript** in the
    repository (on `main`'s working tree they are moved into an untracked
    `archive/`, uncommitted; a commit removing them takes them out of the tree,
    not out of history).
14. Decide `patentsview` (declared, never existed); retire `discover.py` or
    justify it; split `quarter.build_context` (826 lines).

**Waiting on the owner:** the placement verdicts (item 1); the weights ruling
and the insufficient-evidence default (item 2); Lens (item 3); actor-unclear
claims (item 4); the go to merge (item 5);
funds (item 6); the calendar (item 12).

**Specced, not built, by design:** the Phase 2 items above; the in-practice
dashboard (spec §8, only if a third-party evidence base exists); everything
past Phase 0 on the parked index.

## 8. Owner decisions already made — do not relitigate

- **2026-09-25:** keep weights v1; the placement gap is content, not scoring;
  merge `trl` to `main`; the owner investigates sources and stakeholder ideas
  next, and no further tracker work starts until he returns with them.

- Real code pipeline, not ad-hoc research.
- ~~Free sources only. No paid data.~~ **Reversed 2026-09-24:** paid content
  is allowed within its licence's mining terms (see below).
- Fixed watchlist plus auto-discovery of rising terms.
- No LLM in the weekly run. The pipeline never edits `watchlist.yaml`; a human
  merges. **Amended 2026-09-04:** offline, pinned-model extraction by explicit
  command is allowed; the weekly run stays model-free and
  `tests/test_claims_isolation.py` proves it.
- `raw_fetch` is an append-only log of fetch attempts.
- GitHub clone cohorts require at least 1 star, and GitHub stays at the 1-star
  floor until Lens patents are collecting (2026-08-28). Lens is now frozen, so
  the condition that would reopen this has moved (§7 item 3).
- arXiv's old-ID limitation: leave the plan's code, log it.
- Momentum dropped; collection stays weekly.
- **CRA is not being added** (2026-09-03): AUC 0.70, about six precision points
  for thirteen per cent of true positives
  (`docs/cra-feasibility-2026-09-03.md`).
- Three proposed technologies were rejected as fields rather than technologies:
  software supply chain security, e-commerce, machine learning for operations.

**Decided 2026-09-03 and 09-04:**

- **ABI/INFORM is retired**, its 13 observations removed. Reversal conditions
  in `docs/abi-inform-retired-2026-09-03.md`.
- **The overlap guard enforces the 5% tolerance** its comment documented.
- **Post cards carry the finding, not the figure.**
- **Pillow is an accepted dependency.**
- **The technologies sheet expands patterns into readable terms.**
- **The Scopus collector waits for a real API response** (moot while frozen).
- **The marketing plan stays public.** Correspondence is gitignored.

**Decided 2026-09-04 and 09-07, for the index (now parked):**

- **The count-based dashboard has too many shortcomings to be high value**
  (`docs/KD project assessment 20260904.docx`). Still stands.
- The Disclosed Adoption Index was the spine; its spec was approved as written.
  Superseded 2026-09-23, not reversed: parked.
- The quarterly extraction may call the model API directly.
- No adopters forced into the sample; report before coding.

**Decided 2026-09-23 and 09-24, for the tracker:**

- **Technology tracking, not disclosure ranking.** Stakeholders want supply
  chain technology tracking. The DAI and `phase0` are parked; the Phase 0
  hand-coding is no longer required.
- **No dependency on ASU Library downloads** (C1). Scopus, Lens and
  ABI/INFORM are frozen.
- **Paid content is allowed**, within each licence's mining terms, with a
  licence note in `sources.yaml`. Free sources first; paid sources are added
  when funds arrive, Crunchbase first, a news mining licence next.
- **Membership is the sort sheet**, all 51 rows ruled 2026-09-24; the two
  "redefine or split" rows ruled plain retires. No numeric adoption screen.
- **The quarterly offline model narrative is approved** (spec §5), with every
  sentence citing a claim id.
- **Measurability gate for candidates:** added only after a one-quarter probe
  shows they produce claims reliably, with a floor the owner sets after the
  first probe.
- **Everything may be pushed** (2026-09-24, in chat: "push is fine, nothing
  to hide; so push"). `main` was pushed the same day; commits through
  `64db06b` are public. `trl` and `phase0` are still unpushed, pending the
  merge decision.
- **"TLR" in the direction means TRL.**

## 9. Published artifacts

Reports are regenerated from the database and the claims file and are cheap to
remake; do not treat any published copy as current. `output/` holds the latest
of each period: `output/trl-<period>.html` (the tracker), and the count
report, its evidence page and `output/charts/`.

The tracker's committed artifacts are under `docs/audit/`: the sort sheet, the
placement sheet, the blank placement verdicts CSV, the model reader's CSV, and
a copy of the 2026-Q3 claims (`trl-claims-2026-Q3.jsonl`, the evidence behind
the page, C4).
Its gitignored data is under `data/trl/` in the `trl` worktree: the 2026-Q3
claims, raw model responses per document, usage, estimates, the placement
reader's raw output, and the probe's raw responses. The model output is not
regenerable byte for byte.

Phase 0's artifacts are on `phase0` (the coding sheets under `docs/audit/`) and
in `data/phase0/` and its backup (§3).

## 10. A note on how this project has gone wrong

Recorded because the same shape recurs and recognising it early is worth more
than any single fix.

**Verifying the mechanism instead of the outcome.** The tests checked that a
chart's SVG was in the template context, not that it reached the page — it did
not, for two releases. OpenAlex was recommended as a Scopus replacement after
testing its retrieval and never its abstract coverage. A guard was written for
partial quarters, documented accurately, and never connected to its caller.

**Assuming the scope of an action instead of checking it.** `git add -A`
published the owner's marketing plan to a public repository, because the command
was chosen for convenience and nobody looked at what it was staging.

**The remedy that works:** check the artifact, not the code that makes it. Read
the rendered page, count the rows in the database, compare the number against
the export file. Every wrong figure in this project was caught that way, and
none were caught by reading the code that produced them.

**Building ahead of the data, and reviewing the code instead of the data
(added 2026-09-23).** Phase 0's plan wrote the filing parser in Task 3 and
fetched the first real filing in Task 11; the one defect that changed a number
was found only by the review that ran against real filings. The TRL plan put
its two measurements (Tasks 4 and 6) before the page, and the placement check
is what showed the floor problem, which no unit test would have.

**Letting the handover document drift.** On 09-22 this file described a
product the owner had set aside for nineteen days. Update STATUS in the same
session as the decision, not the next.
