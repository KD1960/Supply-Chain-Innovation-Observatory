from observatory.claims import trl_prompt
from observatory.trl.documents import DocText


def test_system_prompt_has_no_dates_or_ids_so_the_cache_holds():
    s = trl_prompt.system([("delivery_drones", "Delivery drones")])
    assert "2026" not in s and "delivery_drones" in s and trl_prompt.UNTRUSTED in s


def test_system_prompt_names_every_closed_set():
    from observatory.trl import schema
    s = trl_prompt.system([("delivery_drones", "Delivery drones")])
    for word in schema.CLAIM_TYPES + schema.ACTOR_TYPES + schema.SETTINGS + schema.SOURCE_TYPES:
        assert word in s


def test_user_prompt_wraps_the_document_and_marks_it_untrusted():
    d = DocText("hn", "hn:1", "2026-09-01", "T", "http://u", "Walmart pilots drones.", 1)
    u = trl_prompt.user(d)
    assert "DOCUMENT TEXT" in u and "Walmart pilots drones." in u and "hn" in u and "2026-09-01" in u
