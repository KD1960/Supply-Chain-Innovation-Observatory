"""Standalone chart files beside the report.

The charts live inline in the HTML, which is right for reading and useless for
putting one in a slide deck. PDF rather than PNG: svglib and reportlab are pure
Python, where every rasteriser available -- cairosvg, rsvg-convert, inkscape --
needs native libraries this project has so far done without.
"""


from observatory import export


def test_a_chart_is_written_beside_the_report(tmp_path):
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">' \
          '<circle cx="50" cy="50" r="10" fill="#A85B12"/></svg>'
    written = export.write_charts(tmp_path, "2026-Q3", {"stage-board": svg})
    assert written
    assert all(path.exists() for path in written)
    suffixes = {path.suffix for path in written}
    assert suffixes == {".svg", ".pdf"}
    assert all("2026-Q3-stage-board" in path.name for path in written)


def test_the_svg_is_written_too(tmp_path):
    """A vector file anyone can open without a converter, and the source the
    PDF was made from."""
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>'
    export.write_charts(tmp_path, "2026-Q3", {"map": svg})
    assert (tmp_path / "charts" / "2026-Q3-map.svg").exists()


def test_a_chart_that_is_absent_writes_nothing(tmp_path):
    """The build map is None on a quarter with nothing located, and an empty
    file is worse than a missing one -- it looks like a chart of nothing."""
    assert export.write_charts(tmp_path, "2026-Q3", {"map": None}) == []


def test_a_chart_that_will_not_convert_still_leaves_its_svg(tmp_path):
    """A report is worth more than an attachment. If the PDF cannot be made the
    vector file is still there and the run carries on."""
    written = export.write_charts(tmp_path, "2026-Q3", {"broken": "<svg>not valid"})
    assert any(path.suffix == ".svg" for path in written)


def test_the_exported_chart_keeps_its_labels(tmp_path):
    """The page numbers its dots and puts the names on hover and in a key. A
    PDF has neither, so the file written for a slide or a paper carries the
    printed labels instead."""
    from observatory import charts
    points = [charts.Point(x=1, y=2, size=5, label="Warehouse robotics", colour="#000")]
    page = charts.scatter(points, numbered=True)
    printable = charts.scatter(points, labels=True)
    export.write_charts(tmp_path, "2026-Q3", {"board": printable})
    import re
    written = (tmp_path / "charts" / "2026-Q3-board.svg").read_text()
    drawn = re.findall(r"<text[^>]*>([^<]+)</text>", written)
    assert "Warehouse robotics" in drawn
    assert "Warehouse robotics" not in re.findall(r"<text[^>]*>([^<]+)</text>", page)
