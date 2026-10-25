"""LookupService sur un vrai PostgreSQL (pg_trgm + unaccent).

La similarité trigramme n'existe pas sous SQLite : ces tests exigent
``TEST_POSTGRES_URL`` (ex. ``postgresql+asyncpg://test:test@localhost:55432/test``)
et sont ignorés sinon. La CI fournit un service PostgreSQL.
"""

import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models.nutrition_item import NutritionItem, NutritionSource
from app.services.lookup_service import LookupService

PG_URL = os.environ.get("TEST_POSTGRES_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not PG_URL, reason="TEST_POSTGRES_URL non défini"),
]

_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic/versions/e2f3a4b5c6d7_trigram_index_lookup.py"
)


def _migration_sql() -> list[str]:
    """Fonction f_unaccent + index trigrammes : le SQL réellement déployé."""
    spec = importlib.util.spec_from_file_location("trgm_migration", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return [module.F_UNACCENT, *module.INDEXES]


_ITEMS = [
    ("Tomate, crue", "Tomato, raw"),
    ("Tomate, séchée, à l'huile, égouttée", "Tomato, sun-dried, in oil, drained"),
    ("Caviar de tomates", None),
    ("Criste marine, fraîche, crue", None),
    ("Poulet blanc, viande et peau crues", None),
    ("Jambon de poulet ou blanc de poulet en tranche", None),
    ("Farine de blé tendre ou froment T55", "Wheat flour, type 55"),
    ("Farine de sarrasin", "Buckwheat flour"),
    ("Oeuf, cru", "Egg, raw"),
    ("Crème fraîche épaisse", None),
]


@pytest.fixture
async def session():
    engine = create_async_engine(PG_URL)
    schema = f"test_lookup_{uuid.uuid4().hex[:8]}"
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(text(f"CREATE SCHEMA {schema}"))
        await conn.execute(text(f"SET search_path TO {schema}, public"))
        await conn.run_sync(lambda c: NutritionItem.__table__.create(c))
        for statement in _migration_sql():
            await conn.execute(text(statement))
    async with AsyncSession(engine) as s:
        await s.execute(text(f"SET search_path TO {schema}, public"))
        for i, (nom_fr, nom_en) in enumerate(_ITEMS):
            s.add(
                NutritionItem(
                    slug=f"item-{i}",
                    nom_fr=nom_fr,
                    nom_en=nom_en,
                    calories=100.0 + i,
                    proteines=1.0,
                    glucides=2.0,
                    lipides=3.0,
                    source=NutritionSource.ciqual,
                )
            )
        await s.flush()
        yield s
        await s.rollback()
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
    await engine.dispose()


class TestLookupService:
    async def test_plural_finds_generic_item_first(self, session):
        """« tomates » → « Tomate, crue » avant la variante plus longue."""
        results = await LookupService(session).search("tomates")
        assert [r.nom_fr for r in results][:2] == [
            "Tomate, crue",
            "Tomate, séchée, à l'huile, égouttée",
        ]
        assert results[0].calories == 100.0

    async def test_head_of_name_beats_exact_substring(self, session):
        """Convention Ciqual : l'aliment principal vient en tête du nom."""
        results = await LookupService(session).search("tomates")
        assert results[0].nom_fr == "Tomate, crue"
        assert "Caviar de tomates" in [r.nom_fr for r in results]

    async def test_any_query_word_can_be_the_head(self, session):
        """« poulet » est la tête : préféré à la charcuterie qui contient la requête."""
        results = await LookupService(session).search("blanc de poulet")
        assert results[0].nom_fr == "Poulet blanc, viande et peau crues"

    async def test_false_friend_rejected(self, session):
        """« fraîche » seul ne suffit pas : pas de tête commune, similarité < 0,8."""
        results = await LookupService(session).search("crème fraîche")
        assert "Criste marine, fraîche, crue" not in [r.nom_fr for r in results]

    async def test_accents_and_case_ignored(self, session):
        results = await LookupService(session).search("CREME FRAICHE")
        assert results[0].nom_fr == "Crème fraîche épaisse"

    async def test_typo_tolerated(self, session):
        results = await LookupService(session).search("farine sarazin")
        assert results[0].nom_fr == "Farine de sarrasin"

    async def test_english_name_matches(self, session):
        results = await LookupService(session).search("buckwheat")
        assert results[0].nom_fr == "Farine de sarrasin"

    async def test_unrelated_query_returns_empty(self, session):
        assert await LookupService(session).search("gochujang") == []

    async def test_size_limits_results(self, session):
        assert len(await LookupService(session).search("farine", size=1)) == 1
