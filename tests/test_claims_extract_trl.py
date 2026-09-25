import json
from types import SimpleNamespace

from observatory.claims import extract_trl
from observatory.trl.documents import DocText


class FakeStream:
    def __init__(self, payload, stop_reason="end_turn"):
        self.payload = payload
        self.stop_reason = stop_reason

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        usage = SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=0, cache_creation_input_tokens=0)
        text = json.dumps(self.payload)
        return SimpleNamespace(stop_reason=self.stop_reason, usage=usage,
                               content=[SimpleNamespace(type="text", text=text)],
                               to_json=lambda: json.dumps({"stop_reason": self.stop_reason,
                                                           "content": [{"type": "text", "text": text}]}))


class FakeClient:
    """Stands in for anthropic.Anthropic: the code calls client.messages.stream(...)."""

    def __init__(self, payload, stop_reason="end_turn"):
        self.payload = payload
        self.stop_reason = stop_reason
        self.calls = []
        self.messages = SimpleNamespace(stream=self.stream)

    def stream(self, **kw):
        self.calls.append(kw)
        return FakeStream(self.payload, self.stop_reason)


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


TECHS = [("delivery_drones", "Delivery drones")]
DOC = DocText("hn", "hn:1", "2026-09-01", "T", "http://u", "Walmart is piloting drone delivery.", 1)


def test_the_raw_response_is_kept_even_when_the_output_fails_the_schema():
    bad = {"claims": [{"tech_id": "delivery_drones", "claim_type": "invented", "actor_type": "user_firm",
                       "actor": "W", "setting": "one_site", "quantity": "", "quote": "q", "source_type": "forum_post"}]}
    raw: dict = {}
    try:
        extract_trl.extract_document(FakeClient(bad), "claude-sonnet-5", TECHS, DOC, "2026-Q3", raw=raw)
    except ValueError:
        pass
    else:
        raise AssertionError("an invalid claim_type must raise")
    assert raw["response"]["stop_reason"] == "end_turn"
    assert "invented" in raw["response"]["content"][0]["text"]


def test_a_refusal_row_records_the_stop_reason_and_keeps_the_raw():
    raw: dict = {}
    rows = extract_trl.extract_document(FakeClient({}, stop_reason="refusal"), "claude-sonnet-5", TECHS, DOC,
                                        "2026-Q3", raw=raw)
    assert rows[0]["refused"] is True and rows[0]["stop_reason"] == "refusal"
    assert raw["response"]["stop_reason"] == "refusal"


def test_raw_record_falls_back_when_the_message_has_no_to_json():
    msg = SimpleNamespace(stop_reason="max_tokens", content=[SimpleNamespace(type="text", text='{"claims": [')],
                          usage=SimpleNamespace(input_tokens=5, output_tokens=8000,
                                                cache_read_input_tokens=0, cache_creation_input_tokens=0))
    rec = extract_trl.raw_record(msg)
    assert rec["stop_reason"] == "max_tokens" and rec["text"] == '{"claims": [' and rec["usage"]["output_tokens"] == 8000


def test_a_document_listed_under_two_technologies_is_read_once():
    a = DocText("hn", "hn:1", "2026-09-01", "T", None, "x", 1)
    b = DocText("hn", "hn:1", "2026-09-01", "T", None, "x", 2)
    c = DocText("arxiv", "hn:1", "2026-09-01", "T", None, "x", 3)
    assert extract_trl.unique_docs([a, b, c]) == [a, c]


def _stub_main(monkeypatch, trl_dir, client):
    """Everything main() touches outside itself: the SDK, the output directory,
    the corpus and the tracked set. No network, no database."""
    import sys
    import types

    from observatory import config, store
    from observatory.trl import documents, tracked

    stub = types.ModuleType("anthropic")
    stub.Anthropic = lambda *a, **k: client
    for name in ("RateLimitError", "APIStatusError", "APIConnectionError"):
        setattr(stub, name, type(name, (Exception,), {}))
    monkeypatch.setitem(sys.modules, "anthropic", stub)
    monkeypatch.setattr(extract_trl, "TRL_DIR", trl_dir)
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(store, "connect", lambda *a, **k: None)
    monkeypatch.setattr(tracked, "tracked_ids", lambda *a, **k: ("delivery_drones",))
    text = "Walmart is piloting drone delivery at 34 stores."
    docs = [DocText("hn", "hn:1", "2026-09-01", "T1", "http://u/1", text, 1),
            DocText("hn", "hn:2", "2026-09-02", "T2", None, text, 2)]
    monkeypatch.setattr(documents, "texts_for", lambda conn, tid, weeks, collectors: iter(docs))


PAYLOAD = {"claims": [{"tech_id": "delivery_drones", "claim_type": "pilots", "actor_type": "user_firm",
                       "actor": "Walmart", "setting": "multiple_sites", "quantity": "34 stores",
                       "quote": "Walmart is piloting drone delivery at 34 stores.", "source_type": "forum_post"}]}


def test_main_writes_claims_raw_and_usage_and_a_rerun_appends(tmp_path, monkeypatch):
    from observatory.trl import report
    trl_dir = tmp_path / "trl"
    client = FakeClient(PAYLOAD)
    _stub_main(monkeypatch, trl_dir, client)

    assert extract_trl.main(["--period", "2026-Q3", "--max-dollars", "5"]) == 0
    claims_path = trl_dir / "claims-2026-Q3.jsonl"
    rows = [json.loads(line) for line in claims_path.read_text().splitlines()]
    assert [r["doc_id"] for r in rows] == ["hn:1", "hn:2"] and all(r["quote_verified"] for r in rows)
    raw = sorted((trl_dir / "raw-2026-Q3-claude-sonnet-5").glob("hn-*.json"))
    assert len(raw) == 2
    for path in raw:
        record = json.loads(path.read_text())
        assert record["response"]["stop_reason"] == "end_turn" and len(record["rows"]) == 1
    usage = json.loads((trl_dir / "usage-2026-Q3-claude-sonnet-5.json").read_text())
    assert usage["requests"] == 2 and usage["input_tokens"] == 200
    assert len(client.calls) == 2

    assert extract_trl.main(["--period", "2026-Q3", "--max-dollars", "5"]) == 0
    assert len(claims_path.read_text().splitlines()) == 4  # appended, as documented
    assert len(report.load_claims(claims_path)) == 2  # and the report counts each claim once
    usage = json.loads((trl_dir / "usage-2026-Q3-claude-sonnet-5.json").read_text())
    assert usage["requests"] == 4  # cumulative across runs


def test_main_refuses_above_the_ceiling_and_creates_nothing(tmp_path, monkeypatch):
    trl_dir = tmp_path / "trl"
    client = FakeClient(PAYLOAD)
    _stub_main(monkeypatch, trl_dir, client)
    assert extract_trl.main(["--period", "2026-Q3", "--max-dollars", "0"]) == 2
    assert not trl_dir.exists() and client.calls == []
