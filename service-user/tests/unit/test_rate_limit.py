"""Tests du limiteur anti brute-force (SEC-07)."""

import pytest
from unittest.mock import MagicMock

from app.core.rate_limit import (
    SlidingWindowRateLimiter,
    client_ip,
    login_rate_limit,
)


class _Clock:
    """Horloge contrôlable pour des tests déterministes."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class TestSlidingWindow:
    def test_allows_up_to_limit_then_blocks(self):
        clock = _Clock()
        rl = SlidingWindowRateLimiter(3, window_seconds=60, clock=clock)
        assert [rl.hit("k") for _ in range(3)] == [True, True, True]
        assert rl.hit("k") is False  # 4e dans la fenêtre → bloqué

    def test_window_slides_and_frees_slots(self):
        clock = _Clock()
        rl = SlidingWindowRateLimiter(2, window_seconds=60, clock=clock)
        assert rl.hit("k") and rl.hit("k")
        assert rl.hit("k") is False
        clock.now += 61  # la fenêtre a glissé
        assert rl.hit("k") is True

    def test_keys_are_isolated(self):
        rl = SlidingWindowRateLimiter(1, window_seconds=60, clock=_Clock())
        assert rl.hit("ip-a") is True
        assert rl.hit("ip-b") is True  # autre clé, pas impactée
        assert rl.hit("ip-a") is False

    def test_zero_disables_limiter(self):
        rl = SlidingWindowRateLimiter(0, window_seconds=60, clock=_Clock())
        assert all(rl.hit("k") for _ in range(100))


class TestClientIp:
    def test_prefers_forwarded_for(self):
        req = MagicMock()
        req.headers = {"x-forwarded-for": "203.0.113.7, 10.0.0.1"}
        assert client_ip(req) == "203.0.113.7"

    def test_falls_back_to_peer(self):
        req = MagicMock()
        req.headers = {}
        req.client.host = "198.51.100.2"
        assert client_ip(req) == "198.51.100.2"


class TestDependency:
    @pytest.mark.asyncio
    async def test_dependency_raises_429_when_exceeded(self):
        from fastapi import HTTPException

        from app.core import rate_limit

        original_max = rate_limit.login_limiter._max
        rate_limit.login_limiter._max = 1
        rate_limit.login_limiter._hits.clear()
        try:
            req = MagicMock()
            req.headers = {"x-forwarded-for": "192.0.2.55"}

            await login_rate_limit(req)  # 1er passe
            with pytest.raises(HTTPException) as exc:
                await login_rate_limit(req)  # 2e bloqué
            assert exc.value.status_code == 429
            assert exc.value.headers.get("Retry-After") == "60"
        finally:
            rate_limit.login_limiter._max = original_max
