from src.api import rate_limit
from src.api.rate_limit import LoginRateLimiter


def test_login_rate_limiter_keeps_bucket_cardinality_bounded():
    limiter = LoginRateLimiter(
        max_attempts=3,
        window_seconds=300,
        lockout_seconds=60,
        max_buckets=2,
    )

    limiter.register_failure(["user:first"])
    limiter.register_failure(["user:second"])
    limiter.register_failure(["user:third"])

    assert len(limiter._buckets) == 2


def test_login_rate_limiter_never_evicts_an_active_lockout():
    limiter = LoginRateLimiter(
        max_attempts=1,
        window_seconds=300,
        lockout_seconds=60,
        max_buckets=2,
    )

    limiter.register_failure(["user:first"])
    limiter.register_failure(["user:second"])
    limiter.register_failure(["user:attacker"])

    assert limiter.retry_after(["user:first"]) > 0
    assert limiter.retry_after(["user:second"]) > 0
    assert len(limiter._buckets) == 2


def test_login_rate_limiter_expires_idle_attempt_buckets(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: clock[0])
    limiter = LoginRateLimiter(
        max_attempts=3,
        window_seconds=60,
        lockout_seconds=30,
        max_buckets=2,
    )

    limiter.register_failure(["user:idle"])
    clock[0] += 61
    limiter.retry_after([])

    assert limiter._buckets == {}
