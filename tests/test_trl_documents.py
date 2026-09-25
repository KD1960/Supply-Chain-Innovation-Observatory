import shutil
from pathlib import Path

from observatory import config, matcher, store
from observatory.collectors.hn import HackerNewsCollector
from observatory.trl import documents

FIX = Path(__file__).parent / "fixtures"


def _seed(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    monkeypatch.setattr(config, "RAW_DIR", raw)
    dst = raw / "2026-W38" / "hn"
    dst.mkdir(parents=True)
    shutil.copy(FIX / "hn_page.json", dst / "000.json")
    conn = store.connect(":memory:")
    store.init_schema(conn)
    raw_ref = store.record_raw(conn, "hn", "2026-W38", "http://x", 200, str(dst / "000.json"))
    wl = matcher.load_watchlist()
    for doc in HackerNewsCollector().parse((dst / "000.json").read_text()):
        store.upsert_observations(conn, matcher.observations_for_document(wl, doc, "hn", "2026-W38", raw_ref))
    return conn


def test_texts_for_returns_the_parsed_text_behind_each_observation(tmp_path, monkeypatch):
    conn = _seed(tmp_path, monkeypatch)
    tech = conn.execute("SELECT tech_id FROM observations LIMIT 1").fetchone()["tech_id"]
    docs = list(documents.texts_for(conn, tech, ["2026-W38"], (HackerNewsCollector(),)))
    assert docs and docs[0].source == "hn" and docs[0].text and docs[0].doc_id.startswith("hn:")


def test_texts_for_is_empty_for_a_week_with_no_raw(tmp_path, monkeypatch):
    conn = _seed(tmp_path, monkeypatch)
    assert list(documents.texts_for(conn, "delivery_drones", ["2026-W01"], (HackerNewsCollector(),))) == []
