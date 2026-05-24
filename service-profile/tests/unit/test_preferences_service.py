"""Tests unitaires du PreferencesService (couche service, repo mocké)."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.preferences import (
    ExcludedFoodCreate,
    LifestyleProfileCreate,
    NutritionPreferencesCreate,
    PerformanceMetricCreate,
    SportsProfileCreate,
)
from app.services.preferences_service import PreferencesService


def _make_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _obj(slug: str = "slug") -> MagicMock:
    obj = MagicMock()
    obj.slug = slug
    return obj


class TestSportsProfile:
    _DATA = SportsProfileCreate(
        sports=["Natation"],
        practice_level="beginner",
        sessions_per_week=3,
        avg_session_duration_min=45,
        avg_intensity_rpe=5,
    )

    @pytest.mark.unit
    async def test_upsert_sports_creates_when_none_exists(self):
        """upsert_sports crée un SportsProfile si aucun n'existe."""
        profile_id = uuid.uuid4()
        session = _make_session()
        with patch(
            "app.services.preferences_service.PreferencesRepository"
        ) as MockRepo:
            repo = AsyncMock()
            repo.get_sports = AsyncMock(return_value=None)
            repo.resolve_slug = AsyncMock(return_value="sports-slug")
            repo.add_sports = MagicMock()
            MockRepo.return_value = repo

            service = PreferencesService(session)
            await service.upsert_sports(profile_id, self._DATA)

        repo.add_sports.assert_called_once()
        session.commit.assert_awaited_once()

    @pytest.mark.unit
    async def test_upsert_sports_updates_when_exists(self):
        """upsert_sports met à jour si un profil sportif existe déjà."""
        profile_id = uuid.uuid4()
        existing = _obj("sports-existing")
        existing.sessions_per_week = 2

        session = _make_session()
        with patch(
            "app.services.preferences_service.PreferencesRepository"
        ) as MockRepo:
            repo = AsyncMock()
            repo.get_sports = AsyncMock(return_value=existing)
            MockRepo.return_value = repo

            service = PreferencesService(session)
            await service.upsert_sports(profile_id, self._DATA)

        assert existing.sessions_per_week == 3
        session.commit.assert_awaited_once()

    @pytest.mark.unit
    async def test_get_sports_returns_none_when_missing(self):
        """get_sports retourne None si aucun profil sportif n'existe."""
        profile_id = uuid.uuid4()
        session = _make_session()
        with patch(
            "app.services.preferences_service.PreferencesRepository"
        ) as MockRepo:
            repo = AsyncMock()
            repo.get_sports = AsyncMock(return_value=None)
            MockRepo.return_value = repo

            service = PreferencesService(session)
            result = await service.get_sports(profile_id)

        assert result is None


class TestLifestyleProfile:
    _DATA = LifestyleProfileCreate(
        stress_level="low",
        sleep_hours=8.0,
        chronotype="morning",
        alcohol_frequency="never",
        is_smoker=False,
        sedentary_hours_per_day=4.0,
    )

    @pytest.mark.unit
    async def test_upsert_lifestyle_creates_when_none_exists(self):
        """upsert_lifestyle crée un LifestyleProfile si aucun n'existe."""
        profile_id = uuid.uuid4()
        session = _make_session()
        with patch(
            "app.services.preferences_service.PreferencesRepository"
        ) as MockRepo:
            repo = AsyncMock()
            repo.get_lifestyle = AsyncMock(return_value=None)
            repo.resolve_slug = AsyncMock(return_value="lifestyle-slug")
            repo.add_lifestyle = MagicMock()
            MockRepo.return_value = repo

            service = PreferencesService(session)
            await service.upsert_lifestyle(profile_id, self._DATA)

        repo.add_lifestyle.assert_called_once()

    @pytest.mark.unit
    async def test_upsert_lifestyle_updates_when_exists(self):
        """upsert_lifestyle met à jour si un lifestyle existe déjà."""
        profile_id = uuid.uuid4()
        existing = _obj("lifestyle-existing")
        existing.sleep_hours = 7.0

        session = _make_session()
        with patch(
            "app.services.preferences_service.PreferencesRepository"
        ) as MockRepo:
            repo = AsyncMock()
            repo.get_lifestyle = AsyncMock(return_value=existing)
            MockRepo.return_value = repo

            service = PreferencesService(session)
            await service.upsert_lifestyle(profile_id, self._DATA)

        assert existing.sleep_hours == 8.0


class TestNutritionPreferences:
    _DATA = NutritionPreferencesCreate(
        diet_type="vegan",
        main_goal="weight_loss",
        cooking_level="beginner",
        cooking_time="fast",
        cooking_for="solo",
        budget_per_day_eur=10.0,
        excluded_foods=[],
    )

    @pytest.mark.unit
    async def test_upsert_nutrition_creates_when_none_exists(self):
        """upsert_nutrition crée des préférences si aucune n'existe."""
        profile_id = uuid.uuid4()
        session = _make_session()
        with patch(
            "app.services.preferences_service.PreferencesRepository"
        ) as MockRepo:
            repo = AsyncMock()
            repo.get_nutrition = AsyncMock(return_value=None)
            repo.resolve_slug = AsyncMock(return_value="nutrition-slug")
            repo.add_nutrition = MagicMock()
            MockRepo.return_value = repo

            service = PreferencesService(session)
            await service.upsert_nutrition(profile_id, self._DATA)

        repo.add_nutrition.assert_called_once()

    @pytest.mark.unit
    async def test_get_nutrition_returns_existing(self):
        """get_nutrition retourne les préférences existantes."""
        profile_id = uuid.uuid4()
        existing = _obj("nutrition-slug")

        session = _make_session()
        with patch(
            "app.services.preferences_service.PreferencesRepository"
        ) as MockRepo:
            repo = AsyncMock()
            repo.get_nutrition = AsyncMock(return_value=existing)
            MockRepo.return_value = repo

            service = PreferencesService(session)
            result = await service.get_nutrition(profile_id)

        assert result == existing


class TestPerformanceMetric:
    _DATA = PerformanceMetricCreate(
        measured_at=date(2026, 5, 1),
        metric_type="vo2max",
        value=45.0,
        unit="mL/kg/min",
    )

    @pytest.mark.unit
    async def test_add_performance_commits(self):
        """add_performance commit la session."""
        profile_id = uuid.uuid4()
        session = _make_session()
        with patch(
            "app.services.preferences_service.PreferencesRepository"
        ) as MockRepo:
            repo = AsyncMock()
            repo.resolve_slug = AsyncMock(return_value="perf-slug")
            repo.add_performance = MagicMock()
            MockRepo.return_value = repo

            service = PreferencesService(session)
            await service.add_performance(profile_id, self._DATA)

        session.commit.assert_awaited_once()

    @pytest.mark.unit
    async def test_list_performance_delegates_to_repo(self):
        """list_performance retourne le résultat du repo."""
        profile_id = uuid.uuid4()
        expected = [_obj("p1"), _obj("p2")]

        session = _make_session()
        with patch(
            "app.services.preferences_service.PreferencesRepository"
        ) as MockRepo:
            repo = AsyncMock()
            repo.list_performance = AsyncMock(return_value=expected)
            MockRepo.return_value = repo

            service = PreferencesService(session)
            result = await service.list_performance(profile_id)

        assert result == expected

    @pytest.mark.unit
    async def test_delete_performance_returns_true(self):
        """delete_performance retourne True si la métrique existe."""
        profile_id = uuid.uuid4()
        obj = _obj("perf-slug")

        session = _make_session()
        with patch(
            "app.services.preferences_service.PreferencesRepository"
        ) as MockRepo:
            repo = AsyncMock()
            repo.get_performance_by_slug = AsyncMock(return_value=obj)
            repo.delete_performance = AsyncMock()
            MockRepo.return_value = repo

            service = PreferencesService(session)
            result = await service.delete_performance("perf-slug", profile_id)

        assert result is True

    @pytest.mark.unit
    async def test_delete_performance_returns_false_when_not_found(self):
        """delete_performance retourne False si la métrique est introuvable."""
        profile_id = uuid.uuid4()

        session = _make_session()
        with patch(
            "app.services.preferences_service.PreferencesRepository"
        ) as MockRepo:
            repo = AsyncMock()
            repo.get_performance_by_slug = AsyncMock(return_value=None)
            MockRepo.return_value = repo

            service = PreferencesService(session)
            result = await service.delete_performance("ghost", profile_id)

        assert result is False


class TestExcludedFood:
    @pytest.mark.unit
    async def test_add_excluded_food_commits(self):
        """add_excluded_food commit la session."""
        profile_id = uuid.uuid4()
        data = ExcludedFoodCreate(food_name="Gluten", reason="intolerance")

        session = _make_session()
        with patch(
            "app.services.preferences_service.PreferencesRepository"
        ) as MockRepo:
            repo = AsyncMock()
            repo.resolve_slug = AsyncMock(return_value="food-slug")
            repo.add_excluded_food = MagicMock()
            MockRepo.return_value = repo

            service = PreferencesService(session)
            await service.add_excluded_food(profile_id, data)

        session.commit.assert_awaited_once()

    @pytest.mark.unit
    async def test_list_excluded_foods_returns_list(self):
        """list_excluded_foods retourne la liste du repo."""
        profile_id = uuid.uuid4()
        expected = [_obj("food-1")]

        session = _make_session()
        with patch(
            "app.services.preferences_service.PreferencesRepository"
        ) as MockRepo:
            repo = AsyncMock()
            repo.list_excluded_foods = AsyncMock(return_value=expected)
            MockRepo.return_value = repo

            service = PreferencesService(session)
            result = await service.list_excluded_foods(profile_id)

        assert result == expected

    @pytest.mark.unit
    async def test_delete_excluded_food_returns_false_when_not_found(self):
        """delete_excluded_food retourne False si l'aliment est introuvable."""
        profile_id = uuid.uuid4()

        session = _make_session()
        with patch(
            "app.services.preferences_service.PreferencesRepository"
        ) as MockRepo:
            repo = AsyncMock()
            repo.get_excluded_food_by_slug = AsyncMock(return_value=None)
            MockRepo.return_value = repo

            service = PreferencesService(session)
            result = await service.delete_excluded_food("ghost", profile_id)

        assert result is False
