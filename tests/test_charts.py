import re

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


def test_scatter_colour_is_escaped():
    svg = charts.scatter([charts.Point(1.0, 1.0, label="ok", colour='red" onmouseover="alert(1)"')])
    # The colour string must be escaped so that quotes don't break out of the attribute
    assert 'fill="red" onmouseover=' not in svg
    assert "&quot;" in svg
    assert 'red&quot; onmouseover=' in svg


def test_scatter_axis_labels_are_escaped():
    svg = charts.scatter(
        [charts.Point(1.0, 1.0, label="test")],
        x_label='X <label>',
        y_label='Y & "test"'
    )
    assert "&lt;label&gt;" in svg
    assert "&amp;" in svg
    assert "&quot;" in svg
    assert "<label>" not in svg


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


def test_build_map_returns_svg_with_a_circle_per_point():
    svg = charts.build_map([
        charts.Point(x=-111.66, y=34.27, label="Arizona", size=8.0),
        charts.Point(x=-75.53, y=42.95, label="New York", size=4.0),
    ])
    assert svg.startswith("<svg")
    assert svg.count("<circle") == 2


def test_build_map_places_west_left_of_east():
    """Longitude runs west-to-east, so a more negative longitude sits further left."""
    svg = charts.build_map([
        charts.Point(x=-124.0, y=45.0, label="west"),
        charts.Point(x=-70.0, y=45.0, label="east"),
    ])
    xs = [float(v) for v in re.findall(r'<circle cx="([-\d.]+)"', svg)]
    assert xs[0] < xs[1]


def test_build_map_places_north_above_south():
    svg = charts.build_map([
        charts.Point(x=-100.0, y=48.0, label="north"),
        charts.Point(x=-100.0, y=26.0, label="south"),
    ])
    ys = [float(v) for v in re.findall(r'cy="([-\d.]+)"', svg)]
    assert ys[0] < ys[1]


def test_build_map_clamps_points_outside_the_continental_frame():
    svg = charts.build_map([charts.Point(x=-152.28, y=64.07, label="Alaska")])
    assert "<circle" in svg
    assert "nan" not in svg.lower()
    radii = re.findall(r'<circle[^>]*\br="([^"]+)"', svg)
    assert radii
    for value in radii:
        float(value)  # raises ValueError if r ever renders as a complex number


def test_build_map_of_nothing_is_still_valid_svg():
    assert charts.build_map([]).startswith("<svg")


def test_build_map_escapes_labels():
    svg = charts.build_map([charts.Point(x=-100.0, y=40.0, label='<b>&"')])
    assert "&lt;b&gt;" in svg and "<b>" not in svg


def test_a_scatter_can_draw_the_parity_diagonal():
    """Substance against attention is only readable with the line where they
    are equal: above it a technology has more being built than said about it."""
    svg = charts.scatter([charts.Point(x=1, y=2, size=4, label="a", colour="#000")],
                         diagonal=True)
    assert "<line" in svg


def test_a_scatter_omits_the_diagonal_unless_asked():
    svg = charts.scatter([charts.Point(x=1, y=2, size=4, label="a", colour="#000")])
    assert svg.count("<line") == charts.scatter(
        [charts.Point(x=1, y=2, size=4, label="a", colour="#000")]).count("<line")
    assert "stroke-dasharray" not in svg


# --- labels and the parity line ---------------------------------------------

def test_a_scatter_can_print_labels_beside_its_points():
    """A hover title is invisible in a PDF and on paper, and these charts are
    now exported to both."""
    svg = charts.scatter([charts.Point(x=1, y=2, size=4, label="Warehouse robotics",
                                       colour="#000")], labels=True)
    assert "<text" in svg
    assert "Warehouse robotics" in svg


def test_a_label_is_trimmed_so_it_does_not_run_off_the_chart():
    long_name = "General-purpose and humanoid robots in logistics and warehousing"
    svg = charts.scatter([charts.Point(x=1, y=2, size=4, label=long_name, colour="#000")],
                         labels=True)
    import re
    drawn = re.findall(r"<text[^>]*>([^<]+)</text>", svg)
    assert any(len(text) <= charts.LABEL_LIMIT + 1 for text in drawn)


def test_labels_are_off_unless_asked_for():
    svg = charts.scatter([charts.Point(x=1, y=2, size=4, label="a", colour="#000")])
    assert "<text" not in svg or "a</text>" not in svg


def test_the_diagonal_can_carry_a_meaning_at_each_end():
    """A dashed line with nothing said about it is decoration. What matters is
    which side of it a technology sits on."""
    svg = charts.scatter([charts.Point(x=1, y=2, size=4, label="a", colour="#000")],
                         diagonal=True, above="more built than said",
                         below="more said than built")
    assert "more built than said" in svg
    assert "more said than built" in svg


def test_the_diagonal_has_no_captions_unless_given():
    svg = charts.scatter([charts.Point(x=1, y=2, size=4, label="a", colour="#000")],
                         diagonal=True)
    assert "stroke-dasharray" in svg


# --- labels that do not sit on top of each other ----------------------------

def test_labels_that_would_collide_are_moved_apart():
    """Fourteen points on a chart put several at nearly the same height, and
    two labels at the same y overprint into something unreadable."""
    points = [charts.Point(x=1, y=1 + n * 0.001, size=4, label=f"technology {n}",
                           colour="#000") for n in range(6)]
    svg = charts.scatter(points, labels=True)
    import re
    ys = [float(y) for y in re.findall(r'<text x="[^"]+" y="([\d.]+)"', svg)]
    ys.sort()
    assert all(b - a >= charts.LABEL_GAP - 0.01 for a, b in zip(ys, ys[1:])), ys


def test_a_label_that_cannot_be_placed_is_dropped_and_counted():
    """Better a dot with no label than two labels on top of each other. The
    caller is told how many, so a thinned chart never passes as a full one."""
    points = [charts.Point(x=1, y=1, size=4, label=f"t{n}", colour="#000")
              for n in range(40)]
    svg, dropped = charts.scatter_with_report(points, labels=True)
    assert dropped > 0
    assert svg.count("<circle") == 40


def test_nothing_is_dropped_when_there_is_room():
    points = [charts.Point(x=n, y=n, size=4, label=f"t{n}", colour="#000")
              for n in range(5)]
    _, dropped = charts.scatter_with_report(points, labels=True)
    assert dropped == 0
