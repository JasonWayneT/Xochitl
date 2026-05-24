"""Shared HTTP utilities for Xochitl skill modules.

All outbound HTTP calls should use ``fetch_bytes`` rather than calling
``urlopen`` directly.  This single entry point provides:

- SSRF validation    (FR-SEC-005  via security.validate_outbound_url)
- Per-domain rate limiting (NFR-API-002 — 5 req / 10 s per domain)
- Exponential-backoff retry (FR-API-005, NFR-PERF-010)

See CR-017 and ADR-003 for design rationale.
"""
# Implements FR-API-005  (retry on transient HTTP failures)
# Implements NFR-PERF-010 (exponential backoff + jitter)
# Implements NFR-API-002  (per-domain sliding-window rate limiter)

from __future__ import annotations

import random
import threading
import time
from collections import deque
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.security import validate_outbound_url  # FR-SEC-005


# ── Retry configuration ───────────────────────────────────────────────────────

_MAX_ATTEMPTS: int = 3
_BASE_DELAY: float = 0.5    # seconds before first retry
_MAX_DELAY: float = 4.0     # exponential growth cap
_JITTER_FACTOR: float = 0.25  # ±25% of current delay
_DEFAULT_TIMEOUT: float = 8.0
_DEFAULT_UA: str = "Xochitl/1.0"

# HTTP status codes indicating a transient failure worth retrying.
_RETRYABLE_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


# ── Rate limiter configuration ────────────────────────────────────────────────

_RL_CAPACITY: int = 5       # max requests allowed in the window per domain
_RL_WINDOW: float = 10.0    # sliding window length in seconds

_rl_lock = threading.Lock()
_rl_buckets: dict[str, deque[float]] = {}  # domain → timestamps of recent requests


# ── Helpers ───────────────────────────────────────────────────────────────────

def _domain_of(url: str) -> str:
    """Return the lowercased netloc (host[:port]) of *url*."""
    return urlparse(url).netloc.lower()


# ── Rate limiter ──────────────────────────────────────────────────────────────

def _rate_limit_acquire(domain: str) -> None:
    """Block until a rate-limit slot is available for *domain*.

    Uses a sliding-window algorithm: a per-domain deque holds the timestamps
    of the most recent ``_RL_CAPACITY`` requests.  When the deque is full the
    caller sleeps (outside the lock) until the oldest timestamp expires, then
    retries.

    Thread-safe: ``_rl_lock`` guards all deque mutations; no sleep is taken
    while the lock is held.

    Implements NFR-API-002.
    """
    while True:
        with _rl_lock:
            bucket = _rl_buckets.setdefault(domain, deque())
            now = time.monotonic()
            # Evict timestamps that have aged out of the window.
            while bucket and now - bucket[0] > _RL_WINDOW:
                bucket.popleft()
            if len(bucket) < _RL_CAPACITY:
                bucket.append(now)
                return  # Slot acquired — caller may proceed.
            # Window full: compute minimum sleep without holding the lock.
            wait_until = bucket[0] + _RL_WINDOW
        # Lock released; sleep outside the critical section.
        sleep_for = max(0.001, wait_until - time.monotonic())
        time.sleep(sleep_for)


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_bytes(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    read_limit: int | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> bytes:
    """Fetch *url* and return the response body as ``bytes``.

    Pipeline (in order):

    1. **SSRF validation** — ``validate_outbound_url(url)`` raises
       ``XochitlPermissionError`` immediately; this is **never retried**.
    2. **Rate limiting** — ``_rate_limit_acquire(domain)`` blocks until a slot
       is available for this domain.
    3. **Fetch with retry** — up to ``_MAX_ATTEMPTS`` attempts with exponential
       backoff + jitter on retryable errors.

    Parameters
    ----------
    url:
        Fully-qualified URL (http or https).
    headers:
        Extra request headers merged on top of the default ``User-Agent``.
    read_limit:
        Maximum bytes to read from the response body (``None`` = unlimited).
    timeout:
        Per-attempt socket timeout in seconds.

    Returns
    -------
    bytes
        Raw response body.

    Raises
    ------
    XochitlPermissionError
        SSRF violation — raised before any network connection is made.
    HTTPError
        Non-retryable HTTP error (e.g., 404).
    URLError / TimeoutError / OSError
        Network error after all retry attempts are exhausted.
    """
    # Step 1: SSRF guard — raises immediately, never retried.
    validate_outbound_url(url)

    # Step 2: per-domain rate limit.
    _rate_limit_acquire(_domain_of(url))

    # Build headers: default UA first, caller can override.
    hdrs: dict[str, str] = {"User-Agent": _DEFAULT_UA}
    if headers:
        hdrs.update(headers)

    # Step 3: fetch with retry.
    last_exc: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        if attempt > 0:
            delay = min(_BASE_DELAY * (2 ** (attempt - 1)), _MAX_DELAY)
            jitter = delay * _JITTER_FACTOR * (2.0 * random.random() - 1.0)
            time.sleep(max(0.0, delay + jitter))

        try:
            req = Request(url, headers=hdrs)
            with urlopen(req, timeout=timeout) as resp:
                return resp.read(read_limit) if read_limit else resp.read()
        except HTTPError as exc:
            if exc.code not in _RETRYABLE_STATUSES:
                raise  # 4xx (except 429) — not worth retrying.
            last_exc = exc
        except (URLError, TimeoutError, OSError) as exc:
            last_exc = exc

    # Exhausted all attempts.
    assert last_exc is not None
    raise last_exc
