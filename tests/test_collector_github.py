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


# --- the page cap, and saying so ------------------------------------------

import pytest

from observatory import http
from observatory.collectors import github as github_module


def test_a_total_count_above_the_cap_produces_a_warning():
    payload = {"total_count": 2183, "items": []}
    notice = github_module.truncation_warning("supply chain", "2026-W33", payload)
    assert notice is not None
    assert "supply chain" in notice
    assert "2026-W33" in notice
    assert "2183" in notice
    assert str(github_module.MAX_RESULTS) in notice


def test_a_total_count_within_the_cap_produces_no_warning():
    payload = {"total_count": 39, "items": []}
    assert github_module.truncation_warning("freight", "2026-W33", payload) is None


def test_a_total_count_exactly_at_the_cap_is_not_truncated():
    payload = {"total_count": github_module.MAX_RESULTS, "items": []}
    assert github_module.truncation_warning("freight", "2026-W33", payload) is None


def test_a_missing_or_unparseable_total_count_is_not_reported_as_truncation():
    assert github_module.truncation_warning("freight", "2026-W33", {}) is None
    assert github_module.truncation_warning("freight", "2026-W33", {"total_count": None}) is None


class _NoWait:
    """RateLimiter's shape without its sleeping."""

    def __init__(self, *_args, **_kwargs):
        pass

    def wait(self):
        pass


class _FakeResponse:
    def __init__(self, text):
        self.status_code = 200
        self.text = text
        self.headers = {"Content-Type": "application/json"}
        self.url = "https://api.github.com/search/repositories?q=x"


class _FakeSession:
    def __init__(self, pages):
        self._pages = list(pages)
        self.calls = 0

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls += 1
        return _FakeResponse(self._pages[min(self.calls - 1, len(self._pages) - 1)])


def _page(total_count, item_count, offset=0):
    return json.dumps({"total_count": total_count, "items": [
        {"full_name": f"acme/repo{offset + n}",
         "html_url": f"https://github.com/acme/repo{offset + n}",
         "description": "a thing", "language": "Python",
         "created_at": "2026-08-12T10:00:00Z", "stargazers_count": n}
        for n in range(item_count)
    ]})


@pytest.fixture()
def one_anchor(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-value")
    monkeypatch.setattr(github_module, "ANCHOR_QUERIES", ("freight",))
    monkeypatch.setattr(http, "RateLimiter", _NoWait)


def test_fetch_raw_warns_once_per_truncated_anchor(one_anchor, capsys):
    session = _FakeSession([_page(3107, github_module.PAGE_SIZE)])
    pages = list(GithubCollector().fetch_raw(session, "2026-W33"))

    assert len(pages) == github_module.MAX_PAGES, "the cap is unchanged"
    warnings = [line for line in capsys.readouterr().err.splitlines() if "truncated" in line]
    assert len(warnings) == 1, "one line per anchor, not one per page"
    assert "3107" in warnings[0] and "freight" in warnings[0]


def test_fetch_raw_is_silent_when_the_anchor_fits(one_anchor, capsys):
    session = _FakeSession([_page(39, 39)])
    pages = list(GithubCollector().fetch_raw(session, "2026-W33"))

    assert len(pages) == 1, "a short page ends the anchor"
    assert "truncated" not in capsys.readouterr().err


def test_a_dropped_item_does_not_end_a_full_page_early(one_anchor):
    """An item without a `full_name` is skipped by `parse`, so counting parsed
    documents would read a full page as a short one and abandon the anchor."""
    full_page = json.loads(_page(3107, github_module.PAGE_SIZE))
    full_page["items"][0].pop("full_name")
    session = _FakeSession([json.dumps(full_page)])

    assert len(list(GithubCollector().fetch_raw(session, "2026-W33"))) == github_module.MAX_PAGES
