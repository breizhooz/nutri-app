"""Chiffrement at-rest transparent des colonnes sensibles (RGPD art. 32).

``EncryptedText`` est un ``TypeDecorator`` SQLAlchemy : un champ déclaré avec
ce type est chiffré (Fernet) à l'écriture et déchiffré à la lecture, sans que
les routes/repositories n'aient à le savoir. Le stockage reste du ``Text`` (le
jeton Fernet est du base64 URL-safe).

La clé est lue **paresseusement** dans l'environnement (au bind/result, pas à
l'import du modèle) pour éviter les problèmes d'ordre d'initialisation. Une clé
absente lève à la première écriture : on refuse de stocker de la donnée
sensible en clair par accident.

Tolérance migration (MVP) : si le déchiffrement échoue (valeur en clair
héritée, antérieure à l'activation), la valeur brute est renvoyée telle quelle
plutôt que de planter. Les écritures suivantes la re-chiffrent.
"""

import os

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator


class EncryptedText(TypeDecorator):
    """Colonne texte chiffrée Fernet, clé lue depuis une variable d'env."""

    impl = Text
    cache_ok = True

    def __init__(self, key_env: str, **kwargs):
        """key_env : nom de la variable d'env contenant la clé Fernet."""
        super().__init__(**kwargs)
        self._key_env = key_env

    def _fernet(self) -> Fernet:
        key = os.getenv(self._key_env)
        if not key:
            raise RuntimeError(
                f"{self._key_env} manquante : impossible de chiffrer un champ "
                "sensible. Générer une clé (Fernet.generate_key()) et la poser "
                "dans les secrets du service."
            )
        return Fernet(key.encode())

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return self._fernet().encrypt(value.encode()).decode()

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        try:
            return self._fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            # Valeur en clair héritée (avant activation) — tolérée en lecture.
            return value
