from observatory.claims import verify


def test_normalize_unifies_quotes_dashes_and_whitespace_but_keeps_case():
    assert verify.normalize("“Smart”  —   robots’\n\n") == '"Smart" - robots\''
    assert verify.normalize("ABC") == "ABC"


def test_verify_quote_matches_after_normalisation_only():
    text = "We deployed autonomous mobile robots\nin 12 fulfillment centers — this year."
    assert verify.verify_quote("autonomous mobile robots in 12 fulfillment centers - this", text)
    assert not verify.verify_quote("autonomous mobile robots in 13 fulfillment centers", text)
    assert not verify.verify_quote("", text)
    assert not verify.verify_quote("Autonomous Mobile Robots", text)   # case is evidence, not noise
