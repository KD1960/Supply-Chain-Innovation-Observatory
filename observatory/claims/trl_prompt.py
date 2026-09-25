"""The TRL extraction prompt, versioned and published. Any change to a string
here is a change to the instrument: bump PROMPT_VERSION and re-run the
placement check (Task 6) before the new version reads a period.

Nothing in the system prompt varies between requests (no dates, no document
ids), so the prompt cache holds across a run."""

from __future__ import annotations

from ..trl.documents import DocText
from .prompt import UNTRUSTED as _FILING_UNTRUSTED

PROMPT_VERSION = "trl-1"

# The phase0 guard, reworded from SEC filings to any public document.
UNTRUSTED = (_FILING_UNTRUSTED.replace("FILING TEXT", "DOCUMENT TEXT")
             .replace("from a public filing", "from a public source")
             .replace("what the filer says about its own business", "what the document says"))

_RULES = """\
You are coding documents for a research tracker that estimates how mature
supply chain technologies are, on a Technology Readiness Level scale.

A claim is one statement in this document that a named actor did something
with one of the tracked technologies. Code what the document SAYS HAPPENED,
not what the technology is or could do. Descriptions of the technology,
market forecasts and generic risk language are not claims.

claim_type, the strongest verb the text supports, taken literally:
- proposes: describes, analyses or argues for the technology; nothing built
- simulates: models or simulates it; nothing physical
- prototypes: built and tested a prototype in a lab or on a test track
- pilots: trial at one or a few real sites, explicitly limited
- demonstrates_in_operation: running in a real operation, not described as a trial
- sells: a vendor offers it commercially (a product launch counts)
- buys: a user firm orders or purchases it (an order or contract counts)
- operates_at_scale: across a network, in most facilities, or a count that says so
- abandons: discontinued, wound down, paused indefinitely, bankruptcy of the operator

actor_type: university, startup, incumbent_vendor, user_firm (the party that
uses it in its own operations), government, analyst, unclear.
actor: the actor's name as written, or "unclear".
setting: lab, test_site, one_site, multiple_sites, network_wide, unclear.
quantity: any count of sites, units, vehicles, customers or money the text
gives for THIS claim, verbatim; empty if none.
source_type: what this document is: paper, patent, filing, press_release,
trade_article, code_repository, job_posting, analyst_note, funding_record,
government_record, forum_post.
quote: copy the sentence or clause VERBATIM, at most 400 characters, no
paraphrase, no ellipsis. A quote not in the text is a failed claim.

If the document makes no claim about a tracked technology, return an empty
claims list.
"""


def system(techs: list[tuple[str, str]]) -> str:
    frame = "\n".join(f"- {tid}: {name}" for tid, name in techs)
    return _RULES + "\nTRACKED TECHNOLOGIES (tech_id must be one of these)\n" + frame + "\n\n" + UNTRUSTED


def user(doc: DocText) -> str:
    return (f"SOURCE: {doc.source}\nDOC_ID: {doc.doc_id}\nDATE: {doc.doc_date or 'unknown'}\n"
            f"TITLE: {doc.title or ''}\nURL: {doc.url or ''}\n\nDOCUMENT TEXT:\n{doc.text}\n")
