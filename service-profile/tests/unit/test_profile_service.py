"""Tests unitaires du ProfileService (couche service, repo mocké)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.profile import ProfileCreate, ProfileUpdate
from app.services.profile_service import ProfileService


def _make_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _make_profile(user_id: uuid.UUID, slug: str = "profile-abc") -> MagicMock:
    profile = MagicMock()
    profile.user_id = user_id
    profile.slug = slug
    profile.height_cm = 175.0
    profile.weight_kg = 70.0
    return profile


class TestProfileServiceCreate:
    @pytest.mark.unit
    async def test_create_returns_profile(self):
        """create() retourne le profil créé."""
        account_id = uuid.uuid4()
        user_id = uuid.uuid4()
        data = ProfileCreate(height_cm=180.0, weight_kg=75.0)

        session = _make_session()
        with patch("app.services.profile_service.ProfileRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_by_account_id = AsyncMock(return_value=None)
            repo.resolve_slug = AsyncMock(return_value="profile-abc")
            repo.add = MagicMock()
            MockRepo.return_value = repo

            service = ProfileService(session)
            await service.create(account_id, user_id, data)

        repo.add.assert_called_once()
        session.commit.assert_awaited_once()

    @pytest.mark.unit
    async def test_create_raises_if_profile_already_exists(self):
        """create() lève ValueError('already_exists') si le dossier existe déjà."""
        account_id = uuid.uuid4()
        user_id = uuid.uuid4()
        data = ProfileCreate(height_cm=175.0)
        existing_profile = _make_profile(user_id)

        session = _make_session()
        with patch("app.services.profile_service.ProfileRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_by_account_id = AsyncMock(return_value=existing_profile)
            MockRepo.return_value = repo

            service = ProfileService(session)
            with pytest.raises(ValueError, match="already_exists"):
                await service.create(account_id, user_id, data)

    @pytest.mark.unit
    async def test_create_calls_resolve_slug(self):
        """create() résout le slug avant d'ajouter le profil."""
        account_id = uuid.uuid4()
        user_id = uuid.uuid4()
        data = ProfileCreate()

        session = _make_session()
        with patch("app.services.profile_service.ProfileRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_by_account_id = AsyncMock(return_value=None)
            repo.resolve_slug = AsyncMock(return_value="profile-slug")
            repo.add = MagicMock()
            MockRepo.return_value = repo

            service = ProfileService(session)
            await service.create(account_id, user_id, data)

        repo.resolve_slug.assert_awaited_once()


class TestProfileServiceGetByUserId:
    @pytest.mark.unit
    async def test_get_by_user_id_returns_profile(self):
        """get_by_user_id retourne le profil via le repo."""
        user_id = uuid.uuid4()
        profile = _make_profile(user_id)

        session = _make_session()
        with patch("app.services.profile_service.ProfileRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_by_user_id = AsyncMock(return_value=profile)
            MockRepo.return_value = repo

            service = ProfileService(session)
            result = await service.get_by_user_id(user_id)

        assert result == profile

    @pytest.mark.unit
    async def test_get_by_user_id_returns_none_when_missing(self):
        """get_by_user_id retourne None si aucun profil n'existe."""
        user_id = uuid.uuid4()

        session = _make_session()
        with patch("app.services.profile_service.ProfileRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_by_user_id = AsyncMock(return_value=None)
            MockRepo.return_value = repo

            service = ProfileService(session)
            result = await service.get_by_user_id(user_id)

        assert result is None


class TestProfileServiceUpdate:
    @pytest.mark.unit
    async def test_update_returns_none_when_profile_not_found(self):
        """update() retourne None si le dossier est introuvable."""
        account_id = uuid.uuid4()
        data = ProfileUpdate(weight_kg=80.0)

        session = _make_session()
        with patch("app.services.profile_service.ProfileRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_by_account_id = AsyncMock(return_value=None)
            MockRepo.return_value = repo

            service = ProfileService(session)
            result = await service.update(account_id, data)

        assert result is None

    @pytest.mark.unit
    async def test_update_applies_fields(self):
        """update() applique les champs fournis au profil."""
        account_id = uuid.uuid4()
        profile = MagicMock()
        profile.weight_kg = 70.0
        profile.updated_at = None
        data = ProfileUpdate(weight_kg=85.0)

        session = _make_session()
        with patch("app.services.profile_service.ProfileRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_by_account_id = AsyncMock(return_value=profile)
            MockRepo.return_value = repo

            service = ProfileService(session)
            await service.update(account_id, data)

        assert profile.weight_kg == 85.0
        session.commit.assert_awaited_once()

    @pytest.mark.unit
    async def test_update_sets_updated_at(self):
        """update() met à jour le champ updated_at."""
        account_id = uuid.uuid4()
        profile = MagicMock()
        data = ProfileUpdate(height_cm=182.0)

        session = _make_session()
        with patch("app.services.profile_service.ProfileRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_by_account_id = AsyncMock(return_value=profile)
            MockRepo.return_value = repo

            service = ProfileService(session)
            await service.update(account_id, data)

        assert profile.updated_at is not None
