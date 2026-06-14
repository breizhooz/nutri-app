"""Service du matériel de clés E2E (Phase 3).

Range et rend des octets opaques. N'effectue AUCUNE opération cryptographique :
le chiffrement/déchiffrement et la dérivation de clés se font exclusivement côté
client. Cf. docs/rgpd/plan_dpo.md §1.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.key_material import UserKeyMaterial


class KeyMaterialAlreadyExists(Exception):
    """L'utilisateur a déjà inscrit son matériel de clés."""


class KeyMaterialNotFound(Exception):
    """L'utilisateur n'a pas encore de matériel de clés (non inscrit)."""


class KeyMaterialService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID) -> UserKeyMaterial | None:
        result = await self._session.execute(
            select(UserKeyMaterial).where(UserKeyMaterial.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def enroll(
        self,
        user_id: uuid.UUID,
        *,
        salt: bytes,
        kdf_memory_mib: int,
        kdf_iterations: int,
        kdf_parallelism: int,
        wrapped_uk: bytes,
        recovery_salt: bytes,
        wrapped_uk_recovery: bytes,
    ) -> UserKeyMaterial:
        if await self.get(user_id) is not None:
            raise KeyMaterialAlreadyExists()
        material = UserKeyMaterial(
            user_id=user_id,
            salt=salt,
            kdf_memory_mib=kdf_memory_mib,
            kdf_iterations=kdf_iterations,
            kdf_parallelism=kdf_parallelism,
            wrapped_uk=wrapped_uk,
            recovery_salt=recovery_salt,
            wrapped_uk_recovery=wrapped_uk_recovery,
        )
        self._session.add(material)
        await self._session.commit()
        await self._session.refresh(material)
        return material

    async def rotate(
        self,
        user_id: uuid.UUID,
        *,
        salt: bytes,
        kdf_memory_mib: int,
        kdf_iterations: int,
        kdf_parallelism: int,
        wrapped_uk: bytes,
    ) -> UserKeyMaterial:
        """Met à jour MK-salt/params + UK ré-enveloppée (changement de mot de passe).

        La UK reste identique : les blobs de données ne sont pas re-chiffrés. La
        voie de récupération (recovery_salt / wrapped_uk_recovery) est inchangée.
        """
        material = await self.get(user_id)
        if material is None:
            raise KeyMaterialNotFound()
        material.salt = salt
        material.kdf_memory_mib = kdf_memory_mib
        material.kdf_iterations = kdf_iterations
        material.kdf_parallelism = kdf_parallelism
        material.wrapped_uk = wrapped_uk
        await self._session.commit()
        await self._session.refresh(material)
        return material
