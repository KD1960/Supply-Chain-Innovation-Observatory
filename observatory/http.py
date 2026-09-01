"""One shared HTTP path for every collector: same User-Agent, same retry rules,
same rate limiting. Collectors never call requests directly."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

from . import config

TIMEOUT_SECONDS = 60
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class HttpError(RuntimeError):
    """Carries the status so the caller can log the attempt.

    `raw_fetch` is described as a log of fetch attempts and held 200 on all
    3,114 rows, because the only insert sat downstream of this raise. The
    status has to survive the raise for the row to be writable. It is None for
    a network error, where there was no response to have a status.
    """

    def __init__(self, message: str, url: str | None = None, status: int | None = None):
        super().__init__(message)
        self.url = url
        self.status = status


@dataclass(frozen=True)
class Response:
    url: str
    status: int
    text: str
    content_type: str


class RateLimiter:
    """Enforces a minimum gap between requests to one host."""

    def __init__(
        self,
        min_interval_seconds: float,
        sleep_fn: Callable[[float], Any] = time.sleep,
        clock_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.min_interval = min_interval_seconds
        self._sleep = sleep_fn
        self._clock = clock_fn
        self._last: float | None = None

    def wait(self) -> None:
        now = self._clock()
        if self._last is not None:
            remaining = self.min_interval - (now - self._last)
            if remaining > 0:
                self._sleep(remaining)
        self._last = self._clock()


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = config.user_agent()
    session.headers["Accept-Encoding"] = "gzip, deflate"
    return session


def fetch(
    session: Any,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    limiter: RateLimiter | None = None,
    retries: int = 3,
    sleep_fn: Callable[[float], Any] = time.sleep,
) -> Response:
    return _with_retries(
        lambda: session.get(url, params=params, headers=headers, timeout=TIMEOUT_SECONDS),
        url, retries, limiter, sleep_fn,
    )


def fetch_post(
    session: Any,
    url: str,
    payload: dict,
    *,
    headers: dict | None = None,
    limiter: RateLimiter | None = None,
    retries: int = 3,
    sleep_fn: Callable[[float], Any] = time.sleep,
) -> Response:
    return _with_retries(
        lambda: session.post(url, json=payload, headers=headers, timeout=TIMEOUT_SECONDS),
        url, retries, limiter, sleep_fn,
    )


def _with_retries(
    send: Callable[[], Any],
    url: str,
    retries: int,
    limiter: RateLimiter | None,
    sleep_fn: Callable[[float], Any],
) -> Response:
    last_status = None
    last_exception: requests.RequestException | None = None
    for attempt in range(retries + 1):
        if limiter is not None:
            limiter.wait()
        try:
            raw = send()
        except requests.RequestException as e:
            last_exception = e
            last_status = None
            if attempt == retries:
                break
            sleep_fn(_backoff_seconds(None, attempt, limiter))
            continue
        last_exception = None
        last_status = raw.status_code
        if raw.status_code == 200:
            return Response(
                # The resolved URL, params and redirects included: raw_fetch is
                # the traceability record, and the bare endpoint cannot say
                # which query produced which page.
                url=getattr(raw, "url", url),
                status=raw.status_code,
                text=raw.text,
                content_type=raw.headers.get("Content-Type", ""),
            )
        if raw.status_code not in RETRYABLE_STATUSES:
            raise HttpError(f"{url} failed with status {raw.status_code}",
                            url=url, status=raw.status_code)
        if attempt == retries:
            break
        sleep_fn(_backoff_seconds(raw, attempt, limiter))
    if last_exception is not None:
        raise HttpError(f"{url} failed with network error: {last_exception}",
                        url=url) from last_exception
    # Only the failure that surfaced is logged, not each retry: recording every
    # attempt would need a database handle inside the HTTP layer, which is
    # deliberately kept out of it.
    raise HttpError(f"{url} still failing with status {last_status} after {retries} retries",
                    url=url, status=last_status)


def _backoff_seconds(raw: Any, attempt: int, limiter: RateLimiter | None = None) -> float:
    retry_after = raw.headers.get("Retry-After") if raw is not None and hasattr(raw, "headers") else None
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    status = getattr(raw, "status_code", None) if raw is not None else None
    # A 429 is the server explicitly saying our pacing is wrong, not just a
    # bad moment like a 5xx. Repeating the same cadence that got us
    # rate-limited is guaranteed not to help, so escalate faster than the
    # baseline exponential backoff used for retryable server errors.
    base = 4.0 if status == 429 else 2.0
    backoff = float(base**attempt)
    if limiter is not None:
        # A backoff shorter than the caller's own declared rate limit
        # guarantees hitting the server again before the interval it (or we)
        # already committed to has elapsed. Never retry sooner than that.
        backoff = max(backoff, limiter.min_interval)
    return backoff
