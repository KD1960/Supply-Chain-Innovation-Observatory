"""Post cards: one finding, drawn at the sizes a social platform accepts."""

import pytest
from PIL import Image

from observatory import cards, findings


def finding():
    return findings.Finding(
        id="stage_frontier",
        text=("Autonomous trucking is the technology furthest along the pipeline: "
              "12 documents this period, 8 of them company filings from 6 companies."),
        anchor="tech-autonomous-trucking",
        stat="8 of 12 documents are company filings",
        n=12,
    )


def test_the_card_text_carries_the_period_and_the_sample_size():
    """Composed as strings and asserted as strings. A PNG cannot be read back,
    so the words are checked where they can be checked and the drawing is
    checked for the thing a drawing can be checked for -- its size."""
    lines = cards.card_lines(finding(), "2026-Q2")
    assert "2026 Q2" in lines["eyebrow"]
    assert "Autonomous trucking" in lines["body"]
    assert "n = 12" in lines["source"]
    assert "8 of 12" in lines["stat"]


def test_a_linkedin_card_is_written_at_twelve_hundred_by_six_two_seven(tmp_path):
    path = cards.render(finding(), "2026-Q2", "linkedin", tmp_path)
    assert Image.open(path).size == (1200, 627)


def test_a_carousel_card_is_written_at_ten_eighty_by_thirteen_fifty(tmp_path):
    path = cards.render(finding(), "2026-Q2", "portrait", tmp_path)
    assert Image.open(path).size == (1080, 1350)


def test_both_sizes_are_written_for_every_finding(tmp_path):
    written = cards.write_cards(tmp_path, "2026-Q2", [finding(), finding()])
    assert len(written) == 4
    assert all(path.suffix == ".png" for path in written)


def test_the_card_is_named_for_its_period_finding_and_size(tmp_path):
    path = cards.render(finding(), "2026-Q2", "linkedin", tmp_path)
    assert path.name == "2026-Q2-stage_frontier-linkedin.png"


def test_a_missing_font_is_named_rather_than_quietly_replaced(tmp_path):
    """The Ubuntu box that runs CI has no Arial. Falling back to Pillow's
    bitmap default would write a card that looks broken and says nothing about
    why, which is this project's oldest failure mode in a new medium."""
    with pytest.raises(cards.FontsMissing, match="nowhere/Arial.ttf"):
        cards.load_fonts(search=("nowhere/Arial.ttf",))
