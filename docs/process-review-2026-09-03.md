# Process review — Supply Chain Innovation Observatory

Second review, covering 2026-09-01 to 09-03. Basis: 29 commits since
`7359a3a`, 2,185 lines added across 32 files, the live database, and the
project's own documents. Every claim below was checked against the code or the
data rather than against a commit message.

**Read the limitation first, because it changes how to read everything else.**

---

## Limitation, stated up front

**This review is not independent.** The 2026-08-31 review was written by a
reviewer with no prior contact with the project and no stake in it. This one is
written by the assistant that produced all 29 commits it assesses. It is a
self-assessment wearing the same format, and the format should not lend it
authority it has not earned.

Where it is likely to be wrong: it will over-count the value of work it chose
to do, under-count what it did not think of, and describe its own errors in the
vocabulary it already used in the commit messages. The previous review's
Section 7 said the same thing in reverse — that an assistant writing its own
history has no incentive to record when the owner asked for something confused.

The parts most worth trusting are the numbers, which are reproducible. The
parts least worth trusting are the judgements about what mattered.

---

## Verdict

**Six of the twelve risks in the previous register are closed, verified by
behaviour rather than by grep.** Tests went 627 → 687; the source tree grew
6,767 → 8,226 lines. A linter, a pre-commit hook and CI now exist where nothing
ran before.

The working method was better than the previous period's: **every substantive
change this session was measured before it shipped**, and four candidate
additions were measured and *not* built. That is the project's own stated
method finally applied consistently.

The assistant's error rate remains the problem, and its shape has not changed.
Almost none of the errors were crashes. They were claims made without checking
— a stale report described without opening it, a source declared working on the
strength of an HTTP status, a test described as pinned to live data that could
not fail. **One of those was shipped in the same commit that criticised that
exact defect.**

---

## Risk register, rechecked

| # | Risk | Status |
|---|---|---|
| 1 | Every published z-score inflated by ramp-up | **Closed.** `compute_quarter` passes `collected`; boundary test pins `MIN_HISTORY_QUARTERS` at 2 and 4 |
| 2 | Disk loss destroys the licensed corpus | **Closed.** Backup verified byte-for-byte: 58 files, DB SHA-256 identical |
| 3 | A collector fails and nobody notices | **Closed.** `source_attempts` appends; non-200 reaches `raw_fetch`; `empty` status added |
| 4 | A future-period report is shared | **Closed.** `PeriodNotStarted`; `counting_bounds` clamps to today; three future dashboards deleted |
| 5 | Chart dots key the wrong technologies | **Closed.** Verified by the review's own mutation: reversing the legend order now fails two tests |
| 6 | STATUS misleads a successor | **Closed.** §2 generated from the database, checked by a test that fails on drift in either direction |
| 7 | An export of exactly 256 records is ingested | **OPEN, and still exactly as described.** `256/0.95*0.95 != 256` remains true, so the guard still cannot fire at 256 or 512 |
| 8 | Next quarter's export cycle drops a slice | **Improved, not closed.** `missing_exports` reports absences; it cannot detect a file that is present but stale |
| 9 | 2026 annual wrong at W53 | Open. Unchanged |
| 10 | Lexicon precision decays | **Actively managed.** v9 → v10, two technologies retired, two tightened, audited twice |
| 11 | An API changes shape | Open, and evidenced: `search.patentsview.org` now has no DNS record |
| 12 | `quarter.build_context` unmaintainable | Open. It grew this session |

**New risks not in the previous register:**

- **Precision is unsettled, not improved.** The 70% figure was measured at
  lexicon v9 against a corpus that no longer exists. Nothing currently states
  the precision of what is published.
- **EDGAR cannot be audited at all.** 129 observations, the strongest diffusion
  leg, and its precision is unmeasurable without fetching filings.
- **Trade press has been reading subject headings, not abstracts**, since the
  first export. Fixed for future exports; the existing ones need re-running.
- **Four coding passes, all the same model.** Coders A, B, D and the CRA
  validation all come from one source. The independence gap has widened, not
  closed.

---

## What went right, and why

**Measurement before building became consistent.** EDGAR was measured before
terms were added (4–5×, not the 36× the raw counts suggested). CRA was tested
against 120 coded items before any spec change and rejected at AUC 0.70. Reddit
and vendor feeds were probed and neither was built. GDELT was probed, looked
good, and was then ruled out by the owner's operating experience. Four
candidates, four measurements, one build.

**Guards written earlier caught later mistakes, repeatedly.** This is the
strongest evidence that the work compounds:

- `test_every_query_term_can_survive_the_gate`, written Monday morning, failed
  Tuesday when retiring `nearshoring_analytics` orphaned an EDGAR query term
  that would have fetched six filings a quarter for a technology that no longer
  existed.
- The generated-STATUS test caught the by-source row drifting **twice**.
- `INTENDED_TECHNOLOGY`, written by an earlier session, refused a term edit
  until the mapping was updated.
- The `empty` source status, added Monday, was vindicated three times in one
  afternoon: `old.reddit.com` returns 200 with an HTML wall, and GDELT returned
  200 with a non-JSON body.

**Rejections carry reversal conditions.** CRA, the Journal of Commerce, two
EDGAR terms, Reddit and GDELT are all recorded with the specific fact that
would change the answer. That is the habit the previous review praised, applied
without being asked.

**The owner's corrections beat the assistant's reasoning, again.** He found the
audit truncation by coding the sheet and asking why "procurement" was not in a
document tagged for procurement — it was at character 1693, outside a 600-
character window nobody had noticed. He ruled GDELT out of the weekly run on
experience the assistant had no access to. He caught that a Journal of Commerce
diagnosis was wrong twice running.

---

## What went wrong, and the shape of it

**The recurring failure is asserting without checking.** Six instances in three
days:

1. A stale report was described as "the pre-masthead version" without opening
   it. It was byte-identical to the current one.
2. The Journal of Commerce was predicted not to resolve. It returns 133,243
   records.
3. Then predicted to lack recent coverage. It has 4,487 records in 2020–2026.
4. `old.reddit.com` was reported as "HTTP 200 ok" and a working route. The body
   is a 352KB "Welcome to Reddit" wall with zero entries.
5. The agentic patterns were reported as scoring "5 of 5". True of the regexes,
   tested directly, without the context gate, at a width that had not shipped.
6. A test was described in its own docstring as "pinned against the live export
   directory". `conftest` points `MANUAL_DIR` at an empty temporary directory
   for every test, so it saw nothing, reported everything missing, and **could
   not have failed**.

**Number 6 is the sharpest.** It was committed in the same session that fixed
the review's finding about assertions that cannot fail, and it was described as
the opposite of what it was. The defect the previous review named twice was
reproduced by the person writing about it.

**A second pattern: fixes that were not verified end to end.** The agentic
proximity window was widened to 80 in the comment and the green patterns, and
left at 40 in the agentic patterns themselves. It took a targeted re-audit —
sampling what had been *dropped*, not what survived — to find it. Twelve true
positives had been discarded.

**The remedy that worked, both times, was sampling the other side.** Precision
on what survives always improves after a tightening; only the discarded set
says what it cost.

---

## Project management

**The owner's engagement is the strongest asset and is being used well.** Ten
decisions were put to him this session and he answered all ten, several times
reversing the assistant's recommendation on evidence it did not have. The
division of labour the previous review identified — he reviews outputs and
definitions, not mechanism — held.

**The manual export path remains the least-tested and most error-prone.**
Every error that has reached the owner has come through it, and this session
added two more findings there: sixteen of twenty 2026-Q3 exports were never run,
and every ABI/INFORM export ever made lacked abstracts. Both were invisible in
the pipeline's own numbers.

**Documentation drift is now mechanically prevented for the numbers and not for
the prose.** STATUS §2 cannot go stale. STATUS §5 still can, and did: it claimed
the GDELT implementation was written when no such file has ever existed in git
history.

---

## What to do next, ranked

1. **Fix risk 7.** The 256 hole is a four-character change and has now survived
   two reviews.
2. **Re-export 2026-Q3 ABI/INFORM with abstracts.** Sheet is written; it also
   corrects the lexicon version and the window.
3. **A coder who did not write the patterns.** Four passes, one model. This is
   the only thing that will settle what precision actually is.
4. **PatentsView**, once the key arrives — but check the endpoint first, since
   the host the plan names no longer resolves.
5. **Retire `discover.py`** or justify it. The rising-terms loop has still
   contributed nothing, and a second discovery instrument has now been specced
   beside it.

---

## What this review did not examine

- **No network verification of collector queries.** Same gap as last time.
- **No arithmetic verification of any published figure.** Counts were compared
  between database and document; none was recomputed from raw.
- **The 29 commits were not read as a whole.** Claims were spot-checked against
  code and data, which is not the same as reading the diff.
- **Nothing was assessed for domain validity.** Whether the 48 technologies are
  the right ones remains the owner's judgement.
- **The reviewer wrote the code.** See the top of this document.
