from __future__ import annotations

import asyncio
import json
import logging

from pywebpush import WebPushException, webpush

from app.models.subscription import Subscription

logger = logging.getLogger(__name__)


class PushService:
    """
    Envoie une notification WebPush (VAPID) à un device abonné.
    pywebpush est synchrone — exécuté dans asyncio.to_thread pour ne pas
    bloquer la boucle d'événements FastAPI.
    """

    def __init__(self, vapid_private_key: str, vapid_claims_email: str) -> None:
        self._vapid_private_key = vapid_private_key
        self._vapid_claims = {"sub": f"mailto:{vapid_claims_email}"}

    async def send(
        self,
        subscription: Subscription,
        title: str,
        body: str,
        data: dict | None = None,
    ) -> bool:
        """
        Envoie le push au device.
        Retourne True si succès, False sinon (erreurs loguées, non propagées).
        """
        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh_key,
                "auth": subscription.auth_key,
            },
        }
        payload = json.dumps({"title": title, "body": body, "data": data or {}})

        try:
            await asyncio.to_thread(
                webpush,
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=self._vapid_private_key,
                vapid_claims=self._vapid_claims,
            )
            return True
        except WebPushException as exc:
            # 410 Gone = subscription expirée, 400/401 = clés invalides
            logger.warning("WebPush fail (slug=%s) : %s", subscription.slug, exc)
            return False
        except Exception as exc:
            logger.error(
                "WebPush unexpected failure (slug=%s) : %s", subscription.slug, exc
            )
            return False