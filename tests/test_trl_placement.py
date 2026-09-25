# tests/test_trl_placement.py
from observatory.trl import placement, score


def test_sheet_lists_each_technology_with_its_claims_fenced():
    md = placement.sheet({"delivery_drones": [{"claim_id": "abc", "claim_type": "pilots", "actor": "Walmart",
                                               "actor_type": "user_firm", "setting": "one_site", "quote": "q```x",
                                               "source": "hn", "doc_date": "2026-09-01", "url": "http://u",
                                               "quote_verified": True, "source_type": "forum_post", "quantity": ""}]})
    assert "## delivery_drones" in md and "abc" in md and "````" in md  # fence longer than the backtick run in the quote


def test_agreement_counts_within_one_level():
    est = {"a": score.TRLEstimate(6, 5, 7), "b": score.TRLEstimate(3, 1, 3), "c": score.TRLEstimate(None, None, None)}
    verdicts = [{"tech_id": "a", "reader_trl": "7"}, {"tech_id": "b", "reader_trl": "5"}, {"tech_id": "c", "reader_trl": "4"}]
    r = placement.agreement(verdicts, est)
    assert r == {"n": 2, "within_one": 1, "exact": 0, "mean_abs_diff": 1.5}
