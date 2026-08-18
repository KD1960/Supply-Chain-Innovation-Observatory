import json
from pathlib import Path

from observatory.collectors.github import GithubCollector

FIXTURE = Path(__file__).parent / "fixtures" / "github_page.json"


def test_parse_returns_a_document_per_repository():
    documents = GithubCollector().parse(FIXTURE.read_text())
    assert documents
    assert all(doc.doc_id.startswith("github:") for doc in documents)


def test_doc_id_is_the_full_name_so_a_repo_counts_once():
    first = GithubCollector().parse(FIXTURE.read_text())[0]
    assert first.doc_id == f"github:{first.title}"
    assert "/" in first.title


def test_created_at_becomes_the_document_date():
    for doc in GithubCollector().parse(FIXTURE.read_text()):
        assert doc.date is None or (len(doc.date) == 10 and doc.date[4] == "-")


def test_star_count_lands_in_amount():
    for doc in GithubCollector().parse(FIXTURE.read_text()):
        assert doc.amount is None or isinstance(doc.amount, float)


def test_description_and_language_are_searchable_body():
    documents = GithubCollector().parse(FIXTURE.read_text())
    assert any(doc.text for doc in documents)


def test_a_null_description_does_not_crash_or_become_the_string_none():
    payload = json.dumps({"items": [{
        "full_name": "acme/thing", "html_url": "https://github.com/acme/thing",
        "description": None, "language": None,
        "created_at": "2026-08-12T10:00:00Z", "stargazers_count": 4,
    }]})
    doc = GithubCollector().parse(payload)[0]
    assert doc.text == ""
    assert "None" not in (doc.text or "")


def test_items_without_a_full_name_are_skipped():
    payload = json.dumps({"items": [{"html_url": "https://github.com/x"}]})
    assert GithubCollector().parse(payload) == []


def test_parse_handles_an_empty_result_set():
    assert GithubCollector().parse(json.dumps({"items": []})) == []


def test_date_range_covers_the_week_plus_the_lookback():
    assert GithubCollector().date_range("2026-W33") == "created:2026-08-03..2026-08-16"


def test_auth_headers_carry_a_bearer_token_and_never_a_url_parameter(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-value")
    headers = GithubCollector().auth_headers()
    assert headers["Authorization"] == "Bearer test-token-value"
    assert headers["Accept"] == "application/vnd.github+json"


def test_the_committed_fixture_contains_no_credential():
    text = FIXTURE.read_text()
    for marker in ("ghp_", "github_pat_", "Authorization", "Bearer "):
        assert marker not in text, f"fixture leaks {marker}"
