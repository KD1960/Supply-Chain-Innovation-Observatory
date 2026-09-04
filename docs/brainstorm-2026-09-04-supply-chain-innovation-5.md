# Supply Chain Innovation 5: what to build instead

Brainstorm, 2026-09-04. Written for Kevin. This is not a spec, and nothing in
it is built. Basis: STATUS.md, the 09-04 process review, Kevin's assessment of
2026-09-04, the marketing plan, the SCDAI status file, and two probes run today
against EDGAR full-text search.

Untracked on purpose. The repository is public; committing this is Kevin's call.

---

## 1. The diagnosis, restated

Both dashboards had the same shape. Each counted how often a term appeared in
documents. A count of mentions has three problems that engineering cannot fix.

- **No expectation to violate.** "Digital twin: 33 papers this quarter"
  surprises nobody, because nobody had a number in their head to compare it
  with. Surprise needs a gap.
- **The unit is a word.** Professionals think about companies, competitors,
  sites and money. Researchers want a panel. Students want examples. Nobody
  wants a term-frequency table.
- **Stage was read off the source.** A paper mentioning ERP made ERP
  "research". Stage is a property of the world, and a mention cannot see it.

The corpus problem was real, but it was downstream of the design. Free text
that merely *mentions* supply chain technology is thin, and the rich mention
sources are licensed. Free text in which a party *attests to its own use* of a
technology is large, public and unlicensed. That is the pivot.

The AI answer Kevin liked was interesting for reasons a pipeline can copy. It
had a thesis (agency). It separated hype from adoption (humanoids). It named
what is no longer hot. It used survey percentages. It gave one concrete
deployment. It stated a tension: most leaders expect agents to break silos, and
most say the investments have not paid off. Every one of those is a gap. None
is a count.

## 2. What makes a recurring product interesting

Five properties. Each idea below is scored against them.

1. **A gap.** Said vs built. Promised vs delivered. Then vs now. Us vs peers.
2. **A unit people care about.** Companies, places, dollars, people. Not terms.
3. **Attested or physical facts.** A 10-K statement, a permit, a grant, a
   charging station. Not a mention.
4. **A verdict.** A ranking, a grade, a map, a survival curve. Something that
   can be wrong, and can therefore be argued with.
5. **Memory.** Each period judges the last. The product gets more interesting
   with age.

The current Observatory has property 3 in part, through SEC filings, and none
of the others.

## 3. The ideas

### A. The Disclosed Adoption Index. Recommended spine.

**What.** Rank companies, not technologies, by what they attest in their own
SEC filings about supply chain technology they use. Annual index, quarterly
movers. Technology-level adoption falls out as a share of filers, which is the
percentage Kevin asked for.

**Data.** EDGAR full-text search is free, keyless, and covers every filing
since 2001. Fetching a filing is free with the contact header the project
already sets. Universe: filers in the retail, wholesale, manufacturing and
transportation SIC ranges. Measured today, 10-K filings in the twelve months
to 2026-09-04:

| phrase | 10-K filings |
|---|---|
| "our business", as a denominator proxy | 6,323 |
| "supply chain" | 4,686 |
| "artificial intelligence" | 4,055 |
| "generative AI" | 1,249 |
| "blockchain" | 674 |
| "robotics" | 520 |
| "agentic" | 361 |
| "predictive maintenance" | 77 |
| "RFID" | 54 |
| "digital twin" | 33 |
| "warehouse automation" | 22 |
| "nearshoring" | 15 |
| "electric trucks" | 14 |
| "autonomous mobile robots" | 13 |
| "automated fulfillment" | 7 |
| "autonomous trucks" | 6 |

The AI family is huge. Physical automation is thin by exact phrase and widens
with synonyms, and one filing is one company, which is worth far more than one
paper. This is the opposite of the data problem the Observatory had.

**Method.** Weekly, deterministic collection, as now. Quarterly and offline, a
model reads the Business and MD&A sections of each new filing and extracts
structured claims: company, technology (the 48-item lexicon is the coding
frame), stance, scope, a verbatim quote, and the filing URL. Stance is the
company's own verb: sells it, plans it, pilots it, uses it, has scaled it,
dropped it. Pinned model, published prompt, a fixed benchmark of 200 hand-coded
claims re-run every quarter to catch drift, and a human codes 100 fresh claims
a quarter against their quotes. Scoring from the claims is deterministic and
every score links to a sentence in a filing. This is exactly the exception
STATUS §6 already carves out for periodic studies.

**Why interesting.** A ranking of companies is the most shared format in
business media. Gartner's Top 25 is the proof, and it is opinion. This one is
public data with a quote behind every score. It yields the index, the movers,
sector contrasts, adoption share by technology among filers, a said-versus-
attested gap per company (8-K press-release language against 10-K language),
and abandonment, when a technology leaves a company's filing. The stage problem
disappears, because stage comes from the filer's own words.

**Sellers and users.** Today's sample shows the trap: Symbotic, Rockwell
Automation and Teradyne come up for "autonomous mobile robots" because they
sell them. Extraction must separate vendor claims from adopter claims. Both are
useful, and a vendor index is a second product, but the two must never be
summed.

**What could kill it.** Disclosure is not adoption, so it is an index of
*disclosed* adoption and says so on its face. Boilerplate risk-factor language
about AI must not count; only a concrete claim about the filer's own operations
does. Private companies are invisible; say so, and give them a route to submit
evidence, which is also engagement. Companies may dislike their rank. That is
the point, and it is why they will read it.

**Cadence and automation.** Collection weekly. Extraction and index quarterly.
Ranking annual, for the January launch. Everything is automated except the
quarterly audit. The cost is compute rather than data, and small next to any
subscription.

**Reuse.** The 48-technology lexicon, the store, rebuild, render and test
infrastructure, the EDGAR contact setup, the findings layer, the cards, the
brief, the brand assets and the launch calendar. Firm-level technology
diffusion measured from text has academic precedent using earnings calls and
job postings; those are paid, and filings are free, which is the methods-paper
angle.

### B. The Promise Audit. Annual companion.

**What.** A registry of published predictions about supply chain technology,
graded when they come due. The MHI and Deloitte annual survey has asked every
year since 2014 what adoption is now and what it will be in five years, per
technology. So the industry's 2019 forecast for 2024 can be graded against its
own 2024 measurement. Vendor and analyst claims of the form "by 2025, X% of
..." are added as they appear and graded on their date.

**Why interesting.** Nobody grades forecasts in this field. A hype ratio per
technology, promised adoption over realised, is one chart people will repeat.
It also gives the Observatory the expectation it never had: the number already
in the reader's head.

**Data and automation.** One free PDF a year, entered by hand in about an hour.
A copy of the 2026 report appears to be in the repository root already. Grading
is arithmetic and fully deterministic. Citing survey figures is fine;
reproducing Gartner's curves is not.

**What could kill it.** MHI's technology categories have changed over the
years. Mapping them takes judgment, once.

### C. The Deployment Registry with follow-up.

**What.** ClinicalTrials.gov for supply chain technology. Every disclosed pilot
or deployment becomes a registered entry with a date, a company, a technology,
a site and a status. Every entry is re-checked in later filings. Output:
survival curves and a graveyard. "Of the blockchain pilots disclosed in 2019
filings, this many were still mentioned in 2022."

**Why interesting.** Failure is the least reported thing in this field, and a
university is the only neutral party that can publish it. Property 5, memory,
in its purest form.

**Fit.** Not a separate product. It is what A becomes once the same claims are
tracked across years. Give a claim an identity that survives from one filing to
the next in A's first schema, and C is free.

### D. The Innovation Infrastructure Atlas.

**What.** A map of where supply chain innovation is physically happening, from
government records that carry coordinates: federal freight and port grant
awards, state autonomous-vehicle permits and disengagement reports, FAA drone
waivers and delivery certificates, freight EV charging stations, foreign trade
zones, intermodal terminals, automated container terminals, factory
announcements. Quarterly.

**Why interesting.** The only idea that uses the "Infrastructure" in the
Center's name. Maps get shared. The findings are spatial gaps: charging against
freight corridors, AV corridors against regulation, where grant dollars
concentrate. Arizona sits naturally at the centre of the map.

**What could kill it.** Twenty small sources, each with its own format, each
drifting. Coverage will be uneven and must be shown as uneven. This is a
maintenance problem rather than a count problem. Best as a second product, or a
supervised student team, once A is running.

### E. The Payoff Monitor.

**What.** Monthly and wholly automated from FRED, Census, BLS and BTS: the
outcome series all this technology is supposed to move. Inventory-to-sales
ratios, warehousing labour productivity and employment, truck driver
employment, port dwell, rail velocity, the LMI, the New York Fed's GSCPI. Set
beside adoption from A.

**Why interesting.** The Solow paradox for supply chains: adoption up,
productivity flat. It poses a question professionals argue about.

**What could kill it.** Attribution is impossible, and the honest version says
so. As a product it is a set of charts. As one section of A's annual report it
is strong. Recommend the latter.

### F. The Forecast Panel.

**What.** Twenty resolvable questions a year, such as whether a driverless
truck will run scheduled freight on three or more lanes by a given date. CAPS
members, researchers and students submit probabilities. Resolution is scripted
where possible. Brier scores are published: practitioners against academics
against students.

**Why interesting.** Every resolution is a small news event. Participants
return to see their score. The Center owns data nobody else has. The marketing
plan's beta cohort and CAPS panel are this panel already.

**What could kill it.** Cold start. Question writing needs judgment.
Resolution is sometimes contestable. Not automatable end to end. A natural
companion to B, since graded predictions and graded forecasters are one idea.

### G. Attention against adoption.

**What.** Wikipedia page views per technology page, free and daily through a
stable API, as the "said" axis. Set against A's attested adoption as the
"built" axis. The hype gap per technology per quarter.

**Fit.** One chart, not a product. It replaces the trade press the licence took
away, at zero licence risk.

### H. Keep the instrument and add a model-written narrative. The trap.

The cheapest pivot is to let a model write the quarterly story from the
existing observations. It would still be dull, because the corpus is dull:
one-star repositories and paper abstracts. The model Kevin queried was
interesting because it drew on surveys and deployments, not on counts. Fix the
corpus, not the summariser.

## 4. Side by side

| | Gap | Unit | Attested | Verdict | Memory | Data today | Automated | Cadence |
|---|---|---|---|---|---|---|---|---|
| A Adoption Index | yes | company | yes | ranking | yes | large, measured | ~95% | quarterly, annual |
| B Promise Audit | yes | technology | survey | grade | yes | 12 years, free | ~90% | annual |
| C Registry | yes | deployment | yes | survival | yes | same as A | same as A | annual |
| D Atlas | some | place | yes | map | some | many small | ~70% | quarterly |
| E Payoff | yes | economy | yes | chart | yes | rich, free | 100% | monthly |
| F Forecast panel | yes | person | no | score | yes | none yet | ~50% | annual |
| G Attention | yes | technology | no | chart | yes | free API | 100% | weekly |
| H Narrative | no | term | partly | prose | no | thin | ~90% | quarterly |

## 5. Recommendation

Build **A** as the spine, with **C** designed into its first schema. Add **B**
and **G** as companions in the annual report; each is about a day of work. Fold
**E** in as one section. Hold **D** for a second product or a student team. Run
**F** only if CAPS wants it.

A is the one idea that scores on all five properties, whose data are measured
today as large and free, that reuses most of what exists, and that produces a
format both professionals and the press already know how to share: a ranking
with evidence. It also answers Kevin's question about determinism. Scoring
stays deterministic and traceable. Reading uses a model, offline, with
published prompts and a human audit. That is the division STATUS §6 already
allows.

"Disclosed Adoption Index" is accurate. A better name can wait.

## 6. Decisions needed

1. The spine: A, or D, or B with F?
2. A model in the offline quarterly extraction, with a pinned version,
   published prompts and a human audit: yes or no?
3. Year one: US public filers only, with a submission route for everyone else?

If A, the next step is a spec, and before the spec one more measurement, in
keeping with the project's rule: pull fifty 10-Ks, extract claims by hand for
ten technologies, and see whether the seller-versus-user split and the stance
coding come out clean. That is a day, and it decides whether the index is
real.
