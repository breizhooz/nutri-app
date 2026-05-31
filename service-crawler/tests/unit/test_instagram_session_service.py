import json
import os

from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.services.instagram_session_service import (
    InstagramSessionError,
    InstagramSessionService,
)


def _fake_loader(test_login_return="bob", raises: Exception | None = None) -> MagicMock:
    loader = MagicMock()
    loader.context = MagicMock()
    loader.context._session = MagicMock()
    if raises is not None:
        loader.test_login.side_effect = raises
    else:
        loader.test_login.return_value = test_login_return
    return loader


@pytest.fixture
def session_file(tmp_path, monkeypatch):
    path = str(tmp_path / "instagram_session")
    monkeypatch.setattr(settings, "INSTAGRAM_SESSION_FILE", path)
    monkeypatch.setattr(settings, "INSTAGRAM_USERNAME", "bob")
    return path


class TestInstagramSessionService:
    def test_valid_session_is_saved(self, session_file):
        loader = _fake_loader(test_login_return="bob")
        service = InstagramSessionService(loader_factory=lambda: loader)

        who = service.update_session("SID123")

        assert who == "bob"
        loader.context._session.cookies.set.assert_called_once()
        _, kwargs = loader.context._session.cookies.set.call_args
        assert loader.context._session.cookies.set.call_args[0][0] == "sessionid"
        assert loader.context._session.cookies.set.call_args[0][1] == "SID123"
        loader.save_session_to_file.assert_called_once_with(session_file)

    def test_update_writes_meta_sidecar(self, session_file):
        loader = _fake_loader(test_login_return="bob")
        service = InstagramSessionService(loader_factory=lambda: loader)

        service.update_session("SID123")

        meta_path = session_file + ".meta.json"
        assert os.path.exists(meta_path)
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
        assert meta["username"] == "bob"
        assert meta["updated_at"]  # ISO non vide

    def test_session_info_not_configured_when_missing(self, session_file):
        # session_file pointe vers un chemin qui n'existe pas encore
        service = InstagramSessionService()
        info = service.session_info()
        assert info.configured is False
        assert info.username is None

    def test_session_info_reads_meta(self, session_file):
        # crée un fichier de session + son sidecar
        with open(session_file, "w", encoding="utf-8") as fh:
            fh.write("x")
        with open(session_file + ".meta.json", "w", encoding="utf-8") as fh:
            json.dump({"username": "alice", "updated_at": "2026-05-30T10:00:00+00:00"}, fh)

        info = InstagramSessionService().session_info()

        assert info.configured is True
        assert info.username == "alice"
        assert info.updated_at == "2026-05-30T10:00:00+00:00"

    def test_session_info_falls_back_to_mtime(self, session_file):
        with open(session_file, "w", encoding="utf-8") as fh:
            fh.write("x")  # pas de sidecar

        info = InstagramSessionService().session_info()

        assert info.configured is True
        assert info.username == "bob"  # depuis settings.INSTAGRAM_USERNAME
        assert info.updated_at is not None

    def test_username_override_strips_at(self, session_file):
        loader = _fake_loader(test_login_return="alice")
        service = InstagramSessionService(loader_factory=lambda: loader)

        who = service.update_session("SID", username="@alice")

        assert who == "alice"
        assert loader.context.username == "alice"

    def test_invalid_session_raises_and_does_not_save(self, session_file):
        loader = _fake_loader(test_login_return=None)
        service = InstagramSessionService(loader_factory=lambda: loader)

        with pytest.raises(InstagramSessionError):
            service.update_session("SID")
        loader.save_session_to_file.assert_not_called()

    def test_test_login_exception_wrapped(self, session_file):
        loader = _fake_loader(raises=RuntimeError("network down"))
        service = InstagramSessionService(loader_factory=lambda: loader)

        with pytest.raises(InstagramSessionError):
            service.update_session("SID")
        loader.save_session_to_file.assert_not_called()

    def test_empty_session_id_raises(self, session_file):
        loader = _fake_loader()
        service = InstagramSessionService(loader_factory=lambda: loader)

        with pytest.raises(InstagramSessionError):
            service.update_session("   ")
        loader.test_login.assert_not_called()

    def test_no_username_configured_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            settings, "INSTAGRAM_SESSION_FILE", str(tmp_path / "s")
        )
        monkeypatch.setattr(settings, "INSTAGRAM_USERNAME", "")
        loader = _fake_loader()
        service = InstagramSessionService(loader_factory=lambda: loader)

        with pytest.raises(InstagramSessionError):
            service.update_session("SID")
        loader.test_login.assert_not_called()
