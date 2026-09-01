# Process review — Supply Chain Innovation Observatory

Independent assessment of software engineering practice and project management.
2026-08-31. The reviewer had no prior contact with this project and no stake in
it. Basis: 153 commits, 5,941 lines of source, 6,990 lines of tests, the live
SQLite store, and the project's own documents. Findings quoted from delegated
audits were re-verified directly; where verification disagreed with the audit,
the verified result is what appears here.

---

## Verdict

This is a better-run project than most commercial data pipelines I review, and
its strength is unusual: it decides things by measuring them rather than by
arguing, and it writes down what the measurement said. The test suite is
genuinely strong — a 45-mutation sample killed 71%, well above the 40–60% a
hand-written suite normally manages, and every one of its 961 assertions
actually executes. The precision audit is real work; I recomputed every
statistic from the raw coding sheets and they are correct. But the project has
a consistent failure mode that its own prose conceals: **it builds a guard,
documents the guard carefully, and does not connect it.** There are now at
least five of these, and one is serious — the quarterly z-scores that the
current report is built on violate the project's own founding rule, because the
parameter that enforces it is never passed. Alongside that, the project has no
durable record of its own failures, and its handover document misstates the
corpus by 15%. The engineering is sound. The wiring between the engineering and
the claims made about it is not, and that gap is where every remaining defect
lives.

---

## 1. What is genuinely good

**Measure before building.** `3feb11c` rejected SBIR after collecting 500 awards
and matching zero. `d8c3958` reversed its own recommendation to replace Scopus
with OpenAlex after measuring abstract coverage — 99% against 49% — on the same
twelve journals. `ccac3ac` measured swapping CPC class `G06K7` for `G06K19/07`
and recorded that it changes nothing. `3f590e4` records six sources checked and
*not* adopted, each with the condition that would reverse the rejection. Most
teams argue about these questions; this one runs them.

**Willingness to delete.** `5b1c4f4` dropped momentum and deleted 28 tests
rather than adapting them. `90607c8` retired `operations_research`, giving up
546 observations and 20% of the corpus. Sunk cost has little grip here.

**The test suite is good, and I want to be unambiguous about it** because the
criticisms below are easy to over-weight. A 45-mutation sample killed 32 (71%),
against the 40–60% a hand-written suite normally manages. Every one of the 961
`assert` statements executes at least once under a line tracer — no unreachable
assertions, no zero-iteration assert loops, so an entire category of test
pathology is absent. There are **zero** mock-call assertions: no
`assert_called`, no `MagicMock`. `tests/test_run.py` uses hand-written fakes
implementing the real `BaseCollector` interface, so the
fetch→parse→match→store→render path runs end to end.
`tests/test_guardrails.py` meta-tests its own detector before testing its
verdict. Roughly 85% of the suite is strong, 12% weak, under 2% vacuous.

**The commit log is a real decision record**, and honest about authorship of
mistakes. `ef451bd` contains the sentence "I flagged this last round and claimed
a later `--rebuild` would fold them in; it did not." Few engineering logs do.

**Security hygiene.** `.env` was never committed, no token appears in history,
and `tests/test_collector_github.py` asserts the committed GitHub fixture holds
no `ghp_`, `github_pat_`, `Authorization` or `Bearer` string.

---

## 2. The pattern: guards that were built, documented, and never connected

Each item below is a mechanism the project designed deliberately, described
accurately in prose, and then failed to wire up. Because the prose is accurate
about the *intent*, reading the code confirms the narrative and the defect stays
invisible.

### 2.1 The quarterly z-score violates the project's oldest rule — serious

`observatory/metrics.py:207` defines `quarterly_signal(conn, tech_id, signal,
quarters, collected=None)`. Its docstring: *"A quarter nobody collected is
absent rather than zero — the project's oldest rule. Folding a hole into a zero
invents a decline."* The `collected` parameter implements exactly that.

**The only production caller — `compute_quarter` at metrics.py:256 — never
passes it.** I reproduced the consequence against the live database:

```
2026-Q2 window = ['2025-Q3', '2025-Q4', '2026-Q1', '2026-Q2']
  2025-Q3 weeks_run = 5 of 13     <- collection began at 2025-W34
  research_papers, ungated = [32.0, 69.0, 96.0, 116.0]  -> z = +1.199
  research_papers, gated   = [None, None, 96.0, 116.0]  -> z = None
```

2025-Q3 was 38% collected and enters the series as a full quarter. The apparent
trend 32→69→96→116 is substantially the ramp-up of collection itself, and it
yields a confident positive z-score. **Every trailing-four-quarter z-score in
every report published so far is inflated by this**, most for exactly the
fast-rising technologies the tool exists to surface.

Worse, it disables a second guard. `MIN_HISTORY_QUARTERS = 3` (metrics.py:165)
is enforced via `observed()` (metrics.py:36), which counts non-`None` entries.
Since nothing is ever `None`, `observed()` is always 4 and the history gate has
**never fired in the life of the project**. A test exists
(`tests/test_metrics_quarter.py:57`) but never probes the boundary: mutating
`MIN_HISTORY_QUARTERS` from 3 to 2 leaves the suite green. This is not a typo —
it is a rule the project states in STATUS §4, implements in a parameter,
documents in a docstring, and does not connect.

### 2.2 The anti-silent-thinning apparatus is itself silent

Commit `e9959c4` (yesterday): *"The count of labels not drawn is printed under
the chart: silent thinning is this project's oldest failure mode, and a chart
missing three labels looks exactly like one that has them all."* `labels_dropped`
is created at `quarter.py:559`, populated at `:588` and `:618`, and placed in the
context at `:629` — and `grep -rn labels_dropped observatory/templates/` returns
nothing. **It is never rendered.** The count is also wrong: `charts.py:171`
counts drawn labels as `svg.count('font-size="10"')`, but the diagonal's captions
use the same size, so the figure is short by two and can go negative — a
six-point chart with all six labels drawn reports `-2`, which `if missed:` at
`quarter.py:143` treats as truthy. The test that should catch this
(`test_quarter.py:826`) asserts only that `"labels_dropped" in context`.

### 2.3 The overlapping-export guard has no tolerance and a hole in it

`manual.py:328` declares `UNION_LIMIT = 0.95` with a three-line comment
explaining the 5% tolerance. Line 357 reads
`if len(union) <= len(largest) / UNION_LIMIT * UNION_LIMIT and len(union) <=
len(largest):`. Since `n / 0.95 * 0.95` returns `n` for most integers, the first
clause duplicates the second and the documented tolerance does not exist —
mutating `0.95` to `1.5` leaves the suite green. And since `union ⊇ largest`
always, the guard can only fire on exact equality. For the 59 sizes under 3,000
where the float round-trip lands *below* `n` (every power of two to 512, plus
245, 490, 493, …) it cannot fire even then. Confirmed end to end against the
real `read_exports`: at largest = 255 an exactly-duplicated set is refused, at
**256 it is accepted**, at 257 refused. The historical incident (52 records) is
still caught; a future one of 256 is not.

### 2.4 The substance index is a three-signal model wearing five-signal clothes

`metrics.py:69-71` declares `HARD_SIGNALS` with five members and `SOFT_SIGNALS`
with two. `weekly_signals` has only ever held eight signal names, and `patents`,
`gh_commits` and `media_articles` are not among them. The index reduces to
three-against-one, published under the full model's name. There is an honest
allowlist test (`tests/test_run.py:383-389`) that stops this being a typo — but
nothing stops the scores being published as though the whole model ran.

### 2.5 `source_runs` exists for the dashboard and the dashboard does not use it

`store.py:23-25` explains why the table was created: *"Replaying an old week
needs to know how that week went, not how the last one did."*
`render.dashboard_context:96` queries the `sources` table instead, which holds
only the latest state, so every re-rendered archived week stamps today's status
onto a page headed with an old week.

---

## 3. The project cannot see its own failures

STATUS §2 reports "**Source runs** 318 recorded, **none has ever failed**" as
evidence of reliability. It is evidence of nothing, because none of the three
mechanisms that would record a failure does so.

- `store.set_source_status` (`store.py:339-345`) writes `source_runs` with
  `ON CONFLICT (source, week) DO UPDATE` on a primary key of `(source, week)`, so
  a week that failed and was later refetched has its failure row overwritten. The
  table holds 427 rows, all `ok`, and after any successful retry it is
  structurally incapable of holding anything else.
- `data/run_log.jsonl` records `ok_sources` and nothing else — not one failure
  field across 1,823 lines. Its first line reads `"ok_sources": ["hn"]` for
  2026-W33 where later lines for the same week read `["arxiv",
  "federalregister", "hn"]`: something failed, and the log cannot say what.
- `raw_fetch`, described in STATUS §8 as "an append-only log of fetch
  **attempts**", has `http_status = 200` on all 3,114 rows, because a failed
  fetch raises before the insert. It is a log of successes.

The isolation code itself is correct (`run.py:48-52`, `156-159`); the defect is
that the only durable channel is stderr, which reaches `data/cron.log`,
currently seven lines long. A project whose epistemology rests on separating "we
looked and found nothing" from "we did not look" has discarded the record that
makes the distinction possible.

**A related hole:** `run.fetch_week:48` records `ok` if `fetch_raw` completes
without raising, regardless of what it yielded, and `normalize.compute_signals`
then writes a hard `0.0`. An API that begins returning empty-but-valid 200s is
reported as a real zero across every signal with the source marked healthy.
Four collectors warn about the opposite condition; nothing checks the floor.

---

## 4. Other live defects

**Reports are generated for periods that have not happened.** Scopus `PUBYEAR =
2026` exports carry issue dates to 2026-12-01, so the store holds 62
observations and 346 retrieved documents dated after 2026-09-27, and `output/`
contains `dashboard-2026-W40/W44/W49.html`. Running
`quarter.build_context(conn, "2026-Q4", watchlist)` today returns 12
technologies, every one at 100% research concentration, because Scopus is the
only source that can see the future; the 2026 annual total of 1,896 includes 62
rows from a quarter that has not begun. Worse, `run.main:401` iterates *every*
week holding an observation and `_score_and_render` defaults `latest=True`, so
any `--import-manual` run leaves `output/latest.html` pointing at 2026-W49.
STATUS §4g records that the broken weekly ranking was "spotted by the owner on
2026-W49" without anyone asking why a W49 dashboard existed.

**A commit shipped a call to a function that did not exist.** At `9ccf2b2` and
`74da8e2`, `discover.py:137` calls `_already_covered`, which `git grep` confirms
is defined nowhere in the package or the suite; any call to `detect_rising`
reaching a qualifying term raises `NameError`. It was fixed by `4e4b773`, whose
message credits a code review, not the tests — and a thirty-second AST parse
finds it as an undefined name. Relatedly, **there is no automated quality gate
at all**: no CI (the repo is on GitHub; nothing runs there), no pre-commit, no
linter, no type checker, no coverage tooling. `pyproject.toml`'s `dev` extra is
`pytest>=8.0` and nothing else.

**The newest feature's only guard is a dead assertion.**
`tests/test_quarter.py:851`:

```python
assert [row["name"] for row in context["stage_legend"]] == \
challenge if False else [point.label.split(" — ")[0] for point in context["stage_points"]]
```

`==` binds tighter than the conditional, so the AST is
`IfExp(test=Constant(False), …)` and Python always takes the `orelse` branch —
a bare list comprehension. The assertion reduces to `assert <non-empty list>`;
the comparison never runs and the undefined name `challenge` is never evaluated.
This is the sole test guarding the number↔name alignment of the numbered chart
dots introduced in `c7de9e4`, the HEAD commit, today. Two mutations — replacing
the legend's `name` key with `"WRONG"`, and reversing the legend order —
**both survive**. The chart can key entirely the wrong technologies and nothing
fails.

**The network path is untested by design.** `collectors/base.py:1-6`: "Tests only
ever exercise `parse`, against saved fixtures." Every query-construction bug in
this history was found by running live — the arXiv `+TO+` encoding and the stale
CBP slug (`916876e`), USAspending's `date_type` (`79a477d`), NSF's `startDate`
trap (`3feb11c`), Scopus's rejection of `PUBDATETXT` (`16e70a5`). A defensible
trade, but a known gap rather than a design virtue. Two smaller items in the same
family: `quarter.period_bounds` (calendar) and `supplemental.period_bounds` (ISO
weeks) disagree by three days at each quarter edge, so `--export-queries 2026-Q1`
asks a human for a window the 2026-Q1 report does not count; and the quarterly
evidence page ships with an empty `<title>`, because `evidence.html.j2:6` reads
`{{ week }}` and the quarterly context omits it.

---

## 5. Documentation drift

STATUS.md is the handover document and its headline table does not match the
database.

| STATUS §2 | Reality |
|---|---|
| 2,130 observations, 54 weeks, 2025-W34 → 2026-W35 | **2,455**, **76** weeks, **2024-W12 → 2026-W49** |
| scopus 830 / arxiv 705 / lens 85 | 434 / 569 / 64 |
| (openalex, nsf absent) | openalex **253**, nsf **49** |
| 318 source runs | 427 |

The by-source row sums to 2,711 against its own stated 2,130 and omits the two
sources that §4e and §4f of the same document describe adding. Two consecutive
rows both labelled "Evidence families" state "all 8 populated" and "7 of 8 (no
trade press yet)". §4c says lens is 64, contradicting §2. §7 lists as item 1
"Backfill USAspending", which §5 reports as done, and has two items numbered 3.
The header reads "Last updated after commit `2ebfc58`" — 61 commits ago. Only
the test count (623) and the lexicon state survive checking; `51a64c3` claimed
"Every number in it was verified against the database", and nothing has
re-verified it since.

Elsewhere: **"six sources" is wrong in nine places**, including
`quarter.html.j2:346`, which puts it on the published report — `run.COLLECTORS`
registers eight. **STATUS §4d** claims the rate denominator is "counted from raw
… **rather than stored**, so it cannot drift"; `quarter.py:470-475` says
"Counted at ingest and **stored** rather than recomputed." **README.md**
(untouched since `2ebfc58`) sends a new operator to `data/manual/<source>/` when
the real layout is `data/manual/<quarter>/`, says Scopus caps at 2,000 where
`sources.yaml:169` says 1,000, and describes an `evidence.html` link the
dashboard template does not contain.

**In the audit itself:** `0f636a2` and the audit document both state "of
thirteen disagreements, nine resolved against coder A and **none** against coder
B." Recomputing from the CSVs: nine against A and **four** against B (rows 35,
38, 43, 44). The same document elsewhere says those four were "left standing
rather than adjudicated" — i.e. resolved in coder A's favour, by the party who
wrote coder A's patterns. The leniency finding survives at 9–4; "none" does not.

---

## 6. Project management

**Traceability is the project's best management asset.** Every significant call
has a commit stating the alternatives, the measurement and the reason. A
successor can reconstruct not just what was decided but what was rejected.

**Scope was controlled on the domain and not on the machinery.** The owner's
three rejections in `6bf0700` kept the corpus from doubling with things that are
fields rather than technologies. The engineering side is looser: the weekly
rising-terms discovery loop took roughly seven commits plus `lexicon.py` (16KB)
and 38 tests, and carries several of the ugliest bugs in the history.
`lexicon/requests/` contains **one** file. Of 51 watchlist entries, 42 came from
the original spec, 8 from a one-off arXiv backlog sweep, 1 from the precision
audit — **not one from the loop built to feed it**, and it still occupies a slot
on the weekly page. Separately, `render.py` is roughly 40% dead code, residue
from the dashboard `34e4a68` replaced.

**Errors that reached the owner** — three, all in the human-in-the-loop export
path, the one path with no test:

1. `b76f442` — the ABI/INFORM query, printed beside two others, was pasted into
   Lens.org and returned "a clean and entirely believable zero".
2. `590f057` — he hit Scopus's 1,000-record cap by hand; code and README said
   2,000, taken from documentation. The README still says 2,000.
3. `8f7635b`/`9f35d29` — he exported ProQuest's marked-items list four times as
   it accumulated. The resulting overlap guard then refused legitimate batched
   exports and had to be rewritten, and two further commits (`94d053c`,
   `0b55f40`) were built on counts the accumulation had corrupted. `8cb5dd6`:
   "Both of the fixes built on them were solving a problem that did not exist."

**Reproducibility: good for code, poor for data.** The repository is on GitHub
and in sync, but `.gitignore` excludes `data/` and `output/`, so 900MB of raw
responses, 6.7MB of manual exports and the database exist on one iMac and
nowhere else. The raw archive is refetchable; the licensed exports are not —
they need ASU subscriptions, and the marked-items incident proves re-running an
export does not reliably reproduce it. Losing that disk costs roughly 500
observations, the whole patents and trade-press families, and the ability to
reproduce the precision audit. Nothing in STATUS mentions a backup.

Could a new person pick this up? For the code, yes — the commit log and STATUS
§4 and §8 are an unusually good briefing, and 623 tests run in 5.6 seconds. For
the data, only if they have the machine.

---

## 7. The owner's engagement

Kevin's participation is materially better than a domain expert's usually is.

**What he caught that the assistant missed.** `90607c8` — reading the audit
sample, he noticed `operations_research` was being kept while
machine-learning-for-operations had been rejected on identical reasoning. That
cost 546 observations and 20% of the corpus to fix, and the assistant had drawn,
coded and written up the sample without seeing it. **This is the single most
valuable contribution by either party.** `d353cd9` — two rulings on one day,
both reversing work shipped hours earlier: that a technology drawing 88% of its
evidence from research is *telling you it is at the research stage*, so the gate
was deleting the finding along with the risk; and that the 0-100 index was a
percentile, and "a percentile cannot move", which is fatal in a tool built to
detect movement. `f08817c` — he ruled out the broad `G06Q10/08` CPC codes, which
would have labelled 135 of 185 patents as warehouse management systems.
`5e000a0` — he spotted that seven of the top eight weekly movers had no
documents in the week they were named for.

These are conceptual corrections a measurement specialist makes and a programmer
does not. The division of labour works precisely because he does not pretend to
review code: he reviews outputs and definitions and leaves mechanism alone.

**Where he was too permissive.** He approved the rising-terms subsystem and has
never used it; it should have died when its first real output produced eleven
junk phrases out of twenty-five (`e7ec848`). He accepted STATUS.md as the
handover artifact without checking its headline table — the one document he
*can* fully audit without reading code, because every number in it is in his
domain. And he accepted 57 commits on day one; nobody reviews 57 commits in a
day, and the two Critical defects `2cd771a` records as surfacing "only in the
whole-branch review" are what that looks like.

**Where he was slow or asked for the wrong thing.** The manual export procedure
was learned by making mistakes on live exports rather than by doing one small
export end to end first; four overlapping files and two wasted commits came out
of that. And he approves same-day: `36981da` shipped in the morning was reversed
by `d353cd9` in the afternoon. Both reversals were his and both were right,
which suggests he could catch these *before* they ship by reviewing the proposal
rather than the result.

**The gap** is that nothing reviews the assistant's bookkeeping — STATUS's table,
the failure logging, the README, whether a guard is connected. Those fall between
"code, which Kevin does not read" and "findings, which he does".

---

## 8. The assistant's performance

**Volume.** Of the 95 commits using conventional prefixes, 34 are `fix:` (36%),
and the later 58 unprefixed commits contain many more corrections. Roughly one
commit in three repairs a defect the assistant introduced, usually within hours.
Some of that is a reporting artifact — this project commits fixes separately and
describes them, where most would squash them away — but the volume is real.

**The errors are one species.** Almost none are crashes. They are numbers that
are wrong and look right: an absent source rendered as zero adopters
(`99cecd7`), a stock summed as a flow (`6a730bb`), awards keyed to the wrong
date field (`79a477d`), a Hacker News story counted as an unplaceable federal
award (`bdc7d9d`), a manual denominator sixty-five times too small (`d8c3958`),
Scopus records dated to January 1st (`2ee6163`). Read honestly, STATUS §4's
"rules this project runs on" is a taxonomy of its own assistant's failure modes.

**Verification is done at the wrong layer, repeatedly.** `2e034e0` — a generator
produced "warehouse robot s ics" and 150 other mangled phrases; "the test that
let it through asserted `'warehouse robot' in query`, which the broken string
satisfies." `36981da` — two blocks rendered empty because Jinja autoescaped the
SVG; "the tests had checked the context rather than the report, so they passed."
`91353eb` — a rule measured as one thing and shipped as a stricter one; its own
conclusion: "Measure the rule you intend to ship, not an approximation of it."
`ef451bd` — "deleting `carry_forward` entirely left all 132 tests green."
Section 2 is the mature form of the same fault: verifying that a guard is
*written* and not that it is *called*.

**Claimed-but-unperformed verification.** Once explicitly: `ef451bd` records "I
flagged this last round and claimed a later `--rebuild` would fold them in; it
did not." Structurally, in STATUS: `51a64c3` asserted every number was verified
against the database, and seven are now wrong.

**Are the self-corrections genuine or performative?** Genuine. `36981da`
promised "a test that reads the rendered page"; it exists at
`tests/test_quarter.py:589` and asserts both `"<svg" in page` and `"&lt;svg" not
in page`, the right pair. `c4e9f7f` promised a network-proof guard test verified
by removing the guard, and the test monkeypatches `http.make_session` to raise.
The confessional prose is somewhat performative; the code behind it is not.

**Where the assistant is strongest:** verifying offline against stored raw before
shipping. `32d38d2` projected the GitHub star filter's effect (1,606→669
observations, 13 of 46 clone copies surviving) and matched it exactly. That
discipline should be the template for everything else.

---

## 9. What to do differently — ranked

1. **Pass `collected` to `quarterly_signal`** — one argument at
   `metrics.py:256`. Re-publish and expect the rankings to change; until then no
   z-score in any report should be quoted. Add a test that fails when
   `MIN_HISTORY_QUARTERS` is mutated.
2. **Make failures durable.** An append-only attempts table (or drop the
   `source_runs` upsert), failed sources in `run_log.jsonl`, a `raw_fetch` row on
   non-200, and a floor check so a source returning zero documents is not
   silently `ok`. Then delete "none has ever failed" from STATUS.
3. **Add a linter today** — `ruff check` in a pre-commit hook and a GitHub
   Action. It would have caught the `NameError`, the unused imports and the
   undefined `challenge` in `test_quarter.py:851`.
4. **Fix the dead assertion at `test_quarter.py:851`** and check the chart legend
   alignment by hand once, since nothing ever has.
5. **Refuse to report on a period that has not ended**, quarantine future-dated
   observations, and delete the three future dashboards.
6. **Generate STATUS §2 from the database**, run as a test so it cannot go stale.
7. **Back up `data/`.** The 6.7MB of manual exports are the only genuinely
   irreplaceable asset here.
8. **Connect or delete the orphans:** `labels_dropped`, `UNION_LIMIT`, the
   unwritten `HARD_SIGNALS` members, `source_runs` in the dashboard.
9. **Rewrite or delete the README**, and kill the rising-terms loop.
10. **Buy an hour of a doctoral student** to code the audit sheet independently —
    STATUS §4b already names this as the only move that would settle whether 51%
    is optimistic, since both current coders are the same model.
11. **Stop approving the same day you ask.** Your two sharpest calls (`d353cd9`)
    reversed work shipped hours earlier.

---

## 10. Risk register

| # | Risk | When | Severity |
|---|---|---|---|
| 1 | Every published z-score is inflated by collection ramp-up | **Already true** | **Critical** — §2.1; affects the stage board, SAI and LFI in every report to date |
| 2 | Disk loss destroys the licensed corpus | Any time | **Critical** — `data/` is gitignored and local-only; exports are not reliably reproducible |
| 3 | A collector fails or starts returning empty 200s and nobody notices | **Now** | High — no durable failure record; `cron.log` holds 7 lines |
| 4 | A future-period report is shared | **Now** | High — 2026-Q4 renders today; `report-2026.html` already carries 62 future-dated rows |
| 5 | Chart dots key the wrong technologies | **Now** | High — the only guard is dead; two mutations survive |
| 6 | STATUS misleads a successor or co-author | **Now** | Medium — seven headline figures wrong, two rows self-contradictory |
| 7 | An accumulating export of exactly 256 records is ingested | Next export cycle | Medium — §2.3 |
| 8 | Next quarter's export cycle drops a slice | Oct 2026 | Medium — 18 hand-made files with hand-written sidecars |
| 9 | 2026 annual report is wrong at W53 | Dec 2026 | Medium — Q4's denominator grows while part of its numerator is already stored |
| 10 | Lexicon precision decays | ~Feb 2027 | Medium — 51 hand-written entries at 51%, audited once, changing most weeks |
| 11 | An API changes shape | 3–6 months | Medium — nothing tests `fetch_raw`; three sources have already shifted |
| 12 | `quarter.build_context` becomes unmaintainable | 6 months | Low — 167 lines, 32-key dict, `metrics`↔`quarter` import cycle papered over with function-local imports |

---

## 11. Limitations of this review

- **About five hours.** Roughly 180 of 623 tests were read closely; the rest were
  analysed mechanically (AST scanning, assert-execution tracing, 45 mutations).
- **I ran nothing against the network.** Every collector's query construction is
  unverified by me and by the suite. If a query is silently wrong today, neither
  of us would know.
- **I verified no published figure arithmetically.** I confirmed which contexts
  build and what they contain, not that a number in `output/` is right.
- **I cannot assess domain validity** — whether these are the right 51
  technologies, and whether 51% precision is fit for the claim being made, is
  Kevin's expertise and not mine.
- **The owner's contribution is visible only where the assistant recorded it.** I
  have no conversation transcripts, and an assistant writing its own history has
  no incentive to record the times the owner asked for something confused.
  Section 7 is a systematically generous sample: read it as a floor.
- **Two weeks of history is a thin base for a six-month projection.** The risk
  register beyond three months is inference, not measurement.
- One delegated finding I could not reproduce and have excluded: a claim that the
  *weekly* evidence page renders with empty headers. It does not —
  `output/evidence-2026-W36.html` is correct. Only the quarterly page's `<title>`
  is affected, as noted in §4.
