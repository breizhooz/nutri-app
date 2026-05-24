"""Tests unitaires du MedicalService (couche service, repo mocké)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums.enums import AllergySeverity, MedicalCategory
from app.schemas.medical import (
    FoodAllergyCreate,
    InjuryCreate,
    MedicalConditionCreate,
    MedicationCreate,
)
from app.services.medical_service import MedicalService


def _make_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _obj(slug: str = "slug") -> MagicMock:
    obj = MagicMock()
    obj.slug = slug
    return obj


class TestInjury:
    _DATA = InjuryCreate(body_part="Genou gauche", injury_type="Tendinite")

    @pytest.mark.unit
    async def test_add_injury_commits(self):
        """add_injury commit la session et appelle repo.add."""
        profile_id = uuid.uuid4()
        session = _make_session()
        with patch("app.services.medical_service.MedicalRepository") as MockRepo:
            repo = AsyncMock()
            repo.resolve_slug = AsyncMock(return_value="injury-slug")
            repo.add = MagicMock()
            MockRepo.return_value = repo

            service = MedicalService(session)
            await service.add_injury(profile_id, self._DATA)

        repo.add.assert_called_once()
        session.commit.assert_awaited_once()

    @pytest.mark.unit
    async def test_list_injuries_delegates_to_repo(self):
        """list_injuries retourne le résultat du repo."""
        profile_id = uuid.uuid4()
        expected = [_obj("inj-1"), _obj("inj-2")]

        session = _make_session()
        with patch("app.services.medical_service.MedicalRepository") as MockRepo:
            repo = AsyncMock()
            repo.list_injuries = AsyncMock(return_value=expected)
            MockRepo.return_value = repo

            service = MedicalService(session)
            result = await service.list_injuries(profile_id)

        assert result == expected

    @pytest.mark.unit
    async def test_delete_injury_returns_true_when_found(self):
        """delete_injury retourne True si la blessure existe."""
        profile_id = uuid.uuid4()
        session = _make_session()
        with patch("app.services.medical_service.MedicalRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_injury = AsyncMock(return_value=_obj("inj-slug"))
            repo.delete = AsyncMock()
            MockRepo.return_value = repo

            service = MedicalService(session)
            result = await service.delete_injury("inj-slug", profile_id)

        assert result is True
        session.commit.assert_awaited_once()

    @pytest.mark.unit
    async def test_delete_injury_returns_false_when_not_found(self):
        """delete_injury retourne False si la blessure est introuvable."""
        profile_id = uuid.uuid4()
        session = _make_session()
        with patch("app.services.medical_service.MedicalRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_injury = AsyncMock(return_value=None)
            MockRepo.return_value = repo

            service = MedicalService(session)
            result = await service.delete_injury("ghost", profile_id)

        assert result is False
        session.commit.assert_not_awaited()


class TestMedicalCondition:
    _DATA = MedicalConditionCreate(
        category=MedicalCategory.METABOLIC,
        condition_name="Diabète type 2",
        is_current=True,
    )

    @pytest.mark.unit
    async def test_add_condition_commits(self):
        """add_condition commit la session."""
        profile_id = uuid.uuid4()
        session = _make_session()
        with patch("app.services.medical_service.MedicalRepository") as MockRepo:
            repo = AsyncMock()
            repo.resolve_slug = AsyncMock(return_value="cond-slug")
            repo.add = MagicMock()
            MockRepo.return_value = repo

            service = MedicalService(session)
            await service.add_condition(profile_id, self._DATA)

        session.commit.assert_awaited_once()

    @pytest.mark.unit
    async def test_list_conditions_delegates_to_repo(self):
        """list_conditions retourne la liste du repo."""
        profile_id = uuid.uuid4()
        expected = [_obj("c1")]

        session = _make_session()
        with patch("app.services.medical_service.MedicalRepository") as MockRepo:
            repo = AsyncMock()
            repo.list_conditions = AsyncMock(return_value=expected)
            MockRepo.return_value = repo

            service = MedicalService(session)
            result = await service.list_conditions(profile_id)

        assert result == expected

    @pytest.mark.unit
    async def test_delete_condition_returns_true_when_found(self):
        """delete_condition retourne True si la pathologie existe."""
        profile_id = uuid.uuid4()
        session = _make_session()
        with patch("app.services.medical_service.MedicalRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_condition = AsyncMock(return_value=_obj("cond-slug"))
            repo.delete = AsyncMock()
            MockRepo.return_value = repo

            service = MedicalService(session)
            result = await service.delete_condition("cond-slug", profile_id)

        assert result is True

    @pytest.mark.unit
    async def test_delete_condition_returns_false_when_not_found(self):
        """delete_condition retourne False si la pathologie est introuvable."""
        profile_id = uuid.uuid4()
        session = _make_session()
        with patch("app.services.medical_service.MedicalRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_condition = AsyncMock(return_value=None)
            MockRepo.return_value = repo

            service = MedicalService(session)
            result = await service.delete_condition("ghost", profile_id)

        assert result is False


class TestFoodAllergy:
    _DATA = FoodAllergyCreate(allergen="Lactose", severity=AllergySeverity.INTOLERANCE)

    @pytest.mark.unit
    async def test_add_allergy_commits(self):
        """add_allergy commit la session."""
        profile_id = uuid.uuid4()
        session = _make_session()
        with patch("app.services.medical_service.MedicalRepository") as MockRepo:
            repo = AsyncMock()
            repo.resolve_slug = AsyncMock(return_value="allergy-slug")
            repo.add = MagicMock()
            MockRepo.return_value = repo

            service = MedicalService(session)
            await service.add_allergy(profile_id, self._DATA)

        session.commit.assert_awaited_once()

    @pytest.mark.unit
    async def test_list_allergies_delegates_to_repo(self):
        """list_allergies retourne la liste du repo."""
        profile_id = uuid.uuid4()
        expected = [_obj("a1")]

        session = _make_session()
        with patch("app.services.medical_service.MedicalRepository") as MockRepo:
            repo = AsyncMock()
            repo.list_allergies = AsyncMock(return_value=expected)
            MockRepo.return_value = repo

            service = MedicalService(session)
            result = await service.list_allergies(profile_id)

        assert result == expected

    @pytest.mark.unit
    async def test_delete_allergy_returns_false_when_not_found(self):
        """delete_allergy retourne False si l'allergie est introuvable."""
        profile_id = uuid.uuid4()
        session = _make_session()
        with patch("app.services.medical_service.MedicalRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_allergy = AsyncMock(return_value=None)
            MockRepo.return_value = repo

            service = MedicalService(session)
            result = await service.delete_allergy("ghost", profile_id)

        assert result is False


class TestMedication:
    _DATA = MedicationCreate(
        medication_name="Metformine 500mg", impacts_metabolism=True
    )

    @pytest.mark.unit
    async def test_add_medication_commits(self):
        """add_medication commit la session."""
        profile_id = uuid.uuid4()
        session = _make_session()
        with patch("app.services.medical_service.MedicalRepository") as MockRepo:
            repo = AsyncMock()
            repo.resolve_slug = AsyncMock(return_value="med-slug")
            repo.add = MagicMock()
            MockRepo.return_value = repo

            service = MedicalService(session)
            await service.add_medication(profile_id, self._DATA)

        session.commit.assert_awaited_once()

    @pytest.mark.unit
    async def test_list_medications_delegates_to_repo(self):
        """list_medications retourne la liste du repo."""
        profile_id = uuid.uuid4()
        expected = [_obj("med-1"), _obj("med-2")]

        session = _make_session()
        with patch("app.services.medical_service.MedicalRepository") as MockRepo:
            repo = AsyncMock()
            repo.list_medications = AsyncMock(return_value=expected)
            MockRepo.return_value = repo

            service = MedicalService(session)
            result = await service.list_medications(profile_id)

        assert result == expected

    @pytest.mark.unit
    async def test_delete_medication_returns_true_when_found(self):
        """delete_medication retourne True si le traitement existe."""
        profile_id = uuid.uuid4()
        session = _make_session()
        with patch("app.services.medical_service.MedicalRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_medication = AsyncMock(return_value=_obj("med-slug"))
            repo.delete = AsyncMock()
            MockRepo.return_value = repo

            service = MedicalService(session)
            result = await service.delete_medication("med-slug", profile_id)

        assert result is True

    @pytest.mark.unit
    async def test_delete_medication_returns_false_when_not_found(self):
        """delete_medication retourne False si le traitement est introuvable."""
        profile_id = uuid.uuid4()
        session = _make_session()
        with patch("app.services.medical_service.MedicalRepository") as MockRepo:
            repo = AsyncMock()
            repo.get_medication = AsyncMock(return_value=None)
            MockRepo.return_value = repo

            service = MedicalService(session)
            result = await service.delete_medication("ghost", profile_id)

        assert result is False
