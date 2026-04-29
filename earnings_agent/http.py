"""Shared HTTP client with polite defaults (User-Agent, throttling)."""

from __future__ import annotations

import os
import time
from threading import Lock

import httpx

# SEC requires a descriptive User-Agent with contact info.
# https://www.sec.gov/os/accessing-edgar-data
DEFAULT_UA = "earnings-agent/0.1 (contact: set SEC_USER_AGENT env var)"


def sec_user_agent() -> str:
    return os.environ.get("SEC_USER_AGENT", DEFAULT_UA)


class Throttle:
    """Simple per-host minimum-interval throttle."""

    def __init__(self, min_interval: float) -> None:
        self.min_interval = min_interval
        self._last = 0.0
        self._lock = Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self.min_interval - (now - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()


# SEC limit is 10 req/s; stay well under.
_sec_throttle = Throttle(min_interval=0.15)
_fool_throttle = Throttle(min_interval=1.0)


def sec_client() -> httpx.Client:
    return httpx.Client(
        headers={
            "User-Agent": sec_user_agent(),
            "Accept-Encoding": "gzip, deflate",
        },
        timeout=30.0,
        follow_redirects=True,
    )


def fool_client() -> httpx.Client:
    return httpx.Client(
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
        timeout=30.0,
        follow_redirects=True,
    )


def sec_get(client: httpx.Client, url: str) -> httpx.Response:
    _sec_throttle.wait()
    r = client.get(url)
    r.raise_for_status()
    return r


def fool_get(client: httpx.Client, url: str) -> httpx.Response:
    _fool_throttle.wait()
    r = client.get(url)
    r.raise_for_status()
    return r
