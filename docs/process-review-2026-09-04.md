# Process review — Supply Chain Innovation Observatory

Third review, covering 2026-09-03 and 09-04. Basis: 11 commits since `1866539`,
2,703 lines added and 184 removed across 29 files, the live database, the
rendered artifacts, and the project's own documents.

**Read the limitation first.**

---

## Limitation, stated up front

**This review is not independent.** It is written by the assistant that produced
all 11 commits it assesses — the same disqualification the 2026-09-03 review
carried, and for the same reason it should not borrow authority from the format.
The 2026-08-31 review remains the only independent one.

Where this is likely to be wrong: it will overrate work it chose to do, miss
what it never considered, and describe its own errors in the vocabulary of the
commit messages that made them. The numbers are reproducible; the judgements
about what mattered are the least trustworthy part.

---

## Verdict

**The largest gap the marketing plan named is closed, and a licence problem
nobody had checked was found and acted on.** Tests 687 → 746. Four new modules:
`findings.py`, `cards.py`, `brief.py`, `sheet.py`. The corpus shrank for the
first time — 2,324 → 2,311 observations, eleven sources to ten, nine evidence
families to eight.

The working method held where it has been strongest: **every artifact was
checked as an artifact.** The overlap-guard fix was verified end to end against
`data/manual` and at the 255/256/257/512 boundary, not only against tests. The
findings were read off the rendered HTML. The brief and the sheet were opened
and looked at, which is how two defects were found that no test would have
caught.

**Twice, measurement stopped work rather than justifying it.** Scopus was
measured against OpenAlex before a collector was written for it, and the
collector was then not written at all, because the response shape cannot be
verified without a key.

**The session's worst error was not in the pipeline.** A `git add -A` published
the owner's marketing and distribution plan — CAPS pitch, targets, time budget,
candid remarks about communications staff — to a public repository. The owner
elected to leave it up. The error stands.

---

## Risk register, rechecked

| # | Risk | Status |
|---|---|---|
| 1–6 | (closed in the 09-03 review) | Closed. Not rechecked here |
| 7 | An export of exactly 256 records is ingested | **Closed.** Verified end to end: 255, 256, 257 and 512 all refused through `read_exports`. The documented 5% tolerance now exists, on the owner's call |
| 8 | Next quarter's export cycle drops a slice | Open. `missing_exports` still cannot detect a file that is present but stale |
| 9 | 2026 annual wrong at W53 | Open. Unchanged |
| 10 | Lexicon precision decays | **Open and further from settled.** No independent coder; the corpus changed again when ABI/INFORM was removed, so the 70% figure is now two corpus changes away from what is published |
| 11 | An API changes shape | Open. `search.patentsview.org` still has no DNS record |
| 12 | `quarter.build_context` unmaintainable | **Worse.** `quarter.py` 795 → 826 lines, and `render_quarter` gained three more things it writes |

**New risks:**

- **A. The Scopus position is inconsistent with the ABI/INFORM decision.**
  ABI/INFORM was retired because its licence forbids mining. The same library
  answer says the Elsevier API is the sanctioned route and "any other text &
  data mining activity would violate the Elsevier terms" — and 421 Scopus
  observations, from hand-run exports, remain in the corpus and in published
  reports. The distinction being relied on (a person clicks export; only the
  API clause names robots) is a reading, not an answer. It is question 1 in the
  drafted reply and it should be answered before the next report is published.
- **B. Diffusion now rests on two sources.** Trade press was the only
  non-government, non-academic voice. With it gone, the diffusion stage is SEC
  filings and Hacker News. The project's central question is about diffusion.
- **C. Post cards depend on a font CI does not have.** `FontsMissing` is raised
  rather than falling back, which is right, but `render_quarter` catches it and
  prints a line. A quarter can therefore ship with no cards and one line of
  output saying so.
- **D. The findings layer was built before the discovery meant to shape it.**
  The marketing plan's §5 says to run think-aloud sessions "before the findings
  layer is final, using the Q2 report as the stimulus". The layer was built
  first, on the owner's instruction. It is now the stimulus, which is defensible
  — but the plan's ordering was inverted and the override file is what has to
  absorb that.
- **E. `patentsview` is declared as a source and has never existed.** It sits in
  `EVIDENCE_FAMILIES` and was, until this session, printed in Appendix B as a
  source feeding the experiment stage. This review noticed it while fixing the
  retired-source case and did not act on it or raise it until now.

---

## What went right, and why

**Artifacts were checked as artifacts, and it paid three times.** The Scopus
blind spot in the overlap guard was found by running the guard over the real
`data/manual` directory rather than reading its code: every one of twelve Scopus
exports has a blank identifier, `if ids` was false every time, and the guard had
never once applied to the largest manual source. The brief's mid-word
truncation and the sheet's chopped term lines were both found by opening the
files. None of the three would have failed a test.

**Measurement preceded building, and twice prevented it.** Scopus was compared
with OpenAlex before any collector was written — 159 matched documents OpenAlex
does not have, which contradicts the OpenAlex docstring's claim to have replaced
it. And the collector was then deferred rather than written against a guessed
response shape, which is the mistake that produced the OpenAlex abstract-coverage
failure the 08-31 review named.

**The retirement was enforced in four places rather than trusted.** Registry
field with the reversal condition, export sheet that says the source exists and
why it is absent, importer that refuses the files, and an appendix that no
longer claims the coverage. A fifth — the CLI's own `--help`, which was still
telling people to export from ABI/INFORM — was found only when the README was
reviewed, two commits later.

**Tests were written first throughout, and caught two real bugs in new code:**
a character-class expansion that did not handle `[- ]`, and a readability check
that skipped plain patterns because they expand to themselves.

---

## What went wrong, and the shape of it

**1. `git add -A` published a document nobody asked to publish.** The marketing
plan was untracked; staging everything committed it, and it was pushed. Nothing
in the session's process looked at what was being staged. This is the same
family as the project's other failures — an action whose scope was assumed
rather than checked — and it is the first one that reached the public internet.

**2. The top of the pick-up list was an action the licence forbade, and it was
recommended twice** before the library answered. That was not knowable at the
time. What is knowable, and was not recorded anywhere until 2026-09-03, is that
**no source in this project had a licence check on file.** Four sources sat
behind institutional authentication and the question had never been asked.

**3. A date was wrong in the handover document.** A STATUS entry was dated
2026-09-04 while it was still 09-03; corrected in the next commit. Small, and in
exactly the document a successor is told to trust.

**4. Guards were added after looking, not designed in.** The brief would have
drawn text past the bottom of the page silently — reportlab does not complain —
and `BriefOverflow` exists because the page was opened and the white space
looked wrong. The same for the sheet's one-page guard. Both are now correct;
neither was anticipated.

**5. Two findings can name the same technology.** 2026-Q2 publishes autonomous
trucking in finding 1 and again in finding 4. Nothing tests for it and nothing
prevents it.

---

## Project management

**The owner was asked six times and answered six times**, on: the overlap
guard's tolerance, what the post cards should show, whether to add Pillow, what
the technologies sheet should carry beside each entry, what to do with the
ABI/INFORM records, and whether to build the Scopus collector blind. Two of the
six reversed the assistant's initial framing. The division of labour the
previous reviews identified held again: the owner decides what things mean and
what may be published, not how they are built.

**The licence answer arrived from outside and changed the project's shape more
than any technical work in the session did.** It closed four questions, retired
a source, opened one, and produced the first standing rule this project has that
did not come from shipping a wrong number.

**The public repository is now a real surface.** Eight commits were pushed in
one day, including a README rewrite and a licensing section. The marketing-plan
incident is the visible half of that; the general point is that "commit and
push" is now an outward-facing action and was treated as a routine one.

---

## What to do next, ranked

1. **Send the reply to the library** (`correspondence/`). Question 1 decides
   whether 421 Scopus observations may stay in a published report, which is the
   largest unresolved thing in the project.
2. **The Elsevier key, then the Scopus collector** — capture a real response as
   the fixture, and measure abstract coverage before adopting.
3. **A coder who did not write the patterns.** Unchanged from the last two
   reviews, and now three corpus versions stale.
4. **The think-aloud sessions** the marketing plan schedules for October. The
   findings layer that was built ahead of them is the stimulus.
5. **Split `quarter.build_context`.** Risk 12 has been open across three reviews
   and grew in each.
6. **Decide `patentsview`:** build it or delete the declaration.

---

## What this review did not examine

- **No network verification of any collector.** Third review running.
- **No arithmetic verification of a published figure.** Counts were compared
  between database, rendered page and PDF; none was recomputed from raw.
- **The findings rules were not evaluated for whether they are the right
  findings.** They were checked for truth against the data, not for usefulness
  to a reader. That is what the think-aloud sessions are for.
- **The reviewer wrote the code.** See the top of this document.
