from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field

import httpx
from pywebpush import webpush, WebPushException

from app.models.enums import PushChannel
from app.models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotificationPayload:
    """Contenu structuré d'une notification push."""
    title: str
    body: str
    data: dict = field(default_factory=dict)


@dataclass
class DispatchResult:
    """Résultat agrégé d'un envoi multi-appareil."""
    sent: int = 0
    failed: int = 0


class NotificationService:
    """
    Envoie des notifications push via Web Push (VAPID) ou Expo Push.
    Une instance par tâche Celery — clés VAPID injectées au constructeur.
    """

    _EXPO_PUSH_API_URL = "https://exp.host/--/api/v2/push/send"

    def __init__(
        self,
        vapid_private_key: str,
        vapid_claims_email: str,
        expo_api_url: str = _EXPO_PUSH_API_URL,
    ) -> None:
        self._vapid_private_key = vapid_private_key
        self._vapid_claims = {"sub": f"mailto:{vapid_claims_email}"}
        self._expo_api_url = expo_api_url

    @staticmethod
    def build_payload(
        source_type: str,
        new_count: int,
        source_label: str = "",
    ) -> NotificationPayload:
        """Construit le payload depuis les métadonnées du crawl terminé."""
        label = source_label or source_type
        return NotificationPayload(
            title="NutriPlanner — Nouveaux contenus",
            body=(
                f"{new_count} recette(s) extraite(s) depuis {label} "
                "sont en attente de validation."
            ),
            data={"source_type": source_type, "new_count": new_count},
        )

    async def dispatch(
        self,
        subscriptions: list[PushSubscription],
        payload: NotificationPayload,
    ) -> DispatchResult:
        """
        Envoie la notification à tous les abonnements.
        Les erreurs individuelles sont loguées sans interrompre la boucle.
        """
        result = DispatchResult()
        for sub in subscriptions:
            success = await self._route(sub, payload)
            if success:
                result.sent += 1
            else:
                result.failed += 1
        return result

    async def _route(
        self,
        subscription: PushSubscription,
        payload: NotificationPayload,
    ) -> bool:
        """Délègue vers le bon canal selon subscription.channel."""
        if subscription.channel == PushChannel.WEB_PUSH:
            return await self._send_web_push(subscription, payload)
        if subscription.channel == PushChannel.EXPO:
            return await self._send_expo(subscription, payload)
        logger.warning("Canal de notification inconnu : %s", subscription.channel)
        return False

    async def _send_web_push(
        self,
        subscription: PushSubscription,
        payload: NotificationPayload,
    ) -> bool:
        """
        Envoie via VAPID (pywebpush est synchrone).
        Exécuté dans un thread pool pour ne pas bloquer la boucle event.
        """
        try:
            subscription_info = json.loads(subscription.token)
        except json.JSONDecodeError:
            logger.error("WebPush : token non-JSON (user=%s)", subscription.user_id)
            return False

        try:
            data = json.dumps(
                {"title": payload.title, "body": payload.body, "data": payload.data}
            )
            await asyncio.to_thread(
                webpush,
                subscription_info=subscription_info,
                data=data,
                vapid_private_key=self._vapid_private_key,
                vapid_claims=self._vapid_claims,
            )
            return True
        except WebPushException as exc:
            logger.error("WebPush échoué (user=%s) : %s", subscription.user_id, exc)
            return False
        except Exception as exc:
            logger.error(
                "WebPush erreur inattendue (user=%s) : %s", subscription.user_id, exc
            )
            return False

    async def _send_expo(
        self,
        subscription: PushSubscription,
        payload: NotificationPayload,
    ) -> bool:
        """Envoie via l'API HTTP Expo Push."""
        body = {
            "to": subscription.token,
            "title": payload.title,
            "body": payload.body,
            "data": payload.data,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self._expo_api_url,
                    json=body,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                # L'API Expo renvoie {"data": [{"status": "ok"|"error", ...}]}
                tickets = response.json().get("data", [])
                ticket = tickets[0] if tickets else {}
                if ticket.get("status") == "error":
                    logger.error(
                        "Expo Push refusé (user=%s) : %s",
                        subscription.user_id,
                        ticket.get("message"),
                    )
                    return False
            return True
        except httpx.HTTPError as exc:
            logger.error(
                "Expo Push HTTP échoué (user=%s) : %s", subscription.user_id, exc
            )
            return False