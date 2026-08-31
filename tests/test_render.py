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




def test_context_reports_source_health(conn, watchlist):
    context = render.dashboard_context(conn, "2026-W33", watchlist)
    statuses = {source["name"]: source["status"] for source in context["sources"]}
    assert statuses == {"arxiv": "ok", "hn": "failed"}




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




def test_rising_terms_appear_in_the_context(conn, watchlist):
    from observatory.discover import Candidate

    store.upsert_candidates(conn, "2026-W33", [
        Candidate(term="dark factory", count=7, baseline=1.0, ratio=7.0,
                  examples=[("Dark factory retrofit in Ohio", "https://x.test/1")]),
    ])
    context = render.dashboard_context(conn, "2026-W33", watchlist)
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

    context = render.dashboard_context(conn, "2026-W33", watchlist)
    assert context["rising_total"] == 1

    html = render.render_dashboard(conn, "2026-W33", watchlist, tmp_path / "d.html").read_text()
    assert "dark factory" in html


# --- the weekly dashboard is a collection health view now -------------------
#
# A week is too small a window to interpret: two thirds of technology-weeks
# hold nothing, and a trailing score let a technology with no documents at all
# top "This Week's Movers". Everything interpretive moved to the quarterly
# report. What is left is the question a week can actually answer -- did the
# collectors run, and what arrived.


def test_the_dashboard_no_longer_carries_the_analytical_blocks(conn):
    from observatory import matcher
    context = render.dashboard_context(conn, "2026-W35", matcher.load_watchlist(), set())
    for gone in ("movers", "stage_board_svg", "substance_svg", "crossovers", "build_map_svg"):
        assert gone not in context, f"{gone} belongs to the quarterly report now"


def test_the_dashboard_still_answers_whether_the_collectors_ran(conn):
    from observatory import matcher
    context = render.dashboard_context(conn, "2026-W35", matcher.load_watchlist(), set())
    assert "sources" in context
    assert "arrivals" in context
    assert "rising_terms" in context


def test_arrivals_count_what_each_source_brought_this_week(conn):
    from observatory import matcher
    from observatory.matcher import Observation
    store.upsert_observations(conn, [Observation(
        source="arxiv", week="2026-W35", tech_id="a", doc_id="d1",
        doc_date="2026-08-26", title="t", url="", entity=None, entity_id=None,
        amount=None, lat=None, lon=None, matched_pattern="x", raw_ref=None)])
    context = render.dashboard_context(conn, "2026-W35", matcher.load_watchlist(), set())
    assert dict(context["arrivals"]).get("arxiv") == 1


def test_the_dashboard_escapes_what_it_prints(conn, watchlist, tmp_path):
    """The page carries source names and candidate terms, both of which come
    from outside. Technology names left with the movers block."""
    from observatory.discover import Candidate
    store.upsert_candidates(conn, "2026-W33", [
        Candidate(term="<script>alert(1)</script>", count=7, baseline=1.0,
                  ratio=7.0, examples=[]),
    ])
    html = render.render_dashboard(conn, "2026-W33", watchlist,
                                   tmp_path / "d.html").read_text()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
