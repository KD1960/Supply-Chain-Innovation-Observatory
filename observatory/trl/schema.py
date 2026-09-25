# observatory/trl/schema.py
"""What a TRL claim is. Closed vocabularies on purpose (spec §4): the argument
should be about the evidence, not the words used to code it.

A claim is one statement, in one document, about one tracked technology,
saying what someone did with it. Source type is a feature, not the label (C3).
"""

from __future__ import annotations

import hashlib
from typing import Sequence

from ..textnorm import normalize

CLAIM_TYPES = ("proposes", "simulates", "prototypes", "pilots", "demonstrates_in_operation",
               "sells", "buys", "operates_at_scale", "abandons")
# (low, high) TRL each claim type is evidence for. "abandons" is evidence
# that the level was NOT held: the scorer treats it as a contrary claim.
BAND = {
    "proposes": (1, 2), "simulates": (2, 3), "prototypes": (4, 5), "pilots": (5, 6),
    "demonstrates_in_operation": (7, 8), "sells": (7, 8), "buys": (7, 8),
    "operates_at_scale": (9, 9), "abandons": (0, 0),
}
ACTOR_TYPES = ("university", "startup", "incumbent_vendor", "user_firm", "government", "analyst", "unclear")
SETTINGS = ("lab", "test_site", "one_site", "multiple_sites", "network_wide", "unclear")
SOURCE_TYPES = ("paper", "patent", "filing", "press_release", "trade_article", "code_repository",
                "job_posting", "analyst_note", "funding_record", "government_record", "forum_post")

FIELDS = ("tech_id", "claim_type", "actor_type", "actor", "setting", "quantity", "quote", "source_type")


def response_schema(tech_ids: Sequence[str]) -> dict:
    """The JSON schema the model is held to for one document."""
    return {
        "type": "object",
        "properties": {"claims": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "tech_id": {"type": "string", "enum": list(tech_ids)},
                "claim_type": {"type": "string", "enum": list(CLAIM_TYPES)},
                "actor_type": {"type": "string", "enum": list(ACTOR_TYPES)},
                "actor": {"type": "string"},
                "setting": {"type": "string", "enum": list(SETTINGS)},
                "quantity": {"type": "string"},
                "quote": {"type": "string"},
                "source_type": {"type": "string", "enum": list(SOURCE_TYPES)},
            },
            "required": list(FIELDS), "additionalProperties": False}}},
        "required": ["claims"], "additionalProperties": False,
    }


def validate(payload: dict, tech_ids: Sequence[str]) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("claims"), list):
        raise ValueError("payload has no 'claims' list")
    allowed = set(tech_ids)
    for i, claim in enumerate(payload["claims"]):
        if not isinstance(claim, dict):
            raise ValueError(f"claim {i}: not an object")
        for field in FIELDS:
            if field not in claim:
                raise ValueError(f"claim {i}: missing {field}")
        checks = (("tech_id", allowed), ("claim_type", CLAIM_TYPES), ("actor_type", ACTOR_TYPES),
                  ("setting", SETTINGS), ("source_type", SOURCE_TYPES))
        for field, closed in checks:
            if claim[field] not in closed:
                raise ValueError(f"claim {i}: {field} {claim[field]!r} is not allowed")
    return payload["claims"]


def claim_id(source: str, doc_id: str, tech_id: str, quote: str) -> str:
    digest = hashlib.sha1(f"{source}|{doc_id}|{tech_id}|{normalize(quote)}".encode("utf8"))
    return digest.hexdigest()[:12]
