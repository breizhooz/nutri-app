"""Port ``EncryptedBlobStore`` + adaptateur PostgreSQL.

Le store range et rend des **octets opaques** ; il ne chiffre/déchiffre JAMAIS
(le chiffrement est exclusivement côté client — E2E zero-knowledge). L'abstraction
permet de remplacer le backend de stockage (PG sur VPS aujourd'hui ; Materia KV
HDS demain) sans toucher aux routes : cf. docs/rgpd/plan_dpo.md §3.

L'adaptateur PG est paramétré par la **classe modèle** du service (qui lie
:class:`~nutri_shared.blobs.models.EncryptedBlobMixin` à sa ``Base`` et sa table),
afin d'être réutilisable tel quel par chaque service (santé, menu, …).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class BlobRecord:
    """Un blob complet (ciphertext inclus)."""

    collection: str
    ref_key: str
    content_version: int
    ciphertext: bytes


@dataclass(frozen=True)
class BlobEnvelope:
    """Enveloppe claire d'un blob (sans ciphertext) — pour la synchro multi-appareils."""

    collection: str
    ref_key: str
    content_version: int
    updated_at: datetime


class BlobConflictError(Exception):
    """Concurrence : la version attendue (If-Match) ne correspond pas à la version courante."""

    def __init__(self, current_version: int) -> None:
        super().__init__(f"version courante={current_version}")
        self.current_version = current_version


class EncryptedBlobStore(ABC):
    """Contrat de stockage de blobs opaques, adressés par (account_id, collection, ref_key)."""

    @abstractmethod
    async def get(
        self, account_id: uuid.UUID, collection: str, ref_key: str
    ) -> BlobRecord | None: ...

    @abstractmethod
    async def put(
        self,
        account_id: uuid.UUID,
        collection: str,
        ref_key: str,
        ciphertext: bytes,
        expected_version: int | None,
    ) -> BlobRecord: ...

    @abstractmethod
    async def delete(
        self, account_id: uuid.UUID, collection: str, ref_key: str
    ) -> bool: ...

    @abstractmethod
    async def list(
        self, account_id: uuid.UUID, collection: str
    ) -> list[BlobEnvelope]: ...


class PgEncryptedBlobStore(EncryptedBlobStore):
    """Adaptateur PostgreSQL (via SQLAlchemy async), paramétré par la classe modèle."""

    def __init__(self, session: AsyncSession, model: type) -> None:
        self._session = session
        self._model = model

    async def _fetch(self, account_id: uuid.UUID, collection: str, ref_key: str):
        model = self._model
        result = await self._session.execute(
            select(model).where(
                model.account_id == account_id,
                model.collection == collection,
                model.ref_key == ref_key,
            )
        )
        return result.scalar_one_or_none()

    async def get(
        self, account_id: uuid.UUID, collection: str, ref_key: str
    ) -> BlobRecord | None:
        row = await self._fetch(account_id, collection, ref_key)
        if row is None:
            return None
        return BlobRecord(
            collection=row.collection,
            ref_key=row.ref_key,
            content_version=row.content_version,
            ciphertext=row.ciphertext,
        )

    async def put(
        self,
        account_id: uuid.UUID,
        collection: str,
        ref_key: str,
        ciphertext: bytes,
        expected_version: int | None,
    ) -> BlobRecord:
        """Upsert avec verrouillage optimiste.

        - ``expected_version`` = version attendue par le client (en-tête If-Match).
          ``None`` = pas de contrôle (dernier écrivain gagne), ``0`` = « doit ne pas exister ».
        - Lève :class:`BlobConflictError` si la version ne correspond pas.
        """
        row = await self._fetch(account_id, collection, ref_key)

        if row is None:
            if expected_version not in (None, 0):
                raise BlobConflictError(current_version=0)
            row = self._model(
                account_id=account_id,
                collection=collection,
                ref_key=ref_key,
                content_version=1,
                ciphertext=ciphertext,
            )
            self._session.add(row)
        else:
            if expected_version is not None and expected_version != row.content_version:
                raise BlobConflictError(current_version=row.content_version)
            row.ciphertext = ciphertext
            row.content_version += 1
            row.updated_at = datetime.now(timezone.utc)

        await self._session.commit()
        return BlobRecord(
            collection=row.collection,
            ref_key=row.ref_key,
            content_version=row.content_version,
            ciphertext=row.ciphertext,
        )

    async def delete(
        self, account_id: uuid.UUID, collection: str, ref_key: str
    ) -> bool:
        model = self._model
        result = await self._session.execute(
            sa_delete(model).where(
                model.account_id == account_id,
                model.collection == collection,
                model.ref_key == ref_key,
            )
        )
        await self._session.commit()
        return (result.rowcount or 0) > 0

    async def list(self, account_id: uuid.UUID, collection: str) -> list[BlobEnvelope]:
        model = self._model
        result = await self._session.execute(
            select(
                model.collection,
                model.ref_key,
                model.content_version,
                model.updated_at,
            ).where(
                model.account_id == account_id,
                model.collection == collection,
            )
        )
        return [
            BlobEnvelope(
                collection=r.collection,
                ref_key=r.ref_key,
                content_version=r.content_version,
                updated_at=r.updated_at,
            )
            for r in result.all()
        ]
