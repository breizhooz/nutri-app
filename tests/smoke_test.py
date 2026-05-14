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
@pytest.fixture(scope="module")
def auth_token():
    """" récupe le token pour le module """
    payload= {"email": "user2@example.com", "password": "VTR4qheb!"}
    with httpx.Client() as client:
        response = client.post(f"{SERVICE_USER_URL}/api/v1/auth/login", json=payload)
        assert response.status_code == 200
        return response.json()['access_token']
        
@pytest.fixture(params=INGREDIENTS_TO_TEST, ids=lambda d: d["name"])
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