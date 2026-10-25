"""RecipeSearchService + triggers ``search_vector`` sur un vrai PostgreSQL.

Plein texte, unaccent et pg_trgm n'existent pas sous SQLite : ces tests exigent
``TEST_POSTGRES_URL`` (ex. ``postgresql+asyncpg://test:test@localhost:55432/test``)
et sont ignorés sinon. La CI fournit un service PostgreSQL.

Chaque test tourne dans un schéma jetable où l'on crée les tables puis les
fonctions et triggers de la migration ``e5f6a7b8c9d0`` (le SQL réellement
déployé, pas une copie).
"""

import importlib.util
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models.enums import CourseType, DifficultyLevel
from app.models.ingredient import Ingredient
from app.models.recipe import Recipe
from app.models.recipe_ingredients import RecipeIngredient
from app.schemas.search import MacroTarget, SearchCriteria
from app.services.search_service import RecipeSearchService

PG_URL = os.environ.get("TEST_POSTGRES_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not PG_URL, reason="TEST_POSTGRES_URL non défini"),
]

ACCOUNT = "acc-1"
OTHER_ACCOUNT = "acc-2"

_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic/versions/e5f6a7b8c9d0_recipe_fulltext_search.py"
)


def _migration_sql() -> list[str]:
    spec = importlib.util.spec_from_file_location("fts_migration", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return [module._DOCUMENT_FUNCTION, *module._TRIGGERS]


@pytest.fixture
async def session():
    schema = f"test_search_{uuid.uuid4().hex[:8]}"
    engine = create_async_engine(
        PG_URL, connect_args={"server_settings": {"search_path": f"{schema},public"}}
    )
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(text(f"CREATE SCHEMA {schema}"))
        await conn.run_sync(
            lambda c: Recipe.metadata.create_all(
                c,
                tables=[
                    Ingredient.__table__,
                    Recipe.__table__,
                    RecipeIngredient.__table__,
                ],
            )
        )
        for statement in _migration_sql():
            await conn.execute(text(statement))
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
    await engine.dispose()


_created = datetime(2026, 1, 1)


async def _ingredient(session, name, tags=()):
    ingredient = Ingredient(name=name, tags=list(tags), free_tags=[])
    session.add(ingredient)
    await session.flush()
    return ingredient


async def _recipe(
    session,
    title,
    ingredients=(),
    account=ACCOUNT,
    description=None,
    instructions="Cuire.",
    calories=None,
    age_days=0,
    **fields,
):
    recipe = Recipe(
        title=title,
        slug=f"{title.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}",
        description=description,
        instructions=instructions,
        account_id=account,
        calories_per_serving=calories,
        created_at=_created - timedelta(days=age_days),
        **fields,
    )
    session.add(recipe)
    await session.flush()
    for ingredient in ingredients:
        session.add(
            RecipeIngredient(
                recipe_id=recipe.id, ingredient_id=ingredient.id, quantity=1, unit="g"
            )
        )
    await session.commit()
    return recipe


def _titles(response) -> list[str]:
    return [r["title"] for r in response["results"]]


async def _search(session, **kwargs):
    return await RecipeSearchService(session).search_recipes(
        account_id=kwargs.pop("account_id", ACCOUNT), **kwargs
    )


class TestFullText:
    async def test_finds_by_ingredient_name(self, session):
        poulet = await _ingredient(session, "Blanc de poulet")
        await _recipe(session, "Curry maison", [poulet])
        await _recipe(session, "Salade verte")
        assert _titles(await _search(session, query="poulet")) == ["Curry maison"]

    async def test_prefix_search_as_you_type(self, session):
        await _recipe(session, "Poulet rôti")
        assert _titles(await _search(session, query="poul")) == ["Poulet rôti"]

    async def test_accents_case_and_plural_ignored(self, session):
        await _recipe(session, "Crème brûlée")
        await _recipe(session, "Tarte à la tomate")
        assert _titles(await _search(session, query="CREME")) == ["Crème brûlée"]
        assert _titles(await _search(session, query="tomates")) == ["Tarte à la tomate"]

    async def test_all_words_required(self, session):
        await _recipe(session, "Tarte aux pommes")
        await _recipe(session, "Tarte au citron")
        assert _titles(await _search(session, query="tarte pommes")) == [
            "Tarte aux pommes"
        ]

    async def test_typo_in_title_tolerated(self, session):
        """Inversion de lettres non rattrapable par le préfixe → trigrammes."""
        await _recipe(session, "Tarte aux pommes")
        assert _titles(await _search(session, query="tatre aux pommes")) == [
            "Tarte aux pommes"
        ]

    async def test_title_match_ranks_above_description_match(self, session):
        await _recipe(session, "Gratin dauphinois", description="Avec du poulet")
        await _recipe(session, "Poulet basquaise", age_days=10)
        assert _titles(await _search(session, query="poulet")) == [
            "Poulet basquaise",
            "Gratin dauphinois",
        ]

    async def test_stopword_or_punctuation_query_does_not_fail(self, session):
        await _recipe(session, "Soupe de légumes")
        for query in ["de", "l'", "!!!"]:
            response = await _search(session, query=query)
            assert response["total"] == 0

    async def test_ingredient_rename_updates_search(self, session):
        poulet = await _ingredient(session, "Poulet")
        await _recipe(session, "Curry", [poulet])
        await session.execute(
            update(Ingredient).where(Ingredient.id == poulet.id).values(name="Dinde")
        )
        await session.commit()
        assert _titles(await _search(session, query="dinde")) == ["Curry"]
        assert _titles(await _search(session, query="poulet")) == []

    async def test_removing_ingredient_updates_search(self, session):
        poulet = await _ingredient(session, "Poulet")
        await _recipe(session, "Curry", [poulet])
        await session.execute(text("DELETE FROM recipe_ingredients"))
        await session.commit()
        assert _titles(await _search(session, query="poulet")) == []


class TestFilters:
    async def test_scoped_to_account(self, session):
        await _recipe(session, "Ma recette")
        await _recipe(session, "Recette d'un autre", account=OTHER_ACCOUNT)
        assert _titles(await _search(session)) == ["Ma recette"]

    async def test_no_query_sorted_by_newest(self, session):
        await _recipe(session, "Ancienne", age_days=5)
        await _recipe(session, "Récente", age_days=1)
        assert _titles(await _search(session)) == ["Récente", "Ancienne"]

    async def test_enum_filters_take_api_values(self, session):
        await _recipe(
            session,
            "Facile",
            difficulty=DifficultyLevel.EASY,
            course_type=CourseType.MAIN_COURSE,
        )
        await _recipe(session, "Difficile", difficulty=DifficultyLevel.HARD)
        assert _titles(await _search(session, difficulty="enums.difficulty.easy")) == [
            "Facile"
        ]
        assert _titles(
            await _search(session, course_type="enums.course_type.main")
        ) == ["Facile"]
        assert await _search(session, difficulty="inconnu") == {
            "total": 0,
            "limit": 10,
            "offset": 0,
            "results": [],
        }

    async def test_max_prep_time(self, session):
        await _recipe(session, "Rapide", prep_time_minutes=10)
        await _recipe(session, "Lente", prep_time_minutes=90)
        assert _titles(await _search(session, max_prep_time=30)) == ["Rapide"]

    async def test_exclude_allergens_from_ingredient_tags(self, session):
        farine = await _ingredient(session, "Farine", ["enums.allergen.gluten"])
        await _recipe(session, "Pain", [farine])
        await _recipe(session, "Salade")
        response = await _search(session, exclude_allergens=["enums.allergen.gluten"])
        assert _titles(response) == ["Salade"]

    async def test_pagination_and_total(self, session):
        for day in range(5):
            await _recipe(session, f"Recette {day}", age_days=day)
        response = await _search(session, limit=2, offset=2)
        assert response["total"] == 5
        assert _titles(response) == ["Recette 2", "Recette 3"]


class TestEngineCriteria:
    async def test_excluded_terms_match_whole_words(self, session):
        """« lait » exclut « Lait entier » mais pas « Laitue »."""
        lait = await _ingredient(session, "Lait entier")
        laitue = await _ingredient(session, "Laitue")
        await _recipe(session, "Béchamel", [lait])
        await _recipe(session, "Salade", [laitue])
        criteria = SearchCriteria(excluded_terms=["lait"])
        assert _titles(await _search(session, criteria=criteria)) == ["Salade"]

    async def test_excluded_terms_plural_and_accents(self, session):
        oeufs = await _ingredient(session, "Œufs frais")
        await _recipe(session, "Omelette", [oeufs])
        criteria = SearchCriteria(excluded_terms=["oeuf"])
        assert _titles(await _search(session, criteria=criteria)) == []

    async def test_excluded_tags(self, session):
        boeuf = await _ingredient(
            session, "Boeuf", ["enums.type_of_ingredient.red_meat"]
        )
        await _recipe(session, "Bourguignon", [boeuf])
        await _recipe(session, "Ratatouille")
        criteria = SearchCriteria(excluded_tags=["enums.type_of_ingredient.red_meat"])
        assert _titles(await _search(session, criteria=criteria)) == ["Ratatouille"]

    async def test_required_fields_and_unknown_field_ignored(self, session):
        await _recipe(session, "Avec macros", calories=500)
        await _recipe(session, "Sans macros")
        criteria = SearchCriteria(required_fields=["calories", "budget"])
        assert _titles(await _search(session, criteria=criteria)) == ["Avec macros"]

    async def test_macro_proximity_ranks_closest_first(self, session):
        await _recipe(session, "Trop lourde", calories=1200)
        await _recipe(session, "Pile", calories=600)
        await _recipe(session, "Sans macros")
        await _recipe(session, "Un peu légère", calories=500)
        criteria = SearchCriteria(
            macro_targets=[MacroTarget(field="calories", target=600, scale=60)]
        )
        response = await _search(session, criteria=criteria)
        assert _titles(response)[:3] == ["Pile", "Un peu légère", "Trop lourde"]
        assert response["results"][0]["score"] == pytest.approx(1.0)
        # ½ à target ± scale : 500 est à 100/60 d'écart → 0,5^(1,67²)
        assert response["results"][1]["score"] == pytest.approx(
            0.5 ** ((100 / 60) ** 2)
        )

    async def test_scoring_disabled_keeps_exclusions(self, session):
        lait = await _ingredient(session, "Lait")
        await _recipe(session, "Béchamel", [lait], calories=600)
        await _recipe(session, "Salade", calories=100, age_days=1)
        await _recipe(session, "Soupe", calories=600, age_days=2)
        criteria = SearchCriteria(
            excluded_terms=["lait"],
            macro_targets=[MacroTarget(field="calories", target=600, scale=60)],
        )
        response = await _search(session, criteria=criteria, apply_scoring=False)
        # plus de scoring → ordre chronologique, exclusion toujours appliquée
        assert _titles(response) == ["Salade", "Soupe"]


class TestResultDocument:
    async def test_document_shape(self, session):
        farine = await _ingredient(session, "Farine", ["enums.allergen.gluten"])
        await _recipe(
            session,
            "Crêpes",
            [farine],
            calories=350,
            difficulty=DifficultyLevel.EASY,
            created_by_user_id="user-1",
        )
        result = (await _search(session, query="crepes"))["results"][0]
        assert result["ingredient_names"] == ["Farine"]
        assert result["allergens"] == ["enums.allergen.gluten"]
        assert result["difficulty"] == "enums.difficulty.easy"
        assert result["calories"] == 350
        assert result["account_id"] == ACCOUNT
        assert "created_by_user_id" not in result
        assert "search_vector" not in result
        assert isinstance(result["id"], int)
        assert result["score"] > 0
