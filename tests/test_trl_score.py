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


def test_with_no_level_held_there_is_no_point_but_the_span_is_kept():
    # Five user-firm pilots clear the threshold (see the average test above); one
    # university paper does not, so there is no point, only the span it evidences.
    held = score.estimate([claim("pilots", cid=f"a{i}") for i in range(5)], AS_OF, W)
    thin = score.estimate([claim("proposes", actor="university", src="paper", cid="p")], AS_OF, W)
    assert held.held is True and held.point == 6
    assert thin.held is False and thin.point is None and (thin.low, thin.high) == (1, 2)
    assert [c["claim_id"] for c in thin.top] == ["p"]
    assert score.estimate([], AS_OF, W).held is False


def test_a_two_level_band_claim_is_counted_once():
    one = claim("sells", cid="s")
    w = score.claim_weight(one, AS_OF, W)
    e = score.estimate([one], AS_OF, W)
    assert abs(e.cumulative[7] - w) < 1e-12 and abs(e.cumulative[1] - w) < 1e-12
    assert e.support[7] == e.support[8] == w  # per-level support, for display, is unchanged


def test_sells_and_operates_at_scale_of_equal_weight_meet_the_threshold_alike():
    # One user-firm/press_release/one_site claim weighs ~0.40: below 0.5 alone,
    # above it in pairs. Before the fix a single "sells" claim held level 7 (counted
    # at 7 and 8) while a single "operates_at_scale" claim held nothing.
    w = score.claim_weight(claim("sells"), AS_OF, W)
    assert W.support_threshold / 2 < w < W.support_threshold
    one_sells = score.estimate([claim("sells", cid="s")], AS_OF, W)
    one_scale = score.estimate([claim("operates_at_scale", cid="o")], AS_OF, W)
    assert one_sells.held is False and one_scale.held is False
    two_sells = score.estimate([claim("sells", cid=f"s{i}") for i in range(2)], AS_OF, W)
    two_scale = score.estimate([claim("operates_at_scale", cid=f"o{i}") for i in range(2)], AS_OF, W)
    assert two_sells.held and two_scale.held
    assert (two_sells.point, two_scale.point) == (8, 9)


def test_abandons_dents_levels_seven_to_nine_whatever_its_setting():
    base = [claim("pilots", cid=f"p{i}") for i in range(3)] + [claim("sells", cid=f"s{i}") for i in range(2)]
    lab = base + [claim("abandons", setting="lab", cid="x")]
    a, b = score.estimate(base, AS_OF, W), score.estimate(lab, AS_OF, W)
    dent = score.claim_weight(claim("abandons", setting="lab", cid="x"), AS_OF, W) * W.contrary_penalty
    for level in (7, 8, 9):
        assert abs((a.support[level] - b.support[level]) - dent) < 1e-12
    for level in range(1, 7):
        assert a.support[level] == b.support[level] and a.cumulative[level] == b.cumulative[level]
