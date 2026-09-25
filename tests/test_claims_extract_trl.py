import json
from types import SimpleNamespace

from observatory.claims import extract_trl
from observatory.trl.documents import DocText


class FakeStream:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        usage = SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=0, cache_creation_input_tokens=0)
        return SimpleNamespace(stop_reason="end_turn", usage=usage,
                               content=[SimpleNamespace(type="text", text=json.dumps(self.payload))],
                               to_json=lambda: "{}")


class FakeClient:
    """Stands in for anthropic.Anthropic: the code calls client.messages.stream(...)."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = []
        self.messages = SimpleNamespace(stream=self.stream)

    def stream(self, **kw):
        self.calls.append(kw)
        return FakeStream(self.payload)


def test_one_document_yields_verified_claim_rows(tmp_path):
    doc = DocText("hn", "hn:1", "2026-09-01", "T", "http://u", "Walmart is piloting drone delivery at 34 stores.", 1)
    payload = {"claims": [{"tech_id": "delivery_drones", "claim_type": "pilots", "actor_type": "user_firm",
                           "actor": "Walmart", "setting": "multiple_sites", "quantity": "34 stores",
                           "quote": "Walmart is piloting drone delivery at 34 stores.", "source_type": "forum_post"}]}
    client = FakeClient(payload)
    rows = extract_trl.extract_document(client, "claude-sonnet-5", [("delivery_drones", "Delivery drones")], doc, "2026-Q3")
    assert len(rows) == 1 and rows[0]["quote_verified"] is True and rows[0]["claim_type"] == "pilots"
    assert rows[0]["prompt_version"] == "trl-1" and len(rows[0]["claim_id"]) == 12
    call = client.calls[0]
    assert call["model"] == "claude-sonnet-5"
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_an_unverifiable_quote_is_kept_but_marked(tmp_path):
    doc = DocText("hn", "hn:1", "2026-09-01", "T", "http://u", "Nothing about drones here.", 1)
    payload = {"claims": [{"tech_id": "delivery_drones", "claim_type": "pilots", "actor_type": "user_firm",
                           "actor": "Walmart", "setting": "one_site", "quantity": "",
                           "quote": "Walmart pilots drones.", "source_type": "forum_post"}]}
    rows = extract_trl.extract_document(FakeClient(payload), "claude-sonnet-5", [("delivery_drones", "Delivery drones")], doc, "2026-Q3")
    assert rows[0]["quote_verified"] is False


def test_cost_estimate_refuses_above_the_ceiling():
    docs = [DocText("hn", f"hn:{i}", "2026-09-01", "T", None, "x" * 40000, i) for i in range(50)]
    assert extract_trl.estimate_dollars(docs, "claude-sonnet-5") > 1.0
