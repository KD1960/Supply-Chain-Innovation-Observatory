"""The findings layer: what the quarter says about the world, not the instrument."""

from observatory import findings


def row(name, total, by_family, stage="", **extra):
    """A report row of the shape `quarter.build_context` builds."""
    top_family = max(by_family, key=lambda family: by_family[family]) if by_family else ""
    base = {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "total": total,
        "by_family": dict(by_family),
        "top_family": top_family,
        "stage": stage,
        "concentration": round(100 * by_family[top_family] / total) if total else 0,
        "filers": 0,
        "single_source": False,
        "sai": None,
        "lfi": None,
        "shift": None,
    }
    base.update(extra)
    return base


def ids(found):
    return [finding.id for finding in found]


def text_of(found, rule_id):
    return next(finding.text for finding in found if finding.id == rule_id)


def test_the_filings_led_technology_is_named_with_its_evidence():
    """The finding the marketing plan wrote by hand: a technology whose
    evidence is led by SEC filings is at the diffusion end, and the sentence
    has to carry what that rests on."""
    rows = [row("Autonomous trucking", 12, {"filings": 8, "community": 3, "research": 1},
                stage="diffusion", filers=6),
            row("ERP platforms", 100, {"code": 97, "research": 3}, stage="experiment")]
    found = findings.compose(rows)
    assert "stage_frontier" in ids(found)
    sentence = text_of(found, "stage_frontier")
    assert "Autonomous trucking" in sentence
    assert "12" in sentence and "8" in sentence and "6" in sentence


def test_a_technology_at_diffusion_on_one_document_is_counted_not_named():
    """2026-Q2 really does hold cold chain IoT at diffusion on a single filing.
    Naming it makes the plan's own example sentence -- autonomous trucking is
    the only technology at diffusion -- false."""
    rows = [row("Autonomous trucking", 12, {"filings": 8, "community": 3, "research": 1},
                stage="diffusion", filers=6),
            row("Cold chain IoT monitoring", 1, {"filings": 1}, stage="diffusion", filers=1)]
    sentence = text_of(findings.compose(rows), "stage_frontier")
    assert "Cold chain IoT monitoring" not in sentence
    assert "Autonomous trucking" in sentence


def test_a_finding_points_at_the_row_it_came_from():
    rows = [row("Autonomous trucking", 12, {"filings": 8, "community": 3, "research": 1},
                stage="diffusion", filers=6)]
    found = findings.compose(rows)
    assert found[0].anchor == "tech-autonomous-trucking"


def test_federal_money_is_a_finding_with_the_share_it_rests_on():
    rows = [row("Port electrification and shore power", 6, {"money": 4, "research": 2},
                stage="investment"),
            row("ERP platforms", 100, {"code": 97, "research": 3}, stage="experiment")]
    sentence = text_of(findings.compose(rows), "federal_money")
    assert "Port electrification and shore power" in sentence
    assert "4" in sentence and "6" in sentence


def test_a_patent_led_technology_is_named():
    rows = [row("Warehouse robotics", 32, {"patents": 23, "research": 9},
                stage="experiment")]
    sentence = text_of(findings.compose(rows), "patent_led")
    assert "Warehouse robotics" in sentence
    assert "32" in sentence


def test_the_most_evidenced_technology_carries_its_concentration():
    """Loudest is not most important, and a bare count reads as importance.
    121 documents that are 96% research is a statement about the literature."""
    rows = [row("Vehicle routing and path optimization", 121,
                {"research": 116, "code": 5}, stage="idea"),
            row("ERP platforms", 100, {"code": 97, "research": 3}, stage="experiment")]
    sentence = text_of(findings.compose(rows), "most_evidenced")
    assert "Vehicle routing and path optimization" in sentence
    assert "121" in sentence and "96" in sentence


def test_score_findings_are_absent_when_the_period_withholds_its_scores():
    """2026-Q3 has sai, lfi and shift as None on every row. The count findings
    still have to fire: a withheld quarter is not a quarter with nothing to
    say, and the report went out to a beta cohort in that state."""
    rows = [row("Autonomous trucking", 12, {"filings": 8, "research": 4},
                stage="diffusion", filers=6),
            row("Warehouse robotics", 32, {"patents": 23, "research": 9})]
    found = ids(findings.compose(rows))
    assert "stage_frontier" in found and "patent_led" in found
    assert "built_versus_said" not in found
    assert "crossing" not in found
    assert "movers" not in found


def test_the_substance_leaders_are_named_when_the_period_is_scored():
    rows = [row("ERP platforms", 100, {"code": 97, "research": 3}, sai=0.87),
            row("Warehouse management systems", 40, {"code": 21, "filings": 19}, sai=0.66),
            row("Vehicle routing", 121, {"research": 116, "code": 5}, sai=0.35)]
    sentence = text_of(findings.compose(rows), "built_versus_said")
    assert "ERP platforms" in sentence
    assert "Warehouse management systems" in sentence


def test_technologies_crossing_out_of_the_laboratory_are_named():
    rows = [row("Blockchain traceability", 22, {"filings": 12, "research": 10}, lfi=0.4),
            row("Autonomous trucking", 12, {"filings": 8, "research": 4}, lfi=0.2),
            row("Vehicle routing", 121, {"research": 116, "code": 5}, lfi=-0.3)]
    sentence = text_of(findings.compose(rows), "crossing")
    assert "Blockchain traceability" in sentence
    assert "Vehicle routing" not in sentence


def test_the_largest_share_movement_is_a_finding():
    rows = [row("ML demand forecasting", 75, {"code": 58, "research": 17}, shift=3.3),
            row("ERP platforms", 100, {"code": 97, "research": 3}, shift=3.1),
            row("Vehicle routing", 121, {"research": 116, "code": 5}, shift=-0.4)]
    sentence = text_of(findings.compose(rows), "movers")
    assert "ML demand forecasting" in sentence
    assert "3.3" in sentence


def test_no_more_than_five_findings_ship():
    rows = [row("Autonomous trucking", 12, {"filings": 8, "research": 4},
                stage="diffusion", filers=6, sai=0.5, lfi=0.3, shift=1.0),
            row("Port electrification", 6, {"money": 4, "research": 2}, sai=0.4,
                lfi=0.2, shift=0.9),
            row("Warehouse robotics", 32, {"patents": 23, "research": 9}, sai=0.3,
                lfi=0.1, shift=0.8),
            row("Vehicle routing", 121, {"research": 116, "code": 5}, sai=0.2,
                lfi=-0.4, shift=0.7)]
    assert len(findings.compose(rows)) == 5


# --- the owner's override ---------------------------------------------------
#
# The marketing plan gives the pipeline the draft and Kevin the final text.
# The file is optional: with none present the drafted sentences ship, which is
# what keeps a report reproducible from the database alone.


def q2_rows():
    return [row("Autonomous trucking", 12, {"filings": 8, "research": 4},
                stage="diffusion", filers=6),
            row("Warehouse robotics", 32, {"patents": 23, "research": 9})]


def test_a_replacement_sentence_wins_over_the_drafted_one(tmp_path):
    (tmp_path / "2026-Q2.yaml").write_text(
        "stage_frontier:\n  text: Autonomous trucking is the only one anyone is filing about.\n")
    found = findings.compose(q2_rows(), overrides=findings.load_overrides("2026-Q2", tmp_path))
    assert text_of(found, "stage_frontier") == (
        "Autonomous trucking is the only one anyone is filing about.")


def test_a_dropped_finding_does_not_ship(tmp_path):
    (tmp_path / "2026-Q2.yaml").write_text("patent_led:\n  drop: true\n")
    found = findings.compose(q2_rows(), overrides=findings.load_overrides("2026-Q2", tmp_path))
    assert "patent_led" not in ids(found)
    assert "stage_frontier" in ids(found)


def test_the_file_sets_the_order(tmp_path):
    (tmp_path / "2026-Q2.yaml").write_text(
        "patent_led:\n  text: Patents first.\nstage_frontier:\n  text: Filings second.\n")
    found = findings.compose(q2_rows(), overrides=findings.load_overrides("2026-Q2", tmp_path))
    assert ids(found)[:2] == ["patent_led", "stage_frontier"]


def test_an_override_naming_no_rule_is_an_error(tmp_path):
    """Silence is the failure mode this project keeps paying for. An override
    that names nothing has to say so rather than quietly doing nothing."""
    (tmp_path / "2026-Q2.yaml").write_text("stage_fronteir:\n  drop: true\n")
    import pytest
    with pytest.raises(findings.OverrideProblem, match="stage_fronteir"):
        findings.load_overrides("2026-Q2", tmp_path)


def test_no_file_means_the_drafted_sentences_ship(tmp_path):
    found = findings.compose(q2_rows(), overrides=findings.load_overrides("2026-Q2", tmp_path))
    assert "stage_frontier" in ids(found)


def test_every_finding_carries_a_stat_and_a_sample_size():
    """A card puts the stat in large type and the n in the source line. A
    finding with neither cannot be posted without someone inventing them."""
    rows = [row("Autonomous trucking", 12, {"filings": 8, "research": 4},
                stage="diffusion", filers=6, sai=0.5, lfi=0.3, shift=1.2),
            row("Port electrification", 6, {"money": 4, "research": 2}, sai=0.4),
            row("Warehouse robotics", 32, {"patents": 23, "research": 9}, sai=0.3),
            row("Vehicle routing", 121, {"research": 116, "code": 5}, sai=0.2)]
    for rule in findings.RULES:
        found = rule(rows)
        assert found is not None, rule.__name__
        assert found.stat, rule.__name__
        assert found.n > 0, rule.__name__
