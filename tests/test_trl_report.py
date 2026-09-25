import json

from observatory.trl import report


def _claims(tmp_path):
    rows = [{"claim_id": "a1", "period": "2026-Q3", "source": "hn", "doc_id": "hn:1", "doc_date": "2026-09-01",
             "url": "http://u", "title": "T", "tech_id": "delivery_drones", "claim_type": "pilots",
             "actor_type": "user_firm", "actor": "Walmart", "setting": "multiple_sites", "quantity": "34 stores",
             "quote": "Walmart is piloting drone delivery at 34 stores.", "quote_verified": True,
             "source_type": "forum_post", "model": "claude-sonnet-5", "prompt_version": "trl-1"},
            {"error": "boom", "source": "hn", "doc_id": "hn:2", "period": "2026-Q3"}]
    p = tmp_path / "claims-2026-Q3.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def test_context_estimates_each_tracked_technology_and_skips_error_rows(tmp_path):
    ctx = report.build_context("2026-Q3", _claims(tmp_path))
    drones = next(t for t in ctx["technologies"] if t["id"] == "delivery_drones")
    assert drones["point"] in (5, 6) and drones["n_claims"] == 1 and drones["top"][0]["claim_id"] == "a1"
    assert all(t["point"] is None for t in ctx["technologies"] if t["id"] != "delivery_drones")


def test_render_writes_a_page_that_shows_the_quote_and_the_weights_version(tmp_path, monkeypatch):
    from observatory import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    path = report.render("2026-Q3", _claims(tmp_path))
    html = path.read_text()
    assert "Walmart is piloting drone delivery" in html and "weights v1" in html and "TRL" in html


def test_estimates_are_written_beside_the_claims_they_came_from(tmp_path):
    """A test run on a fixture must not overwrite the real period's estimates."""
    report.build_context("2026-Q3", _claims(tmp_path))
    written = json.loads((tmp_path / "estimates-2026-Q3.json").read_text())
    assert set(written["estimates"]) >= {"delivery_drones"}


def test_a_point_below_the_threshold_is_marked_floor_on_the_page(tmp_path, monkeypatch):
    from observatory import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    ctx = report.build_context("2026-Q3", _claims(tmp_path))
    drones = next(t for t in ctx["technologies"] if t["id"] == "delivery_drones")
    assert drones["held"] is False  # one forum post does not clear the threshold
    html = report.render("2026-Q3", _claims(tmp_path)).read_text()
    assert f"TRL {drones['point']} (floor)" in html
    assert any("floor" in n and "weights v1" in n for n in ctx["notes"])


def test_the_page_says_trl_is_maturity_not_adoption_and_carries_the_lockup(tmp_path, monkeypatch):
    from observatory import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    html = report.render("2026-Q3", _claims(tmp_path)).read_text()
    assert "TRL is a maturity scale, not an adoption scale" in html
    assert 'src="data:image/png;base64,' in html and 'alt="W. P. Carey School of Business' in html
    assert "not estimated" in html
