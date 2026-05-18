import httpx
import pytest

SERVICE_USER_URL = "http://localhost:8001"
SERVICE_RECIPE_URL = "http://localhost:8002"

INGREDIENTS_TO_TEST = [
    {
        "name": "filet de poulet",
        "tags": ["enums.type_of_ingredient.meat"],
        "free_tags": ["tag1", "tag2"],
        "calories_per_100g": 110.0,
        "proteins_per_100g": 26.2,
        "carbs_per_100g": 0.4,
        "fats_per_100g": 0.0,
    },
    {
        "name": "oeuf",
        "tags": ["enums.type_of_ingredient.egg"],
        "free_tags": ["vegan"],
        "calories_per_100g": 76.0,
        "proteins_per_100g": 8.0,
        "carbs_per_100g": 1.9,
        "fats_per_100g": 4.8,
    },
]

INGREDIENTS_TO_TEST2 = [
    {
        "name": "filet de coin",
        "tags": ["enums.type_of_ingredient.meat"],
        "free_tags": ["tag1", "tag2"],
        "calories_per_100g": 110.0,
        "proteins_per_100g": 26.2,
        "carbs_per_100g": 0.4,
        "fats_per_100g": 0.0,
    },
    {
        "name": "roule",
        "tags": ["enums.type_of_ingredient.egg"],
        "free_tags": ["vegan"],
        "calories_per_100g": 76.0,
        "proteins_per_100g": 8.0,
        "carbs_per_100g": 1.9,
        "fats_per_100g": 4.8,
    },
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

USER_PAYLOAD = [{"email": "waza@waza.com", "password": "wazaaaaa"}]


# ── Fixtures communes (user + auth) ─────────────────────────────────────────────

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


# ── Fixtures ingrédients / recettes ─────────────────────────────────────────────

@pytest.fixture(params=INGREDIENTS_TO_TEST2, ids=lambda d: d["name"])
def ingredient_setup(request, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    ingredient_data = request.param

    with httpx.Client() as client:
        response = client.post(f"{SERVICE_RECIPE_URL}/api/v1/ingredient/", json=ingredient_data, headers=headers)
        assert response.status_code == 201, f"Erreur creation: {response.text}"
        ingredient_id = response.json()["id"]

        yield {"id": ingredient_id, "data": ingredient_data}
        client.delete(f"{SERVICE_RECIPE_URL}/api/v1/ingredient/{ingredient_id}", headers=headers)


@pytest.fixture()
def all_ingredients_setup(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    created_ids = []

    with httpx.Client() as client:
        for ing_data in INGREDIENTS_TO_TEST:
            response = client.post(f"{SERVICE_RECIPE_URL}/api/v1/ingredient/", json=ing_data, headers=headers)
            assert response.status_code == 201
            created_ids.append(response.json()["id"])

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
        ],
    }
    with httpx.Client() as client:
        response = client.post(f"{SERVICE_RECIPE_URL}/api/v1/recipe", json=recipe_payload, headers=headers)
        assert response.status_code == 201, f"Erreur création recette: {response.text}"
        recipe_id = response.json()["id"]

    yield recipe_id

    with httpx.Client() as client:
        client.delete(f"{SERVICE_RECIPE_URL}/api/v1/recipe/id/{recipe_id}", headers=headers)


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


# ── Tests ────────────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_ingredient_already_exist(auth_token, ingredient_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    duplicate_data = ingredient_setup["data"]

    with httpx.Client() as client:
        response = client.post(f"{SERVICE_RECIPE_URL}/api/v1/ingredient/", json=duplicate_data, headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"] == "Cet ingrédient existe déjà."


@pytest.mark.smoke
def test_workflow_ingredient_exists(auth_token, ingredient_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    ingredient_id = ingredient_setup["id"]
    with httpx.Client() as client:
        response = client.get(f"{SERVICE_RECIPE_URL}/api/v1/ingredient/{ingredient_id}", headers=headers)
    assert response.status_code == 200


@pytest.mark.smoke
def test_create_recipe(recipe_setup):
    assert recipe_setup is not None


@pytest.mark.smoke
def test_four_recipes_created(four_recipes_setup):
    assert len(four_recipes_setup) == 4


@pytest.mark.smoke
def test_four_recipes_accessible(auth_token, four_recipes_setup):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with httpx.Client() as client:
        for recipe_id in four_recipes_setup:
            response = client.get(f"{SERVICE_RECIPE_URL}/api/v1/recipe/id/{recipe_id}", headers=headers)
            assert response.status_code == 200
