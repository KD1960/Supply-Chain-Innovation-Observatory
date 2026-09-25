import pytest
from observatory.trl import schema


def _claim(**over):
    base = {"tech_id": "delivery_drones", "claim_type": "pilots", "actor_type": "user_firm",
            "actor": "Walmart", "setting": "multiple_sites", "quantity": "", "quote": "Walmart is piloting drone delivery at 34 stores.",
            "source_type": "press_release"}
    base.update(over)
    return base


def test_every_claim_type_has_a_band_inside_one_to_nine():
    # "abandons" is contrary evidence, not a band (schema.py docstring); its
    # sentinel (0, 0) is checked separately below.
    for ct in schema.CLAIM_TYPES:
        if ct == "abandons":
            continue
        lo, hi = schema.BAND[ct]
        assert 1 <= lo <= hi <= 9


def test_abandons_is_the_zero_sentinel():
    assert schema.BAND["abandons"] == (0, 0)


def test_bands_are_monotone_in_the_listed_order():
    highs = [schema.BAND[ct][1] for ct in schema.CLAIM_TYPES if ct != "abandons"]
    assert highs == sorted(highs)


def test_validate_accepts_a_well_formed_claim():
    assert schema.validate({"claims": [_claim()]}, ["delivery_drones"]) == [_claim()]


@pytest.mark.parametrize("field,value", [
    ("tech_id", "erp"), ("claim_type", "diffuses"), ("actor_type", "person"), ("setting", "everywhere"),
])
def test_validate_rejects_values_outside_the_closed_sets(field, value):
    with pytest.raises(ValueError):
        schema.validate({"claims": [_claim(**{field: value})]}, ["delivery_drones"])


def test_validate_requires_every_field():
    claim = _claim()
    del claim["quote"]
    with pytest.raises(ValueError, match="quote"):
        schema.validate({"claims": [claim]}, ["delivery_drones"])


def test_claim_id_is_stable_under_whitespace_and_curly_quotes():
    a = schema.claim_id("hn", "hn:1", "delivery_drones", "Walmart  is “piloting” drones")
    b = schema.claim_id("hn", "hn:1", "delivery_drones", 'Walmart is "piloting" drones')
    assert a == b and len(a) == 12
