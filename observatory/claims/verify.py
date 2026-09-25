# observatory/claims/verify.py
"""Is the quote really in the filing? The one check that makes the model's
output auditable without trusting it."""

from __future__ import annotations

import re
import unicodedata

_QUOTES = {"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-",
           "\u00a0": " "}   # NFKC already maps the non-breaking space; listed so nobody wonders
_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    for src, dst in _QUOTES.items():
        text = text.replace(src, dst)
    return _WS.sub(" ", text).strip()


def verify_quote(quote: str, text: str) -> bool:
    q = normalize(quote)
    return bool(q) and q in normalize(text)
