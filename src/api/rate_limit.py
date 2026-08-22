"""In-process throttling for the unauthenticated login endpoint.

Deliberately dependency-free and per-process: it blunts credential stuffing
and the bcrypt CPU cost of a brute-force burst against a single instance. It
is not a substitute for an edge rate limiter once the API runs behind more
than one worker, because each worker keeps its own counters.
"""

import threading
import time
from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status

from src.config import settings


@dataclass
class _Bucket:
    attempts: list[float] = field(default_factory=list)
    locked_until: float = 0.0
    last_seen: float = 0.0


class LoginRateLimiter:
    def __init__(
        self,
        max_attempts: int,
        window_seconds: int,
        lockout_seconds: int,
        max_buckets: int = 10_000,
    ):
        if max_buckets < 1:
            raise ValueError("max_buckets must be positive")
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self.max_buckets = max_buckets
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def _prune(self, bucket: _Bucket, now: float) -> None:
        cutoff = now - self.window_seconds
        bucket.attempts = [moment for moment in bucket.attempts if moment > cutoff]

    def _cleanup(self, now: float) -> None:
        """Drop idle buckets so attacker-controlled keys cannot grow forever."""
        cutoff = now - self.window_seconds
        stale_keys: list[str] = []
        for key, bucket in self._buckets.items():
            self._prune(bucket, now)
            if bucket.locked_until <= now and not bucket.attempts and bucket.last_seen < cutoff:
                stale_keys.append(key)
        for key in stale_keys:
            self._buckets.pop(key, None)

    def _bucket_for_failure(self, key: str, now: float) -> _Bucket | None:
        bucket = self._buckets.get(key)
        if bucket is None:
            self._cleanup(now)
            if len(self._buckets) >= self.max_buckets:
                # Never evict an active lockout: doing so would let an attacker
                # bypass throttling by cycling through fresh usernames.
                candidates = [
                    (candidate_key, candidate)
                    for candidate_key, candidate in self._buckets.items()
                    if candidate.locked_until <= now
                ]
                if candidates:
                    oldest_key, _ = min(candidates, key=lambda item: item[1].last_seen)
                    self._buckets.pop(oldest_key, None)
            if len(self._buckets) >= self.max_buckets:
                # The IP bucket is still bounded and remains effective. Do not
                # allocate an unbounded fallback for this key.
                return None
            bucket = _Bucket(last_seen=now)
            self._buckets[key] = bucket
        bucket.last_seen = now
        return bucket

    def retry_after(self, keys: list[str]) -> int:
        """Return the number of seconds the caller must wait, 0 when allowed."""
        now = time.monotonic()
        with self._lock:
            self._cleanup(now)
            wait = 0.0
            for key in keys:
                bucket = self._buckets.get(key)
                if bucket and bucket.locked_until > now:
                    wait = max(wait, bucket.locked_until - now)
            return int(wait) + 1 if wait > 0 else 0

    def register_failure(self, keys: list[str]) -> None:
        now = time.monotonic()
        with self._lock:
            for key in keys:
                bucket = self._bucket_for_failure(key, now)
                if bucket is None:
                    continue
                self._prune(bucket, now)
                bucket.attempts.append(now)
                bucket.last_seen = now
                if len(bucket.attempts) >= self.max_attempts:
                    bucket.locked_until = now + self.lockout_seconds
                    bucket.attempts.clear()

    def register_success(self, keys: list[str]) -> None:
        with self._lock:
            for key in keys:
                self._buckets.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()

 

login_rate_limiter = LoginRateLimiter(
    max_attempts=settings.login_max_attempts,
    window_seconds=settings.login_attempt_window_seconds,
    lockout_seconds=settings.login_lockout_seconds,
    max_buckets=settings.login_rate_limit_max_buckets,
)


def login_throttle_keys(request: Request, username: str) -> list[str]:
    client_ip = request.client.host if request.client else "unknown"
    return [f"ip:{client_ip}", f"user:{username.strip().lower()}"]


def enforce_login_rate_limit(keys: list[str]) -> None:
    retry_after = login_rate_limiter.retry_after(keys)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas de login. Tente novamente mais tarde.",
            headers={"Retry-After": str(retry_after)},
        )
