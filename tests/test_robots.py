"""RFC 9309 robots.txt: the cases urllib.robotparser got wrong (probe 3,
2026-09-29) and the real files that showed them."""

from pathlib import Path

from observatory import robots

FIX = Path(__file__).parent / "fixtures" / "robots"
UA = "SupplyChainObservatory/1.0 (mailto:x@example.org)"


def test_an_empty_disallow_does_not_cancel_the_rules_after_it():
    r = robots.parse("User-agent: *\nDisallow:\nDisallow: /tag/\n")
    assert not r.allows(UA, "/tag/x")
    assert r.allows(UA, "/news")


def test_repeated_star_groups_are_merged():
    r = robots.parse("User-agent: *\nDisallow: /cp/\n\nUser-agent: *\nDisallow: /member/\n")
    assert not r.allows(UA, "/member/x")
    assert not r.allows(UA, "/cp/y")


def test_the_longest_matching_rule_wins_not_the_first():
    r = robots.parse("User-agent: *\nAllow: /\nDisallow: /search\n")
    assert not r.allows(UA, "https://h.test/search?q=1")
    assert r.allows(UA, "/about")
    r = robots.parse("User-agent: *\nDisallow: /search\nAllow: /search/public\n")
    assert r.allows(UA, "/search/public/x")
    assert not r.allows(UA, "/search/private")


def test_an_allow_and_disallow_of_equal_length_allow_wins():
    assert robots.parse("User-agent: *\nDisallow: /p\nAllow: /p\n").allows(UA, "/p/x")


def test_wildcards_and_the_end_anchor():
    r = robots.parse("User-agent: *\nDisallow: /*.pdf$\nDisallow: /private*/data\n")
    assert not r.allows(UA, "/a/b.pdf")
    assert r.allows(UA, "/a/b.pdf?x")
    assert not r.allows(UA, "/private123/data/x")
    assert r.allows(UA, "/private123/other")


def test_a_named_group_beats_star_and_an_unnamed_agent_uses_the_merged_star_groups():
    text = ("User-agent: observatory\nDisallow: /x\n\n"
            "User-agent: *\nAllow: /\n\n"
            "User-agent: *\nDisallow: /y\n")
    r = robots.parse(text)
    assert not r.allows("observatory/0.1 (mailto:x@example.org)", "/x")
    assert r.allows("observatory/0.1 (mailto:x@example.org)", "/y")     # its own group only
    assert r.allows("otherbot/2.0", "/x")
    assert not r.allows("otherbot/2.0", "/y")
    # RFC 9309 2.2.1 matches the product token, not a substring of it.
    assert r.allows("SupplyChainObservatory/1.0", "/x")
    assert not r.allows("SupplyChainObservatory/1.0", "/y")


def test_case_insensitive_fields_and_agent_comments_crlf_and_bom():
    text = "﻿USER-AGENT: ObServatory # us\r\nDISALLOW: /x # not /y\r\n# Disallow: /z\r\n"
    r = robots.parse(text)
    assert not r.allows("OBSERVATORY/0.1", "/x")
    assert r.allows("observatory/0.1", "/y") and r.allows("observatory/0.1", "/z")


def test_percent_encoding_compares_hex_digits_case_insensitively():
    r = robots.parse("User-agent: *\nDisallow: /a%3cb\n")
    assert not r.allows(UA, "/a%3Cb")


def test_crawl_delay_is_the_largest_across_merged_groups():
    r = robots.parse("User-agent: *\nCrawl-delay: 5\n\nUser-agent: *\nCrawl-delay: abc\n\n"
                     "User-agent: *\nCrawl-delay: 12.5\n")
    assert r.crawl_delay(UA) == 12.5
    assert robots.parse("User-agent: *\nCrawl-delay: abc\n").crawl_delay(UA) is None
    assert robots.parse("User-agent: *\nDisallow: /x\n").crawl_delay(UA) is None


def test_no_rules_allow_everything_and_robots_txt_is_always_allowed():
    assert robots.parse("").allows(UA, "/anything")
    assert robots.parse("Sitemap: https://h.test/s.xml\n").allows(UA, "/anything")
    assert robots.Robots.allow_all().allows(UA, "/anything")
    everything = robots.Robots.disallow_all()
    assert not everything.allows(UA, "/anything") and not everything.allows(UA, "/")
    assert everything.allows(UA, "/robots.txt")
    assert robots.parse("User-agent: *\nDisallow: /\n").allows(UA, "https://h.test/robots.txt")


def test_the_three_probe_3_files():
    joc = robots.parse((FIX / "joc.txt").read_text())
    assert not joc.allows(UA, "https://www.joc.com/search")
    assert not joc.allows(UA, "https://www.joc.com/user/profile")
    assert joc.allows(UA, "https://www.joc.com/news")
    mmh = robots.parse((FIX / "mmh.txt").read_text())
    assert not mmh.allows(UA, "https://www.mmh.com/member/x")
    assert mmh.allows(UA, "https://www.mmh.com/article/x")
    assert mmh.crawl_delay(UA) == 20
    loadstar = robots.parse((FIX / "loadstar.txt").read_text())
    assert not loadstar.allows(UA, "https://theloadstar.com/tag/ports/")
    assert loadstar.allows(UA, "https://theloadstar.com/some-story/")


def test_matching_is_linear_in_the_path_not_exponential_in_the_stars():
    """A joined `.*` regex took over 60 s on `/*a*a*a*a*a*b` against 200 a's;
    robots.txt is third-party input and the cron has no watchdog."""
    import time
    r = robots.parse("User-agent: *\nDisallow: /*a*a*a*a*a*a*a*a*a*b\n")
    started = time.perf_counter()
    assert r.allows(UA, "/" + "a" * 100_000)
    assert time.perf_counter() - started < 0.1


def test_the_matcher_agrees_with_a_reference_regex():
    import random
    import re
    rng = random.Random(9309)

    def reference(pattern, path):
        body, anchored = (pattern[:-1], True) if pattern.endswith("$") else (pattern, False)
        rx = ".*".join(re.escape(p) for p in body.split("*")) + (r"\Z" if anchored else "")
        return re.match(rx, path) is not None

    for _ in range(500):
        pieces = ["".join(rng.choice("ab/$") for _ in range(rng.randint(0, 3)))
                  for _ in range(rng.randint(1, 4))]            # at most 3 stars
        pattern = "/" + "*".join(pieces) + rng.choice(["", "$"])
        path = "/" + "".join(rng.choice("ab/$") for _ in range(rng.randint(0, 8)))
        assert robots.Rule(False, pattern).matches(path) == reference(pattern, path), (pattern, path)


def test_percent_encoded_unreserved_characters_are_decoded_and_reserved_ones_are_not():
    r = robots.parse("User-agent: *\nDisallow: /~joe\n")
    assert not r.allows(UA, "/%7Ejoe") and not r.allows(UA, "/%7ejoe")
    assert robots.parse("User-agent: *\nDisallow: /%7Ejoe\n").allows(UA, "/~jo") is True
    assert not robots.parse("User-agent: *\nDisallow: /%7Ejoe\n").allows(UA, "/~joe")
    assert robots.parse("User-agent: *\nDisallow: /a%2Fb\n").allows(UA, "/a/b")


def test_only_a_bare_star_is_the_wildcard_group():
    r = robots.parse("User-agent: *bot\nDisallow: /x\n")
    assert r.allows(UA, "/x")
