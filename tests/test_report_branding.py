"""The report's masthead, its explanatory tabs, and its credit line.

Checked on the rendered page rather than the context. The context held the SVG
and the page did not once already, because Jinja autoescaped the markup and the
tests had checked the context -- so they passed while two blocks rendered empty.
"""

import base64
import re

import pytest

from observatory import quarter, store
from observatory.matcher import Observation, Technology, Watchlist


@pytest.fixture()
def conn():
    connection = store.connect(":memory:")
    store.init_schema(connection)
    yield connection
    connection.close()


def _watchlist():
    return Watchlist(version=1, context=("supply chain",), technologies=(Technology(
        id="a", name="Warehouse robotics", family="f", include=("widget",), exclude=(),
        status="active", added_week="2020-W01", patterns_changed_week="2020-W01"),))


def _flat(page):
    """Whitespace-normalised, so an assertion is about the words and not about
    where the template happened to wrap a line."""
    return re.sub(r"\s+", " ", page)


def _page(conn, tmp_path, period="2026-Q2"):
    for day in ("06", "13", "20"):
        store.upsert_observations(conn, [Observation(
            source="arxiv", week="2026-W20", tech_id="a", doc_id=f"d{day}",
            doc_date=f"2026-05-{day}", title="widget", url="https://x.test/widget",
            entity=None, entity_id=None, amount=None, lat=None, lon=None,
            matched_pattern="widget", raw_ref=None)])
    return quarter.render_quarter(conn, period, _watchlist(), tmp_path).read_text()


def _rich_page(conn, tmp_path):
    """Enough evidence, of enough kinds, for both figures to be drawn.

    `substance_rows` needs documents on both axes -- github is substance, hn is
    attention -- and a technology with only preprints sits on neither.
    """
    for day in ("06", "13", "20"):
        for source, prefix in (("github", "g"), ("hn", "h"), ("edgar", "e")):
            store.upsert_observations(conn, [Observation(
                source=source, week="2026-W20", tech_id="a", doc_id=f"{prefix}{day}",
                doc_date=f"2026-05-{day}", title="widget", url="https://x.test/widget",
                entity="Acme", entity_id="1", amount=None, lat=None, lon=None,
                matched_pattern="widget", raw_ref=None)])
    return _page(conn, tmp_path)


# --- 1. the lockup ----------------------------------------------------------


def test_the_brand_lockup_is_embedded_not_linked(conn, tmp_path):
    """A report is one file that gets emailed and opened from a download
    folder. A linked image would be a broken box everywhere but this machine."""
    page = _page(conn, tmp_path)
    assert "data:image/png;base64," in page
    match = re.search(r'src="data:image/png;base64,([A-Za-z0-9+/=]+)"', page)
    assert match, "no embedded logo"
    assert base64.b64decode(match.group(1))[:8] == b"\x89PNG\r\n\x1a\n"


def test_the_lockup_carries_alt_text(conn, tmp_path):
    assert 'alt="W. P. Carey School of Business' in _page(conn, tmp_path)


# --- 2 and 3. the masthead --------------------------------------------------


def test_the_eyebrow_names_the_centre(conn, tmp_path):
    """Written in title case; `.eyebrow` sets `text-transform: uppercase`, so
    it reaches the reader in caps without shouting in the source."""
    page = _page(conn, tmp_path)
    assert ("Produced by the Center for Supply Chain Innovation, Technology, "
            "&amp; Infrastructure") in _flat(page)
    assert "text-transform:uppercase" in re.sub(r"\s+", "", page[:page.index("</style>")])


def test_the_title_spells_out_what_the_report_is(conn, tmp_path):
    """`2026-Q2` alone is a filename, not a title."""
    page = _page(conn, tmp_path)
    assert ("Supply Chain Innovation Observatory &middot; Quarterly Report "
            "&middot; 2026 Q2") in _flat(page)


def test_an_annual_report_says_annual_and_has_no_quarter(conn, tmp_path):
    page = _flat(_page(conn, tmp_path, period="2026"))
    assert "Annual Report &middot; 2026" in page
    assert "Quarterly Report" not in page


# --- 4, 5, 6. the disclosure tabs -------------------------------------------


def test_how_to_read_sits_above_the_numbers(conn, tmp_path):
    page = _page(conn, tmp_path)
    assert "How to read this document" in page
    assert page.index("How to read this document") < page.index("documents matched")


def test_how_to_read_never_links_to_a_section_that_is_not_there(conn, tmp_path):
    """Half this report's sections are conditional -- the substance chart needs
    substance, the money map needs awards, the movers need a comparable previous
    period. A contents list written as though they were always present is a set
    of dead anchors on any sparse quarter."""
    page = _page(conn, tmp_path)
    anchors = set(re.findall(r'<a href="#([a-z-]+)">', page))
    assert {"summary", "what-held"} <= anchors
    for anchor in anchors:
        assert f'id="{anchor}"' in page, f"#{anchor} is a link to nowhere"


def test_the_table_prose_is_behind_a_tab(conn, tmp_path):
    page = _page(conn, tmp_path)
    assert "Table explanation" in page
    # The prose that used to sit loose above the table is inside the tab now.
    body = page[page.index("Table explanation"):]
    assert "percentage of the family's whole supply-chain corpus" in body


def test_a_full_report_links_to_its_figures_and_explains_each(conn, tmp_path):
    page = _rich_page(conn, tmp_path)
    anchors = set(re.findall(r'<a href="#([a-z-]+)">', page))
    assert {"substance", "stage-board"} <= anchors
    for anchor in anchors:
        assert f'id="{anchor}"' in page, f"#{anchor} is a link to nowhere"
    # The tab belongs to the figure, not to the heading. Substance and
    # attention is drawn here and carries one; the Stage Board is withheld in
    # this fixture -- the window has no collected quarters -- so it explains
    # why there is no figure instead of explaining a figure that is absent.
    assert page.count("Figure explanation") == 1
    assert "Withheld." in page[page.index("Stage Board"):]


def test_the_tabs_are_shut_when_the_page_opens(conn, tmp_path):
    """A disclosure tab that ships open is a paragraph with extra chrome."""
    page = _page(conn, tmp_path)
    assert "<details open" not in page


# --- 8. the credit ----------------------------------------------------------


def test_the_report_is_signed(conn, tmp_path):
    page = _page(conn, tmp_path)
    assert "Created and produced by Dr. Kevin Dooley." in page
    assert "kevin.dooley@asu.edu" in page
    assert page.rindex("Created and produced by Dr. Kevin Dooley.") > page.rindex("</table>")
