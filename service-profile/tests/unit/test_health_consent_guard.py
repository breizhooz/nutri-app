"""Tests du garde-fou RGPD (art. 9) : pas de traitement santé sans consentement."""

import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import AsyncClient


def _token(*, sub: uuid.UUID, account_id: uuid.UUID, health_consent: bool) -> str:
    """Forge un JWT d'accès portant (ou non) le claim ``health_consent``."""
    payload = {
        "sub": str(sub),
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "act_account": str(account_id),
        "scopes": ["profile:read", "profile:write"],
        "user_admin": False,
        "user_right": {},
        "health_consent": health_consent,
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")


class TestHealthConsentGuard:
    """POST des écritures santé exige le consentement (art. 9)."""

    @pytest.mark.unit
    async def test_write_blocked_without_consent(
        self,
        raw_client: AsyncClient,
        test_user_id: uuid.UUID,
        test_account_id: uuid.UUID,
    ) -> None:
        """Sans consentement actif, créer une condition médicale est refusé (403)."""
        consent = {
            "Authorization": f"Bearer {_token(sub=test_user_id, account_id=test_account_id, health_consent=True)}"
        }
        no_consent = {
            "Authorization": f"Bearer {_token(sub=test_user_id, account_id=test_account_id, health_consent=False)}"
        }
        # Dossier créé avec consentement (la création de profil n'est pas gardée).
        await raw_client.post(
            "/api/v1/profiles", json={"height_cm": 170.0}, headers=consent
        )

        blocked = await raw_client.post(
            "/api/v1/profiles/me/conditions",
            json={"category": "metabolic", "condition_name": "Diabète"},
            headers=no_consent,
        )
        assert blocked.status_code == 403

    @pytest.mark.unit
    async def test_write_allowed_with_consent(
        self,
        raw_client: AsyncClient,
        test_user_id: uuid.UUID,
        test_account_id: uuid.UUID,
    ) -> None:
        """Avec consentement actif, l'écriture santé passe (201)."""
        consent = {
            "Authorization": f"Bearer {_token(sub=test_user_id, account_id=test_account_id, health_consent=True)}"
        }
        await raw_client.post(
            "/api/v1/profiles", json={"height_cm": 170.0}, headers=consent
        )
        allowed = await raw_client.post(
            "/api/v1/profiles/me/conditions",
            json={"category": "metabolic", "condition_name": "Diabète"},
            headers=consent,
        )
        assert allowed.status_code == 201
