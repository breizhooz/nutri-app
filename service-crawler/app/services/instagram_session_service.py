"""Installation/rafraîchissement de la session instaloader depuis un cookie navigateur.

Instagram bloque les logins automatisés : la voie fiable est de copier le cookie
``sessionid`` d'une session navigateur connectée, puis de le valider et de le
persister dans le fichier de session partagé (``INSTAGRAM_SESSION_FILE``) que le
worker de crawl recharge à chaque tâche.
"""

import json
import logging
import os
from datetime import datetime, timezone

import instaloader

from app.core.config import settings
from app.schemas.instagram import InstagramSessionInfo

logger = logging.getLogger(__name__)

# Sidecar JSON stocké à côté du fichier de session : porte le compte et la date
# d'insertion du sessionid (le cookie lui-même n'est jamais relu ni exposé).
_META_SUFFIX = ".meta.json"


class InstagramSessionError(Exception):
    """Cookie ``sessionid`` invalide, expiré, ou session impossible à enregistrer."""


class InstagramSessionService:
    """Valide un cookie ``sessionid`` puis l'enregistre comme session instaloader."""

    def __init__(self, loader_factory=None) -> None:
        self._loader_factory = loader_factory or self._default_loader

    @staticmethod
    def _default_loader() -> instaloader.Instaloader:
        return instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            quiet=True,
            max_connection_attempts=1,
        )

    def update_session(self, session_id: str, username: str | None = None) -> str:
        """Valide ``session_id`` via ``test_login()`` puis l'enregistre sur disque.

        Retourne le compte Instagram authentifié. Bloquant (appel réseau) : à
        exécuter hors de l'event loop.

        Raises:
            InstagramSessionError: aucun compte configuré, cookie vide/invalide,
                ou échec de la vérification réseau.
        """
        user = (username or settings.INSTAGRAM_USERNAME or "").strip().lstrip("@")
        if not user:
            raise InstagramSessionError(
                "Aucun compte Instagram configuré (INSTAGRAM_USERNAME) — "
                "renseignez-le ou fournissez un username."
            )

        session_id = session_id.strip()
        if not session_id:
            raise InstagramSessionError("Le cookie sessionid est vide.")

        loader = self._loader_factory()
        loader.context._session.cookies.set(
            "sessionid", session_id, domain=".instagram.com"
        )
        loader.context.username = user

        try:
            who = loader.test_login()
        except Exception as exc:  # réseau, cookie malformé, etc.
            raise InstagramSessionError(
                f"Échec de la vérification de la session : {exc}"
            ) from exc

        if not who:
            raise InstagramSessionError(
                "Session invalide ou expirée — récupérez un sessionid frais "
                "depuis votre navigateur (instagram.com → cookies → sessionid)."
            )

        session_file = settings.INSTAGRAM_SESSION_FILE
        directory = os.path.dirname(session_file)
        if directory:
            os.makedirs(directory, exist_ok=True)
        loader.save_session_to_file(session_file)
        self._write_meta(session_file, who)
        logger.info("Session Instagram rafraîchie pour @%s", who)
        return who

    @staticmethod
    def _write_meta(session_file: str, username: str) -> None:
        """Persiste le compte et la date d'insertion à côté du fichier de session."""
        meta = {
            "username": username,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with open(session_file + _META_SUFFIX, "w", encoding="utf-8") as fh:
                json.dump(meta, fh)
        except OSError as exc:
            logger.warning("Impossible d'écrire les métadonnées de session : %s", exc)

    def session_info(self) -> InstagramSessionInfo:
        """Retourne l'état de la session enregistrée (compte + date), sans le cookie."""
        session_file = settings.INSTAGRAM_SESSION_FILE
        if not os.path.exists(session_file):
            return InstagramSessionInfo(configured=False)

        username = settings.INSTAGRAM_USERNAME or None
        updated_at = None

        meta_path = session_file + _META_SUFFIX
        if os.path.exists(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as fh:
                    meta = json.load(fh)
                username = meta.get("username") or username
                updated_at = meta.get("updated_at")
            except (OSError, ValueError) as exc:
                logger.warning("Métadonnées de session illisibles : %s", exc)

        if updated_at is None:
            # Sidecar absent (session posée hors UI) → on retombe sur la mtime.
            mtime = os.path.getmtime(session_file)
            updated_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

        return InstagramSessionInfo(
            configured=True, username=username, updated_at=updated_at
        )
