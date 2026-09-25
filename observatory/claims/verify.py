# observatory/claims/verify.py
"""Is the quote really in the filing? The one check that makes the model's
output auditable without trusting it."""

from __future__ import annotations

from ..textnorm import normalize

__all__ = ["normalize", "verify_quote"]


def verify_quote(quote: str, text: str) -> bool:
    q = normalize(quote)
    return bool(q) and q in normalize(text)
