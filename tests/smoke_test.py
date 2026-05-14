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
        # 1. CRÉATION
        user_data = request.param
        response = client.post(f"{SERVICE_USER_URL}/api/v1/users", json=user_data)
        assert response.status_code == 201
        
        user_info = response.json()
        user_info['password'] = user_data['password'] 
        
        # On donne les infos au test
        yield user_info
        
        # --- TEARDOWN : NETTOYAGE ---
        # 2. LOGIN pour pouvoir supprimer
        login_payload = {"email": user_info["email"], "password": user_info["password"]}
        login_resp = client.post(f"{SERVICE_USER_URL}/api/v1/auth/login", json=login_payload)
        
        if login_resp.status_code == 200:
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            # 3. SUPPRESSION avec le token
            client.delete(f"{SERVICE_USER_URL}/api/v1/users/{user_info['id']}", headers=headers)
        else:
            print(f"Nettoyage impossible, login échoué : {login_resp.text}")

@pytest.fixture()
def auth_token(create_user):
    """" récupe le token pour le module """
    payload = {"email": create_user["email"], "password": create_user["password"]}
    with httpx.Client() as client:
        response = client.post(f"{SERVICE_USER_URL}/api/v1/auth/login", json=payload)
        assert response.status_code == 200
        return response.json()['access_token']
        
@pytest.fixture(params=INGREDIENTS_TO_TEST2, ids=lambda d: d["name"])
def ingredient_setup(request, auth_token):
    """ crée un ingrédient """
    headers = {"Authorization": f"Bearer {auth_token}"}
    ingredient_data = request.param

    with httpx.Client() as client:
        response = client.post(f"{SERVICE_RECIPE_URL}/api/v1/ingredient/", json=ingredient_data, headers=headers)
        assert response.status_code == 201, f"Erreur creation: {response.text}" 
        ingredient_id = response.json()['id']
        
        yield {"id": ingredient_id, "data": ingredient_data}
        # --- TEARDOWN : Nettoyage automatique ---
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
            resp = client.delete(f"{SERVICE_RECIPE_URL}/api/v1/ingredient/{ing_id}", headers=headers)
            # print(f"\n[TEARDOWN ingredient] DELETE ingredient {ing_id}: {resp.status_code} {resp.text}")

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
        resp = client.delete(f"{SERVICE_RECIPE_URL}/api/v1/recipe/id/{recipe_id}", headers=headers)
        # print(f"\n[TEARDOWN recipe] DELETE recipe {recipe_id}: {resp.status_code} {resp.text}")


def test_create_recipe(recipe_setup):
    assert recipe_setup is not None


def _build_four_recipes(ids):
    # ids: [pâtes, tomates, ail, huile d'olive, sel, poivre, basilic, parmesan, oignon]
    #       [  0       1      2         3          4     5       6         7       8   ]
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

