"""The tracked technologies, on one page, for a class rather than a board.

Appendix A of the report is the artifact a student or an instructor wants and
the least reachable thing in a 14,000-pixel document. This is that appendix as
a page: every active technology, the terms it actually matches, and the version
of the lexicon it was made from.

The terms are expanded from the patterns rather than written beside them, for
the same reason Appendix A generates its descriptions: a definition kept by
hand drifts away from what the entry matches, and then the sheet is teaching
something the instrument does not do. What the expander cannot read cleanly is
printed as written -- guessing at a pattern would be the drift this avoids.
"""

from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas

ASSET_DIR = Path(__file__).parent / "assets"
REPO = "github.com/KD1960/Supply-Chain-Innovation-Observatory"

INK = "#231F20"
MAROON = "#8C0B42"
MUTED = "#5C6874"

# Three reads as a definition; the fourth is a list.
TERMS_SHOWN = 3

# What is left after expansion when a pattern is more than alternatives and
# optional pieces. Any of these means the expansion cannot be trusted.
LEFTOVER = re.compile(r"[\\{}*+^$.\[\]()|?]")


class SheetOverflow(Exception):
    """More technologies than one page holds."""


def _variants(text: str) -> list[str]:
    """Every string a pattern of alternations and optional groups can match."""
    match = re.search(r"\(([^()]*)\)(\?)?", text)
    if not match:
        return [text]
    body, optional = match.group(1), match.group(2)
    alternatives = body.split("|")
    # A group welded to the word before it is a suffix -- robot(s|ics)? -- and
    # its empty form is the bare singular, which says nothing the suffixed
    # forms do not. A group standing on its own is a word that may be absent,
    # and both readings are real terms.
    attached = match.start() > 0 and text[match.start() - 1].isalnum()
    if optional and not attached:
        alternatives.append("")
    expanded = []
    for alternative in alternatives:
        expanded.extend(_variants(text[:match.start()] + alternative + text[match.end():]))
    return expanded


def expand(pattern: str) -> list[str]:
    """A lexicon pattern as the terms a reader would recognise."""
    text = pattern.replace(r"\b", "")
    text = re.sub(r"\[[-\s]+\]", " ", text)        # [- ] is hyphen-or-space
    text = re.sub(r"([A-Za-z])\?", r"\1", text)     # AMRs? -> AMRs
    terms = []
    for variant in _variants(text):
        cleaned = re.sub(r"\s+", " ", variant).strip()
        if cleaned and cleaned not in terms:
            terms.append(cleaned)
    if not terms or any(LEFTOVER.search(term) for term in terms):
        return [pattern]
    return terms


def terms_of(technology) -> str:
    """The first few terms, as one line.

    Readable ones first. Seven of the forty-eight entries lead with a proximity
    pattern -- agentic ai within eighty characters of procurement -- and taking
    the patterns in order would hand the reader that and hide the two plain
    terms behind it. A technology with nothing readable shows its pattern as
    written, because saying nothing would claim it matches nothing.
    """
    terms: list[str] = []
    for pattern in technology.include:
        expanded = expand(pattern)
        # Readable, rather than merely different from what went in: a plain
        # pattern expands to itself and is perfectly readable.
        if any(LEFTOVER.search(term) for term in expanded):
            continue
        for term in expanded:
            if term not in terms:
                terms.append(term)
            if len(terms) >= TERMS_SHOWN:
                return ", ".join(terms)
    if terms:
        return ", ".join(terms)
    return technology.include[0] if technology.include else ""


def trim(text: str, fits) -> str:
    """The terms line, cut at a term boundary when it will not fit.

    `fits` answers whether a string is narrow enough. Cutting characters off
    the end instead produced lines like "generative ai in supply chain,
    generative ai in l", which reads as a mistake rather than as a list that
    goes on.
    """
    if fits(text):
        return text
    terms = [term.strip() for term in text.split(",")]
    while len(terms) > 1:
        terms.pop()
        candidate = ", ".join(terms) + "\u2026"
        if fits(candidate):
            return candidate
    cut = terms[0]
    while cut and not fits(cut + "\u2026"):
        cut = cut[:-1]
    return cut + "\u2026"


def compose(watchlist, period: str) -> dict:
    """The sheet as text, before any of it is drawn."""
    technologies = sorted(watchlist.active, key=lambda item: item.name)
    return {
        "title": f"Supply Chain Innovation Observatory · Tracked Technologies · "
                 f"{period.replace('-Q', ' Q')}",
        "standfirst": (
            "Every technology this Observatory watches, and the terms a document "
            "has to use to count as evidence for it. A term counts only where the "
            "document also uses supply chain language, so “computer vision” in a "
            "paper about faces is not a match."),
        "technologies": [
            {"name": technology.name, "terms": terms_of(technology)}
            for technology in technologies],
        "provenance": (
            f"Lexicon version {watchlist.version}, {len(technologies)} technologies, "
            f"as of {period.replace('-Q', ' Q')}. The list changes: entries are "
            f"added, tightened and retired on audit evidence, and the version above "
            f"says which state this page is. Method, data and code: {REPO}"),
    }


def write(watchlist, period: str, out_dir: Path) -> Path:
    """Draw the sheet. One page, always."""
    composed = compose(watchlist, period)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"technologies-{period}.pdf"
    width, height = letter
    canvas = pdfcanvas.Canvas(str(path), pagesize=letter)
    margin = 40
    inner = width - 2 * margin

    y = height - margin
    logo = ImageReader(str(ASSET_DIR / "naspo-logo.png"))
    logo_width = 120
    canvas.drawImage(logo, margin, y - logo_width * 139 / 412, width=logo_width,
                     height=logo_width * 139 / 412, mask="auto")
    y -= logo_width * 139 / 412 + 18

    canvas.setFont("Helvetica-Bold", 13)
    canvas.setFillColor(INK)
    canvas.drawString(margin, y, composed["title"])
    y -= 6
    canvas.setStrokeColor(MAROON)
    canvas.setLineWidth(1.5)
    canvas.line(margin, y, width - margin, y)
    y -= 14

    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(MUTED)
    line = ""
    for word in composed["standfirst"].split():
        trial = f"{line} {word}".strip()
        if canvas.stringWidth(trial, "Helvetica", 8.5) <= inner or not line:
            line = trial
        else:
            canvas.drawString(margin, y, line)
            y -= 11
            line = word
    canvas.drawString(margin, y, line)
    y -= 18

    # Two columns: forty-eight entries down one column would need six-point
    # type, and a sheet nobody can read is not a sheet.
    top = y
    column_width = (inner - 24) / 2
    columns = (margin, margin + column_width + 24)
    entries = composed["technologies"]
    half = (len(entries) + 1) // 2
    floor = margin + 46
    for index, column in enumerate(columns):
        y = top
        for entry in entries[index * half:(index + 1) * half]:
            canvas.setFont("Helvetica-Bold", 8.5)
            canvas.setFillColor(INK)
            canvas.drawString(column, y, entry["name"][:52])
            y -= 10
            canvas.setFont("Helvetica", 7.5)
            canvas.setFillColor(MUTED)
            canvas.drawString(column, y, trim(
                entry["terms"],
                lambda text: canvas.stringWidth(text, "Helvetica", 7.5) <= column_width))
            y -= 13
        if y < floor:
            raise SheetOverflow(
                f"{len(entries)} technologies do not fit on one page. The sheet "
                f"is one page by design: retire an entry, or split the sheet by "
                f"family and say which family each page is.")

    canvas.setStrokeColor(MAROON)
    canvas.setLineWidth(0.75)
    canvas.line(margin, margin + 34, width - margin, margin + 34)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    y = margin + 24
    line = ""
    for word in composed["provenance"].split():
        trial = f"{line} {word}".strip()
        if canvas.stringWidth(trial, "Helvetica", 7.5) <= inner or not line:
            line = trial
        else:
            canvas.drawString(margin, y, line)
            y -= 10
            line = word
    canvas.drawString(margin, y, line)

    canvas.showPage()
    canvas.save()
    return path
