"""A two-page brief: the quarter for a reader who will not open the report.

The report is 14,000 pixels tall and answers a sceptic. The brief answers a
practitioner: five findings, the table behind them, and what the quarter will
not tell you. Two pages is the format rather than an accident of how much
fitted -- a third page means something has to be cut.

Built from the same `build_context` the HTML uses, so a number in the brief and
a number on the page cannot disagree.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas

ASSET_DIR = Path(__file__).parent / "assets"
REPO = "github.com/KD1960/Supply-Chain-Innovation-Observatory"

INK = "#231F20"
MAROON = "#8C0B42"
MUTED = "#5C6874"

TABLE_ROWS = 8


class BriefOverflow(Exception):
    """More text than the two pages hold.

    reportlab draws past the bottom edge without complaint -- the words are in
    the file and simply not on the paper. Silent truncation is this project's
    oldest failure mode, so the brief refuses rather than quietly losing a
    sentence.
    """

LIMITATIONS = (
    "What this will not tell you. The diffusion end of the pipeline is thin: "
    "company filings and federal awards are a small share of the corpus, so a "
    "technology can be moving without this seeing it yet. Trade press coverage "
    "is partial. Counts are documents matched rather than mentions, and a small "
    "corpus moves by whole percentage points on a single document. Every "
    "sentence here carries the sample it rests on; where the sample is under "
    "three documents, the technology is counted but not named."
)


def compose(context: dict, period: str) -> dict:
    """The brief as text, before any of it is drawn.

    Separated from the drawing because what a PDF says is worth testing and a
    drawn PDF cannot be read back.
    """
    rows = [row for row in context["rows"] if row["total"]][:TABLE_ROWS]
    withheld = None
    if context.get("partial"):
        withheld = (
            f"Scores are withheld this quarter: {context['weeks_run']} of "
            f"{context['weeks_total']} weeks have run, and a score compares a "
            f"period against periods that are complete. The counts stand -- "
            f"they are observations, and only the scores are inferences.")
    elif context.get("short_history"):
        withheld = (
            f"Scores are withheld: {context['window_collected']} of the "
            f"{context['window_total']} quarters a score is computed over were "
            f"collected. The counts stand; only the scores are inferences.")
    return {
        "title": f"Supply Chain Innovation Observatory · Quarterly Brief · "
                 f"{period.replace('-Q', ' Q')}",
        "standfirst": (
            "Which supply chain technologies are being built rather than talked "
            "about, from public data only. Every number below can be traced to "
            "the document that produced it."),
        "findings": [(finding.stat, finding.text) for finding in context["findings"]],
        "rows": rows,
        "withheld": withheld,
        "limitations": LIMITATIONS,
        "provenance": (
            f"Produced by the Center for Supply Chain Innovation, Technology & "
            f"Infrastructure, W. P. Carey School of Business, Arizona State "
            f"University. Lexicon version {context['lexicon_version']}; "
            f"{context['weeks_run']} of {context['weeks_total']} weeks collected. "
            f"Method, data and code: {REPO}"),
    }


def _wrap(canvas, text: str, font: str, size: float, width: float) -> list[str]:
    lines: list[str] = []
    line = ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if canvas.stringWidth(trial, font, size) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _paragraph(canvas, text, x, y, width, font="Helvetica", size=10.5, leading=15,
               colour=INK) -> float:
    canvas.setFont(font, size)
    canvas.setFillColor(colour)
    for line in _wrap(canvas, text, font, size, width):
        canvas.drawString(x, y, line)
        y -= leading
    return y


def _check(y: float, floor: float, what: str) -> None:
    if y < floor:
        raise BriefOverflow(
            f"{what} runs past the bottom of the page. The brief is two pages "
            f"by design; shorten a finding in findings/<period>.yaml, or drop "
            f"one, and rebuild.")


def write(context: dict, period: str, out_dir: Path) -> Path:
    """Draw the brief. Two pages, always."""
    composed = compose(context, period)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"brief-{period}.pdf"
    width, height = letter
    canvas = pdfcanvas.Canvas(str(path), pagesize=letter)
    margin = 54
    inner = width - 2 * margin

    # --- page one: the findings ---
    y = height - margin
    logo = ImageReader(str(ASSET_DIR / "naspo-logo.png"))
    logo_width = 150
    logo_height = logo_width * 139 / 412
    canvas.drawImage(logo, margin, y - logo_height, width=logo_width,
                     height=logo_height, mask="auto")
    y -= logo_height + 26

    canvas.setFont("Helvetica-Bold", 16)
    canvas.setFillColor(INK)
    for line in _wrap(canvas, composed["title"], "Helvetica-Bold", 16, inner):
        canvas.drawString(margin, y, line)
        y -= 20
    y -= 6
    canvas.setStrokeColor(MAROON)
    canvas.setLineWidth(2)
    canvas.line(margin, y, width - margin, y)
    y -= 22

    y = _paragraph(canvas, composed["standfirst"], margin, y, inner,
                   size=11.5, leading=16, colour=MUTED) - 22

    for stat, text in composed["findings"]:
        canvas.setFont("Helvetica-Bold", 13)
        canvas.setFillColor(MAROON)
        for line in _wrap(canvas, stat, "Helvetica-Bold", 13, inner):
            canvas.drawString(margin, y, line)
            y -= 18
        y = _paragraph(canvas, text, margin, y, inner, size=11, leading=15.5) - 20
    _check(y, margin, "The findings")

    canvas.showPage()

    # --- page two: what it rests on ---
    y = height - margin
    canvas.setFont("Helvetica-Bold", 12)
    canvas.setFillColor(INK)
    canvas.drawString(margin, y, "What the quarter held")
    y -= 8
    canvas.setStrokeColor(MAROON)
    canvas.line(margin, y, width - margin, y)
    y -= 20

    columns = (margin, margin + 250, margin + 320, margin + 430)
    canvas.setFont("Helvetica-Bold", 8.5)
    canvas.setFillColor(MUTED)
    for x, label in zip(columns, ("Technology", "Documents", "Stage", "Concentration")):
        canvas.drawString(x, y, label.upper())
    y -= 14
    canvas.setFont("Helvetica", 9.5)
    canvas.setFillColor(INK)
    for row in composed["rows"]:
        canvas.drawString(columns[0], y, row["name"][:44])
        canvas.drawString(columns[1], y, str(row["total"]))
        canvas.drawString(columns[2], y, row["stage"] or "—")
        canvas.drawString(columns[3], y, f"{row['concentration']}% {row['top_family']}")
        y -= 14
    y -= 12

    if composed["withheld"]:
        y = _paragraph(canvas, composed["withheld"], margin, y, inner,
                       font="Helvetica-Oblique") - 14
    y = _paragraph(canvas, composed["limitations"], margin, y, inner) - 20
    y = _paragraph(canvas, composed["provenance"], margin, y, inner, size=9,
                   leading=12, colour=MUTED)
    _check(y, margin - 12, "The second page")

    canvas.showPage()
    canvas.save()
    return path
