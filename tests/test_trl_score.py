import datetime as dt
from observatory.trl import score

AS_OF = dt.date(2026, 9, 30)
W = score.load_weights()


def claim(ct, actor="user_firm", src="press_release", days_ago=30, verified=True, setting="one_site", cid=None):
    return {"claim_id": cid or f"{ct}-{actor}-{days_ago}", "tech_id": "delivery_drones", "claim_type": ct,
            "actor_type": actor, "actor": "x", "setting": setting, "quantity": "", "quote": "q",
            "source_type": src, "doc_date": (AS_OF - dt.timedelta(days=days_ago)).isoformat(),
            "quote_verified": verified}


def test_no_claims_gives_no_estimate():
    e = score.estimate([], AS_OF, W)
    assert e.point is None and e.low is None and e.high is None and e.n_claims == 0


def test_a_hundred_papers_cannot_lift_the_point_above_three():
    claims = [claim("proposes", actor="university", src="paper", cid=f"p{i}") for i in range(100)]
    assert score.estimate(claims, AS_OF, W).point <= 3


def test_one_verified_multi_site_operation_by_a_user_firm_sets_seven_or_eight():
    claims = [claim("proposes", actor="university", src="paper", cid=f"p{i}") for i in range(20)]
    claims.append(claim("demonstrates_in_operation", setting="multiple_sites"))
    assert score.estimate(claims, AS_OF, W).point in (7, 8)


def test_point_is_the_highest_level_with_sufficient_support_not_an_average():
    claims = [claim("pilots", cid=f"a{i}") for i in range(5)] + [claim("operates_at_scale", actor="startup", src="press_release", cid="b")]
    e = score.estimate(claims, AS_OF, W)
    # One startup press release is below the support threshold for 9; five user-firm pilots hold 6.
    assert e.point == 6 and e.high >= 6


def test_unverified_quotes_carry_no_weight():
    claims = [claim("operates_at_scale", verified=False)]
    assert score.estimate(claims, AS_OF, W).point is None


def test_recency_decays_with_the_half_life():
    fresh = score.claim_weight(claim("pilots", days_ago=0), AS_OF, W)
    old = score.claim_weight(claim("pilots", days_ago=W.half_life_days), AS_OF, W)
    assert abs(old - fresh / 2) < 1e-9


def test_abandons_is_reported_as_the_contrary_claim_and_lowers_support():
    base = [claim("demonstrates_in_operation", cid=f"d{i}") for i in range(3)]
    with_drop = base + [claim("abandons", cid="x")]
    a, b = score.estimate(base, AS_OF, W), score.estimate(with_drop, AS_OF, W)
    assert b.contrary is not None and b.contrary["claim_id"] == "x"
    assert b.support[8] < a.support[8]


def test_top_three_are_the_heaviest_claims_at_the_point_level():
    claims = [claim("pilots", actor="startup", cid="s"), claim("pilots", actor="user_firm", cid="u"),
              claim("pilots", actor="government", cid="g"), claim("pilots", actor="analyst", cid="a")]
    e = score.estimate(claims, AS_OF, W)
    assert len(e.top) == 3 and e.top[0]["claim_id"] == "u"


def test_weights_table_is_complete_over_the_closed_sets():
    from observatory.trl import schema
    assert set(W.actor) == set(schema.ACTOR_TYPES)
    assert set(W.source) == set(schema.SOURCE_TYPES)
