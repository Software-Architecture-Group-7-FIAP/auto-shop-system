"""Rate limiting for authentication and unauthenticated public endpoints."""

import hashlib
import hmac
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Protocol

from fastapi import HTTPException, Request, status

from src.config import settings


@dataclass
class _Bucket:
    attempts: list[float] = field(default_factory=list)
    locked_until: float = 0.0
    last_seen: float = 0.0


@dataclass(frozen=True)
class RateLimitPolicy:
    max_requests: int
    window_seconds: int


class PublicRateLimitBackend(Protocol):
    def enforce(self, keys: list[str], policy: RateLimitPolicy) -> int:
        """Consume one request and return seconds to wait, or zero."""

    def reset(self) -> None:
        ...


class InMemoryRateLimitBackend:
    """Bounded in-memory window limiter for local development and tests."""

    def __init__(self, max_buckets: int = 10_000):
        if max_buckets < 1:
            raise ValueError("max_buckets must be positive")
        self.max_buckets = max_buckets
        self._requests: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _cleanup(self, now: float, window_seconds: int) -> None:
        cutoff = now - window_seconds
        stale = []
        for key, timestamps in self._requests.items():
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if not timestamps:
                stale.append(key)
        for key in stale:
            self._requests.pop(key, None)

    def enforce(self, keys: list[str], policy: RateLimitPolicy) -> int:
        now = time.monotonic()
        with self._lock:
            self._cleanup(now, policy.window_seconds)
            retry_after = 0
            for key in keys:
                timestamps = self._requests.get(key)
                if timestamps is None:
                    if len(self._requests) >= self.max_buckets:
                        continue
                    timestamps = deque()
                    self._requests[key] = timestamps
                cutoff = now - policy.window_seconds
                while timestamps and timestamps[0] <= cutoff:
                    timestamps.popleft()
                if len(timestamps) >= policy.max_requests:
                    retry_after = max(
                        retry_after,
                        int(timestamps[0] + policy.window_seconds - now) + 1,
                    )
                    continue
                timestamps.append(now)
            return retry_after

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()


class RedisRateLimitBackend:
    """Shared fixed-window limiter backed by Redis/ElastiCache."""

    _CONSUME_SCRIPT = """
    local count = redis.call('INCR', KEYS[1])
    if count == 1 then
      redis.call('EXPIRE', KEYS[1], ARGV[1])
    end
    return {count, redis.call('TTL', KEYS[1])}
    """

    def __init__(self, url: str):
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("Redis rate limiting requires the redis package") from exc
        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._script = self._client.register_script(self._CONSUME_SCRIPT)
        self._prefix = "oficina:rate-limit:"

    def enforce(self, keys: list[str], policy: RateLimitPolicy) -> int:
        retry_after = 0
        for key in keys:
            count, ttl = self._script(
                keys=[f"{self._prefix}{key}"],
                args=[policy.window_seconds],
            )
            if int(count) > policy.max_requests:
                retry_after = max(retry_after, int(ttl) + 1)
        return retry_after

    def reset(self) -> None:
        # Reset is intended for isolated test Redis instances only.
        for key in self._client.scan_iter(match=f"{self._prefix}*"):
            self._client.delete(key)


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


def _public_rate_limit_backend() -> PublicRateLimitBackend:
    if settings.redis_url:
        return RedisRateLimitBackend(settings.redis_url)
    if settings.is_production_like():
        raise RuntimeError("REDIS_URL is required in production-like environments")
    return InMemoryRateLimitBackend(settings.public_rate_limit_max_buckets)


public_rate_limiter = _public_rate_limit_backend()
_DEFAULT_PUBLIC_RATE_LIMIT_POLICY = RateLimitPolicy(
    max_requests=settings.public_rate_limit_max_requests,
    window_seconds=settings.public_rate_limit_window_seconds,
)
PUBLIC_RATE_LIMIT_POLICIES = {
    "service_order_tracking": _DEFAULT_PUBLIC_RATE_LIMIT_POLICY,
    "budget_decision": _DEFAULT_PUBLIC_RATE_LIMIT_POLICY,
    "customer_lookup": _DEFAULT_PUBLIC_RATE_LIMIT_POLICY,
}


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


def public_throttle_keys(request: Request, fingerprint: str, route: str) -> list[str]:
    client_ip = request.client.host if request.client else "unknown"
    key_fingerprint = hmac.new(
        settings.jwt_secret().encode(),
        fingerprint.encode(),
        hashlib.sha256,
    ).hexdigest()
    return [
        f"route:{route}:ip:{client_ip}",
        f"route:{route}:fingerprint:{key_fingerprint}",
    ]


def enforce_public_rate_limit(request: Request, fingerprint: str, route: str) -> None:
    try:
        policy = PUBLIC_RATE_LIMIT_POLICIES[route]
    except KeyError as exc:
        raise ValueError(f"Unknown public rate-limit route: {route}") from exc
    retry_after = public_rate_limiter.enforce(
        public_throttle_keys(request, fingerprint, route),
        policy,
    )
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas requisições. Tente novamente mais tarde.",
            headers={"Retry-After": str(retry_after)},
        )
