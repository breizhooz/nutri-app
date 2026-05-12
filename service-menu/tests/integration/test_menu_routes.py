import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.weekly_menu import WeeklyMenu
from tests.integration.conftest import TEST_USER_ID, menu_payload, slot_payload

BASE = "/api/v1/menus"


# ---------------------------------------------------------------------------
# POST /api/v1/menus  —  create
# ---------------------------------------------------------------------------

class TestCreateMenu:
    async def test_returns_201(self, client: AsyncClient):
        r = await client.post(BASE, json=menu_payload())
        assert r.status_code == 201

    async def test_response_contains_id_and_timestamps(self, client: AsyncClient):
        body = (await client.post(BASE, json=menu_payload())).json()
        assert "id" in body
        assert "created_at" in body
        assert "updated_at" in body

    async def test_user_id_set_from_jwt(self, client: AsyncClient):
        body = (await client.post(BASE, json=menu_payload())).json()
        assert body["user_id"] == TEST_USER_ID

    async def test_slug_auto_generated_contains_date(self, client: AsyncClient):
        body = (await client.post(BASE, json=menu_payload())).json()
        assert body["slug"] is not None
        assert "2026-06-02" in body["slug"]

    async def test_custom_slug_stored(self, client: AsyncClient):
        body = (await client.post(BASE, json=menu_payload(slug="my-slug"))).json()
        assert body["slug"] == "my-slug"

    async def test_slug_with_space_rejected(self, client: AsyncClient):
        r = await client.post(BASE, json=menu_payload(slug="bad slug"))
        assert r.status_code == 422

    async def test_rating_3_accepted(self, client: AsyncClient):
        body = (await client.post(BASE, json=menu_payload(rating=3))).json()
        assert body["rating"] == 3

    async def test_rating_above_5_rejected(self, client: AsyncClient):
        assert (await client.post(BASE, json=menu_payload(rating=6))).status_code == 422

    async def test_rating_below_1_rejected(self, client: AsyncClient):
        assert (await client.post(BASE, json=menu_payload(rating=0))).status_code == 422

    async def test_nb_persons_zero_rejected(self, client: AsyncClient):
        assert (await client.post(BASE, json=menu_payload(nb_persons=0))).status_code == 422

    async def test_slots_created_inline(self, client: AsyncClient):
        body = (await client.post(BASE, json=menu_payload(slots=[slot_payload()]))).json()
        assert len(body["slots"]) == 1

    async def test_multiple_slots(self, client: AsyncClient):
        slots = [
            slot_payload(day="enums.day.monday", meal="enums.meal_type.lunch"),
            slot_payload(day="enums.day.tuesday", meal="enums.meal_type.dinner"),
        ]
        body = (await client.post(BASE, json=menu_payload(slots=slots))).json()
        assert len(body["slots"]) == 2

    async def test_exclusions_stored(self, client: AsyncClient):
        body = (await client.post(BASE, json=menu_payload(exclusions=["enums.allergen.gluten"]))).json()
        assert body["exclusions"] == ["enums.allergen.gluten"]

    async def test_free_tags_stored(self, client: AsyncClient):
        body = (await client.post(BASE, json=menu_payload(free_tags={"occasion": "birthday"}))).json()
        assert body["free_tags"] == {"occasion": "birthday"}

    async def test_notes_stored(self, client: AsyncClient):
        body = (await client.post(BASE, json=menu_payload(notes="Vegetarian week"))).json()
        assert body["notes"] == "Vegetarian week"

    async def test_caloric_target_stored(self, client: AsyncClient):
        body = (await client.post(BASE, json=menu_payload(caloric_target=2000))).json()
        assert body["caloric_target"] == 2000


# ---------------------------------------------------------------------------
# POST /api/v1/menus/generate  —  randomised generation
# ---------------------------------------------------------------------------

class TestGenerateMenu:
    async def test_returns_201(self, client: AsyncClient):
        r = await client.post(f"{BASE}/generate", json=menu_payload())
        assert r.status_code == 201

    async def test_generates_14_slots_by_default(self, client: AsyncClient):
        body = (await client.post(f"{BASE}/generate", json=menu_payload())).json()
        assert len(body["slots"]) == 14  # 7 days × 2 meals

    async def test_generated_menu_belongs_to_authenticated_user(self, client: AsyncClient):
        body = (await client.post(f"{BASE}/generate", json=menu_payload())).json()
        assert body["user_id"] == TEST_USER_ID

    async def test_generated_menu_retrievable(self, client: AsyncClient):
        created = (await client.post(f"{BASE}/generate", json=menu_payload())).json()
        r = await client.get(f"{BASE}/{created['id']}")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/v1/menus  —  list
# ---------------------------------------------------------------------------

class TestListMenus:
    async def test_empty_initially(self, client: AsyncClient):
        assert (await client.get(BASE)).json() == []

    async def test_lists_own_menus(self, client: AsyncClient):
        await client.post(BASE, json=menu_payload())
        await client.post(BASE, json=menu_payload(start_date="2026-06-09"))
        r = await client.get(BASE)
        assert len(r.json()) == 2

    async def test_does_not_return_other_users_menus(
        self, client: AsyncClient, other_user_menu: WeeklyMenu
    ):
        await client.post(BASE, json=menu_payload())
        r = await client.get(BASE)
        ids = [m["id"] for m in r.json()]
        assert other_user_menu.id not in ids

    async def test_pagination_skip(self, client: AsyncClient):
        for i in range(3):
            await client.post(BASE, json=menu_payload(start_date=f"2026-06-0{i + 2}"))
        r = await client.get(BASE, params={"skip": 1})
        assert len(r.json()) == 2

    async def test_pagination_limit(self, client: AsyncClient):
        for i in range(5):
            await client.post(BASE, json=menu_payload(start_date=f"2026-06-0{i + 2}"))
        r = await client.get(BASE, params={"limit": 2})
        assert len(r.json()) == 2


# ---------------------------------------------------------------------------
# GET /api/v1/menus/{id}  —  get one
# ---------------------------------------------------------------------------

class TestGetMenu:
    async def test_returns_200_for_own_menu(self, client: AsyncClient):
        created = (await client.post(BASE, json=menu_payload())).json()
        r = await client.get(f"{BASE}/{created['id']}")
        assert r.status_code == 200
        assert r.json()["id"] == created["id"]

    async def test_includes_slots_in_response(self, client: AsyncClient):
        slots = [slot_payload(), slot_payload(day="enums.day.tuesday")]
        created = (await client.post(BASE, json=menu_payload(slots=slots))).json()
        body = (await client.get(f"{BASE}/{created['id']}")).json()
        assert len(body["slots"]) == 2

    async def test_404_for_nonexistent_id(self, client: AsyncClient):
        assert (await client.get(f"{BASE}/99999")).status_code == 404

    async def test_403_for_other_users_menu(
        self, client: AsyncClient, other_user_menu: WeeklyMenu
    ):
        assert (await client.get(f"{BASE}/{other_user_menu.id}")).status_code == 403


# ---------------------------------------------------------------------------
# PUT /api/v1/menus/{id}  —  update
# ---------------------------------------------------------------------------

class TestUpdateMenu:
    async def test_updates_notes(self, client: AsyncClient):
        created = (await client.post(BASE, json=menu_payload())).json()
        body = (await client.put(f"{BASE}/{created['id']}", json={"notes": "Updated"})).json()
        assert body["notes"] == "Updated"

    async def test_updates_rating(self, client: AsyncClient):
        created = (await client.post(BASE, json=menu_payload())).json()
        body = (await client.put(f"{BASE}/{created['id']}", json={"rating": 5})).json()
        assert body["rating"] == 5

    async def test_updates_nb_persons(self, client: AsyncClient):
        created = (await client.post(BASE, json=menu_payload())).json()
        body = (await client.put(f"{BASE}/{created['id']}", json={"nb_persons": 4})).json()
        assert body["nb_persons"] == 4

    async def test_replaces_slots_when_provided(self, client: AsyncClient):
        created = (await client.post(BASE, json=menu_payload(slots=[slot_payload()]))).json()
        new_slots = [
            slot_payload(day="enums.day.wednesday"),
            slot_payload(day="enums.day.friday"),
        ]
        body = (await client.put(f"{BASE}/{created['id']}", json={"slots": new_slots})).json()
        assert len(body["slots"]) == 2

    async def test_partial_update_leaves_other_fields_unchanged(self, client: AsyncClient):
        created = (await client.post(BASE, json=menu_payload(notes="Original", rating=3))).json()
        body = (await client.put(f"{BASE}/{created['id']}", json={"notes": "Changed"})).json()
        assert body["rating"] == 3

    async def test_invalid_rating_rejected(self, client: AsyncClient):
        created = (await client.post(BASE, json=menu_payload())).json()
        assert (
            await client.put(f"{BASE}/{created['id']}", json={"rating": 10})
        ).status_code == 422

    async def test_404_for_nonexistent(self, client: AsyncClient):
        assert (await client.put(f"{BASE}/99999", json={"notes": "x"})).status_code == 404

    async def test_403_for_other_users_menu(
        self, client: AsyncClient, other_user_menu: WeeklyMenu
    ):
        assert (
            await client.put(f"{BASE}/{other_user_menu.id}", json={"notes": "hack"})
        ).status_code == 403


# ---------------------------------------------------------------------------
# DELETE /api/v1/menus/{id}
# ---------------------------------------------------------------------------

class TestDeleteMenu:
    async def test_returns_204(self, client: AsyncClient):
        created = (await client.post(BASE, json=menu_payload())).json()
        r = await client.delete(f"{BASE}/{created['id']}")
        assert r.status_code == 204

    async def test_menu_gone_after_delete(self, client: AsyncClient):
        created = (await client.post(BASE, json=menu_payload())).json()
        await client.delete(f"{BASE}/{created['id']}")
        assert (await client.get(f"{BASE}/{created['id']}")).status_code == 404

    async def test_slots_cascade_deleted(self, client: AsyncClient, session: AsyncSession):
        from app.models.menu_slot import MenuSlot
        from sqlalchemy import select as sa_select
        created = (await client.post(BASE, json=menu_payload(slots=[slot_payload()]))).json()
        menu_id = created["id"]
        await client.delete(f"{BASE}/{menu_id}")
        result = await session.execute(sa_select(MenuSlot).where(MenuSlot.menu_id == menu_id))
        assert result.scalars().all() == []

    async def test_404_for_nonexistent(self, client: AsyncClient):
        assert (await client.delete(f"{BASE}/99999")).status_code == 404

    async def test_403_for_other_users_menu(
        self, client: AsyncClient, other_user_menu: WeeklyMenu
    ):
        assert (await client.delete(f"{BASE}/{other_user_menu.id}")).status_code == 403
        assert other_user_menu.id is not None