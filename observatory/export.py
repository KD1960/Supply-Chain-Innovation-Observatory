"""Standalone chart files beside the report.

The charts live inline in the HTML, which is right for reading and useless for
putting one in a slide deck or a paper.

PDF rather than PNG, deliberately. Every rasteriser available -- cairosvg,
rsvg-convert, inkscape -- needs native libraries, and this project has so far
needed none; svglib and reportlab are pure Python. The SVG is written beside
the PDF as well, because it is the source the PDF came from and anything can
open it.
"""

from __future__ import annotations

from pathlib import Path


def write_charts(out_dir: Path, period: str, charts: dict[str, str | None]) -> list[Path]:
    """Write each chart as SVG and, where it converts, as PDF.

    A chart that is None writes nothing: the build map is absent on a quarter
    with nothing located, and an empty file reads as a chart of nothing rather
    than as a chart that was never made.
    """
    directory = Path(out_dir) / "charts"
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, svg in charts.items():
        if not svg:
            continue
        svg_path = directory / f"{period}-{name}.svg"
        svg_path.write_text(str(svg))
        written.append(svg_path)
        pdf_path = directory / f"{period}-{name}.pdf"
        try:
            from reportlab.graphics import renderPDF
            from svglib.svglib import svg2rlg

            drawing = svg2rlg(str(svg_path))
            if drawing is None:
                raise ValueError("svglib could not read the drawing")
            renderPDF.drawToFile(drawing, str(pdf_path))
            written.append(pdf_path)
        except Exception as error:
            # A report is worth more than an attachment. Say it and carry on.
            print(f"  chart {name}: no PDF written ({type(error).__name__}: {error})")
    return written
