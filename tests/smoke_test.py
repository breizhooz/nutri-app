import httpx
import pytest

SERVICE_USER_URL = "http://localhost:8001"
SERVICE_RECIPE_URL = "http://localhost:8002"
SERVICE_MENU_URL = "http://localhost:8003"
INGREDIENTS_TO_TEST = [
    {
        "name": "filet de poulet",
        "tags": ["enums.type_of_ingredient.meat"],
        "free_tags": ["tag1", "tag2"],
        "calories_per_100g": 110.0,
        "proteins_per_100g": 26.2,
        "carbs_per_100g": 0.4,
        "fats_per_100g": 0.0
    },
    {
        "name": "oeuf",
        "tags": ["enums.type_of_ingredient.egg"],
        "free_tags": ["vegan"],
        "calories_per_100g": 76.0,
        "proteins_per_100g": 8.0,
        "carbs_per_100g": 1.9,
        "fats_per_100g": 4.8
    }
]

INGREDIENTS_TO_TEST2 = [
    {
        "name": "filet de coin",
        "tags": ["enums.type_of_ingredient.meat"],
        "free_tags": ["tag1", "tag2"],
        "calories_per_100g": 110.0,
        "proteins_per_100g": 26.2,
        "carbs_per_100g": 0.4,
        "fats_per_100g": 0.0
    },
    {
        "name": "roule",
        "tags": ["enums.type_of_ingredient.egg"],
        "free_tags": ["vegan"],
        "calories_per_100g": 76.0,
        "proteins_per_100g": 8.0,
        "carbs_per_100g": 1.9,
        "fats_per_100g": 4.8
    }
]
INGREDIENTS_9 = [
    {"name": "pâtes",         "tags": ["enums.type_of_ingredient.grain"],           "free_tags": [],        "calories_per_100g": 350.0, "proteins_per_100g": 12.0, "carbs_per_100g": 70.0, "fats_per_100g":   1.5},
    {"name": "tomates",       "tags": ["enums.type_of_ingredient.fruit_vegetable"], "free_tags": ["vegan"], "calories_per_100g":  18.0, "proteins_per_100g":  0.9, "carbs_per_100g":  3.5, "fats_per_100g":   0.2},
    {"name": "ail",           "tags": ["enums.type_of_ingredient.bulb_vegetable"],  "free_tags": [],        "calories_per_100g": 149.0, "proteins_per_100g":  6.4, "carbs_per_100g": 33.0, "fats_per_100g":   0.5},
    {"name": "huile d'olive", "tags": ["enums.type_of_ingredient.oil"],             "free_tags": ["vegan"], "calories_per_100g": 884.0, "proteins_per_100g":  0.0, "carbs_per_100g":  0.0, "fats_per_100g": 100.0},
    {"name": "sel",           "tags": ["enums.type_of_ingredient.condiment"],       "free_tags": [],        "calories_per_100g":   0.0, "proteins_per_100g":  0.0, "carbs_per_100g":  0.0, "fats_per_100g":   0.0},
    {"name": "poivre",        "tags": ["enums.type_of_ingredient.spice"],           "free_tags": [],        "calories_per_100g": 251.0, "proteins_per_100g": 10.4, "carbs_per_100g": 64.0, "fats_per_100g":   3.3},
    {"name": "basilic",       "tags": ["enums.type_of_ingredient.herb"],            "free_tags": ["vegan"], "calories_per_100g":  22.0, "proteins_per_100g":  3.2, "carbs_per_100g":  2.7, "fats_per_100g":   0.6},
    {"name": "parmesan",      "tags": ["enums.type_of_ingredient.cheese"],          "free_tags": [],        "calories_per_100g": 392.0, "proteins_per_100g": 36.0, "carbs_per_100g":  0.0, "fats_per_100g":  28.0},
    {"name": "oignon",        "tags": ["enums.type_of_ingredient.bulb_vegetable"],  "free_tags": ["vegan"], "calories_per_100g":  40.0, "proteins_per_100g":  1.1, "carbs_per_100g":  9.3, "fats_per_100g":   0.1},
]

USER_PAYLOAD = [{"email": "waza@waza.com",  "password": "wazaaaaa"}]

@pytest.fixture(params=USER_PAYLOAD, ids=lambda d: d["email"])
def create_user(request):
    with httpx.Client() as client:
        user_data = request.param
        response = client.post(f"{SERVICE_USER_URL}/api/v1/users", json=user_data)
        assert response.status_code == 201

        user_info = response.json()
        user_info['password'] = user_data['password']

        yield user_info

        login_payload = {"email": user_info["email"], "password": user_info["password"]}
        login_resp = client.post(f"{SERVICE_USER_URL}/api/v1/auth/login", json=login_payload)

        if login_resp.status_code == 200:
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            client.delete(f"{SERVICE_USER_URL}/api/v1/users/{user_info['id']}", headers=headers)
        else:
            print(f"Nettoyage impossible, login échoué : {login_resp.text}")

@pytest.fixture()
def auth_token(create_user):
    payload = {"email": create_user["email"], "password": create_user["password"]}
    with httpx.Client() as client:
        response = client.post(f"{SERVICE_USER_URL}/api/v1/auth/login", json=payload)
        assert response.status_code == 200
        return response.json()['access_token']

@pytest.fixture(params=INGREDIENTS_TO_TEST2, ids=lambda d: d["name"])
def ingredient_setup(request, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    ingredient_data = request.param

    with httpx.Client() as client:
        response = client.post(f"{SERVICE_RECIPE_URL}/api/v1/ingredient/", json=ingredient_data, headers=headers)
        assert response.status_code == 201, f"Erreur creation: {response.text}"
        ingredient_id = response.json()['id']

        yield {"id": ingredient_id, "data": ingredient_data}
        client.delete(f"{SERVICE_RECIPE_URL}/api/v1/ingredient/{ingredient_id}", headers=headers)

def test_ingredient_already_exist(auth_token, ingredient_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    duplicate_data = ingredient_setup["data"]

    with httpx.Client() as client:
        response = client.post(f"{SERVICE_RECIPE_URL}/api/v1/ingredient/", json=duplicate_data, headers=headers)
        assert response.status_code == 409
        assert response.json()['detail'] == 'Cet ingrédient existe déjà.'


def test_workflow_ingredient_exists(auth_token, ingredient_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    ingredient_id = ingredient_setup['id']
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_RECIPE_URL}/api/v1/ingredient/{ingredient_id}", headers=headers)
        assert response.status_code == 200

@pytest.fixture()
def all_ingredients_setup(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    created_ids = []

    with httpx.Client() as client:
        for ing_data in INGREDIENTS_TO_TEST:
            response = client.post(f"{SERVICE_RECIPE_URL}/api/v1/ingredient/", json=ing_data, headers=headers)
            assert response.status_code == 201
            created_ids.append(response.json()['id'])

    yield created_ids

    with httpx.Client() as client:
        for ing_id in created_ids:
            client.delete(f"{SERVICE_RECIPE_URL}/api/v1/ingredient/{ing_id}", headers=headers)

@pytest.fixture()
def recipe_setup(auth_token, all_ingredients_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    recipe_payload = {
        "title": "Poulet aux œufs",
        "instructions": "Faire cuire le filet de poulet. Ajouter les œufs en fin de cuisson.",
        "recipe_ingredients": [
            {"ingredient_id": all_ingredients_setup[0], "quantity": 200.0, "unit": "g"},
            {"ingredient_id": all_ingredients_setup[1], "quantity": 2.0, "unit": "pièce"},
        ]
    }
    with httpx.Client() as client:
        response = client.post(f"{SERVICE_RECIPE_URL}/api/v1/recipe", json=recipe_payload, headers=headers)
        assert response.status_code == 201, f"Erreur création recette: {response.text}"
        recipe_id = response.json()['id']

    yield recipe_id

    with httpx.Client() as client:
        client.delete(f"{SERVICE_RECIPE_URL}/api/v1/recipe/id/{recipe_id}", headers=headers)


def test_create_recipe(recipe_setup):
    assert recipe_setup is not None


def _build_four_recipes(ids):
    return [
        {
            "title": "Pâtes à l'ail",
            "instructions": "Cuire les pâtes. Faire revenir l'ail dans l'huile d'olive. Mélanger et assaisonner.",
            "recipe_ingredients": [
                {"ingredient_id": ids[0], "quantity": 200.0, "unit": "g"},
                {"ingredient_id": ids[2], "quantity":   3.0, "unit": "gousse"},
                {"ingredient_id": ids[3], "quantity":  30.0, "unit": "ml"},
                {"ingredient_id": ids[4], "quantity":   1.0, "unit": "pincée"},
                {"ingredient_id": ids[5], "quantity":   1.0, "unit": "pincée"},
            ],
        },
        {
            "title": "Sauce tomate maison",
            "instructions": "Faire revenir l'oignon et l'ail dans l'huile. Ajouter les tomates. Laisser mijoter avec le basilic.",
            "recipe_ingredients": [
                {"ingredient_id": ids[1], "quantity": 400.0, "unit": "g"},
                {"ingredient_id": ids[2], "quantity":   2.0, "unit": "gousse"},
                {"ingredient_id": ids[8], "quantity":   1.0, "unit": "pièce"},
                {"ingredient_id": ids[6], "quantity":  10.0, "unit": "feuilles"},
                {"ingredient_id": ids[3], "quantity":  20.0, "unit": "ml"},
                {"ingredient_id": ids[4], "quantity":   1.0, "unit": "pincée"},
            ],
        },
        {
            "title": "Salade caprese",
            "instructions": "Trancher les tomates. Disposer avec les feuilles de basilic et le parmesan râpé.",
            "recipe_ingredients": [
                {"ingredient_id": ids[1], "quantity": 300.0, "unit": "g"},
                {"ingredient_id": ids[6], "quantity":  15.0, "unit": "feuilles"},
                {"ingredient_id": ids[7], "quantity":  50.0, "unit": "g"},
            ],
        },
        {
            "title": "Spaghetti bolognaise",
            "instructions": "Faire revenir oignon et ail. Ajouter les tomates. Cuire les pâtes. Mélanger et parsemer de parmesan.",
            "recipe_ingredients": [
                {"ingredient_id": ids[0], "quantity": 200.0, "unit": "g"},
                {"ingredient_id": ids[1], "quantity": 300.0, "unit": "g"},
                {"ingredient_id": ids[8], "quantity":   1.0, "unit": "pièce"},
                {"ingredient_id": ids[2], "quantity":   2.0, "unit": "gousse"},
                {"ingredient_id": ids[3], "quantity":  20.0, "unit": "ml"},
                {"ingredient_id": ids[7], "quantity":  30.0, "unit": "g"},
                {"ingredient_id": ids[4], "quantity":   1.0, "unit": "pincée"},
                {"ingredient_id": ids[5], "quantity":   1.0, "unit": "pincée"},
            ],
        },
    ]


@pytest.fixture()
def nine_ingredients_setup(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    created_ids = []

    with httpx.Client() as client:
        for ing_data in INGREDIENTS_9:
            response = client.post(f"{SERVICE_RECIPE_URL}/api/v1/ingredient/", json=ing_data, headers=headers)
            assert response.status_code == 201, f"Erreur creation ingrédient: {response.text}"
            created_ids.append(response.json()['id'])

    yield created_ids

    with httpx.Client() as client:
        for ing_id in created_ids:
            client.delete(f"{SERVICE_RECIPE_URL}/api/v1/ingredient/{ing_id}", headers=headers)


@pytest.fixture()
def four_recipes_setup(auth_token, nine_ingredients_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    created_ids = []

    with httpx.Client() as client:
        for payload in _build_four_recipes(nine_ingredients_setup):
            response = client.post(f"{SERVICE_RECIPE_URL}/api/v1/recipe", json=payload, headers=headers)
            assert response.status_code == 201, f"Erreur création recette: {response.text}"
            created_ids.append(response.json()['id'])

    yield created_ids

    with httpx.Client() as client:
        for recipe_id in created_ids:
            client.delete(f"{SERVICE_RECIPE_URL}/api/v1/recipe/id/{recipe_id}", headers=headers)


def test_four_recipes_created(four_recipes_setup):
    assert len(four_recipes_setup) == 4


def test_four_recipes_accessible(auth_token, four_recipes_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        for recipe_id in four_recipes_setup:
            response = client.get(f"{SERVICE_RECIPE_URL}/api/v1/recipe/id/{recipe_id}", headers=headers)
            assert response.status_code == 200


DAYS = [
    "enums.day.monday",
    "enums.day.tuesday",
    "enums.day.wednesday",
    "enums.day.thursday",
    "enums.day.friday",
    "enums.day.saturday",
    "enums.day.sunday",
]
MEAL_TYPES = [
    "enums.meal_type.breakfast",
    "enums.meal_type.lunch",
    "enums.meal_type.dinner",
]


def _build_seven_day_menu(recipe_ids):
    slots = [
        {
            "day_of_week": day,
            "meal_type": meal_type,
            "recipe_id": recipe_ids[(i * len(MEAL_TYPES) + j) % len(recipe_ids)],
        }
        for i, day in enumerate(DAYS)
        for j, meal_type in enumerate(MEAL_TYPES)
    ]
    return {
        "start_date": "2026-06-02",
        "nb_persons": 2,
        "notes": "Menu smoke test 7 jours",
        "slots": slots,
    }


@pytest.fixture()
def seven_day_menu_setup(auth_token, four_recipes_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    payload = _build_seven_day_menu(four_recipes_setup)

    with httpx.Client() as client:
        response = client.post(f"{SERVICE_MENU_URL}/api/v1/menus", json=payload, headers=headers)
        assert response.status_code == 201, f"Erreur création menu: {response.text}"
        menu_id = response.json()["id"]

    yield menu_id

    with httpx.Client() as client:
        client.delete(f"{SERVICE_MENU_URL}/api/v1/menus/{menu_id}", headers=headers)


def test_seven_day_menu_created(seven_day_menu_setup):
    assert seven_day_menu_setup is not None


def test_seven_day_menu_has_21_slots(auth_token, seven_day_menu_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_MENU_URL}/api/v1/menus/{seven_day_menu_setup}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["slots"]) == 21


# ══════════════════════════════════════════════════════════
# SERVICE — Crawler
# ══════════════════════════════════════════════════════════

SERVICE_CRAWLER_URL = "http://localhost:8004"
_NULL_UUID = "00000000-0000-0000-0000-000000000000"
_RESULTS_URL = f"{SERVICE_CRAWLER_URL}/api/v1/crawler/results"


class ResultsSmokeHelper:
    @staticmethod
    def get_paginated(client: httpx.Client, **params) -> httpx.Response:
        return client.get(_RESULTS_URL, params=params)

    @staticmethod
    def get_one(client: httpx.Client, result_id: str) -> httpx.Response:
        return client.get(f"{_RESULTS_URL}/{result_id}")

    @staticmethod
    def patch_result(client: httpx.Client, result_id: str, payload: dict) -> httpx.Response:
        return client.patch(f"{_RESULTS_URL}/{result_id}", json=payload)

    @staticmethod
    def validate(client: httpx.Client, result_id: str) -> httpx.Response:
        return client.patch(f"{_RESULTS_URL}/{result_id}/validate")

    @staticmethod
    def reject(client: httpx.Client, result_id: str) -> httpx.Response:
        return client.patch(f"{_RESULTS_URL}/{result_id}/reject")

    @staticmethod
    def poll_for_result(
        client: httpx.Client,
        source_id: str,
        timeout: int = 30,
        interval: float = 2.0,
    ) -> dict | None:
        import time
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            resp = client.get(_RESULTS_URL, params={"status": "waiting", "source_id": source_id})
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                if items:
                    return items[0]
            time.sleep(interval)
        return None


@pytest.fixture()
def source_setup():
    with httpx.Client() as client:
        response = client.post(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources", json={
            "type": "web",
            "url": "https://smoke-test.example.com",
            "frequency_hours": 24,
        })
        assert response.status_code == 201, f"Erreur création source: {response.text}"
        source_id = response.json()["id"]

    yield source_id

    with httpx.Client() as client:
        client.delete(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{source_id}")


@pytest.fixture()
def crawled_result_setup():
    import uuid as _uuid
    unique_url = f"https://www.marmiton.org/recettes/recette_tarte-aux-pommes_12372.aspx?smoke={_uuid.uuid4().hex}"

    with httpx.Client(timeout=60.0) as client:
        create = client.post(
            f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources",
            json={"type": "web", "url": unique_url},
        )
        assert create.status_code == 201, f"Création source échouée: {create.text}"
        source_id = create.json()["id"]

        trigger = client.post(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{source_id}/crawl")
        assert trigger.status_code == 202, f"Trigger crawl échoué: {trigger.text}"

        result = ResultsSmokeHelper.poll_for_result(client, source_id, timeout=60)

        if result is None:
            client.delete(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{source_id}")
            pytest.skip("Worker Celery injoignable ou crawl échoué — stack incomplète")

        yield result

        client.delete(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{source_id}")


# ── Health ─────────────────────────────────────────────────────────────────────

def test_crawler_health():
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_CRAWLER_URL}/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "service-crawler"


def test_crawler_health_db():
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_CRAWLER_URL}/health/db")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


# ── Sources ────────────────────────────────────────────────────────────────────

def test_create_web_source():
    with httpx.Client() as client:
        response = client.post(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources", json={
            "type": "web",
            "url": "https://create-test.example.com",
        })
        assert response.status_code == 201
        body = response.json()
        assert body["url"] == "https://create-test.example.com"
        assert body["type"] == "web"
        assert body["actif"] is True
        assert "id" in body

        client.delete(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{body['id']}")


def test_source_lifecycle(source_setup):
    source_id = source_setup
    with httpx.Client() as client:
        get = client.get(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{source_id}")
        assert get.status_code == 200
        assert get.json()["id"] == source_id

        patch = client.patch(
            f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{source_id}",
            json={"actif": False, "frequency_hours": 48},
        )
        assert patch.status_code == 200
        assert patch.json()["actif"] is False
        assert patch.json()["frequency_hours"] == 48


def test_list_sources_contains_created(source_setup):
    source_id = source_setup
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources")
    assert response.status_code == 200
    ids = [s["id"] for s in response.json()]
    assert source_id in ids


def test_trigger_crawl_queued(source_setup):
    source_id = source_setup
    with httpx.Client() as client:
        response = client.post(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{source_id}/crawl")
    assert response.status_code == 202
    body = response.json()
    assert "source_id" in body
    assert "task_id" in body


def test_trigger_crawl_unsupported_type():
    with httpx.Client() as client:
        create = client.post(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources", json={
            "type": "instagram",
            "url": "@smoke_test_account",
        })
        assert create.status_code == 201
        source_id = create.json()["id"]

        response = client.post(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{source_id}/crawl")
        assert response.status_code == 400

        client.delete(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{source_id}")


def test_get_source_not_found():
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/sources/{_NULL_UUID}")
    assert response.status_code == 404


# ── Résultats — listing paginé (Phase 4) ───────────────────────────────────────

def test_list_results_returns_paginated_envelope():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.get_paginated(client)
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert "pages" in body
    assert isinstance(body["items"], list)
    assert body["page"] == 1
    assert body["page_size"] == 20


def test_list_results_default_status_is_waiting():
    with httpx.Client() as client:
        r1 = ResultsSmokeHelper.get_paginated(client)
        r2 = ResultsSmokeHelper.get_paginated(client, status="waiting")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["total"] == r2.json()["total"]


def test_list_results_filter_by_valid_status():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.get_paginated(client, status="valid")
    assert response.status_code == 200
    for item in response.json()["items"]:
        assert item["status"] == "valid"


def test_list_results_filter_by_rejected_status():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.get_paginated(client, status="rejected")
    assert response.status_code == 200
    for item in response.json()["items"]:
        assert item["status"] == "rejected"


def test_list_results_pagination_params():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.get_paginated(client, page=1, page_size=5)
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert len(body["items"]) <= 5


def test_list_results_page_size_above_max_rejected():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.get_paginated(client, page_size=200)
    assert response.status_code == 422


def test_list_results_page_zero_rejected():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.get_paginated(client, page=0)
    assert response.status_code == 422


def test_list_results_filter_by_source_id_empty():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.get_paginated(client, source_id=_NULL_UUID, status="waiting")
    assert response.status_code == 200
    assert response.json()["total"] == 0


# ── Résultats — détail ─────────────────────────────────────────────────────────

def test_get_result_not_found():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.get_one(client, _NULL_UUID)
    assert response.status_code == 404


def test_get_result_invalid_uuid():
    with httpx.Client() as client:
        response = client.get(f"{_RESULTS_URL}/not-a-uuid")
    assert response.status_code == 422


# ── Résultats — guards 404 sans résultat réel ──────────────────────────────────

def test_validate_result_not_found():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.validate(client, _NULL_UUID)
    assert response.status_code == 404


def test_reject_result_not_found():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.reject(client, _NULL_UUID)
    assert response.status_code == 404


def test_patch_result_not_found():
    with httpx.Client() as client:
        response = ResultsSmokeHelper.patch_result(client, _NULL_UUID, {"title": "X"})
    assert response.status_code == 404


# ── Résultats — flux complets (nécessite Celery worker) ───────────────────────

@pytest.mark.integration
def test_get_crawled_result_detail(crawled_result_setup):
    result = crawled_result_setup
    with httpx.Client() as client:
        response = ResultsSmokeHelper.get_one(client, result["id"])
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == result["id"]
    assert body["status"] == "waiting"
    assert body["url_origin"] != ""


@pytest.mark.integration
def test_edit_waiting_result(crawled_result_setup):
    result = crawled_result_setup
    with httpx.Client() as client:
        response = ResultsSmokeHelper.patch_result(
            client, result["id"], {"title": "Titre corrigé smoke test"}
        )
    assert response.status_code == 200
    assert response.json()["title"] == "Titre corrigé smoke test"


@pytest.mark.integration
def test_reject_waiting_result(crawled_result_setup):
    result = crawled_result_setup
    with httpx.Client() as client:
        response = ResultsSmokeHelper.reject(client, result["id"])
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


@pytest.mark.integration
def test_cannot_edit_after_rejection(crawled_result_setup):
    result = crawled_result_setup
    with httpx.Client() as client:
        ResultsSmokeHelper.reject(client, result["id"])
        response = ResultsSmokeHelper.patch_result(client, result["id"], {"title": "X"})
    assert response.status_code == 409


@pytest.mark.integration
def test_cannot_reject_twice(crawled_result_setup):
    result = crawled_result_setup
    with httpx.Client() as client:
        ResultsSmokeHelper.reject(client, result["id"])
        response = ResultsSmokeHelper.reject(client, result["id"])
    assert response.status_code == 409


@pytest.mark.integration
def test_validate_waiting_result(crawled_result_setup):
    result = crawled_result_setup
    with httpx.Client() as client:
        response = ResultsSmokeHelper.validate(client, result["id"])
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "valid"
    assert body["validate_by"] is not None


@pytest.mark.integration
def test_cannot_edit_after_validation(crawled_result_setup):
    result = crawled_result_setup
    with httpx.Client() as client:
        ResultsSmokeHelper.validate(client, result["id"])
        response = ResultsSmokeHelper.patch_result(client, result["id"], {"title": "X"})
    assert response.status_code == 409


@pytest.mark.integration
def test_cannot_validate_twice(crawled_result_setup):
    result = crawled_result_setup
    with httpx.Client() as client:
        ResultsSmokeHelper.validate(client, result["id"])
        response = ResultsSmokeHelper.validate(client, result["id"])
    assert response.status_code == 409


@pytest.mark.integration
def test_validated_result_appears_in_valid_filter(crawled_result_setup):
    result = crawled_result_setup
    with httpx.Client() as client:
        ResultsSmokeHelper.validate(client, result["id"])
        response = ResultsSmokeHelper.get_paginated(client, status="valid")
    ids = [item["id"] for item in response.json()["items"]]
    assert result["id"] in ids


# ── Settings ───────────────────────────────────────────────────────────────────

def test_crawler_settings_get():
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/settings")
    assert response.status_code == 200
    body = response.json()
    assert "js_detection_threshold" in body
    assert isinstance(body["js_detection_threshold"], int)


def test_crawler_settings_update():
    with httpx.Client() as client:
        original = client.get(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/settings").json()["js_detection_threshold"]

        response = client.patch(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/settings", json={"js_detection_threshold": 300})
        assert response.status_code == 200
        assert response.json()["js_detection_threshold"] == 300

        get = client.get(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/settings")
        assert get.json()["js_detection_threshold"] == 300

        client.patch(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/settings", json={"js_detection_threshold": original})


def test_crawler_settings_rejects_invalid_threshold():
    with httpx.Client() as client:
        response = client.patch(f"{SERVICE_CRAWLER_URL}/api/v1/crawler/settings", json={"js_detection_threshold": 5})
    assert response.status_code == 422