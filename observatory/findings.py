"""What the period says about the world, as sentences a person would repeat.

The report's tiles and its "In summary" describe the instrument: how many
documents were matched, how many technologies were silent, how the rates are
computed. All true, none of it a finding. This module writes the other kind --
a plain sentence about a technology, its sample size inside the sentence, and
a link to the row it came from.

Rules read the rows `quarter.build_context` already assembles and nothing
else. A finding that needs a query of its own is a finding the evidence page
cannot support, and every published number in this project has to be
followable to the document it came from.
"""

from dataclasses import dataclass, replace
from pathlib import Path

import yaml

from . import config

# Below this, a technology is counted in a sentence but never named. 2026-Q2
# holds cold chain IoT monitoring at the diffusion stage on a single SEC
# filing; naming it would make the sentence beside it -- that autonomous
# trucking is the only technology there -- false, on one document.
MIN_EVIDENCE = 3


class OverrideProblem(Exception):
    """An override file that cannot be applied as written."""


@dataclass(frozen=True)
class Finding:
    """One sentence, and the row a reader can check it against."""

    id: str
    text: str
    anchor: str = ""


def _anchor(row) -> str:
    return f"tech-{row['id']}"


def _named(rows):
    """The rows a finding is allowed to name."""
    return [row for row in rows if row["total"] >= MIN_EVIDENCE]


def _join(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def stage_frontier(rows, context=None) -> Finding | None:
    """Technologies whose evidence is led by company filings.

    This is the diffusion end of the pipeline and the thinnest part of the
    corpus, which is exactly why it is the first thing a practitioner asks
    about: what is far enough along that companies are writing it down.
    """
    led = [row for row in rows if row["by_family"].get("filings")
           and row["top_family"] == "filings"]
    named = _named(led)
    if not named:
        return None
    named.sort(key=lambda row: -row["total"])
    first = named[0]
    filings = first["by_family"]["filings"]
    sentence = (
        f"{first['name']} is the technology furthest along the pipeline: "
        f"{first['total']} documents this period, {filings} of them company "
        f"filings from {first['filers']} companies."
    )
    others = len(led) - len(named)
    if len(named) > 1:
        sentence = (
            f"{_join([row['name'] for row in named])} are led by company "
            f"filings, the diffusion end of the pipeline: "
            + ", ".join(f"{row['name'].lower()} on {row['total']} documents, "
                        f"{row['by_family']['filings']} of them filings"
                        for row in named) + "."
        )
    if others:
        sentence += (
            f" {others} further technolog{'y' if others == 1 else 'ies'} "
            f"appeared there on fewer than {MIN_EVIDENCE} documents, too few "
            f"to name."
        )
    return Finding("stage_frontier", sentence, _anchor(first))


def federal_money(rows, context=None) -> Finding | None:
    """Technologies drawing federal awards.

    The investment stage is the thinnest leg in this corpus, so the sentence
    says how much of the technology's own evidence the money is rather than
    letting four awards stand as a trend.
    """
    funded = _named([row for row in rows if row["by_family"].get("money")])
    if not funded:
        return None
    funded.sort(key=lambda row: -row["by_family"]["money"])
    first = funded[0]
    awards = first["by_family"]["money"]
    rest = ""
    if len(funded) > 1:
        rest = (f" {len(funded) - 1} other technolog"
                f"{'y' if len(funded) == 2 else 'ies'} drew federal money as well.")
    return Finding(
        "federal_money",
        f"{first['name']} is where federal money went: {awards} of its "
        f"{first['total']} documents this period are federal awards.{rest}",
        _anchor(first),
    )


def patent_led(rows, context=None) -> Finding | None:
    """Technologies whose largest evidence family is patents.

    A patent is a claim on a mechanism someone expects to be worth owning,
    which is a different statement from a paper about the same idea.
    """
    led = _named([row for row in rows if row["top_family"] == "patents"])
    if not led:
        return None
    led.sort(key=lambda row: -row["total"])
    first = led[0]
    others = (f", ahead of {_join([row['name'].lower() for row in led[1:3]])}"
              if len(led) > 1 else "")
    return Finding(
        "patent_led",
        f"{first['name']} is led by patents rather than papers: "
        f"{first['total']} documents, {first['concentration']}% of them "
        f"patents{others}.",
        _anchor(first),
    )


def most_evidenced(rows, context=None) -> Finding | None:
    """The most-written-about technology, stated so it cannot read as importance.

    A bare count is heard as a ranking of what matters. 121 documents that are
    96% research is a statement about a literature, not about an industry.
    """
    named = _named(rows)
    if not named:
        return None
    first = max(named, key=lambda row: row["total"])
    return Finding(
        "most_evidenced",
        f"{first['name']} draws more evidence than anything else tracked, "
        f"{first['total']} documents, but {first['concentration']}% of it is "
        f"{first['top_family']} \u2014 volume in one family, not movement across "
        f"stages.",
        _anchor(first),
    )


def crossing(rows, context=None) -> Finding | None:
    """Technologies with more late-stage evidence than early-stage.

    This is the question the project exists to answer, so it is a finding
    whenever the period can compute it.
    """
    over = _named([row for row in rows if (row.get("lfi") or 0) > 0])
    if not over:
        return None
    over.sort(key=lambda row: -(row["lfi"] or 0))
    names = _join([row["name"] for row in over[:3]])
    verb = "is" if len(over) == 1 else "are"
    return Finding(
        "crossing",
        f"{names} {verb} carrying more evidence from filings, awards and "
        f"regulation than from research and code \u2014 what leaving the "
        f"laboratory looks like in this data ({over[0]['total']} documents "
        f"for {over[0]['name'].lower()}).",
        _anchor(over[0]),
    )


def built_versus_said(rows, context=None) -> Finding | None:
    """The substance-against-attention leaders, when the period is scored."""
    scored = _named([row for row in rows if row.get("sai") is not None])
    if not scored:
        return None
    scored.sort(key=lambda row: -row["sai"])
    leaders = scored[:2]
    return Finding(
        "built_versus_said",
        f"{_join([row['name'] for row in leaders])} lead on substance against "
        f"attention \u2014 more of their evidence is code, filings and awards than "
        f"talk ({leaders[0]['total']} documents for "
        f"{leaders[0]['name'].lower()}).",
        _anchor(leaders[0]),
    )


def movers(rows, context=None) -> Finding | None:
    """The largest share movement against the previous period."""
    moved = _named([row for row in rows if row.get("shift") is not None])
    if not moved:
        return None
    moved.sort(key=lambda row: -row["shift"])
    first = moved[0]
    if first["shift"] <= 0:
        return None
    return Finding(
        "movers",
        f"{first['name']} gained the most ground against the previous period, "
        f"up {first['shift']:.1f} points of its family's share on "
        f"{first['total']} documents.",
        _anchor(first),
    )


RULES = (stage_frontier, federal_money, patent_led, most_evidenced,
         crossing, built_versus_said, movers)

LIMIT = 5


def load_overrides(period: str, root: Path | None = None) -> dict:
    """The owner's edits for one period, or nothing if the file is absent.

    The marketing plan gives the pipeline the draft and Kevin the final text.
    Absent means the drafts ship, so a report stays reproducible from the
    database alone; present means a human has been through it.
    """
    directory = Path(root) if root else config.FINDINGS_DIR
    path = directory / f"{period}.yaml"
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text()) or {}
    if not isinstance(loaded, dict):
        raise OverrideProblem(
            f"{path.name} should be a mapping of rule id to an override, and "
            f"holds {type(loaded).__name__}.")
    known = {rule.__name__ for rule in RULES}
    unknown = [rule_id for rule_id in loaded if rule_id not in known]
    if unknown:
        raise OverrideProblem(
            f"{path.name} names {', '.join(sorted(unknown))}, which no rule "
            f"owns. The rules are: {', '.join(sorted(known))}. An override "
            f"that matches nothing would otherwise sit in the file looking "
            f"applied.")
    return loaded


def compose(rows, context=None, overrides: dict | None = None) -> list[Finding]:
    """Every rule that fires, in ranked order, capped at what a reader reads."""
    overrides = overrides or {}
    found = []
    for rule in RULES:
        edit = overrides.get(rule.__name__, {}) or {}
        if edit.get("drop"):
            continue
        finding = rule(rows, context)
        if finding is None:
            continue
        if edit.get("text"):
            finding = replace(finding, text=str(edit["text"]))
        found.append(finding)
    # The file's own order, when it states one. A reader's first sentence is
    # the owner's call and not the rule order's.
    stated = [rule_id for rule_id in overrides if not (overrides.get(rule_id) or {}).get("drop")]
    if stated:
        found.sort(key=lambda finding: (stated.index(finding.id)
                                        if finding.id in stated else len(stated)))
    return found[:LIMIT]
