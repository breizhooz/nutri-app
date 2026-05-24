"""Tests unitaires du TrackerService (couche service, repo mocké)."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.tracker import BodyCompositionCreate, BodyMeasurementsCreate
from app.services.tracker_service import TrackerService


def _make_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _make_snap(profile_id: uuid.UUID, slug: str = "compo-slug") -> MagicMock:
    snap = MagicMock()
    snap.profile_id = profile_id
    snap.slug = slug
    return snap


class TestTrackerServiceAddComposition:
    @pytest.mark.unit
    async def test_add_composition_returns_snapshot(self):
        """add_composition crée et retourne le snapshot."""
        profile_id = uuid.uuid4()
        data = BodyCompositionCreate(
            measured_at=date(2026, 5, 1), body_fat_percentage=20.0
        )

        session = _make_session()
        with patch("app.services.tracker_service.TrackerRepository") as MockRepo:
            repo = AsyncMock()
            repo.resolve_slug = AsyncMock(return_value="compo-slug")
            repo.add_composition = MagicMock()
            MockRepo.return_value = repo
            session.refresh = AsyncMock(return_value=None)

            service = TrackerService(session)
            await service.add_composition(profile_id, data)

        repo.add_composition.assert_called_once()
        session.commit.assert_awaited_once()

    @pytest.mark.unit
    async def test_add_composition_calls_resolve_slug(self):
        """Le slug est résolu via le repo avant création."""
        profile_id = uuid.uuid4()
        data = BodyCompositionCreate(measured_at=date(2026, 5, 1))

        session = _make_session()
        with patch("app.services.tracker_service.TrackerRepository") as MockRepo:
            repo = AsyncMock()
            repo.resolve_slug = AsyncMock(return_value="generated-slug")
            repo.add_composition = MagicMock()
            MockRepo.return_value = repo

            service = TrackerService(session)
            await service.add_composition(profile_id, data)

        repo.resolve_slug.assert_awaited_once()


class TestTrackerServiceListComposition:
    @pytest.mark.unit
    async def test_list_composition_delegates_to_repo(self):
        """list_composition retourne le résultat du repo."""
        profile_id = uuid.uuid4()
        expected = [_make_snap(profile_id, "s1"), _make_snap(profile_id, "s2")]

        session = _make_session()
        with patch("app.services.tracker_service.TrackerRepository") as MockRepo:
            repo = AsyncMock()
            repo.list_composition = AsyncMock(return_value=expected)
            MockRepo.return_value = repo

            service = TrackerService(session)
            result = await service.list_composition(profile_id)

        assert result == expected


class TestTrackerServiceDeleteComposition:
    @pytest.mark.unit
    async def test_delete_composition_returns_true_on_success(self):
        """delete_composition retourne True si le snapshot existe."""
        profile_id = uuid.uuid4()
        snap = _make_snap(profile_id)

        session = _make_session()
        with patch("app.services.tracker_service.TrackerRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_composition_by_slug = AsyncMock(return_value=snap)
            repo.delete_composition = AsyncMock()
            MockRepo.return_value = repo

            service = TrackerService(session)
            result = await service.delete_composition("compo-slug", profile_id)

        assert result is True
        session.commit.assert_awaited_once()

    @pytest.mark.unit
    async def test_delete_composition_returns_false_when_not_found(self):
        """delete_composition retourne False si le snapshot est introuvable."""
        profile_id = uuid.uuid4()

        session = _make_session()
        with patch("app.services.tracker_service.TrackerRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_composition_by_slug = AsyncMock(return_value=None)
            MockRepo.return_value = repo

            service = TrackerService(session)
            result = await service.delete_composition("ghost-slug", profile_id)

        assert result is False
        session.commit.assert_not_awaited()


class TestTrackerServiceMeasurements:
    @pytest.mark.unit
    async def test_add_measurements_commits(self):
        """add_measurements commit la session."""
        profile_id = uuid.uuid4()
        data = BodyMeasurementsCreate(measured_at=date(2026, 5, 1), waist_cm=80.0)

        session = _make_session()
        with patch("app.services.tracker_service.TrackerRepository") as MockRepo:
            repo = AsyncMock()
            repo.resolve_slug = AsyncMock(return_value="mensuration-slug")
            repo.add_measurements = MagicMock()
            MockRepo.return_value = repo

            service = TrackerService(session)
            await service.add_measurements(profile_id, data)

        session.commit.assert_awaited_once()

    @pytest.mark.unit
    async def test_list_measurements_delegates_to_repo(self):
        """list_measurements retourne le résultat du repo."""
        profile_id = uuid.uuid4()
        expected = [_make_snap(profile_id, "m1")]

        session = _make_session()
        with patch("app.services.tracker_service.TrackerRepository") as MockRepo:
            repo = AsyncMock()
            repo.list_measurements = AsyncMock(return_value=expected)
            MockRepo.return_value = repo

            service = TrackerService(session)
            result = await service.list_measurements(profile_id)

        assert result == expected

    @pytest.mark.unit
    async def test_delete_measurements_returns_true_on_success(self):
        """delete_measurements retourne True si le snapshot existe."""
        profile_id = uuid.uuid4()
        snap = _make_snap(profile_id)

        session = _make_session()
        with patch("app.services.tracker_service.TrackerRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_measurements_by_slug = AsyncMock(return_value=snap)
            repo.delete_measurements = AsyncMock()
            MockRepo.return_value = repo

            service = TrackerService(session)
            result = await service.delete_measurements("mensuration-slug", profile_id)

        assert result is True

    @pytest.mark.unit
    async def test_delete_measurements_returns_false_when_not_found(self):
        """delete_measurements retourne False si le snapshot est introuvable."""
        profile_id = uuid.uuid4()

        session = _make_session()
        with patch("app.services.tracker_service.TrackerRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_measurements_by_slug = AsyncMock(return_value=None)
            MockRepo.return_value = repo

            service = TrackerService(session)
            result = await service.delete_measurements("ghost", profile_id)

        assert result is False
