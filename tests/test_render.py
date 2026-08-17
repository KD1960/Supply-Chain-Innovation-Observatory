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


def test_an_absent_adoption_count_renders_as_a_dash_not_a_zero(conn, watchlist, tmp_path):
    """EDGAR failing leaves no edgar_filers row, so adoption is None. Printing
    0 adopters would be the fabricated decline the hole rule forbids."""
    store.upsert_metrics(conn, dict(
        tech_id="warehouse_robotics", week="2026-W33", momentum=-0.5, sai=-1.3,
        lfi=-0.4, adoption=None, adoption_new=None, stage_idea=1.1,
        stage_experiment=0.8, stage_investment=0.1, stage_deployment=-0.2,
        stage_diffusion=0.0, position=2.1, lexicon_version=3))

    context = render.build_context(conn, "2026-W33", watchlist)
    absent = [row for row in context["movers"] if row["tech_id"] == "warehouse_robotics"]
    assert absent and absent[0]["adoption"] is None

    html = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html").read_text()
    movers = html.split("This Week's Movers", 1)[1].split("<h2>", 1)[0]
    # Both movers have a substance and a lab-to-field score, so the only cell
    # that can hold a dash is the adopters count.
    assert "Warehouse robotics" in movers
    assert '<td class="num">—</td>' in movers
    assert '<td class="num">0</td>' not in movers


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
    """No external *resource* -- a stylesheet, script, font, or image fetched
    to render the page -- is allowed. An outbound `<a href>` a reader clicks,
    such as the Rising Terms block's links to source documents, is not that:
    nothing is fetched until the reader chooses to follow it. So the check is
    scoped to `src` attributes and `<link>` hrefs (stylesheets, favicons,
    preloads -- the href-bearing elements that fetch on load) rather than
    every href, and a genuine Rising Terms candidate with an external example
    link is included here to prove that link doesn't trip it."""
    from observatory.discover import Candidate

    store.upsert_candidates(conn, "2026-W33", [
        Candidate(term="dark factory", count=7, baseline=1.0, ratio=7.0,
                  examples=[("Dark factory retrofit in Ohio", "https://x.test/1")]),
    ])
    path = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "dashboard.html")
    html = path.read_text()
    assert "https://x.test/1" in html  # the outbound link is really there

    src_refs = re.findall(r'\bsrc\s*=\s*[\'"](?:https?:)?//[^\'"]*[\'"]', html)
    link_tags = re.findall(r'<link\b[^>]*>', html)
    link_refs = [tag for tag in link_tags if re.search(r'\bhref\s*=\s*[\'"](?:https?:)?//', tag)]
    url_refs = re.findall(
        r'url\(\s*[\'"]?(?:https?:)?//[^)\'"]*[\'"]?\)', html
    )
    assert src_refs == []
    assert link_refs == []
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


def test_unplaceable_awards_are_counted_rather_than_dropped(conn, watchlist, tmp_path):
    """Spec §8 block 6. A week whose places would not resolve must not render
    as a near-empty map indistinguishable from a quiet week."""
    from observatory.matcher import Observation

    store.upsert_observations(conn, [
        Observation(source="usaspending", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="p1", doc_date="2026-08-12", title="Placed award",
                    url="u", entity="ACME", entity_id=None, amount=1_000_000.0,
                    lat=34.27, lon=-111.66, matched_pattern="x", raw_ref=1),
        Observation(source="usaspending", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="p2", doc_date="2026-08-12", title="Foreign award",
                    url="u", entity="ACME", entity_id=None, amount=2_000_000.0,
                    lat=None, lon=None, matched_pattern="x", raw_ref=1),
        # No amount at all: an arXiv paper is not a missing dot on the map.
        Observation(source="arxiv", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="p3", doc_date="2026-08-12", title="A paper", url="u",
                    entity=None, entity_id=None, amount=None, lat=None, lon=None,
                    matched_pattern="x", raw_ref=1),
        # hn puts a story's points in `amount` and never sets coordinates. The
        # map's candidates are defined by source, not by having an amount, so
        # counting this as an award that could not be placed would fabricate a
        # number in the very block that exists to stop the page fabricating.
        Observation(source="hn", week="2026-W33", tech_id="autonomous_trucking",
                    doc_id="p4", doc_date="2026-08-12", title="Show HN: a truck",
                    url="u", entity=None, entity_id=None, amount=214.0,
                    lat=None, lon=None, matched_pattern="x", raw_ref=1),
    ])

    assert render.unplaced_award_count(conn, "2026-W33") == 1
    assert len(render.build_map_points(conn, "2026-W33")) == 1

    html = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html").read_text()
    build_map = html.split("<h2>Build Map</h2>", 1)[1].split("<h2>", 1)[0]
    assert "Location unknown: 1 award" in build_map


def test_the_build_map_caption_does_not_promise_a_news_layer(conn, watchlist, tmp_path):
    """GDELT is deferred, so there is no news layer to describe."""
    html = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html").read_text()
    build_map = html.split("<h2>Build Map</h2>", 1)[1].split("<h2>", 1)[0]
    assert "news-reported" not in build_map


def test_substance_and_attention_name_the_signals_actually_in_play(conn, watchlist, tmp_path):
    """With GDELT deferred, media_articles is always absent and "attention"
    means Hacker News alone. The block has to say so."""
    store.set_signal(conn, "autonomous_trucking", "2026-W33", "hn_points", 40.0)
    store.set_signal(conn, "autonomous_trucking", "2026-W33", "edgar_filers", 3.0)

    context = render.build_context(conn, "2026-W33", watchlist)
    assert context["attention_signals"] == ["hn_points"]
    assert context["substance_signals"] == ["edgar_filers"]

    html = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html").read_text()
    block = html.split("<h2>Substance vs. Attention</h2>", 1)[1].split("<h2>", 1)[0]
    prose = " ".join(block.split())
    assert "Substance this week is edgar_filers" in prose
    assert "attention is hn_points" in prose
    assert "media_articles" not in prose


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


def test_dashboard_links_movers_to_its_own_weeks_evidence(conn, watchlist, tmp_path):
    """`evidence.html` is overwritten every run, so an archived dashboard that
    linked to it would send the reader to a different week's evidence."""
    html = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html").read_text()
    assert "evidence-2026-W33.html#" in html
    assert "evidence.html#" not in html


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
    evidence_html = (tmp_path / "evidence-2026-W33.html").read_text()

    # tech ids can contain digits (gs1_2d, private_5g_warehouse) -- [\w] not [a-z_]
    links = set(re.findall(r'evidence-2026-W33\.html#([\w-]+)', dashboard_html))
    anchors = set(re.findall(r'id="([\w-]+)"', evidence_html))

    assert links, "expected the dashboard to link to evidence at all"
    assert links <= anchors, f"dead links: {links - anchors}"


def test_rising_terms_appear_in_the_context(conn, watchlist):
    from observatory.discover import Candidate

    store.upsert_candidates(conn, "2026-W33", [
        Candidate(term="dark factory", count=7, baseline=1.0, ratio=7.0,
                  examples=[("Dark factory retrofit in Ohio", "https://x.test/1")]),
    ])
    context = render.build_context(conn, "2026-W33", watchlist)
    assert context["rising_terms"][0]["term"] == "dark factory"


def test_rising_terms_render_with_their_evidence(conn, watchlist, tmp_path):
    from observatory.discover import Candidate

    store.upsert_candidates(conn, "2026-W33", [
        Candidate(term="dark factory", count=7, baseline=1.0, ratio=7.0,
                  examples=[("Dark factory retrofit in Ohio", "https://x.test/1")]),
    ])
    html = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html").read_text()
    assert "dark factory" in html
    assert "Dark factory retrofit in Ohio" in html
    assert "Arrives with the discovery step" not in html


def test_rising_terms_block_says_so_when_there_are_none(conn, watchlist, tmp_path):
    html = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html").read_text()
    assert "No new terms rose above the threshold this week." in html


def test_rising_term_titles_are_escaped(conn, watchlist, tmp_path):
    from observatory.discover import Candidate

    store.upsert_candidates(conn, "2026-W33", [
        Candidate(term="dark factory", count=7, baseline=1.0, ratio=7.0,
                  examples=[("<script>alert(1)</script>", "https://x.test/1")]),
    ])
    html = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html").read_text()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_rising_term_links_only_render_for_http_urls(conn, watchlist, tmp_path):
    """The URL arrives in a third-party payload. Every one today is
    collector-constructed or from a federal API, but a `javascript:` URL would
    become a link the owner clicks in a file opened locally, so only http(s)
    is made clickable and anything else shows as plain text."""
    from observatory.discover import Candidate

    store.upsert_candidates(conn, "2026-W33", [
        Candidate(term="dark factory", count=7, baseline=1.0, ratio=7.0,
                  examples=[("Hostile link", "javascript:alert(1)"),
                            ("Honest link", "https://x.test/1")]),
    ])
    html = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html").read_text()
    assert "javascript:" not in html
    assert "Hostile link" in html
    assert '<a href="https://x.test/1">' in html


def test_rising_terms_block_discloses_truncation(conn, watchlist, tmp_path):
    """227 real terms qualified against live raw and only 25 are shown; the
    block must say so rather than showing 25 and implying that's all there
    was."""
    from observatory.discover import Candidate

    candidates = [
        Candidate(term=f"term {i}", count=7, baseline=1.0, ratio=7.0, examples=[])
        for i in range(5)
    ]
    store.upsert_candidates(conn, "2026-W33", candidates, total=227)
    html = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html").read_text()
    assert "the 5 strongest of 227" in html


def test_rising_terms_block_says_nothing_of_truncation_when_the_list_is_whole(
    conn, watchlist, tmp_path
):
    from observatory.discover import Candidate

    candidates = [
        Candidate(term=f"term {i}", count=7, baseline=1.0, ratio=7.0, examples=[])
        for i in range(5)
    ]
    store.upsert_candidates(conn, "2026-W33", candidates, total=5)
    html = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html").read_text()
    assert "strongest of" not in html


def test_rising_terms_survive_a_null_total(conn, watchlist, tmp_path):
    """A row can carry a NULL total when it predates the `total` column and
    the migration's backfill missed it -- the guard in build_context exists
    for exactly that case, distinct from the migration's own backfill (see
    test_store.test_init_schema_backfills_total_for_pre_existing_rows). Set
    it to NULL by hand here, after a normal upsert, to simulate that gap
    directly rather than relying on the migration to reproduce it."""
    from observatory.discover import Candidate

    store.upsert_candidates(conn, "2026-W33", [
        Candidate(term="dark factory", count=7, baseline=1.0, ratio=7.0, examples=[]),
    ])
    conn.execute("UPDATE candidate_terms SET total = NULL WHERE week = '2026-W33'")
    conn.commit()

    context = render.build_context(conn, "2026-W33", watchlist)
    assert context["rising_total"] == 1

    html = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html").read_text()
    assert "dark factory" in html
