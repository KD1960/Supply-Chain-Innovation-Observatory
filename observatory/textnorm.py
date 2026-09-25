# observatory/textnorm.py
"""Text normalization shared outside `observatory/claims/` (spec C5): curly
quotes, whitespace, and unicode form, with nothing else in the module so
`trl/` can depend on it without pulling in the claims package."""

from __future__ import annotations

import re
import unicodedata

_QUOTES = {"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-",
           " ": " "}   # NFKC already maps the non-breaking space; listed so nobody wonders
_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    for src, dst in _QUOTES.items():
        text = text.replace(src, dst)
    return _WS.sub(" ", text).strip()
