"""Limiteur de débit léger anti brute-force (SEC-07).

Fenêtre glissante en mémoire, par clé (IP + route). Sans dépendance externe et
sans état partagé : suffisant pour ralentir le credential stuffing / le
brute-force d'OTP sur un déploiement mono-worker.

Limite connue : l'état est par-process (non partagé entre réplicas, remis à zéro
au redémarrage). Pour un durcissement multi-worker, basculer le backend de
comptage vers Redis (clé `login:<ip>` avec TTL).
"""

import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.i18n.loader import t


class SlidingWindowRateLimiter:
    """Autorise au plus ``max_requests`` hits par ``window_seconds`` et par clé."""

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str) -> bool:
        """Enregistre un appel. Retourne ``False`` si la limite est dépassée."""
        if self._max <= 0:  # limitation désactivée
            return True
        now = self._clock()
        cutoff = now - self._window
        bucket = self._hits[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= self._max:
            return False
        bucket.append(now)
        return True


def client_ip(request: Request) -> str:
    """IP réelle du client derrière Traefik (1er maillon de X-Forwarded-For)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _make_dependency(limiter: SlidingWindowRateLimiter, scope: str):
    async def _dependency(request: Request) -> None:
        if not limiter.hit(f"{scope}:{client_ip(request)}"):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=t.get("auth.too_many_requests"),
                headers={"Retry-After": "60"},
            )

    return _dependency


login_limiter = SlidingWindowRateLimiter(
    settings.LOGIN_RATE_LIMIT_PER_MINUTE, window_seconds=60
)
mfa_verify_limiter = SlidingWindowRateLimiter(
    settings.MFA_VERIFY_RATE_LIMIT_PER_MINUTE, window_seconds=60
)

login_rate_limit = _make_dependency(login_limiter, "login")
mfa_verify_rate_limit = _make_dependency(mfa_verify_limiter, "mfa-verify")
