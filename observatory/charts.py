"""Charts as inline SVG strings.

Generated in Python rather than by a JavaScript library so the dashboard has no
external dependencies and renders identically offline, forever.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from . import geo

PADDING = 48
AXIS_COLOUR = "#c9cdd2"
TEXT_COLOUR = "#3d4348"


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    label: str = ""
    size: float = 6.0
    colour: str = "#5b7fa6"


def _scale(value: float, low: float, high: float, out_low: float, out_high: float) -> float:
    if high - low == 0:
        return (out_low + out_high) / 2
    return out_low + (value - low) * (out_high - out_low) / (high - low)


def scatter(
    points: list[Point],
    width: int = 720,
    height: int = 440,
    x_label: str = "",
    y_label: str = "",
) -> str:
    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" '
        f'xmlns="http://www.w3.org/2000/svg" role="img">'
    ]
    parts.append(
        f'<line x1="{PADDING}" y1="{height - PADDING}" x2="{width - PADDING}" '
        f'y2="{height - PADDING}" stroke="{AXIS_COLOUR}" />'
        f'<line x1="{PADDING}" y1="{PADDING}" x2="{PADDING}" '
        f'y2="{height - PADDING}" stroke="{AXIS_COLOUR}" />'
    )
    if points:
        xs = [point.x for point in points]
        ys = [point.y for point in points]
        x_low, x_high = min(xs), max(xs)
        y_low, y_high = min(ys), max(ys)
        for point in points:
            cx = _scale(point.x, x_low, x_high, PADDING, width - PADDING)
            cy = _scale(point.y, y_low, y_high, height - PADDING, PADDING)
            parts.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{point.size:.1f}" '
                f'fill="{escape(point.colour, quote=True)}" fill-opacity="0.75">'
                f"<title>{escape(point.label, quote=True)}</title></circle>"
            )
    if x_label:
        parts.append(
            f'<text x="{width / 2:.0f}" y="{height - 12}" text-anchor="middle" '
            f'font-size="12" fill="{TEXT_COLOUR}">{escape(x_label, quote=True)}</text>'
        )
    if y_label:
        parts.append(
            f'<text x="14" y="{height / 2:.0f}" text-anchor="middle" font-size="12" '
            f'fill="{TEXT_COLOUR}" transform="rotate(-90 14 {height / 2:.0f})">'
            f"{escape(y_label, quote=True)}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def build_map(points: list[Point], width: int = 720, height: int = 420) -> str:
    """A US map without a coastline.

    Drawing an accurate outline would mean vendoring geodata; instead each point
    is placed by an equirectangular projection over the continental frame and
    labelled, which answers the question the block asks — which places are
    getting new capability — without pretending to cartographic precision.
    """
    min_lat, max_lat, min_lon, max_lon = geo.CONUS_BOUNDS
    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" '
        f'xmlns="http://www.w3.org/2000/svg" role="img">',
        f'<rect x="{PADDING}" y="{PADDING}" width="{width - 2 * PADDING}" '
        f'height="{height - 2 * PADDING}" fill="#f7f8f9" stroke="{AXIS_COLOUR}" />',
    ]
    for point in points:
        longitude = min(max(point.x, min_lon), max_lon)
        latitude = min(max(point.y, min_lat), max_lat)
        cx = _scale(longitude, min_lon, max_lon, PADDING, width - PADDING)
        cy = _scale(latitude, min_lat, max_lat, height - PADDING, PADDING)
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{point.size:.1f}" '
            f'fill="{escape(point.colour, quote=True)}" fill-opacity="0.6" '
            f'stroke="{escape(point.colour, quote=True)}">'
            f"<title>{escape(point.label, quote=True)}</title></circle>"
        )
    parts.append("</svg>")
    return "".join(parts)


def sparkline(values: list[float | None], width: int = 120, height: int = 28) -> str:
    present = [(index, value) for index, value in enumerate(values) if value is not None]
    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img">'
    ]
    if len(present) >= 2:
        only_values = [value for _, value in present]
        low, high = min(only_values), max(only_values)
        coordinates = " ".join(
            f"{_scale(index, 0, len(values) - 1, 1, width - 1):.1f},"
            f"{_scale(value, low, high, height - 2, 2):.1f}"
            for index, value in present
        )
        parts.append(
            f'<polyline points="{coordinates}" fill="none" '
            f'stroke="#5b7fa6" stroke-width="1.5" />'
        )
    parts.append("</svg>")
    return "".join(parts)
