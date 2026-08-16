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
    pass


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
    last_status = None
    for attempt in range(retries + 1):
        if limiter is not None:
            limiter.wait()
        raw = session.get(url, params=params, headers=headers, timeout=TIMEOUT_SECONDS)
        last_status = raw.status_code
        if raw.status_code == 200:
            return Response(
                url=url,
                status=raw.status_code,
                text=raw.text,
                content_type=raw.headers.get("Content-Type", ""),
            )
        if raw.status_code not in RETRYABLE_STATUSES:
            raise HttpError(f"GET {url} failed with status {raw.status_code}")
        if attempt == retries:
            break
        sleep_fn(_backoff_seconds(raw, attempt))
    raise HttpError(f"GET {url} still failing with status {last_status} after {retries} retries")


def _backoff_seconds(raw: Any, attempt: int) -> float:
    retry_after = raw.headers.get("Retry-After") if hasattr(raw, "headers") else None
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return float(2**attempt)
