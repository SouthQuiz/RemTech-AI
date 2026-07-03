"""Issue #3 — тесты in-memory rate-limiter (sliding window)."""
from app.ratelimit import RateLimiter


def test_allows_up_to_limit_then_blocks():
    rl = RateLimiter(max_events=3, window_seconds=100)
    now = 1000.0
    assert rl.allow("k", now) is True
    assert rl.allow("k", now) is True
    assert rl.allow("k", now) is True
    assert rl.allow("k", now) is False   # 4-я в окне — блок


def test_window_slides():
    rl = RateLimiter(max_events=2, window_seconds=10)
    assert rl.allow("k", 0) is True
    assert rl.allow("k", 1) is True
    assert rl.allow("k", 2) is False
    # спустя окно старые события вытесняются
    assert rl.allow("k", 12) is True


def test_keys_are_independent():
    rl = RateLimiter(max_events=1, window_seconds=100)
    assert rl.allow("a", 0) is True
    assert rl.allow("b", 0) is True
    assert rl.allow("a", 0) is False


def test_reset_clears_key():
    rl = RateLimiter(max_events=1, window_seconds=100)
    assert rl.allow("a", 0) is True
    rl.reset("a")
    assert rl.allow("a", 0) is True
