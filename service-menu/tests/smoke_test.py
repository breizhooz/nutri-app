import httpx
import pytest

SERVICE_USER_URL = "http://localhost:8001"
SERVICE_RECIPE_URL = "http://localhost:8002"
SERVICE_MENU_URL = "http://localhost:8003"

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

USER_PAYLOAD = [{"email": "waza@waza.com", "password": "wazaaaaa"}]


# ── Fixtures user / auth ─────────────────────────────────────────────────────────

@pytest.fixture(params=USER_PAYLOAD, ids=lambda d: d["email"])
def create_user(request):
    with httpx.Client() as client:
        user_data = request.param
        response = client.post(f"{SERVICE_USER_URL}/api/v1/users", json=user_data)
        assert response.status_code == 201

        user_info = response.json()
        user_info["password"] = user_data["password"]

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
        return response.json()["access_token"]


# ── Fixtures recettes (setup pour les menus) ─────────────────────────────────────

@pytest.fixture()
def nine_ingredients_setup(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    created_ids = []

    with httpx.Client() as client:
        for ing_data in INGREDIENTS_9:
            response = client.post(f"{SERVICE_RECIPE_URL}/api/v1/ingredient/", json=ing_data, headers=headers)
            assert response.status_code == 201, f"Erreur creation ingrédient: {response.text}"
            created_ids.append(response.json()["id"])

    yield created_ids

    with httpx.Client() as client:
        for ing_id in created_ids:
            client.delete(f"{SERVICE_RECIPE_URL}/api/v1/ingredient/{ing_id}", headers=headers)


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
def four_recipes_setup(auth_token, nine_ingredients_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    created_ids = []

    with httpx.Client() as client:
        for payload in _build_four_recipes(nine_ingredients_setup):
            response = client.post(f"{SERVICE_RECIPE_URL}/api/v1/recipe", json=payload, headers=headers)
            assert response.status_code == 201, f"Erreur création recette: {response.text}"
            created_ids.append(response.json()["id"])

    yield created_ids

    with httpx.Client() as client:
        for recipe_id in created_ids:
            client.delete(f"{SERVICE_RECIPE_URL}/api/v1/recipe/id/{recipe_id}", headers=headers)


# ── Fixture menu ─────────────────────────────────────────────────────────────────

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


# ── Tests ────────────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_seven_day_menu_created(seven_day_menu_setup):
    assert seven_day_menu_setup is not None


@pytest.mark.smoke
def test_seven_day_menu_has_21_slots(auth_token, seven_day_menu_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_MENU_URL}/api/v1/menus/{seven_day_menu_setup}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["slots"]) == 21
