# Supply Chain Innovation Observatory — Marketing and Distribution Plan

Draft 1, 2026-09-03. Owner: Kevin Dooley. Written for Kevin, a supporting RA, and
W. P. Carey communications staff. Decisions recorded in §1 are Kevin's; the
rest is a proposal to be revised after the beta cohort (§5) reports back.

---

## 1. Decisions already made

- Public launch is January 2027, with the 2026 annual report, coincident with
  the announcement of the Center for Supply Chain Innovation, Technology, and
  Infrastructure. The Observatory is the Center's first public output and gives
  the announcement substance.
- The 2026-Q3 report (scores withheld, correctly) is a soft launch to a named
  beta cohort in October 2026, not a public release.
- CAPS Research is pursued as a formal distribution partner (member brief,
  webinar, possible co-brand), not only as a network.
- Resources: Kevin plus Claude, RA support, W. P. Carey communications staff.
  No dedicated budget is assumed; anything below that costs money is marked.
- Success at twelve months is defined as (a) Center positioning — the
  Observatory is what people associate with the Center, and it attracts
  corporate partners or sponsors — and (b) practitioner behaviour —
  professionals report using it in technology scanning or planning. Reach
  metrics are instrumental, not the goal.

## 2. Positioning

**One sentence.** An open, evidence-based, reproducible view of which supply
chain technologies are being built rather than talked about — the honest
alternative to opinion-based hype rankings.

**Tagline candidate.** *Built versus said.* It is the report's most portable
idea (the substance-against-attention axis) and it is understood in one
reading by every target audience.

**Frame of reference.** The incumbent in the audience's head is the Gartner
Hype Cycle: expert opinion, paywalled, not reproducible. The Observatory is
positioned against it on three attributes — public data, deterministic
scoring, every number traceable to a document. Say all three, every time. Do
not position against Gartner by name in ASU-branded material; let the
audience draw the comparison.

**What we do not claim.** The investment stage has little data and the free
sources cannot see trade press; precision is 70% at lexicon v9 with one coder.
These limitations go on the face of the report and in the launch post. Saying
them first is the differentiation; being caught on them is the failure mode.

## 3. Audiences, in priority order

1. **Supply chain professionals — CPOs, VPs, technology and strategy leads.**
   Job to be done: "tell me what to watch, what stage it is at, and whether my
   peers are ahead of me." They will read three findings and one chart. They
   will not read the 38-row table. Reached through CAPS, LinkedIn, trade press,
   CSCMP/ISM/ASCM.
2. **Researchers.** Job: method, data, reproducibility, something to cite.
   Cheapest to reach, most likely to cite, and they lend credibility to the
   practitioner pitch. Reached through the GitHub repository, a DOI per report
   (Zenodo, free), a methods paper, POMS/DSI/AOM, and direct email to the ~40
   people in the field who work on technology adoption and text analysis.
3. **Students and instructors.** Job: a curated, current list of technologies
   with definitions and stage, and a teaching case. Appendix A (tracked
   technologies) is the artifact; it should exist as a standalone one-page
   PDF. Reached through W. P. Carey SCM courses first, then ASCM student
   chapters and instructors at peer programs.
4. **Investors — deferred.** Not marketed to until the investment stage carries
   data. Do not put "investors" in launch copy. Revisit when a licensed export
   or a new source fills that stage.

## 4. The product marketing has to sell — the findings layer

The Q2 report is a research instrument. Its headline tiles (documents matched,
technologies seen, silent, filing companies) describe the instrument, not the
world, and "In summary" is mostly method. The findings a professional would
repeat to a colleague are present but buried. This is the single largest
marketing gap and it is a development task, not a communications one.

Add a **findings layer** above the existing report:

- Three to five findings, each one plain sentence, each with the sample size
  beside it ("Autonomous trucking is the only technology at the diffusion
  stage — 12 documents, 8 of them SEC filings"), each backed by exactly one
  figure that can stand alone as an image.
- The existing tiles become instrument metadata and move to the footer or the
  "how to read" disclosure.
- The 38-row table and Appendix A move below a fold or to a second page.
- Every technology gets a stable anchor (`#autonomous-trucking`) so a post can
  link to one row rather than to a 14,000-pixel page.
- Each figure is exported as PNG at 1200×627 (LinkedIn) and 1080×1350
  (carousel) with a one-line caption and the source line "ASU Observatory,
  2026-Q2, n = …". The charts pipeline already writes SVG/PDF; add the PNG
  sizes.

Deliverables per report, generated by the pipeline where possible:

| Artifact | Audience | Format |
|---|---|---|
| Findings page (top of report) | All | HTML, ~1 screen |
| Five standalone figures | Professionals, press | PNG in two sizes |
| Two-page quarterly brief | CAPS members, email list | PDF |
| Tracked-technologies sheet | Students, instructors | One-page PDF |
| Full report + evidence pages | Researchers, sceptics | HTML (existing) |
| Data + code + DOI | Researchers | GitHub release, Zenodo |

## 5. Discovery: knowing whether it meets their needs

Do this before the findings layer is final, using the Q2 report as the
stimulus.

**Think-aloud sessions, 8–12, 30 minutes each, October 2026.** Recruit four
to six CAPS member practitioners, two to three academics, two students. Share
screen or send the link and watch. Protocol:

1. Open the report. Say what you are looking at and what you think it means.
   (Do not help for the first three minutes.)
2. What would you do with this tomorrow? Who would you send it to, and what
   would you say when you sent it?
3. Which technology surprised you? Which do you disagree with, and why?
4. What is missing that you expected to see?
5. If this arrived quarterly, would you open it? What would make you stop?

Record verbatim. Code answers to three things: what they looked at first,
what they said they would do, and what they disbelieved. The disbelief
answers feed the limitations text; the "what I'd do" answers define the
findings layer and the brief.

**Beta cohort, 20–30 named people, Q3 report, October–November.** Same
population plus a few trade journalists and two or three friendly CPOs
outside CAPS. Send the Q3 report with the draft findings layer and a
three-question reply-by-email survey: (1) Which finding, if any, is useful to
you? (2) What would you need to see to trust it? (3) Would you forward it,
and to whom? Track who replies and who forwards without being asked; those
are the first practitioner-behaviour signals.

**After launch, instrumentation.** Plausible (about $9/month, privacy-friendly,
no cookie banner) or GA4 on the report pages: scroll depth, which technology
anchors are visited, referrer. UTM parameters on every post and email link.
Email platform open and click rates. A "propose a technology" form on the
page — it measures engagement and grows the lexicon at the same time.

**Indicators to watch, in order of how much they mean:**

| Indicator | Why it matters | Twelve-month target (provisional) |
|---|---|---|
| Unprompted requests to present, brief, or partner | Direct evidence of Center positioning | 6+ from organisations, not individuals |
| Practitioners describing use in planning or scanning (survey, interview, email) | The success criterion itself | 10 documented cases |
| Citations in trade press and academic papers | Credibility with both audiences | 5 trade, 2 academic |
| "Propose a technology" submissions | Engagement that is also work | 20 |
| Email subscribers (quality over count) | Owned reach | 500, majority practitioners |
| Report page visits, scroll past findings layer | Whether the layering works | ≥30% scroll to the table |
| LinkedIn impressions | Vanity; report it, do not steer by it | — |

Targets are guesses to be replaced after the beta cohort. Reach numbers
without behaviour numbers should be read as failure, not partial success.

## 6. Channels

The problem to design around: an awareness post on a social platform is one
click away from the report, and most people will not click. The answer is to
make the report unnecessary for the common case. Each post carries the whole
finding. The link is provenance for the minority.

**Owned — email list (primary call to action everywhere).** The only channel
that survives algorithm changes. Quarterly brief plus an annual report
announcement; nothing else. Platform: Buttondown or Mailchimp free tier to
start; check whether W. P. Carey communications can host the list on their
system instead, which also solves ASU data-handling questions.

**Owned — Kevin's LinkedIn.** Will outperform a new Center page for at least
the first year; institutional pages get very little organic reach. Cadence:
one native post per finding in the two weeks after each report (four to six
posts per quarter), each an image or a short document post, no external link
in the body — link in the first comment. One "how it works" post per year.
The RA drafts; Kevin edits and posts under his own name. A Center page is
created for the announcement and reposts; it is not the primary channel.

**Partner — CAPS Research.** The pitch: a quarterly *Innovation Observatory
Brief* delivered to members as a CAPS benefit, one member webinar on the
annual report, and CAPS members as the standing beta/feedback panel (which
gives CAPS a voice in what is tracked). Ask for: distribution, a slot in an
existing member communication, and introductions to two or three CPOs for the
think-aloud sessions. Offer: co-branding on the brief, CAPS acknowledged in
the report footer, first look each quarter. Open this conversation in
September; the brief format needs their input before Q3.

**Institutional — W. P. Carey and ASU News.** Announcement package in
January: a news story built around one finding (not "ASU launches a
dashboard"), the Center announcement, a short explainer video if
communications staff will produce one, a page on the W. P. Carey site with a
stable URL. Brand and naming approvals for the Center take longer than
expected; start the paperwork now. Ask communications staff specifically for:
web hosting under wpcarey.asu.edu, media pitching, and design of the brief
template. Do not ask them to write the findings; they will make them
generic.

**Earned — trade press.** Supply Chain Dive, SupplyChainBrain, Supply Chain
Management Review, Logistics Management, Supply Chain Quarterly, FreightWaves.
Pitch a finding with a figure, offer the data, and offer Kevin for a
quote, three weeks before each report. Trade press wants a number and a
surprise; "autonomous trucking is the only technology at diffusion, and
warehouse robotics has more research than filings" is a story, "a new
observatory" is not. Build a list of eight to ten named reporters who cover
technology; the RA maintains it.

**Earned — academic.** A DOI per report via Zenodo, a GitHub release per
report, and a methods paper submitted in 2027 (target: a methods-friendly
outlet such as *Journal of Purchasing and Supply Management*, *Decision
Sciences*, or *Technological Forecasting and Social Change*). Present the
method at POMS or DSI in 2027. Email the report directly to the researchers
most likely to cite it; a personal note from Kevin outperforms every channel
above for this audience.

**Events.** CSCMP EDGE 2026 is October 4–7 in Nashville — too early for a
public launch, but useful for the think-aloud recruiting if Kevin or a
colleague attends. ISM World 2027 is listed for May 16–18 in Washington, DC;
a session proposal built on the 2026 annual report is the natural first
conference appearance. ASCM Connect and the Gartner Supply Chain Symposium
are worth watching for later years. Session proposals are due months ahead;
the RA tracks deadlines.

**Public procurement — separate track.** The NASPO relationship in the report
header is a distinct audience (state procurement officials) with different
needs. Treat it as a second partner conversation in 2027, not part of the
launch.

## 7. Calendar

| When | What |
|---|---|
| September 2026 | Open the CAPS partnership conversation. Start ASU brand/naming approvals for the Center. Set up Zenodo, analytics, email platform, "propose a technology" form. RA recruited and briefed. |
| Early October | Q3 report generated. Draft findings layer written against Q3 counts. Recruit think-aloud participants (via CAPS introductions, W. P. Carey alumni, colleagues). |
| October | 8–12 think-aloud sessions. Q3 report + draft brief to beta cohort with three-question survey. |
| November | Revise findings layer and brief format from session and survey evidence. Agree brief format with CAPS. Build reporter list. Draft January announcement package with communications staff. |
| December | Freeze 2026 annual report content (data through W52 lands early January — confirm the run date works with the announcement date). Produce figures, brief, technologies sheet, DOI. Pre-brief two trade reporters under embargo. |
| January 2027 | Public launch: annual report, Center announcement, ASU News story, LinkedIn series (5–6 posts over two weeks), CAPS member brief and webinar date set, email to researcher list. |
| February–March | Collect and code first practitioner-behaviour signals. Submit ISM World / POMS / DSI proposals. Q1 brief in April. |
| Quarterly thereafter | Report → findings → figures → brief → LinkedIn series → email → CAPS distribution. Three-question survey each quarter. |
| September 2027 | Twelve-month review against §5 indicators. Decide whether to open the investor audience and the NASPO track. |

## 8. Division of labour

- **Kevin:** positioning decisions, findings text (final), CAPS and ASU
  relationships, reporter quotes, posting under his own name, methods paper.
- **RA:** think-aloud logistics and coding, beta cohort management, reporter
  and researcher lists, post drafts, event deadlines, analytics summaries,
  quarterly indicator table.
- **W. P. Carey communications:** Center announcement, ASU News story, web
  hosting, brief template design, media pitching, possible video.
- **Claude / pipeline:** generate findings-layer draft, figures in post sizes,
  brief PDF, technologies sheet, and the quarterly indicator table from
  analytics exports.

## 9. Risks

- **Over-claiming from small n.** Every finding carries its sample size; the
  RA checks each post against the evidence page before it goes out.
- **Precision and coverage criticism from academics.** Limitations stated on
  the page and in the launch post; the methods paper is the full answer.
- **Center approvals slip past January.** Fallback: launch under W. P. Carey
  Department of Supply Chain Management branding and add the Center name when
  approved. Decide the fallback date in November.
- **CAPS declines a formal role.** Fallback: personal distribution to CAPS
  contacts and a direct CPO panel of eight to ten recruited through alumni.
- **Kevin's time.** The plan assumes roughly two days per quarter from Kevin
  and one day per week from the RA. If the RA does not materialise, cut trade
  press and events first; keep CAPS, LinkedIn, email, and the DOI.
- **Weekly posting temptation.** The weekly page is collection health. Weekly
  external posts would reintroduce the noise the momentum metric was dropped
  for. Quarterly is the public cadence.

## 10. Open questions for Kevin

1. Does W. P. Carey communications have a target date for the Center
   announcement, and who owns approval of the name?
2. Who at CAPS is the right first conversation, and is there a member
   communication (newsletter, portal) the brief could ride on?
3. Should the email list live on an ASU system or an external platform?
4. Is a methods paper in 2027 realistic alongside other commitments, or should
   a short methods note on the site stand in for it in year one?
5. Which two or three practitioners would you trust to be first-round
   think-aloud participants this month?
