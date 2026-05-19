import uuid
from datetime import timedelta, datetime, timezone

import pytest
from sqlalchemy import update as sa_update

from app.models.enums.enums import MacroErrorStatus, NutritionSource
from app.models.macro_error import MacroError
from app.repositories.macro_error_repository import MacroErrorRepository
from app.repositories.nutrition_item_repository import NutritionItemRepository
from app.repositories.unit_conversion_repository import UnitConversionRepository

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
USER2_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


async def _create_item(session, nom="Farine", code="1001"):
    return await NutritionItemRepository(session).create(
        nom_fr=nom, calories=340.0, proteines=13.0,
        glucides=71.0, lipides=3.0, source=NutritionSource.CIQUAL,
        ciqual_id=code,
    )


async def _create_error(session, raw="gochujank", user_id=USER_ID):
    return await MacroErrorRepository(session).create(
        user_id=user_id, raw_ingredient=raw
    )


class TestNutritionItemRepository:
    @pytest.mark.unit
    async def test_create_persists_item(self, db_session):
        item = await _create_item(db_session)
        assert item.id is not None
        assert item.slug == "farine"
        assert item.calories == pytest.approx(340.0)
        assert item.source == NutritionSource.CIQUAL

    @pytest.mark.unit
    async def test_create_slug_collision_adds_counter(self, db_session):
        """Deux items même nom → slugs différents."""
        i1 = await _create_item(db_session, "Farine", "A001")
        i2 = await _create_item(db_session, "Farine", "A002")
        assert i1.slug != i2.slug
        assert i2.slug.endswith("-2")

    @pytest.mark.unit
    async def test_get_by_slug_found(self, db_session):
        item = await _create_item(db_session)
        found = await NutritionItemRepository(db_session).get_by_slug(item.slug)
        assert found is not None
        assert found.id == item.id

    @pytest.mark.unit
    async def test_get_by_slug_not_found(self, db_session):
        assert await NutritionItemRepository(db_session).get_by_slug("slug-inexistant") is None

    @pytest.mark.unit
    async def test_get_by_ciqual_id_found(self, db_session):
        await _create_item(db_session)
        found = await NutritionItemRepository(db_session).get_by_ciqual_id("1001")
        assert found is not None

    @pytest.mark.unit
    async def test_get_by_ciqual_id_not_found(self, db_session):
        assert await NutritionItemRepository(db_session).get_by_ciqual_id("XXXX") is None


class TestMacroErrorRepository:
    @pytest.mark.unit
    async def test_create_persists_with_pending(self, db_session):
        error = await _create_error(db_session)
        assert error.id is not None
        assert error.slug
        assert error.status == MacroErrorStatus.PENDING
        assert error.user_id == USER_ID

    @pytest.mark.unit
    async def test_create_with_suggestion(self, db_session):
        error = await MacroErrorRepository(db_session).create(
            user_id=USER_ID, raw_ingredient="gochujank",
            suggested_match="gochujang", match_score=0.85,
        )
        assert error.suggested_match == "gochujang"
        assert error.match_score == pytest.approx(0.85)

    @pytest.mark.unit
    async def test_get_by_slug_found(self, db_session):
        error = await _create_error(db_session)
        found = await MacroErrorRepository(db_session).get_by_slug(error.slug)
        assert found is not None
        assert found.id == error.id

    @pytest.mark.unit
    async def test_get_by_slug_not_found(self, db_session):
        assert await MacroErrorRepository(db_session).get_by_slug("xxx") is None

    @pytest.mark.unit
    async def test_get_by_user_id_returns_all_for_user(self, db_session):
        await _create_error(db_session, "err1")
        await _create_error(db_session, "err2")
        await _create_error(db_session, "autre", user_id=USER2_ID)

        errors = await MacroErrorRepository(db_session).get_by_user_id(USER_ID)
        assert len(errors) == 2
        assert all(e.user_id == USER_ID for e in errors)

    @pytest.mark.unit
    async def test_get_by_user_id_filtered_by_status(self, db_session):
        repo = MacroErrorRepository(db_session)
        e1 = await _create_error(db_session, "pending-err")
        await _create_error(db_session, "other-err")
        await repo.resolve(e1, resolved_name="gochujang")

        resolved = await repo.get_by_user_id(USER_ID, status=MacroErrorStatus.RESOLVED)
        assert len(resolved) == 1

    @pytest.mark.unit
    async def test_resolve_sets_resolved_status(self, db_session):
        error = await _create_error(db_session)
        updated = await MacroErrorRepository(db_session).resolve(error, resolved_name="gochujang")
        assert updated.status == MacroErrorStatus.RESOLVED
        assert updated.resolved_name == "gochujang"
        assert updated.resolved_at is not None

    @pytest.mark.unit
    async def test_resolve_with_macros_sets_manual_status(self, db_session):
        error = await _create_error(db_session)
        updated = await MacroErrorRepository(db_session).resolve(
            error, resolved_name="perso",
            calories=100.0, proteines=5.0, glucides=15.0, lipides=3.0,
        )
        assert updated.status == MacroErrorStatus.MANUAL
        assert updated.calories_manual == pytest.approx(100.0)

    @pytest.mark.unit
    async def test_count_by_user_and_status(self, db_session):
        repo = MacroErrorRepository(db_session)
        await _create_error(db_session, "e1")
        await _create_error(db_session, "e2")
        e3 = await _create_error(db_session, "e3")
        await repo.resolve(e3, resolved_name="ok")

        pending = await repo.count_by_user_and_status(USER_ID, MacroErrorStatus.PENDING)
        resolved = await repo.count_by_user_and_status(USER_ID, MacroErrorStatus.RESOLVED)
        assert pending == 2
        assert resolved == 1

    @pytest.mark.unit
    async def test_get_by_user_id_ordered_desc(self, db_session):
        repo = MacroErrorRepository(db_session)
        e1 = await _create_error(db_session, "first")
        e2 = await _create_error(db_session, "second")

        # Force e1 dans le passé pour garantir l'ordre DESC
        await db_session.execute(
            sa_update(MacroError)
            .where(MacroError.id == e1.id)
            .values(created_at=datetime.now(timezone.utc) - timedelta(seconds=5))
        )
        await db_session.commit()

        errors = await repo.get_by_user_id(USER_ID)
        assert errors[0].raw_ingredient == "second"
        assert errors[1].raw_ingredient == "first"

    @pytest.mark.unit
    def test_build_slug_contains_ingredient_and_timestamp(self):
        slug = MacroErrorRepository._build_slug("gochujank")
        assert "gochujank" in slug
        assert len(slug) > 10


class TestUnitConversionRepository:
    @pytest.mark.unit
    async def test_create_and_find_universal(self, db_session):
        repo = UnitConversionRepository(db_session)
        await repo.create(unite="cs", grammes=10.0, note="cuillère à soupe")
        found = await repo.find("cs")
        assert found is not None
        assert found.grammes == pytest.approx(10.0)

    @pytest.mark.unit
    async def test_find_specific_before_universal(self, db_session):
        """Conversion spécifique aliment prioritaire sur universelle."""
        repo = UnitConversionRepository(db_session)
        await repo.create(unite="cs", grammes=10.0)
        await repo.create(unite="cs", grammes=15.0, aliment_type="farine")

        found = await repo.find("cs", aliment_type="farine")
        assert found.grammes == pytest.approx(15.0)

    @pytest.mark.unit
    async def test_find_universal_fallback(self, db_session):
        """Sans conversion spécifique → fallback universelle."""
        repo = UnitConversionRepository(db_session)
        await repo.create(unite="cs", grammes=10.0)

        found = await repo.find("cs", aliment_type="inconnu")
        assert found is not None
        assert found.grammes == pytest.approx(10.0)

    @pytest.mark.unit
    async def test_find_not_found_returns_none(self, db_session):
        assert await UnitConversionRepository(db_session).find("bol") is None