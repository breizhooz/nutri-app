import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.nutrition_item import NutritionItem, NutritionSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_item(
    session: AsyncSession,
    *,
    slug: str = "poulet-roti",
    nom_fr: str = "Poulet rôti",
    nom_en: str | None = "Roasted chicken",
    calories: float | None = 165.0,
    proteines: float | None = 31.0,
    glucides: float | None = 0.0,
    lipides: float | None = 4.0,
    fibres: float | None = 0.0,
    source: NutritionSource = NutritionSource.ciqual,
    ciqual_id: int | None = 1001,
) -> NutritionItem:
    item = NutritionItem(
        id=uuid.uuid4(),
        slug=slug,
        nom_fr=nom_fr,
        nom_en=nom_en,
        calories=calories,
        proteines=proteines,
        glucides=glucides,
        lipides=lipides,
        fibres=fibres,
        source=source,
        ciqual_id=ciqual_id,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


# ---------------------------------------------------------------------------
# GET /api/v1/nutrition-items/{slug}
# ---------------------------------------------------------------------------

class TestGetNutritionItem:
    async def test_get_existing_item_returns_200(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await _create_item(db_session, slug="poulet-roti")

        resp = await client.get("/api/v1/nutrition-items/poulet-roti")

        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "poulet-roti"
        assert data["nom_fr"] == "Poulet rôti"
        assert data["nom_en"] == "Roasted chicken"
        assert data["calories"] == 165.0
        assert data["proteines"] == 31.0
        assert data["glucides"] == 0.0
        assert data["lipides"] == 4.0
        assert data["fibres"] == 0.0
        assert data["source"] == "ciqual"

    async def test_get_item_public_no_auth_required(
        self, db_session: AsyncSession, app
    ):
        """L'endpoint GET est public — pas de token nécessaire."""
        from httpx import ASGITransport, AsyncClient as HttpxClient

        await _create_item(db_session, slug="riz-basmati", ciqual_id=2001)

        async with HttpxClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as anon_client:
            resp = await anon_client.get("/api/v1/nutrition-items/riz-basmati")

        assert resp.status_code == 200
        assert resp.json()["slug"] == "riz-basmati"

    async def test_get_unknown_slug_returns_404(self, client: AsyncClient):
        resp = await client.get("/api/v1/nutrition-items/inexistant-slug")

        assert resp.status_code == 404

    async def test_get_item_with_null_fields(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await _create_item(
            db_session,
            slug="aliment-incomplet",
            nom_en=None,
            calories=None,
            proteines=None,
            glucides=None,
            lipides=None,
            fibres=None,
            ciqual_id=None,
        )

        resp = await client.get("/api/v1/nutrition-items/aliment-incomplet")

        assert resp.status_code == 200
        data = resp.json()
        assert data["nom_en"] is None
        assert data["calories"] is None
        assert data["fibres"] is None

    async def test_get_item_off_source(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        item = NutritionItem(
            id=uuid.uuid4(),
            slug="yaourt-nature",
            nom_fr="Yaourt nature",
            source=NutritionSource.open_food_facts,
            calories=59.0,
            proteines=3.8,
            glucides=4.9,
            lipides=1.5,
            off_id="3033490004743",
            off_enriched=True,
        )
        db_session.add(item)
        await db_session.commit()

        resp = await client.get("/api/v1/nutrition-items/yaourt-nature")

        assert resp.status_code == 200
        assert resp.json()["source"] == "open_food_facts"


# ---------------------------------------------------------------------------
# PATCH /api/v1/nutrition-items/{slug}
# ---------------------------------------------------------------------------

class TestPatchNutritionItem:
    async def test_patch_updates_fields(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await _create_item(db_session, slug="beurre", calories=717.0, source=NutritionSource.user, ciqual_id=None)

        resp = await client.patch(
            "/api/v1/nutrition-items/beurre",
            json={"calories": 720.0, "nom_en": "Butter"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["calories"] == 720.0
        assert data["nom_en"] == "Butter"
        assert data["slug"] == "beurre"

    async def test_patch_requires_auth(self, db_session: AsyncSession, app):
        await _create_item(db_session, slug="lait", ciqual_id=3001)

        from httpx import ASGITransport, AsyncClient as HttpxClient

        async with HttpxClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as anon_client:
            resp = await anon_client.patch(
                "/api/v1/nutrition-items/lait",
                json={"calories": 50.0},
            )

        assert resp.status_code == 401

    async def test_patch_unknown_slug_returns_404(self, client: AsyncClient):
        resp = await client.patch(
            "/api/v1/nutrition-items/inexistant",
            json={"calories": 100.0},
        )

        assert resp.status_code == 404

    async def test_patch_partial_update_preserves_other_fields(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await _create_item(
            db_session,
            slug="huile-olive",
            calories=884.0,
            proteines=0.0,
            lipides=100.0,
            ciqual_id=4001,
        )

        resp = await client.patch(
            "/api/v1/nutrition-items/huile-olive",
            json={"nom_en": "Olive oil"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["calories"] == 884.0
        assert data["lipides"] == 100.0
        assert data["nom_en"] == "Olive oil"

    async def test_patch_set_null_optional_field(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await _create_item(
            db_session,
            slug="fromage",
            nom_en="Cheese",
            ciqual_id=5001,
        )

        resp = await client.patch(
            "/api/v1/nutrition-items/fromage",
            json={"nom_en": None},
        )

        assert resp.status_code == 200
        assert resp.json()["nom_en"] is None

    async def test_patch_empty_body_returns_200_unchanged(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await _create_item(db_session, slug="oeuf", calories=155.0, ciqual_id=6001)

        resp = await client.patch("/api/v1/nutrition-items/oeuf", json={})

        assert resp.status_code == 200
        assert resp.json()["calories"] == 155.0

    async def test_patch_invalid_calories_type_returns_422(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await _create_item(db_session, slug="pain", ciqual_id=7001)

        resp = await client.patch(
            "/api/v1/nutrition-items/pain",
            json={"calories": "pas-un-nombre"},
        )

        assert resp.status_code == 422

    async def test_patch_negative_calories_returns_422(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        await _create_item(db_session, slug="pomme", ciqual_id=8001)

        resp = await client.patch(
            "/api/v1/nutrition-items/pomme",
            json={"calories": -10.0},
        )

        assert resp.status_code == 422