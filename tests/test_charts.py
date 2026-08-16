from observatory import charts


def points():
    return [
        charts.Point(x=1.0, y=2.0, label="alpha"),
        charts.Point(x=3.0, y=-1.0, label="beta"),
        charts.Point(x=2.0, y=0.5, label="gamma"),
    ]


def test_scatter_returns_an_svg_element():
    svg = charts.scatter(points())
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")


def test_scatter_draws_one_circle_per_point():
    assert charts.scatter(points()).count("<circle") == 3


def test_scatter_labels_are_escaped():
    svg = charts.scatter([charts.Point(1.0, 1.0, label='rob"ots & <carts>')])
    assert "&amp;" in svg and "&lt;carts&gt;" in svg
    assert "<carts>" not in svg


def test_scatter_never_references_an_external_resource():
    # The opening tag carries the SVG xmlns, which is an identifier and not a
    # fetched resource. Everything after it must be free of URLs.
    body = charts.scatter(points()).split(">", 1)[1]
    assert "http://" not in body and "https://" not in body


def test_scatter_of_identical_points_does_not_divide_by_zero():
    svg = charts.scatter([charts.Point(1.0, 1.0, "a"), charts.Point(1.0, 1.0, "b")])
    assert "<circle" in svg
    assert "nan" not in svg.lower()


def test_scatter_handles_an_empty_series():
    assert "<svg" in charts.scatter([])


def test_sparkline_draws_a_polyline_through_every_value():
    svg = charts.sparkline([1.0, 2.0, 1.5, 3.0])
    assert "<polyline" in svg
    assert svg.count(",") >= 4


def test_sparkline_skips_missing_values_without_crashing():
    assert "<polyline" in charts.sparkline([1.0, None, 3.0])


def test_sparkline_of_nothing_is_still_valid_svg():
    assert charts.sparkline([]).startswith("<svg")
