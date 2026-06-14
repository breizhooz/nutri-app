"""RGPD Phase 5 — chiffrement at-rest (EncryptedText) + scrubbing des logs.

Couvre les utilitaires partagés `nutri_shared` consommés par service-profile :
le ``TypeDecorator`` de chiffrement Fernet et la rédaction des champs sensibles
du middleware de journalisation.
"""

import os

import pytest
from cryptography.fernet import Fernet

from nutri_shared.core.middleware import _redact
from nutri_shared.db.encrypted import EncryptedText

KEY_ENV = "PROFILE_FIELD_ENCRYPTION_KEY"


# ── Chiffrement at-rest ─────────────────────────────────────────────────────
def test_encrypted_text_round_trips():
    col = EncryptedText(KEY_ENV)
    cipher = col.process_bind_param("hypertension légère", None)
    assert col.process_result_value(cipher, None) == "hypertension légère"


def test_stored_value_is_ciphertext_not_plaintext():
    col = EncryptedText(KEY_ENV)
    cipher = col.process_bind_param("allergie arachide sévère", None)
    # Le contenu stocké ne doit jamais contenir le clair.
    assert "arachide" not in cipher
    assert cipher != "allergie arachide sévère"


def test_none_passes_through():
    col = EncryptedText(KEY_ENV)
    assert col.process_bind_param(None, None) is None
    assert col.process_result_value(None, None) is None


def test_legacy_plaintext_is_tolerated_on_read():
    # Valeur en clair antérieure à l'activation : lue telle quelle, sans planter.
    col = EncryptedText(KEY_ENV)
    assert col.process_result_value("ancien texte non chiffré", None) == (
        "ancien texte non chiffré"
    )


def test_missing_key_raises_on_write():
    col = EncryptedText("CLE_INEXISTANTE_XYZ")
    assert os.getenv("CLE_INEXISTANTE_XYZ") is None
    with pytest.raises(RuntimeError):
        col.process_bind_param("donnée santé", None)


def test_two_keys_are_incompatible():
    a = EncryptedText(KEY_ENV)
    cipher = a.process_bind_param("secret médical", None)
    # Une autre clé ne peut pas déchiffrer → tolérance renvoie le ciphertext brut.
    other_env = "OTHER_FERNET_KEY"
    os.environ[other_env] = Fernet.generate_key().decode()
    b = EncryptedText(other_env)
    assert b.process_result_value(cipher, None) == cipher  # pas le clair


# ── Scrubbing des logs ──────────────────────────────────────────────────────
def test_redact_masks_health_and_secret_fields():
    payload = {
        "condition_name": "diabète",          # non sensible (nom de clé)
        "notes": "détails médicaux intimes",
        "medical_contraindications": "ne pas prescrire X",
        "password": "hunter2",
        "access_token": "abc.def",
    }
    out = _redact(payload)
    assert out["condition_name"] == "diabète"
    assert out["notes"] == "[REDACTED]"
    assert out["medical_contraindications"] == "[REDACTED]"
    assert out["password"] == "[REDACTED]"
    assert out["access_token"] == "[REDACTED]"


def test_redact_is_recursive():
    payload = {"profile": {"items": [{"notes": "x"}, {"label": "ok"}]}}
    out = _redact(payload)
    assert out["profile"]["items"][0]["notes"] == "[REDACTED]"
    assert out["profile"]["items"][1]["label"] == "ok"


def test_redact_leaves_non_sensitive_untouched():
    payload = {"allergen": "arachide", "severity": "high"}
    assert _redact(payload) == payload
