import pytest
from httpx import AsyncClient

from app.models.weekly_menu import WeeklyMenu
from tests.integration.conftest import menu_payload, slot_payload

MENUS_BASE = "/api/v1/menus"


def shopping_url(menu_id: int) -> str:
    return f"{MENUS_BASE}/{menu_id}/shopping-list"


def export_url(menu_id: int, fmt: str) -> str:
    return f"{MENUS_BASE}/{menu_id}/shopping-list/export?format={fmt}"


async def _create_menu(client: AsyncClient, recipe_id: int = 100) -> dict:
    payload = menu_payload(nb_persons=2, slots=[slot_payload(recipe_id=recipe_id)])
    r = await client.post(MENUS_BASE, json=payload)
    assert r.status_code == 201
    return r.json()


# ---------------------------------------------------------------------------
# GET /api/v1/menus/{id}/shopping-list
# ---------------------------------------------------------------------------

class TestGetShoppingList:
    async def test_returns_200(self, client: AsyncClient):
        menu = await _create_menu(client)
        assert (await client.get(shopping_url(menu["id"]))).status_code == 200

    async def test_response_contains_required_fields(self, client: AsyncClient):
        menu = await _create_menu(client)
        body = (await client.get(shopping_url(menu["id"]))).json()
        assert body["menu_id"] == menu["id"]
        assert body["nb_persons"] == 2
        assert body["start_date"] == menu["start_date"]
        assert isinstance(body["items"], list)

    async def test_items_have_ingredient_fields(self, client: AsyncClient):
        menu = await _create_menu(client)
        body = (await client.get(shopping_url(menu["id"]))).json()
        assert len(body["items"]) > 0
        item = body["items"][0]
        for field in ("ingredient_id", "ingredient_name", "total_quantity", "unit"):
            assert field in item

    async def test_quantities_multiplied_by_nb_persons(self, client: AsyncClient):
        # RICH_RECIPE pasta: 200g/serving × 2 persons = 400g
        menu = (await client.post(
            MENUS_BASE,
            json=menu_payload(nb_persons=2, slots=[slot_payload(recipe_id=100)]),
        )).json()
        body = (await client.get(shopping_url(menu["id"]))).json()
        pasta = next((i for i in body["items"] if i["ingredient_name"] == "Pasta"), None)
        assert pasta is not None
        assert pasta["total_quantity"] == pytest.approx(400.0)

    async def test_empty_slots_returns_empty_items(self, client: AsyncClient):
        menu = (await client.post(MENUS_BASE, json=menu_payload(slots=[]))).json()
        body = (await client.get(shopping_url(menu["id"]))).json()
        assert body["items"] == []

    async def test_404_for_nonexistent_menu(self, client: AsyncClient):
        assert (await client.get(shopping_url(99999))).status_code == 404

    async def test_403_for_other_users_menu(
        self, client: AsyncClient, other_user_menu: WeeklyMenu
    ):
        assert (await client.get(shopping_url(other_user_menu.id))).status_code == 403

    async def test_same_ingredient_aggregated_across_slots(self, client: AsyncClient):
        # Deux slots avec la même recette → quantités doublées (200 × 2 slots × 1 person)
        slots = [
            slot_payload(day="enums.day.monday",  recipe_id=100),
            slot_payload(day="enums.day.tuesday", recipe_id=100),
        ]
        menu = (await client.post(MENUS_BASE, json=menu_payload(nb_persons=1, slots=slots))).json()
        body = (await client.get(shopping_url(menu["id"]))).json()
        pasta = next((i for i in body["items"] if i["ingredient_name"] == "Pasta"), None)
        assert pasta is not None
        assert pasta["total_quantity"] == pytest.approx(400.0)


# ---------------------------------------------------------------------------
# GET /api/v1/menus/{id}/shopping-list/export?format=csv
# ---------------------------------------------------------------------------

class TestExportCsv:
    async def test_returns_200(self, client: AsyncClient):
        menu = await _create_menu(client)
        assert (await client.get(export_url(menu["id"], "csv"))).status_code == 200

    async def test_content_type_csv(self, client: AsyncClient):
        menu = await _create_menu(client)
        r = await client.get(export_url(menu["id"], "csv"))
        assert "text/csv" in r.headers["content-type"]

    async def test_content_disposition_has_filename(self, client: AsyncClient):
        menu = await _create_menu(client)
        r = await client.get(export_url(menu["id"], "csv"))
        assert f"shopping-list-{menu['id']}.csv" in r.headers["content-disposition"]

    async def test_header_row_present(self, client: AsyncClient):
        menu = await _create_menu(client)
        content = (await client.get(export_url(menu["id"], "csv"))).text
        assert "Ingrédient" in content

    async def test_ingredient_names_in_csv(self, client: AsyncClient):
        menu = await _create_menu(client, recipe_id=100)
        content = (await client.get(export_url(menu["id"], "csv"))).text
        assert "Pasta" in content

    async def test_404_for_nonexistent_menu(self, client: AsyncClient):
        assert (await client.get(export_url(99999, "csv"))).status_code == 404

    async def test_403_for_other_users_menu(
        self, client: AsyncClient, other_user_menu: WeeklyMenu
    ):
        assert (await client.get(export_url(other_user_menu.id, "csv"))).status_code == 403


# ---------------------------------------------------------------------------
# GET /api/v1/menus/{id}/shopping-list/export?format=pdf
# ---------------------------------------------------------------------------

class TestExportPdf:
    async def test_returns_200(self, client: AsyncClient):
        menu = await _create_menu(client)
        assert (await client.get(export_url(menu["id"], "pdf"))).status_code == 200

    async def test_content_type_pdf(self, client: AsyncClient):
        menu = await _create_menu(client)
        r = await client.get(export_url(menu["id"], "pdf"))
        assert "application/pdf" in r.headers["content-type"]

    async def test_pdf_body_non_empty(self, client: AsyncClient):
        menu = await _create_menu(client)
        r = await client.get(export_url(menu["id"], "pdf"))
        assert len(r.content) > 0


# ---------------------------------------------------------------------------
# Invalid format
# ---------------------------------------------------------------------------

class TestInvalidFormat:
    async def test_unknown_format_returns_422(self, client: AsyncClient):
        menu = await _create_menu(client)
        r = await client.get(f"{MENUS_BASE}/{menu['id']}/shopping-list/export?format=xlsx")
        assert r.status_code == 422