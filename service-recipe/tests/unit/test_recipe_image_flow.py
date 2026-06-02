from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import (
    ImageNotInSuggestions,
    ImageServiceUnavailable,
    RecipeForbidden,
    RecipeNotFound,
)
from app.services.recipe_service import RecipeService
from app.services.unsplash_service import ImageSuggestion


def _suggestion(pid: str) -> ImageSuggestion:
    return ImageSuggestion(
        unsplash_id=pid,
        thumb_url=f"http://thumb/{pid}",
        full_url=f"http://hd/{pid}",
        download_location=f"http://dl/{pid}",
        author="Jane",
    )


def _make_recipe(
    user_id: str = "owner",
    suggestions: list | None = None,
    image_url: str | None = None,
) -> MagicMock:
    r = MagicMock()
    r.id = 1
    r.title = "Tarte aux pommes"
    r.created_by_user_id = user_id
    r.recipe_ingredients = []
    r.image_suggestions = suggestions if suggestions is not None else []
    r.image_url = image_url
    return r


def _make_service(recipe, unsplash):
    repo = AsyncMock()
    repo.get_by_id_with_relations.return_value = recipe
    repo.update_image_suggestions.return_value = recipe
    repo.select_final_image.return_value = recipe
    search = AsyncMock()
    service = RecipeService(
        repo, search, nutrition_client=AsyncMock(), unsplash=unsplash
    )
    return service, repo, search


# ─── attach (on creation) ───────────────────────────────────────────────────────


class TestAttachSuggestions:
    async def test_searches_with_title_and_persists(self):
        recipe = _make_recipe()
        unsplash = AsyncMock()
        unsplash.search.return_value = [_suggestion("a"), _suggestion("b")]
        service, repo, _ = _make_service(recipe, unsplash)

        await service._attach_suggestions(recipe)

        unsplash.search.assert_called_once_with("Tarte aux pommes")
        repo.update_image_suggestions.assert_called_once()
        args = repo.update_image_suggestions.call_args[0]
        assert args[0] == 1
        assert args[1] == "Tarte aux pommes"
        assert [s["unsplash_id"] for s in args[2]] == ["a", "b"]

    async def test_empty_when_unsplash_disabled(self):
        recipe = _make_recipe()
        unsplash = AsyncMock()
        unsplash.search.return_value = []
        service, repo, _ = _make_service(recipe, unsplash)

        await service._attach_suggestions(recipe)
        assert repo.update_image_suggestions.call_args[0][2] == []

    async def test_auto_selects_first_image_and_tracks_download(self):
        recipe = _make_recipe(image_url=None)
        unsplash = AsyncMock()
        unsplash.search.return_value = [_suggestion("a"), _suggestion("b")]
        service, repo, search = _make_service(recipe, unsplash)

        await service._attach_suggestions(recipe)

        # 1ʳᵉ proposition posée comme image finale + tracking Unsplash + réindex ES.
        repo.select_final_image.assert_called_once_with(
            1, "http://hd/a", "http://thumb/a"
        )
        unsplash.track_download.assert_called_once_with("http://dl/a")
        search.index_recipe.assert_called_once()

    async def test_no_auto_select_when_no_suggestions(self):
        recipe = _make_recipe(image_url=None)
        unsplash = AsyncMock()
        unsplash.search.return_value = []
        service, repo, _ = _make_service(recipe, unsplash)

        await service._attach_suggestions(recipe)

        repo.select_final_image.assert_not_called()
        unsplash.track_download.assert_not_called()

    async def test_does_not_overwrite_existing_image(self):
        recipe = _make_recipe(image_url="http://existing/img.jpg")
        unsplash = AsyncMock()
        unsplash.search.return_value = [_suggestion("a")]
        service, repo, _ = _make_service(recipe, unsplash)

        await service._attach_suggestions(recipe)

        # Suggestions stockées mais image explicite (import) préservée.
        repo.update_image_suggestions.assert_called_once()
        repo.select_final_image.assert_not_called()

    async def test_swallows_unsplash_unavailable_on_creation(self):
        # Une indisponibilité Unsplash (quota) ne doit jamais casser la création :
        # on retombe sur 0 proposition.
        recipe = _make_recipe()
        unsplash = AsyncMock()
        unsplash.search.side_effect = ImageServiceUnavailable()
        service, repo, _ = _make_service(recipe, unsplash)

        await service._attach_suggestions(recipe)  # ne doit pas lever
        assert repo.update_image_suggestions.call_args[0][2] == []
        unsplash.track_download.assert_not_called()


# ─── refresh ──────────────────────────────────────────────────────────────────


class TestRefreshSuggestions:
    async def test_uses_free_keyword(self):
        recipe = _make_recipe()
        unsplash = AsyncMock()
        unsplash.search.return_value = [_suggestion("x")]
        service, repo, _ = _make_service(recipe, unsplash)

        await service.refresh_suggestions(1, "gateau chocolat", "owner")

        unsplash.search.assert_called_once_with("gateau chocolat")
        assert repo.update_image_suggestions.call_args[0][1] == "gateau chocolat"

    async def test_forbidden_for_non_author(self):
        recipe = _make_recipe(user_id="someone-else")
        service, repo, _ = _make_service(recipe, AsyncMock())
        with pytest.raises(RecipeForbidden):
            await service.refresh_suggestions(1, "kw", "owner")

    async def test_not_found(self):
        service, repo, _ = _make_service(_make_recipe(), AsyncMock())
        repo.get_by_id_with_relations.return_value = None
        with pytest.raises(RecipeNotFound):
            await service.refresh_suggestions(1, "kw", "owner")

    async def test_propagates_unsplash_unavailable(self):
        # Recherche d'image explicite (déclenchée par l'utilisateur) : l'erreur
        # remonte pour être affichée comme indisponibilité, pas comme « 0 résultat ».
        recipe = _make_recipe()
        unsplash = AsyncMock()
        unsplash.search.side_effect = ImageServiceUnavailable()
        service, repo, _ = _make_service(recipe, unsplash)
        with pytest.raises(ImageServiceUnavailable):
            await service.refresh_suggestions(1, "saumon", "owner")


# ─── select ───────────────────────────────────────────────────────────────────


class TestSelectImage:
    async def test_selects_matching_suggestion(self):
        recipe = _make_recipe(
            suggestions=[_suggestion("a").to_dict(), _suggestion("b").to_dict()]
        )
        unsplash = AsyncMock()
        service, repo, search = _make_service(recipe, unsplash)

        await service.select_image(1, "b", "owner")

        repo.select_final_image.assert_called_once_with(
            1, "http://hd/b", "http://thumb/b"
        )
        unsplash.track_download.assert_called_once_with("http://dl/b")
        search.index_recipe.assert_called_once()

    async def test_rejects_unknown_id(self):
        recipe = _make_recipe(suggestions=[_suggestion("a").to_dict()])
        service, repo, _ = _make_service(recipe, AsyncMock())
        with pytest.raises(ImageNotInSuggestions):
            await service.select_image(1, "zzz", "owner")
        repo.select_final_image.assert_not_called()

    async def test_forbidden_for_non_author(self):
        recipe = _make_recipe(user_id="other", suggestions=[_suggestion("a").to_dict()])
        service, repo, _ = _make_service(recipe, AsyncMock())
        with pytest.raises(RecipeForbidden):
            await service.select_image(1, "a", "owner")
