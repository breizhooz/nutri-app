"""Schémas du matériel de clés E2E (Phase 3).

Les champs binaires (salt, wrapped_uk, …) transitent en **base64**. Le serveur ne
les interprète jamais : il les range et les rend tels quels.
"""

from pydantic import BaseModel, Field


class KdfParams(BaseModel):
    """Paramètres Argon2id (déterministes par compte)."""

    memory_mib: int = Field(..., ge=8, le=4096)
    iterations: int = Field(..., ge=1, le=20)
    parallelism: int = Field(..., ge=1, le=16)


class KeyMaterialEnrollIn(BaseModel):
    """Inscription initiale du matériel de clés (à la création du compte)."""

    salt: str = Field(..., description="Salt Argon2id (base64).")
    kdf_params: KdfParams
    wrapped_uk: str = Field(
        ..., description="User Key chiffrée par la Master Key (base64)."
    )
    recovery_salt: str = Field(
        ..., description="Salt Argon2id du code de récup (base64)."
    )
    wrapped_uk_recovery: str = Field(
        ..., description="User Key chiffrée par la Recovery Key (base64)."
    )


class KeyRotateIn(BaseModel):
    """Re-enveloppement après changement de mot de passe (la UK ne change pas)."""

    salt: str = Field(..., description="Nouveau salt (base64).")
    kdf_params: KdfParams
    wrapped_uk: str = Field(
        ..., description="UK ré-enveloppée par la nouvelle MK (base64)."
    )


class RecoveryRotateIn(BaseModel):
    """Régénération du code de récupération (la UK ne change pas).

    Seule la voie de récupération est mise à jour ; les params Argon2id (partagés
    avec la Master Key) et le wrap par mot de passe restent inchangés.
    """

    recovery_salt: str = Field(
        ..., description="Nouveau salt du code de récup (base64)."
    )
    wrapped_uk_recovery: str = Field(
        ..., description="UK ré-enveloppée par la nouvelle Recovery Key (base64)."
    )


class KeyMaterialOut(BaseModel):
    """Matériel nécessaire à un appareil pour dériver la MK et déchiffrer la UK."""

    salt: str
    kdf_params: KdfParams
    wrapped_uk: str


class RecoveryMaterialOut(BaseModel):
    """Matériel de la voie de récupération (dérivation de la RK depuis le code)."""

    recovery_salt: str
    kdf_params: KdfParams
    wrapped_uk_recovery: str
