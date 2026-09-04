# Disclosed Adoption Index — design

2026-09-04. Owner: Kevin Dooley. Implements the direction approved the same
day from `docs/brainstorm-2026-09-04-supply-chain-innovation-5.md`: idea A as
the spine, C designed into the first schema, B and G as companions in the
annual report, E folded in as one section, D held, F only if CAPS wants it.
Plus the owner's addition: the categories and lexicon are to be re-examined
against the new source, with the existing lexicon as the baseline and changes
made only on measurement.

"Disclosed Adoption Index" is a working name. The umbrella project remains
the Supply Chain Innovation Observatory.

This spec is untracked until the owner has reviewed it. The repository is
public.

---

## 1. What this is

A recurring, evidence-based ranking of companies by the supply chain
technology they attest to using in their own SEC filings, with every score
traceable to a quoted sentence in a filing. The unit of analysis moves from
the technology to the company. Technology-level adoption is a view over the
same data: the share of filers in a sector that claim to use a technology.

It answers, for the three audiences:

- Professionals: which companies are ahead, and where does mine stand.
- Researchers: a firm-year panel of disclosed technology adoption, public
  data, published method, citable.
- Students: named companies doing named things, with the sentence that says
  so.

It replaces the count-of-mentions instrument as the centre of the quarterly
and annual report. The count-based report keeps running as an instrument page
until the owner retires it; the two are never summed.

## 2. What was measured before writing this

All on 2026-09-04, all keyless, all against live endpoints.

| Question | Answer |
|---|---|
| Is the corpus large? | 10-K filings in the twelve months to 2026-09-04: about 6,300 contain the phrase "our business", a proxy for the total; 4,055 mention "artificial intelligence", 520 "robotics", 33 "digital twin", 13 "autonomous mobile robots" |
| Can the universe be built by industry? | Yes. `data.sec.gov/submissions/CIK##########.json` carries `sic` and `sicDescription` and the filing list with primary document names. The quarterly Financial Statement Data Sets (`2026q2.zip`, 60 MB) also carry SIC per filer |
| Does full-text search filter by industry? | No. A `sics` parameter is accepted and ignored: same total, hits from other industries. The universe must be built outside the search |
| How big is one filing? | Walmart's FY2026 10-K: 2.3 MB of HTML, about 56,000 words after stripping, roughly 78,000 tokens |
| How much of it matters? | In that filing: "agentic" 6 mentions, "automation" 8, "artificial intelligence" 1, "autonomous" 1, "robot" 0. A dozen passages in 56,000 words |
| Do sellers appear beside users? | Yes. Symbotic, Rockwell Automation and Teradyne come up for "autonomous mobile robots" because they sell them |
| Companion endpoints keyless? | Wikipedia page views: yes, monthly and daily per article. FRED: yes, as CSV. BLS API v1: yes, with daily limits |

Two design choices follow directly. The model reads windows around lexicon
hits, not whole filings, because the relevant text is about one percent of
the document and the windows are exactly what an auditor checks. And the
extraction must carry a role field, user or seller, because both file.

## 3. Rules carried over, and three that change

Every rule in STATUS §4 stays: a missing period is not a zero, raw before
parse, the document's own date decides its period, say it out loud when a cap
bites, stage what you mean to commit, no source behind a subscription without
a licence check on file. SEC filings are public records; the SEC's fair-access
policy (declared user agent, at most ten requests a second) is the only
condition, and the project already meets it.

Three things change, each recorded here so nobody re-derives the old rule.

1. **The weekly run stays model-free; the quarterly extraction calls the
   model directly.** STATUS §8 says lexicon work is routed through a Claude
   session and never a direct API call. That rule was written for a task a
   person can do in a session. Extracting claims from thousands of filings a
   year is not one, so the quarterly extraction is a separately invoked,
   offline command that calls the API with a pinned model, a published prompt
   and a human audit, which is the exception STATUS §6 already describes. The
   weekly cron path never imports it, and a test proves that.
2. **Filing bodies are fetched.** The EDGAR collector's docstring says bodies
   are never fetched and attribution rests on the query term. For the index
   they are fetched, stored raw, and read. The old collector's observations
   are a different measurement and are not mixed with claims.
3. **The unit is the company.** Reports rank companies; technologies are a
   view. The 48-technology lexicon remains the coding frame, revised by the
   protocol in §8.

## 4. Architecture

Weekly, deterministic, unattended:

    universe refresh ──> new filings listed ──> primary documents fetched raw
                                            ──> text stripped, windows cut around lexicon hits

Quarterly, by explicit command, offline:

    windows ──> model extracts claims (batch) ──> quotes verified locally
            ──> benchmark agreement checked ──> claims stored with model and prompt version
            ──> registry threads updated ──> index scored ──> reports rendered

Annual: the ranking, the survival analysis, the companions.

Each stage writes to the store and can be re-run from the raw layer, as now.
`--rebuild` replays windows under the current lexicon; claims are replayed only
by re-extraction, which costs money and is therefore never implicit.

### 4.1 Modules

New, each with one job:

| Module | Does | Depends on |
|---|---|---|
| `observatory/universe.py` | Builds and refreshes the company table from the Financial Statement Data Sets and the submissions API; maps SIC to sector. Proposed sectors: manufacturing 2000–3999, transportation and warehousing 4000–4799, wholesale 5000–5199, retail 5200–5999. Software and equipment vendors outside these ranges are not in the user universe; vendors inside them are handled by the role field | `http`, `store` |
| `observatory/collectors/filings.py` | Weekly: for each company, list filings dated in the week, fetch primary documents to `data/raw/<week>/filings/<cik>/`, record in `raw_fetch` | `universe`, `http`, `base` |
| `observatory/sections.py` | HTML to text; a window of 600 characters each side of every lexicon hit, overlapping windows merged, each with a best-effort Item label; deterministic | `matcher` |
| `observatory/claims/schema.py` | The claim record and its JSON schema | none |
| `observatory/claims/prompt.py` | The versioned extraction prompt, published in the repo | `schema` |
| `observatory/claims/extract.py` | Submits windows to the Batch API, polls, collects; refuses to run without an explicit flag and a key; never imported by `run.py`'s weekly path | `schema`, `prompt`, SDK |
| `observatory/claims/verify.py` | Quote verification, role and stance validation, dedupe within a filing | `schema` |
| `observatory/claims/benchmark.py` | Agreement of a run against the hand-coded benchmark; the drift gate | `verify` |
| `observatory/claims/registry.py` | Threads (company, technology) across filings; survival states with censoring | `store` |
| `observatory/claims/index.py` | Deterministic scoring and ranking from claims | `store` |
| `observatory/adoption_report.py` | Builds its own context and renders the index report, company pages, technology pages | `index`, `registry`, `render` assets |

`quarter.py` is not extended. Risk 12 has grown across three reviews; the new
report gets its own context builder.

### 4.2 Store

Additive tables, migrated through the existing `MIGRATIONS` mechanism.

    companies(cik PK, name, sic, sector, tickers, first_seen, last_seen, status)
    filings(accession PK, cik, form, filed, period_end, primary_doc, path, words, window_count, status)
    windows(id PK, accession, tech_id, item, start, end, text)
    claims(id PK, accession, cik, tech_id, role, stance, scope, quote, quote_verified,
           window_id, model, prompt_version, extracted_at, run_id)
    claim_audits(claim_id, coder, verdict, correct_tech_id, correct_role, correct_stance, note, coded_at)
    extraction_runs(run_id PK, period, model, prompt_version, submitted, succeeded, errored,
                    unverified_quotes, benchmark_agreement, status, note)

`role` is one of `user`, `seller`, `both`, `unclear`. `stance` is one of
`plans`, `pilots`, `uses`, `scaled`, `dropped`, `unclear`, ordered
`plans < pilots < uses < scaled` for escalation, with `dropped` terminal and
`unclear` outside the order. `scope` is free text the model copies from the
filing (facility counts, regions, functions), never invented. `quote` is
verbatim.

Threads for the registry are a view over claims keyed on `(cik, tech_id)`,
not a table, so a re-extraction cannot leave a stale thread behind.

### 4.3 The claim, and the gates it passes

A claim is one statement by one filer about one technology in one filing. The
extraction prompt receives the technology sheet as the coding frame (id, name,
definition, terms), the windows for one filing, and instructions that the
windows are untrusted third-party text to be judged, never followed, the same
warning `lexicon.py` already carries. Output is constrained to the schema
through structured outputs.

Four gates, all deterministic and all counted:

1. **Quote verification.** The quote must be a substring of the filing text
   after whitespace normalisation. An unverifiable quote drops the claim and
   increments `unverified_quotes` on the run. This is the check that makes
   the model's work auditable without trusting it.
2. **Lexicon bound.** `tech_id` must be an active lexicon id. Anything else is
   recorded as a discovery candidate (§8) and is not a claim.
3. **Role and stance closed sets.** Values outside the sets fail the run's
   schema validation before anything is stored.
4. **Benchmark agreement.** Every run re-extracts the benchmark filings and
   scores agreement (§6). Below the gate, the run is stored as `withheld` and
   the report says so, in the same voice the current report uses for
   withheld scores.

Item 1A, risk factors, is windowed and extracted like the rest but tagged.
Whether risk-factor claims count towards the index is decided by the Phase 0
measurement (§7), not assumed either way.

### 4.4 The registry and survival (idea C)

A thread is every claim by one company about one technology, in filing order.
Its state at a period is derived, not stored:

- `new`: first claim.
- `continuing`: claimed again.
- `escalated` / `de-escalated`: stance moved up or down the ordered set.
- `silent`: the company filed in the period and made no claim.
- `censored`: the company did not file in the period (acquired, delisted,
  late). Censored is not silent, and silent is not dropped. This is the
  missing-is-not-zero rule applied to companies.
- `dropped`: the company said so.

Survival analysis with censoring is the standard method and the honest one.
The outputs are survival curves by technology and cohort year, and the
graveyard: threads that went silent for two consecutive annual filings. The
two-filing threshold is provisional and measured against the backfill.

### 4.5 Scoring (owner's definition)

Deterministic from `claims` with `role = user` and `quote_verified = 1`.
Proposed, for the owner to accept or change:

- **Breadth**: distinct technologies at stance `uses` or `scaled` in the
  company's filings of the index year.
- **Depth**: distinct technologies at `scaled`.
- **Movement**: escalations minus de-escalations against the prior year.

Rank within sector; publish the two counts and the movement beside the rank,
never a composite alone. Technologies marked `mature` (§8) do not count
towards breadth or depth; they are shown on the company page as
infrastructure. Ties are shown as ties.

The index year is the calendar year of the filing date, consistent with the
rule that the document's own date decides its period. Full-text search reaches
back to 2001, so the backfill starts at 2019 and the launch report carries a
seven-year series.

### 4.6 Outputs

Rendered from `adoption_report.py`, reusing the templates, assets, charts,
cards and brief machinery:

| Artifact | Period | Content |
|---|---|---|
| Index report | annual, with quarterly movers | Sector leaderboards, technology adoption shares, survival curves, the graveyard, the companions |
| Company page | per company | Every claim, quote, stance, filing link; the thread history; a dispute route |
| Technology page | per technology | Filers claiming it by sector and stance; share of sector filers; attention against adoption |
| Findings, cards, brief | per report | Through the existing findings, cards and brief modules, fed from the new context |

Every claim on a page links to the filing. A "dispute a claim" route is a
mailto in year one; disputes and their outcomes are logged in `docs/`.

## 5. The model step, precisely

- **Surface**: Message Batches, because the quarterly run is thousands of
  requests with no latency need, and batches cost half.
- **Model**: pinned by exact id string in `config.py`, recorded on every
  claim. Default `claude-opus-5`. Phase 0 runs the benchmark on Opus 5 and
  Sonnet 5 and keeps the cheaper one only if agreement is within two points.
- **Output**: structured outputs against the schema in `claims/schema.py`.
  No prefill, no free text.
- **Prompt**: `claims/prompt.py`, versioned; a change bumps the version and
  requires a fresh benchmark run before it may be used on a period. The
  technology sheet sits first in the prompt, so it caches across the batch.
- **Thinking**: adaptive, effort medium, revisited if the benchmark says
  higher effort earns its cost.
- **Errors**: a request that errors is retried once in a follow-up batch;
  one that errors twice is recorded on `filings.status` and the report counts
  it. Nothing is silently skipped.
- **Key**: `ANTHROPIC_API_KEY` in `.env`, beside the existing keys. The
  weekly path is tested to run with the variable unset.

Cost, assuming about 2,000 companies in the universe and windows averaging
5,000 input tokens a filing, at batch prices; output tokens are small and
omitted:

| Job | Tokens | Opus 5 | Sonnet 5 |
|---|---|---|---|
| Backfill 2019–2025 10-Ks, about 14,000 filings | ~70M | ~$175 | ~$70 |
| One year of 10-Ks and 10-Qs | ~25M | ~$65 | ~$25 |
| Annual open read, 200 filings in full (§8) | ~12M | ~$30 | ~$12 |
| The same backfill reading whole filings instead of windows | ~1B | ~$2,450 | ~$1,000 |

The last row is why windows are the design and not an optimisation.

## 6. Quality: the benchmark and the audit

**The benchmark** is `docs/audit/claims-benchmark.yaml`: the claims from the
Phase 0 sample, hand-coded by a person who did not write the prompt, each
with technology, role, stance and quote verdicts, grown by every audit until
it holds at least 200. It is the fixed test the
model takes every run. Agreement is reported as three numbers: technology
and role correct; stance correct; quote verified. Proposed gates: 85, 75, 98.
A run below any gate is withheld.

**The quarterly audit** is 100 fresh claims, stratified by sector and stance,
coded against their quotes on the rendered company pages, not against the
database, because every wrong number in this project was caught on the
artifact. Results go in `docs/precision-audit-<date>.md` in the existing
format. Audited claims join the benchmark, so it grows.

**The coder.** STATUS §7 item 3, a coder who did not write the patterns, is
unchanged and now more important. The owner or the RA codes the benchmark;
the assistant that wrote the prompt does not.

**The rendered page is what is tested.** Findings and counts are asserted
against the HTML, as the findings layer already does.

## 7. Phase 0: the measurement that decides whether to build

One day of pipeline work and the owner's coding time. Nothing in §4 beyond
`sections.py` and a throwaway extraction script is built before this reports.

**Sample.** Fifty filers, latest 10-K each: retail 12, wholesale 8,
manufacturing 18, transportation and warehousing 12. Include five known
adopters chosen by the owner and draw the rest at random from the universe.

**Two reads of each filing.**

- *Open read*: the model reads Items 1, 2 and 7 in full and lists every
  supply chain technology the filer says it uses or sells, in free text with
  a quote. No lexicon shown.
- *Windowed read*: the model reads only the windows cut under lexicon v10 and
  emits claims in the schema.

**Coding.** A person codes every claim from both reads: technology right,
role right, stance right, quote real. This coding seeds the benchmark.

**Measures, and the proposed go/no-go line beside each.**

| Measure | Go if |
|---|---|
| Windowed precision, technology and role | ≥ 80% |
| Windowed precision, stance | ≥ 70% |
| Seller/user split correct | ≥ 90% |
| Windowed recall against open-read claims that map to the lexicon | ≥ 80% |
| Filers with at least one verified user claim | ≥ 20% of the sample, which projects to about 400 companies |
| Tokens per filing, windowed | ≤ 8,000 on average |
| Item 1A claims judged real by the coder | decides §4.3's open question |
| Open-read claims that map to no lexicon entry | feeds §8; no gate |

Below a line, the owner decides: adjust the lexicon and re-run, narrow the
universe, or stop. The result is written to `docs/phase0-claims-<date>.md`
with the condition that would reverse it, like every other source decision
in this project.

## 8. Lexicon and categories: the revision protocol

The owner asked whether the categories and lexicon should change for the new
source. The answer is decided by measurement, with v10 as the baseline and
the existing offline workflow (`lexicon prepare` → proposals → `lexicon
check` → human merge) as the only route by which anything changes.

**Evidence.** Every open-read claim, from Phase 0 and from an annual open
read of 200 randomly drawn filings thereafter, is mapped to the lexicon as
one of: matched; pattern gap (the technology is tracked, the filing's words
were not); new technology; not a technology (a field, a function, a vendor
name). The mapping is written into a `filings` request through `lexicon
prepare`, so the owner reads it in the same form as arXiv candidates.

**Proposed rules, for the owner to accept or change.**

- *Add* a technology when at least five distinct filers claim to use it and
  it names a technology rather than a field. "E-commerce" and "machine
  learning for operations" were rejected as fields on 2026-09-03; the same
  test applies.
- *Add patterns* when the same pattern gap recurs in three or more filings.
  Filings say "AI-driven forecasting" where papers say "machine learning
  demand forecasting"; the pattern set widens, the technology does not split.
- *Mark mature* when user claims exceed a share of sector filers. The owner's
  assessment gave 15% as an example; the threshold is his to set once the
  backfill shows the distribution. A mature technology stays tracked, appears on company pages as
  infrastructure, and is excluded from breadth and depth. ERP and warehouse
  management systems are the expected first cases, which resolves the
  owner's objection that ERP cannot be "in research".
- *Retire* when a technology has zero user claims across the backfill and
  zero observations elsewhere.

**Definitions.** Each technology gains a `definition` field in
`watchlist.yaml`, one sentence with its boundary, written or approved by the
owner. The model reads it as the coding frame and the students' sheet prints
it. The sheet currently prints expanded patterns; a definition beside them is
what both readers were missing.

**Granularity.** The AI entries (`demand_forecasting_ml`, `genai_planning`,
`agentic_procurement`, `supply_chain_llm`, `tms_ai`) are the likeliest to blur
in filing language. Phase 0 reports confusion between them; if the coder
cannot tell them apart from the quotes, they merge, and the record says so.

**Families.** The current families stay as the coding categories. The
sense–model–decide–act–govern stack from the owner's assessment is a
presentation layer for the report, if the owner wants it, and is not a coding
change.

## 9. Companions

**B, the promise audit.** `data/manual/promises.yaml`: source, year asked,
horizon, technology as a lexicon id, predicted adoption, and the realised
figure with its source when it arrives. First content: the MHI annual survey's
current and five-year adoption figures, by year, entered by hand from the
free reports. `observatory/promises.py` grades every due promise and draws
one chart, the hype ratio by technology. Survey figures are cited with
attribution; no proprietary curve is reproduced. Category mapping across
survey years is a one-time judgment, recorded in the file.

**G, attention.** `observatory/collectors/wikipedia.py`, weekly, keyless,
deterministic: page views per technology article. `watchlist.yaml` gains a
`wikipedia` list per technology, approved by the owner. Signal
`attention_views` in `weekly_signals`. The technology page plots attention
against the share of filers claiming use. This replaces the trade-press axis
the licence removed, at no licence risk.

**E, the payoff section.** `observatory/collectors/outcomes.py`, monthly:
named series from FRED as CSV and BLS API v1, keyless, starting with the
inventory-to-sales ratio and warehousing employment, extended only on the
owner's say. One section of the annual report, "Is it showing up?", stating
plainly that attribution is not claimed.

**Held.** D, the atlas, and F, the forecast panel, are out of scope for this
spec. F is raised with CAPS in the September conversation the marketing plan
already schedules.

## 10. Testing

Tests first, as the project does, with fixtures cut from real filings and
committed without tokens or personal data:

- `sections.py`: stripping, window boundaries, Item labelling, and that the
  same input yields the same windows twice.
- `verify.py`: a quote that is not in the text drops the claim; whitespace
  variants verify; closed sets reject unknown values.
- `registry.py`: every state in §4.4 from a constructed thread, including
  censored versus silent, and that a re-extraction leaves no stale thread.
- `index.py`: breadth, depth, movement, mature exclusion, ties, sector
  ranking, against a hand-computed fixture.
- `benchmark.py`: the gate withholds below threshold, and the withheld state
  reaches the rendered page.
- `extract.py`: refuses without the flag; refuses without a key; batch
  results are keyed by `custom_id`, never by position; the weekly path never
  imports it (an import-graph test, the same shape as the existing lexicon
  isolation).
- Rendering: claims, quotes and links asserted against the HTML; the
  company page for a fixture filer shows every claim and nothing else.
- Status: `--write-status` gains the claim and company counts, with the
  drift test extended.

## 11. Risks

- **Disclosure is not adoption.** Named on the face of every page. The index
  measures what companies attest, and attestation in a 10-K carries legal
  weight that a press release does not.
- **Boilerplate.** Risk-factor language about AI will dominate mention counts.
  The role and stance fields, the quote gate and the Phase 0 decision on
  Item 1A are the defences; the audit measures whether they hold.
- **Sellers scored as users.** Measured in Phase 0; a company can be both and
  the schema allows it.
- **Model drift.** Pinned id, versioned prompt, benchmark on every run, run
  withheld below the gate.
- **Private companies invisible.** Said plainly; the dispute and submission
  route is the only remedy in year one.
- **Section splitting is fragile.** The design does not depend on it. Windows
  are cut from the whole text; the Item label is metadata.
- **Cost surprises.** The batch is sized and estimated before submission and
  the estimate printed; a run over a configured ceiling stops and says so.
- **A company objects to its rank.** Every score links to its quotes. The
  dispute log is public. This is the product working.
- **Calendar.** The January 2027 launch is unchanged. The index built in
  December ranks filings dated in 2026; FY2026 10-Ks filed in early 2027 land
  in the 2027 index. The think-aloud sessions in October use a Phase 0
  mock-up as the stimulus if it exists, otherwise the Q2 report.

## 12. Decisions

**Made by the owner on 2026-09-04:** A as spine; C in the first schema; B and
G in the annual report; E as one section; D held; F only if CAPS wants it;
lexicon re-examined on measurement from the v10 baseline.

**Assumed by this spec, for the owner to confirm or reverse:**

1. The quarterly extraction may call the API directly, offline, by explicit
   command. The weekly run stays model-free.
2. Year one covers US public filers only, with a submission route for others.
3. `claude-opus-5` is the default; a cheaper model needs benchmark evidence.
4. Item 1A claims are decided by Phase 0.

**Still the owner's to make, when the evidence arrives:**

- The scoring definition in §4.5 and the maturity threshold in §8.
- The go/no-go lines in §7.
- Definitions for each technology.
- The product's name.
- Whether the count-based quarterly report is retired or kept as an appendix.

## 13. Sequence

1. **Phase 0** (September): `sections.py`, the throwaway extraction, the
   fifty-filing sample, coding, the report. Decide.
2. **Lexicon v11** (September): proposals from the Phase 0 mapping, merged by
   the owner; definitions written.
3. **Build** (October–November): universe, filings collector, claims package,
   registry, index, report. Tests first throughout.
4. **Backfill** (November–December): 2019–2025 10-Ks, one batch per year,
   benchmark checked on each.
5. **Companions** (December): promises file, Wikipedia collector, outcomes
   collector, sections in the report.
6. **Launch** (January 2027): the 2026 index with the seven-year series, per
   the marketing plan.

Each step ends with its artifact looked at, not its code read.

This spec is the umbrella design. It is too large for one implementation
plan, so plans are written per step: Phase 0 first, on its own, because it is
a gate; the build steps after Phase 0 has reported and the owner has decided.
