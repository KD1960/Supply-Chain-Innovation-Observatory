"""One finding, drawn at the sizes a social platform will take.

A post is one click from the report and most people will not click, so the
post has to carry the whole finding. These cards are that: the sentence, the
number it rests on, and the line saying where it came from and how big the
sample was.

Drawn with Pillow rather than converted from the report's SVG. `export.py`
refused PNG because every rasteriser it could reach -- cairosvg, rsvg-convert,
inkscape -- needs native libraries, and reportlab's own renderPM turns out to
need cairo too. Pillow needs none: it is a wheel like any other. That was the
condition the refusal was waiting on.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config

ASSET_DIR = Path(__file__).parent / "assets"

# 1200x627 is what LinkedIn shows beside a link; 1080x1350 is the tall crop a
# carousel post uses. Anything else gets cropped by the platform, and a
# cropped card loses its source line first.
SIZES: dict[str, tuple[int, int]] = {
    "linkedin": (1200, 627),
    "portrait": (1080, 1350),
}

# Arial is the ASU brand face and is on the machine these are made on. The two
# after it are what a Linux box has -- CI runs on Ubuntu, which has no Arial --
# and are metrically close enough that a card made there is still legible.
FONT_SEARCH: tuple[str, ...] = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)

INK = "#231F20"        # the lockup's own ink
MAROON = "#8C0B42"     # and its maroon
MUTED = "#5C6874"
GROUND = "#F6F7F9"     # the report's ground; the lockup is dark on transparent


class FontsMissing(Exception):
    """No usable font on this machine."""


def _bold(path: Path) -> Path:
    """The bold cut beside a regular one, when the family ships a separate file."""
    for candidate in (path.with_name(path.stem + " Bold" + path.suffix),
                      path.with_name(path.stem.replace("-Regular", "-Bold") + path.suffix),
                      path.with_name(path.stem + "-Bold" + path.suffix)):
        if candidate.exists():
            return candidate
    return path


def load_fonts(search: tuple[str, ...] = FONT_SEARCH) -> tuple[Path, Path]:
    """The regular and bold faces to draw with.

    Raises rather than falling back to Pillow's bitmap default. A card drawn in
    the default font looks broken and says nothing about why, and silent
    degradation is the failure this project keeps paying for.
    """
    for name in search:
        path = Path(name)
        if path.exists():
            return path, _bold(path)
    raise FontsMissing(
        "No usable font found. Tried: " + ", ".join(search) + ". Install one of "
        "them, or add the path of a TrueType face to cards.FONT_SEARCH.")


def card_lines(finding, period: str) -> dict[str, str]:
    """The words on the card, separated from the drawing of them.

    A PNG cannot be read back, so what a test can check about a card is its
    size. Composing the text first means the wording is checkable where
    wording is checkable.
    """
    return {
        "eyebrow": f"Supply Chain Innovation Observatory · {period.replace('-Q', ' Q')}",
        "stat": finding.stat or "",
        "body": finding.text,
        "source": (f"ASU Observatory · {period} · n = {finding.n} · "
                   f"public data, every number traceable"),
    }


def _wrap(draw, text: str, font, width: int) -> list[str]:
    """Greedy wrap measured in drawn pixels rather than characters."""
    if not text:
        return []
    lines: list[str] = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            trial = f"{line} {word}".strip()
            if draw.textlength(trial, font=font) <= width or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def render(finding, period: str, size: str, out_dir: Path) -> Path:
    """Draw one finding at one size, and return the file."""
    if size not in SIZES:
        raise ValueError(f"{size} is not a card size. Known: {', '.join(SIZES)}.")
    width, height = SIZES[size]
    regular, bold = load_fonts()
    scale = width / 1200
    lines = card_lines(finding, period)

    image = Image.new("RGB", (width, height), GROUND)
    draw = ImageDraw.Draw(image)
    margin = int(64 * scale)
    inner = width - 2 * margin

    eyebrow_font = ImageFont.truetype(str(bold), int(22 * scale))
    stat_font = ImageFont.truetype(str(bold), int(52 * scale))
    body_font = ImageFont.truetype(str(regular), int(34 * scale))
    source_font = ImageFont.truetype(str(regular), int(20 * scale))

    y = margin
    draw.text((margin, y), lines["eyebrow"].upper(), font=eyebrow_font, fill=MAROON)
    y += int(40 * scale)
    draw.line([(margin, y), (width - margin, y)], fill=MAROON, width=max(2, int(3 * scale)))
    y += int(44 * scale)

    for line in _wrap(draw, lines["stat"], stat_font, inner):
        draw.text((margin, y), line, font=stat_font, fill=INK)
        y += int(64 * scale)
    y += int(16 * scale)

    for line in _wrap(draw, lines["body"], body_font, inner):
        draw.text((margin, y), line, font=body_font, fill=INK)
        y += int(46 * scale)

    logo = Image.open(ASSET_DIR / "naspo-logo.png").convert("RGBA")
    logo_width = int(230 * scale)
    logo = logo.resize((logo_width, round(logo.height * logo_width / logo.width)))
    image.paste(logo, (width - margin - logo.width, height - margin - logo.height), logo)

    draw.text((margin, height - margin - int(18 * scale)), lines["source"],
              font=source_font, fill=MUTED)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{period}-{finding.id}-{size}.png"
    image.save(path, "PNG")
    return path


def write_cards(out_dir: Path, period: str, found) -> list[Path]:
    """Every finding at every size."""
    directory = Path(out_dir)
    return [render(finding, period, size, directory)
            for finding in found for size in SIZES]


def cards_dir(out_dir: Path | None = None) -> Path:
    return Path(out_dir or config.OUTPUT_DIR) / "cards"
