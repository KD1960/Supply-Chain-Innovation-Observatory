import pytest
import requests

from observatory import http, config


class FakeResponse:
    def __init__(self, status_code, text="{}", headers=None, url="https://example.test/x"):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {"Content-Type": "application/json"}
        self.url = url


class FakeSession:
    """Returns queued responses in order and records every call.

    Queued entries can be FakeResponse objects or exceptions to raise.
    """

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        response_or_exception = self._responses.pop(0)
        if isinstance(response_or_exception, Exception):
            raise response_or_exception
        return response_or_exception


def test_fetch_returns_body_on_success():
    session = FakeSession([FakeResponse(200, '{"ok": true}')])
    result = http.fetch(session, "https://example.test/x")
    assert result.status == 200
    assert result.text == '{"ok": true}'


def test_fetch_reports_the_resolved_url_not_the_bare_endpoint():
    # raw_fetch.url is the traceability record. Every Hacker News page comes
    # from one endpoint, so without the params it cannot say which query
    # produced which page.
    resolved = "https://example.test/x?query=freight&page=2"
    session = FakeSession([FakeResponse(200, url=resolved)])
    result = http.fetch(session, "https://example.test/x",
                        params={"query": "freight", "page": 2})
    assert result.url == resolved


def test_fetch_retries_on_429_then_succeeds():
    slept = []
    session = FakeSession([FakeResponse(429), FakeResponse(200, "fine")])
    result = http.fetch(session, "https://example.test/x", sleep_fn=slept.append)
    assert result.text == "fine"
    assert len(session.calls) == 2
    assert slept == [1.0]


def test_fetch_backs_off_exponentially_on_server_errors():
    slept = []
    session = FakeSession([FakeResponse(500), FakeResponse(503), FakeResponse(200, "ok")])
    http.fetch(session, "https://example.test/x", sleep_fn=slept.append)
    assert slept == [1.0, 2.0]


def test_fetch_honours_retry_after_header():
    slept = []
    session = FakeSession(
        [FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(200, "ok")]
    )
    http.fetch(session, "https://example.test/x", sleep_fn=slept.append)
    assert slept == [7.0]


def test_fetch_gives_up_after_retry_budget():
    session = FakeSession([FakeResponse(500)] * 4)
    with pytest.raises(http.HttpError) as excinfo:
        http.fetch(session, "https://example.test/x", retries=3, sleep_fn=lambda _: None)
    assert "500" in str(excinfo.value)


def test_fetch_fails_fast_on_client_error():
    session = FakeSession([FakeResponse(404)])
    with pytest.raises(http.HttpError):
        http.fetch(session, "https://example.test/x", sleep_fn=lambda _: None)
    assert len(session.calls) == 1


def test_rate_limiter_sleeps_the_remaining_interval():
    now = [100.0]
    slept = []
    limiter = http.RateLimiter(2.0, sleep_fn=slept.append, clock_fn=lambda: now[0])
    limiter.wait()
    now[0] = 100.5
    limiter.wait()
    assert slept == [1.5]


def test_fetch_retries_on_connection_error_then_succeeds():
    slept = []
    session = FakeSession([requests.ConnectionError("network down"), FakeResponse(200, "ok")])
    result = http.fetch(session, "https://example.test/x", sleep_fn=slept.append)
    assert result.text == "ok"
    assert len(session.calls) == 2
    assert slept == [1.0]


def test_fetch_gives_up_on_timeout_after_retry_budget():
    session = FakeSession([requests.Timeout("timeout")] * 4)
    with pytest.raises(http.HttpError) as excinfo:
        http.fetch(session, "https://example.test/x", retries=3, sleep_fn=lambda _: None)
    assert "network error" in str(excinfo.value)
    assert "timeout" in str(excinfo.value).lower()


def test_make_session_sets_user_agent(monkeypatch):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "test@example.com")
    session = http.make_session()
    assert session.headers["User-Agent"] == config.user_agent()


class FakePostSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_fetch_post_sends_the_payload_as_json():
    session = FakePostSession([FakeResponse(200, '{"results": []}')])
    result = http.fetch_post(session, "https://example.test/s", {"filters": {"a": 1}})
    assert result.status == 200
    assert session.calls[0]["json"] == {"filters": {"a": 1}}


def test_fetch_post_retries_on_server_error():
    slept = []
    session = FakePostSession([FakeResponse(500), FakeResponse(200, "ok")])
    assert http.fetch_post(session, "https://example.test/s", {}, sleep_fn=slept.append).text == "ok"
    assert slept == [1.0]


def test_fetch_post_retries_network_errors_like_fetch_does():
    slept = []
    session = FakePostSession([requests.ConnectionError("reset"), FakeResponse(200, "ok")])
    assert http.fetch_post(session, "https://example.test/s", {}, sleep_fn=slept.append).text == "ok"
    assert slept == [1.0]


def test_fetch_post_fails_fast_on_client_error():
    session = FakePostSession([FakeResponse(400)])
    with pytest.raises(http.HttpError):
        http.fetch_post(session, "https://example.test/s", {}, sleep_fn=lambda _: None)
    assert len(session.calls) == 1
