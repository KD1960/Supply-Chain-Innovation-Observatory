"""An export that arrived without its abstracts has to say so.

ProQuest's RIS export defaults to citation-only: bibliographic fields plus the
indexer's subject terms, and no `AB` tag at all. Every ABI/INFORM export so far
came back that way, so trade press reached the matcher as roughly twenty-six
words of subject headings -- "Supply chains; Inventory; Artificial
intelligence" -- rather than an abstract.

Nothing noticed for months. `manual.haystack` had a keyword fallback built for
it, complete with a comment saying a trade export has no abstract, so the
absence looked like a property of the source rather than a setting on the
export screen. It surfaced only as a side finding of the CRA feasibility test
on 2026-09-03, which measured median words per source to see where CRA could
run at all.

Scopus exports from the same importer carry 39 abstracts in a single file, so
the parser was never the problem.
"""

import pytest

from observatory import manual


def _ris(*records: str) -> str:
    return "\n".join(records)


CITATION_ONLY = """TY  - JOUR
T1  - Target highlights in-stock gains as turnaround plan advances
AN  - 3377785334
JF  - Supply Chain Dive
KW  - Supply chains
KW  - Inventory
ER  -
"""

WITH_ABSTRACT = """TY  - JOUR
T1  - Target highlights in-stock gains as turnaround plan advances
AN  - 3377785334
JF  - Supply Chain Dive
AB  - Target said its in-stock rate improved as the retailer pressed on with a
      turnaround plan centred on inventory discipline and supply chain speed.
KW  - Supply chains
ER  -
"""


def test_an_export_with_no_abstracts_is_reported():
    records = manual.parse_ris(_ris(CITATION_ONLY, CITATION_ONLY))
    assert manual.abstract_coverage(records) == 0.0


def test_an_export_with_abstracts_is_not():
    records = manual.parse_ris(_ris(WITH_ABSTRACT, WITH_ABSTRACT))
    assert manual.abstract_coverage(records) == 1.0


def test_partial_coverage_is_measured_not_rounded():
    records = manual.parse_ris(_ris(WITH_ABSTRACT, CITATION_ONLY))
    assert manual.abstract_coverage(records) == pytest.approx(0.5)


def test_an_empty_export_reports_no_coverage_rather_than_dividing_by_zero():
    assert manual.abstract_coverage([]) is None


def test_the_warning_names_the_source_and_the_setting():
    """A number nobody can act on is not a warning. The message has to say
    which export and which screen to change."""
    line = manual.abstract_warning("abi_inform", "abi_inform-SupplyChainDive-terms1.ris", 0.0)
    assert "abi_inform" in line
    assert "SupplyChainDive" in line
    assert "abstract" in line.lower()


def test_a_well_covered_export_produces_no_warning():
    assert manual.abstract_warning("scopus", "scopus-00207543.ris", 0.97) is None
