import pytest

from observatory.collectors import base


def test_write_raw_stores_the_body_verbatim(tmp_path, monkeypatch):
    monkeypatch.setattr(base.config, "RAW_DIR", tmp_path)
    page = base.RawPage(url="https://x.test/a", status=200, text='{"a": 1}', extension="json")
    path = base.write_raw("arxiv", "2026-W33", 0, page)
    assert path.read_text() == '{"a": 1}'
    assert path.parent == tmp_path / "2026-W33" / "arxiv"
    assert path.name == "000.json"


def test_read_raw_returns_pages_in_stable_order(tmp_path, monkeypatch):
    monkeypatch.setattr(base.config, "RAW_DIR", tmp_path)
    for index, body in enumerate(["first", "second", "third"]):
        base.write_raw("hn", "2026-W33", index, base.RawPage("u", 200, body, "json"))
    bodies = [text for _, text in base.read_raw("hn", "2026-W33")]
    assert bodies == ["first", "second", "third"]


def test_read_raw_is_empty_when_the_source_never_ran(tmp_path, monkeypatch):
    monkeypatch.setattr(base.config, "RAW_DIR", tmp_path)
    assert list(base.read_raw("hn", "2026-W33")) == []


def test_base_collector_requires_subclasses_to_implement_parse():
    class Incomplete(base.BaseCollector):
        name = "incomplete"

    with pytest.raises(NotImplementedError):
        Incomplete().parse("{}")
