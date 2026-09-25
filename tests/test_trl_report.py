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
    # One forum post (weight ~0.17) holds no level: no point, the pilots span 5-6 kept.
    assert drones["point"] is None and (drones["low"], drones["high"]) == (5, 6)
    assert drones["n_claims"] == 1 and drones["top"][0]["claim_id"] == "a1"
    assert all(t["low"] is None for t in ctx["technologies"] if t["id"] != "delivery_drones")


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


def test_no_held_level_is_shown_as_insufficient_evidence_with_the_span(tmp_path, monkeypatch):
    from observatory import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    ctx = report.build_context("2026-Q3", _claims(tmp_path))
    drones = next(t for t in ctx["technologies"] if t["id"] == "delivery_drones")
    assert drones["held"] is False  # one forum post does not clear the threshold
    html = report.render("2026-Q3", _claims(tmp_path)).read_text()
    assert "insufficient evidence <small>(claims span 5–6)</small>" in html
    assert "floor" not in html and not any("floor" in n for n in ctx["notes"])
    assert any("insufficient evidence" in n for n in ctx["notes"])
    assert ctx["movers"]["insufficient"] == [drones]


def test_the_page_says_trl_is_maturity_not_adoption_and_carries_the_lockup(tmp_path, monkeypatch):
    from observatory import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    html = report.render("2026-Q3", _claims(tmp_path)).read_text()
    assert "TRL is a maturity scale, not an adoption scale" in html
    assert 'src="data:image/png;base64,' in html and 'alt="W. P. Carey School of Business' in html
    assert "not estimated" in html


def test_a_missing_claims_file_is_a_named_refusal_not_a_traceback(tmp_path, capsys):
    import pytest
    from observatory import run
    missing = tmp_path / "claims-2099-Q1.jsonl"
    with pytest.raises(report.ClaimsMissing) as error:
        report.build_context("2099-Q1", missing)
    assert str(missing) in str(error.value) and "extract_trl" in str(error.value)
    assert run.main(["--trl-report", "2099-Q1"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("refusing: ") and "extract_trl --period 2099-Q1" in err


def test_what_moved_counts_the_technologies_with_no_claims(tmp_path, monkeypatch):
    from observatory import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    ctx = report.build_context("2026-Q3", _claims(tmp_path))
    html = report.render("2026-Q3", _claims(tmp_path)).read_text()
    assert f"{len(ctx['movers']['unestimated'])} technologies have no estimate this period" in html


def _row(cid, tech="delivery_drones", ct="pilots", actor="user_firm", src="press_release",
         setting="multiple_sites", url="http://u", title="T", quote="q"):
    return {"claim_id": cid, "period": "2026-Q3", "source": "hn", "doc_id": f"hn:{cid}",
            "doc_date": "2026-09-20", "url": url, "title": title, "tech_id": tech, "claim_type": ct,
            "actor_type": actor, "actor": "A", "setting": setting, "quantity": "", "quote": quote,
            "quote_verified": True, "source_type": src, "model": "m", "prompt_version": "trl-1"}


def _write(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return path


def test_a_doubled_claims_file_gives_the_same_estimate_as_the_single_one(tmp_path):
    rows = [_row("d0", ct="sells", setting="one_site"), _row("p1")]
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    single = _write(tmp_path / "one" / "claims-2026-Q3.jsonl", rows)
    doubled = _write(tmp_path / "two" / "claims-2026-Q3.jsonl", rows + rows)
    assert len(report.load_claims(doubled)) == len(rows)
    a = next(t for t in report.build_context("2026-Q3", single)["technologies"] if t["id"] == "delivery_drones")
    b = next(t for t in report.build_context("2026-Q3", doubled)["technologies"] if t["id"] == "delivery_drones")
    assert (a["point"], a["low"], a["high"], a["held"], a["n_claims"]) == \
        (b["point"], b["low"], b["high"], b["held"], b["n_claims"])


def test_load_claims_keeps_the_last_row_per_claim_id_and_type(tmp_path):
    p = _write(tmp_path / "c.jsonl", [_row("x", quote="old"), _row("x", ct="sells"), _row("x", quote="new")])
    got = report.load_claims(p)
    assert [(r["claim_type"], r["quote"]) for r in got] == [("sells", "q"), ("pilots", "new")]


def _previous(tmp_path, estimates):
    (tmp_path / "estimates-2026-Q2.json").write_text(json.dumps({"estimates": estimates}))


def test_retreated_lists_only_a_held_level_that_fell_and_contrary_is_shown_apart(tmp_path, monkeypatch):
    from observatory import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    # delivery_drones: two strong pilots hold 6, down from a held 8 -> retreated.
    # electric_trucks: same level as before, but carries an abandons claim -> contrary, not retreated.
    rows = [_row("p1"), _row("p2"),
            _row("e1", tech="electric_trucks"), _row("e2", tech="electric_trucks"),
            _row("ab", tech="electric_trucks", ct="abandons", quote="We stopped the trial.")]
    _previous(tmp_path, {"delivery_drones": {"point": 8, "held": True},
                         "electric_trucks": {"point": 6, "held": True}})
    ctx = report.build_context("2026-Q3", _write(tmp_path / "claims-2026-Q3.jsonl", rows))
    by = {t["id"]: t for t in ctx["technologies"]}
    assert by["delivery_drones"]["moved"] == -2 and by["electric_trucks"]["moved"] == 0
    assert [t["id"] for t in ctx["movers"]["retreated"]] == ["delivery_drones"]
    assert [t["id"] for t in ctx["movers"]["contrary"]] == ["electric_trucks"]
    html = report.render("2026-Q3", tmp_path / "claims-2026-Q3.jsonl").read_text()
    assert "retreated 2 to TRL 6" in html and "contrary claim “We stopped the trial.”" in html


def test_moved_is_computed_only_between_two_held_levels(tmp_path):
    # Previous period not held (an old floor): no move, even though both have a number.
    _previous(tmp_path, {"delivery_drones": {"point": 2, "held": False},
                         "electric_trucks": {"point": 3, "held": True}})
    rows = [_row("p1"), _row("p2"), _row("e1", tech="electric_trucks", src="forum_post")]
    ctx = report.build_context("2026-Q3", _write(tmp_path / "claims-2026-Q3.jsonl", rows))
    by = {t["id"]: t for t in ctx["technologies"]}
    assert by["delivery_drones"]["held"] and by["delivery_drones"]["moved"] is None
    assert not by["electric_trucks"]["held"] and by["electric_trucks"]["moved"] is None
    assert ctx["movers"]["up"] == [] and ctx["movers"]["retreated"] == []
    written = json.loads((tmp_path / "estimates-2026-Q3.json").read_text())["estimates"]
    assert written["delivery_drones"]["held"] is True and written["electric_trucks"]["held"] is False
    assert written["electric_trucks"]["point"] is None


def test_held_first_then_insufficient_by_claims_then_unestimated(tmp_path):
    rows = ([_row("h1", tech="electric_trucks"), _row("h2", tech="electric_trucks")]
            + [_row(f"d{i}", src="forum_post", setting="lab", ct="proposes") for i in range(3)]
            + [_row("c1", tech="cv_inspection", src="forum_post", setting="lab", ct="sells")])
    ctx = report.build_context("2026-Q3", _write(tmp_path / "claims-2026-Q3.jsonl", rows))
    order = [t["id"] for t in ctx["technologies"]]
    assert order[:3] == ["electric_trucks", "delivery_drones", "cv_inspection"]
    assert all(t["low"] is None for t in ctx["technologies"][3:])


def test_the_citation_carries_the_title_and_no_link_without_a_url(tmp_path, monkeypatch):
    from observatory import config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    rows = [_row("p1", url=None, title="Drone pilot at 34 stores"), _row("p2", url="", title="Second")]
    html = report.render("2026-Q3", _write(tmp_path / "claims-2026-Q3.jsonl", rows)).read_text()
    assert "<cite>Drone pilot at 34 stores</cite>" in html and "<cite>Second</cite>" in html
    assert 'href="None"' not in html and 'href=""' not in html
    assert "hn hn:p1" in html
