import pytest

from observatory.claims import schema


def test_windowed_schema_binds_tech_id_to_the_given_ids_and_closes_every_object():
    s = schema.windowed_schema(["warehouse_robotics", "erp"])
    item = s["properties"]["claims"]["items"]
    assert item["properties"]["tech_id"]["enum"] == ["warehouse_robotics", "erp"]
    assert item["properties"]["role"]["enum"] == list(schema.ROLES)
    assert item["properties"]["stance"]["enum"] == list(schema.STANCES)
    assert item["additionalProperties"] is False
    assert s["additionalProperties"] is False
    assert set(item["required"]) == {"tech_id", "role", "stance", "scope", "quote", "window_id"}


def test_open_schema_has_free_text_technology_and_closed_role_and_stance():
    s = schema.open_schema()
    item = s["properties"]["claims"]["items"]
    assert item["properties"]["technology"] == {"type": "string"}
    assert item["properties"]["role"]["enum"] == list(schema.ROLES)
    assert set(item["required"]) == {"technology", "role", "stance", "quote", "item"}


def test_validate_windowed_accepts_good_claims_and_names_the_bad_field():
    good = {"claims": [{"tech_id": "erp", "role": "user", "stance": "uses",
                        "scope": "all stores", "quote": "We use ERP.", "window_id": 3}]}
    assert schema.validate_windowed(good, ["erp"]) == good["claims"]
    bad_stance = {"claims": [{"tech_id": "erp", "role": "user", "stance": "loves",
                              "scope": "", "quote": "q", "window_id": 0}]}
    with pytest.raises(ValueError, match="stance"):
        schema.validate_windowed(bad_stance, ["erp"])
    bad_tech = {"claims": [{"tech_id": "nope", "role": "user", "stance": "uses",
                            "scope": "", "quote": "q", "window_id": 0}]}
    with pytest.raises(ValueError, match="tech_id"):
        schema.validate_windowed(bad_tech, ["erp"])
    with pytest.raises(ValueError, match="claims"):
        schema.validate_windowed({"nope": []}, ["erp"])


def test_validate_open_requires_every_field():
    with pytest.raises(ValueError, match="item"):
        schema.validate_open({"claims": [{"technology": "x", "role": "user", "stance": "uses", "quote": "q"}]})


def test_validators_refuse_a_claim_that_is_not_an_object():
    for bad in (None, 5, True, "text", ["tech_id"]):
        with pytest.raises(ValueError, match="not an object"):
            schema.validate_windowed({"claims": [bad]}, ["erp"])
        with pytest.raises(ValueError, match="not an object"):
            schema.validate_open({"claims": [bad]})


def test_claim_id_is_stable_across_whitespace_and_quote_style():
    a = schema.claim_id("0000104169", "0000104169-26-000055", "erp", "We  use “ERP” systems.")
    b = schema.claim_id("0000104169", "0000104169-26-000055", "erp", 'We use "ERP" systems.')
    assert a == b
    assert len(a) == 12
    assert a != schema.claim_id("0000104169", "0000104169-26-000055", "wms", "We use ERP systems.")
