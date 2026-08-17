import re

import pytest

from observatory import charts, render, store
from observatory.matcher import Technology, Watchlist


def tech(tech_id, name=None, family="automation"):
    return Technology(
        id=tech_id, name=name or tech_id, family=family, include=("x",), exclude=(),
        status="active", added_week="2020-W01", patterns_changed_week="2020-W01",
    )


@pytest.fixture()
def watchlist():
    return Watchlist(version=3, technologies=(
        tech("autonomous_trucking", "Autonomous trucking", "vehicles"),
        tech("warehouse_robotics", "Warehouse robotics"),
        tech("quiet_tech", "Quiet tech"),
    ))


@pytest.fixture()
def conn(watchlist):
    connection = store.connect(":memory:")
    store.init_schema(connection)
    store.set_source_status(connection, "arxiv", "2026-W33", "ok", "")
    store.set_source_status(connection, "hn", "2026-W33", "failed", "read timeout")
    metrics = [
        dict(tech_id="autonomous_trucking", week="2026-W33", momentum=2.4, sai=0.9,
             lfi=0.6, adoption=14, adoption_new=2, stage_idea=0.2, stage_experiment=0.4,
             stage_investment=0.9, stage_deployment=1.2, stage_diffusion=0.5,
             position=3.8, lexicon_version=3),
        dict(tech_id="warehouse_robotics", week="2026-W33", momentum=-0.5, sai=-1.3,
             lfi=-0.4, adoption=9, adoption_new=0, stage_idea=1.1, stage_experiment=0.8,
             stage_investment=0.1, stage_deployment=-0.2, stage_diffusion=0.0,
             position=2.1, lexicon_version=3),
        dict(tech_id="quiet_tech", week="2026-W33", momentum=None, sai=None, lfi=None,
             adoption=0, adoption_new=0, stage_idea=None, stage_experiment=None,
             stage_investment=None, stage_deployment=None, stage_diffusion=None,
             position=None, lexicon_version=3),
    ]
    for row in metrics:
        store.upsert_metrics(connection, row)
    yield connection
    connection.close()


def test_context_ranks_movers_by_momentum(conn, watchlist):
    context = render.build_context(conn, "2026-W33", watchlist)
    assert [mover["name"] for mover in context["movers"]] == [
        "Autonomous trucking", "Warehouse robotics"
    ]


def test_context_excludes_warming_up_technologies_from_movers(conn, watchlist):
    context = render.build_context(conn, "2026-W33", watchlist)
    assert "Quiet tech" not in [mover["name"] for mover in context["movers"]]
    assert "Quiet tech" in [tech["name"] for tech in context["warming_up"]]


def test_context_reports_source_health(conn, watchlist):
    context = render.build_context(conn, "2026-W33", watchlist)
    statuses = {source["name"]: source["status"] for source in context["sources"]}
    assert statuses == {"arxiv": "ok", "hn": "failed"}


def test_render_writes_a_file_containing_every_block(conn, watchlist, tmp_path):
    path = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "dashboard.html")
    html = path.read_text()
    for block in [
        "Source health", "This Week's Movers", "Stage Board",
        "Substance vs. Attention", "Lab &rarr; Field", "Build Map", "Rising Terms",
    ]:
        assert block in html


def test_render_dashboard_without_out_path_writes_archive_and_latest(
    conn, watchlist, tmp_path, monkeypatch
):
    monkeypatch.setattr(render.config, "OUTPUT_DIR", tmp_path)
    path = render.render_dashboard(conn, "2026-W33", watchlist)
    assert path == tmp_path / "dashboard-2026-W33.html"
    assert path.exists()
    latest = tmp_path / "latest.html"
    assert latest.exists()
    assert latest.read_text() == path.read_text()


def test_rendered_page_has_no_external_resources(conn, watchlist, tmp_path):
    path = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "dashboard.html")
    html = path.read_text()
    attr_refs = re.findall(
        r'\b(?:src|href)\s*=\s*[\'"](?:https?:)?//[^\'"]*[\'"]', html
    )
    url_refs = re.findall(
        r'url\(\s*[\'"]?(?:https?:)?//[^)\'"]*[\'"]?\)', html
    )
    assert attr_refs == []
    assert url_refs == []


def test_rendered_page_states_the_lexicon_version(conn, watchlist, tmp_path):
    path = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "dashboard.html")
    assert "lexicon v3" in path.read_text()


def test_rendered_page_escapes_technology_names(conn, tmp_path):
    hostile = Watchlist(version=1, technologies=(tech("x", "<script>alert(1)</script>"),))
    connection = store.connect(":memory:")
    store.init_schema(connection)
    store.upsert_metrics(connection, dict(
        tech_id="x", week="2026-W33", momentum=1.0, sai=0.0, lfi=0.0, adoption=0,
        adoption_new=0, stage_idea=0.0, stage_experiment=0.0, stage_investment=0.0,
        stage_deployment=0.0, stage_diffusion=0.0, position=3.0, lexicon_version=1))
    path = render.render_dashboard(connection, "2026-W33", hostile, tmp_path / "d.html")
    html = path.read_text()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    connection.close()


def test_build_map_points_come_from_located_observations(conn, watchlist):
    from observatory.matcher import Observation

    store.upsert_observations(conn, [
        Observation(source="usaspending", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="a1", doc_date="2026-08-12", title="Corridor award",
                    url="u", entity="ACME", entity_id=None, amount=5_000_000.0,
                    lat=34.27, lon=-111.66, matched_pattern="x", raw_ref=1),
        Observation(source="arxiv", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="a2", doc_date="2026-08-12", title="A paper",
                    url="u", entity=None, entity_id=None, amount=None,
                    lat=None, lon=None, matched_pattern="x", raw_ref=1),
    ])
    points = render.build_map_points(conn, "2026-W33")
    assert len(points) == 1
    assert points[0].y == 34.27 and points[0].x == -111.66
    assert "ACME" in points[0].label


def test_build_map_points_clamps_negative_amounts_for_sizing(conn, watchlist):
    """USAspending reports negative amounts for deobligations/corrections. A
    negative amount must not reach the square root in the size calculation,
    where it would produce a complex number and invalid SVG (r="3.0+3.4j")."""
    from observatory.matcher import Observation

    store.upsert_observations(conn, [
        Observation(source="usaspending", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="b1", doc_date="2026-08-12", title="Corridor award",
                    url="u", entity="ACME", entity_id=None, amount=5_000_000.0,
                    lat=34.27, lon=-111.66, matched_pattern="x", raw_ref=1),
        Observation(source="usaspending", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="b2", doc_date="2026-08-12", title="Deobligation",
                    url="u", entity="ACME", entity_id=None, amount=-250_000.0,
                    lat=42.95, lon=-75.53, matched_pattern="x", raw_ref=1),
    ])
    points = render.build_map_points(conn, "2026-W33")
    assert len(points) == 2
    for point in points:
        assert isinstance(point.size, float)
        assert render.MAP_MIN_RADIUS <= point.size <= render.MAP_MAX_RADIUS

    svg = charts.build_map(points)
    radii = re.findall(r'<circle[^>]*\br="([^"]+)"', svg)
    assert len(radii) == 2
    for value in radii:
        float(value)  # raises ValueError if r ever renders as a complex number


def test_build_map_points_bounds_radius_when_all_amounts_are_negative(conn, watchlist):
    """A batch with no positive amount must not let 'amount / largest' come out
    greater than 1 (both negative, ratio > 1), which would blow the radius past
    MAP_MAX_RADIUS."""
    from observatory.matcher import Observation

    store.upsert_observations(conn, [
        Observation(source="usaspending", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="c1", doc_date="2026-08-12", title="Deobligation A",
                    url="u", entity="ACME", entity_id=None, amount=-100_000.0,
                    lat=34.27, lon=-111.66, matched_pattern="x", raw_ref=1),
        Observation(source="usaspending", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="c2", doc_date="2026-08-12", title="Deobligation B",
                    url="u", entity="ACME", entity_id=None, amount=-900_000.0,
                    lat=42.95, lon=-75.53, matched_pattern="x", raw_ref=1),
    ])
    points = render.build_map_points(conn, "2026-W33")
    assert points
    for point in points:
        assert point.size <= render.MAP_MAX_RADIUS


def test_dashboard_renders_the_build_map_block(conn, watchlist, tmp_path):
    path = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html")
    html = path.read_text()
    assert "Build Map" in html
    assert "Arrives with the USAspending collector" not in html
    build_map_section = html.split("<h2>Build Map</h2>", 1)[1].split("<h2>", 1)[0]
    assert "<svg" in build_map_section


def test_evidence_page_lists_every_observation_with_its_pattern(conn, watchlist, tmp_path):
    from observatory.matcher import Observation

    store.upsert_observations(conn, [
        Observation(source="arxiv", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="a1", doc_date="2026-08-12",
                    title="Fleet learning for driverless trucks",
                    url="https://arxiv.org/abs/1", entity=None, entity_id=None,
                    amount=None, lat=None, lon=None,
                    matched_pattern="driverless truck(s|ing)?", raw_ref=1),
    ])
    path = render.render_evidence(conn, "2026-W33", watchlist, tmp_path / "e.html")
    html = path.read_text()
    assert "Fleet learning for driverless trucks" in html
    assert "driverless truck(s|ing)?" in html
    assert "https://arxiv.org/abs/1" in html


def test_evidence_page_groups_by_technology_with_a_stable_anchor(conn, watchlist, tmp_path):
    from observatory.matcher import Observation

    store.upsert_observations(conn, [
        Observation(source="arxiv", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="a1", doc_date="2026-08-12", title="T", url="u",
                    entity=None, entity_id=None, amount=None, lat=None, lon=None,
                    matched_pattern="x", raw_ref=1),
    ])
    html = render.render_evidence(conn, "2026-W33", watchlist, tmp_path / "e.html").read_text()
    assert 'id="autonomous_trucking"' in html


def test_evidence_page_escapes_hostile_titles(conn, watchlist, tmp_path):
    from observatory.matcher import Observation

    store.upsert_observations(conn, [
        Observation(source="arxiv", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="a1", doc_date="2026-08-12",
                    title="<script>alert(1)</script>", url="u",
                    entity=None, entity_id=None, amount=None, lat=None, lon=None,
                    matched_pattern="x", raw_ref=1),
    ])
    html = render.render_evidence(conn, "2026-W33", watchlist, tmp_path / "e.html").read_text()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_evidence_page_has_no_external_resources(conn, watchlist, tmp_path):
    html = render.render_evidence(conn, "2026-W33", watchlist, tmp_path / "e.html").read_text()
    assert not re.findall(r'\b(?:src|href)\s*=\s*[\'"](?:https?:)?//[^\'"]*[\'"]', html)


def test_dashboard_links_movers_to_their_evidence(conn, watchlist, tmp_path):
    html = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html").read_text()
    assert "evidence.html#" in html


def test_dashboard_links_all_resolve_to_evidence_anchors(conn, watchlist, tmp_path):
    """The watchlist fixture has three technologies (autonomous_trucking,
    warehouse_robotics, quiet_tech); only one gets an observation here, so the
    dashboard links a mix of technologies with and without evidence. Every
    evidence.html#<anchor> link the dashboard emits must resolve to a real id=
    on the evidence page -- a dead link is worse than useless, since it looks
    like it should work."""
    from observatory.matcher import Observation

    store.upsert_observations(conn, [
        Observation(source="arxiv", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="a1", doc_date="2026-08-12", title="T", url="u",
                    entity=None, entity_id=None, amount=None, lat=None, lon=None,
                    matched_pattern="x", raw_ref=1),
    ])
    dashboard_html = render.render_dashboard(
        conn, "2026-W33", watchlist, tmp_path / "d.html"
    ).read_text()
    evidence_html = (tmp_path / "evidence.html").read_text()

    # tech ids can contain digits (gs1_2d, private_5g_warehouse) -- [\w] not [a-z_]
    links = set(re.findall(r'evidence\.html#([\w-]+)', dashboard_html))
    anchors = set(re.findall(r'id="([\w-]+)"', evidence_html))

    assert links, "expected the dashboard to link to evidence at all"
    assert links <= anchors, f"dead links: {links - anchors}"
