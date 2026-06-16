"""Tests unitaires pour les fonctions du menu_service (repository layer)."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.menu_service import _unique_slug
from app.schemas.weekly_menu import WeeklyMenuCreate


def _make_session(existing_menu=None, loaded_menu=None):
    """Crée une session mocké pour les tests du menu_service."""
    session = AsyncMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=existing_menu)
    session.execute = AsyncMock(return_value=scalar_result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.get = AsyncMock(return_value=existing_menu)
    session.delete = AsyncMock()
    return session


class TestUniqueSlug:
    @pytest.mark.unit
    async def test_returns_base_slug_when_no_conflict(self):
        """_unique_slug retourne le slug de base si pas de conflit."""
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=result_mock)

        slug = await _unique_slug(session, date(2026, 5, 19))
        assert slug == "menu-2026-05-19"

    @pytest.mark.unit
    async def test_appends_counter_when_slug_exists(self):
        """_unique_slug ajoute un suffixe numérique si le slug de base est pris."""
        session = AsyncMock()
        conflict = MagicMock()
        call_count = 0

        async def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            result = MagicMock()
            if call_count == 0:
                result.scalar_one_or_none = MagicMock(return_value=conflict)
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
            call_count += 1
            return result

        session.execute = execute_side_effect

        slug = await _unique_slug(session, date(2026, 5, 19))
        assert slug == "menu-2026-05-19 - 1"


class TestCreateMenu:
    @pytest.mark.unit
    async def test_create_menu_adds_to_session(self):
        """create_menu appelle session.add et session.commit."""
        from app.repositories.menu_service import create_menu

        menu_data = WeeklyMenuCreate(
            start_date=date(2026, 6, 2),
            nb_persons=2,
            slots=[],
            slug="test-menu",
        )
        created_menu = MagicMock()
        created_menu.id = 1

        session = AsyncMock()
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=scalar_result)
        session.add = MagicMock()
        session.flush = AsyncMock(side_effect=lambda: setattr(created_menu, "id", 1))
        session.commit = AsyncMock()

        with patch(
            "app.repositories.menu_service._load_with_slots",
            new=AsyncMock(return_value=created_menu),
        ):
            result = await create_menu(
                session, menu_data, user_id="user-123", account_id="acc-123"
            )

        session.add.assert_called()
        session.commit.assert_awaited_once()
        assert result == created_menu

    @pytest.mark.unit
    async def test_create_menu_uses_provided_slug(self):
        """create_menu utilise le slug fourni sans appeler _unique_slug."""
        from app.repositories.menu_service import create_menu

        menu_data = WeeklyMenuCreate(
            start_date=date(2026, 6, 2),
            nb_persons=1,
            slots=[],
            slug="my-custom-slug",
        )
        created_menu = MagicMock()
        created_menu.id = 99
        created_menu.slug = "my-custom-slug"

        session = AsyncMock()
        scalar_result = MagicMock()
        scalar_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=scalar_result)
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()

        with patch(
            "app.repositories.menu_service._load_with_slots",
            new=AsyncMock(return_value=created_menu),
        ):
            result = await create_menu(
                session, menu_data, user_id="user-abc", account_id="acc-abc"
            )

        assert result.slug == "my-custom-slug"

    @pytest.mark.unit
    async def test_create_menu_overwrites_existing_week(self):
        """create_menu supprime le menu existant de la même (user, semaine) avant d'en créer un nouveau."""
        from app.repositories.menu_service import create_menu

        menu_data = WeeklyMenuCreate(
            start_date=date(2026, 6, 2),
            nb_persons=1,
            slots=[],
            slug="new-slug",
        )
        created_menu = MagicMock()

        session = AsyncMock()
        scalar_result = MagicMock()
        scalar_result.scalars.return_value.all.return_value = [42]
        session.execute = AsyncMock(return_value=scalar_result)
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()

        with patch(
            "app.repositories.menu_service._load_with_slots",
            new=AsyncMock(return_value=created_menu),
        ):
            await create_menu(
                session, menu_data, user_id="user-abc", account_id="acc-abc"
            )

        # 1 SELECT des ids existants + 2 DELETE (slots puis menus)
        assert session.execute.await_count == 3


class TestDeleteMenu:
    @pytest.mark.unit
    async def test_delete_menu_returns_true_when_found(self):
        """delete_menu retourne True et supprime le menu s'il existe."""
        from app.repositories.menu_service import delete_menu

        existing = MagicMock()
        session = AsyncMock()
        session.get = AsyncMock(return_value=existing)
        session.delete = AsyncMock()
        session.commit = AsyncMock()

        result = await delete_menu(session, 1)

        assert result is True
        session.delete.assert_awaited_once_with(existing)
        session.commit.assert_awaited_once()

    @pytest.mark.unit
    async def test_delete_menu_returns_false_when_not_found(self):
        """delete_menu retourne False si le menu est introuvable."""
        from app.repositories.menu_service import delete_menu

        session = AsyncMock()
        session.get = AsyncMock(return_value=None)

        result = await delete_menu(session, 999)

        assert result is False
        session.delete.assert_not_awaited()


class TestGetMenuByUser:
    @pytest.mark.unit
    async def test_get_menu_by_user_returns_list(self):
        """get_menu_by_user retourne la liste des menus de l'utilisateur."""
        from app.repositories.menu_service import get_menu_by_account

        menus = [MagicMock(), MagicMock()]
        scalar_result = MagicMock()
        scalar_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=menus))
        )
        session = AsyncMock()
        session.execute = AsyncMock(return_value=scalar_result)

        result = await get_menu_by_account(session, "acc-123")
        assert result == menus

    @pytest.mark.unit
    async def test_get_menu_by_user_empty_list(self):
        """get_menu_by_user retourne une liste vide si aucun menu n'existe."""
        from app.repositories.menu_service import get_menu_by_account

        scalar_result = MagicMock()
        scalar_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[]))
        )
        session = AsyncMock()
        session.execute = AsyncMock(return_value=scalar_result)

        result = await get_menu_by_account(session, "acc-unknown")
        assert result == []
