# observatory/claims/schema.py
"""What a claim is, and the schema the model is held to.

A claim is one statement by one filer about one technology in one filing.
The closed sets are small on purpose: role and stance are the two things a
reader argues about, and an open vocabulary would make the argument about
the vocabulary instead.
"""

from __future__ import annotations

import hashlib
from typing import Sequence

from .verify import normalize

ROLES = ("user", "seller", "both", "unclear")
STANCES = ("plans", "pilots", "uses", "scaled", "dropped", "unclear")
STANCE_ORDER = {"plans": 0, "pilots": 1, "uses": 2, "scaled": 3}

_WINDOWED_FIELDS = ("tech_id", "role", "stance", "scope", "quote", "window_id")
_OPEN_FIELDS = ("technology", "role", "stance", "quote", "item")


def windowed_schema(tech_ids: Sequence[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tech_id": {"type": "string", "enum": list(tech_ids)},
                        "role": {"type": "string", "enum": list(ROLES)},
                        "stance": {"type": "string", "enum": list(STANCES)},
                        "scope": {"type": "string"},
                        "quote": {"type": "string"},
                        "window_id": {"type": "integer"},
                    },
                    "required": list(_WINDOWED_FIELDS),
                    "additionalProperties": False,
                },
            }
        },
        "required": ["claims"],
        "additionalProperties": False,
    }


def open_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "technology": {"type": "string"},
                        "role": {"type": "string", "enum": list(ROLES)},
                        "stance": {"type": "string", "enum": list(STANCES)},
                        "quote": {"type": "string"},
                        "item": {"type": "string"},
                    },
                    "required": list(_OPEN_FIELDS),
                    "additionalProperties": False,
                },
            }
        },
        "required": ["claims"],
        "additionalProperties": False,
    }


def _claims_list(payload: dict) -> list:
    if not isinstance(payload, dict) or not isinstance(payload.get("claims"), list):
        raise ValueError("payload has no 'claims' list")
    return payload["claims"]


def validate_windowed(payload: dict, tech_ids: Sequence[str]) -> list[dict]:
    allowed = set(tech_ids)
    claims = _claims_list(payload)
    for i, claim in enumerate(claims):
        if not isinstance(claim, dict):
            raise ValueError(f"claim {i}: not an object")
        for field in _WINDOWED_FIELDS:
            if field not in claim:
                raise ValueError(f"claim {i}: missing {field}")
        if claim["tech_id"] not in allowed:
            raise ValueError(f"claim {i}: tech_id {claim['tech_id']!r} is not an active technology")
        if claim["role"] not in ROLES:
            raise ValueError(f"claim {i}: role {claim['role']!r}")
        if claim["stance"] not in STANCES:
            raise ValueError(f"claim {i}: stance {claim['stance']!r}")
        if not isinstance(claim["window_id"], int):
            raise ValueError(f"claim {i}: window_id must be an integer")
    return claims


def validate_open(payload: dict) -> list[dict]:
    claims = _claims_list(payload)
    for i, claim in enumerate(claims):
        if not isinstance(claim, dict):
            raise ValueError(f"claim {i}: not an object")
        for field in _OPEN_FIELDS:
            if field not in claim:
                raise ValueError(f"claim {i}: missing {field}")
        if claim["role"] not in ROLES:
            raise ValueError(f"claim {i}: role {claim['role']!r}")
        if claim["stance"] not in STANCES:
            raise ValueError(f"claim {i}: stance {claim['stance']!r}")
    return claims


def claim_id(cik: str, accession: str, tech_key: str, quote: str) -> str:
    """Stable across models and reads: the same filer, filing, technology and
    quote give the same id, so verdicts coded once apply to every run that
    produced that claim."""
    digest = hashlib.sha1(f"{cik}|{accession}|{tech_key}|{normalize(quote)}".encode("utf8"))
    return digest.hexdigest()[:12]
