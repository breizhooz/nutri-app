import pytest
from fastapi.testclient import TestClient

class TestLocaleMiddleware:
    """Tests pour le middleware de détection de locale"""

    def test_default_locale_is_french(self, app_with_middleware):
        """Sans header Accept-Language, la locale par défaut est 'fr'"""
        client = TestClient(app_with_middleware)
        response = client.get("/test")

        assert response.status_code == 200
        assert response.json()["locale"] == "fr"

    def test_accept_language_french(self, app_with_middleware):
        """Header Accept-Language: fr détecté correctement"""
        client = TestClient(app_with_middleware)
        response = client.get("/test", headers={"Accept-Language": "fr"})

        assert response.status_code == 200
        assert response.json()["locale"] == "fr"

    def test_accept_language_english(self, app_with_middleware):
        """Header Accept-Language: en détecté correctement"""
        client = TestClient(app_with_middleware)
        response = client.get("/test", headers={"Accept-Language": "en"})

        assert response.status_code == 200
        assert response.json()["locale"] == "en"

    def test_accept_language_spanish(self, app_with_middleware):
        """Header Accept-Language: es détecté correctement"""
        client = TestClient(app_with_middleware)
        response = client.get("/test", headers={"Accept-Language": "es"})

        assert response.status_code == 200
        assert response.json()["locale"] == "es"

    def test_accept_language_with_quality(self, app_with_middleware):
        """
        Header avec qualité : Accept-Language: en-US,en;q=0.9,fr;q=0.8
        Prend le premier code (en)
        """
        client = TestClient(app_with_middleware)
        response = client.get(
            "/test",
            headers={"Accept-Language": "en-US,en;q=0.9,fr;q=0.8"}
        )

        assert response.status_code == 200
        assert response.json()["locale"] == "en"

    def test_accept_language_unsupported_fallback_to_french(self, app_with_middleware):
        """Langue non supportée (de, it...) → fallback sur 'fr'"""
        client = TestClient(app_with_middleware)
        response = client.get("/test", headers={"Accept-Language": "de"})

        assert response.status_code == 200
        assert response.json()["locale"] == "fr"

    def test_accept_language_case_insensitive(self, app_with_middleware):
        """La détection est insensible à la casse (FR, En, ES)"""
        client = TestClient(app_with_middleware)

        # Test FR (majuscules)
        response = client.get("/test", headers={"Accept-Language": "FR"})
        assert response.json()["locale"] == "fr"

        # Test En (mixte)
        response = client.get("/test", headers={"Accept-Language": "En"})
        assert response.json()["locale"] == "en"

    def test_accept_language_with_country_code(self, app_with_middleware):
        """
        Accept-Language: fr-FR, en-GB, es-ES
        Extrait uniquement le code langue (2 premiers caractères)
        """
        client = TestClient(app_with_middleware)

        response = client.get("/test", headers={"Accept-Language": "fr-FR"})
        assert response.json()["locale"] == "fr"

        response = client.get("/test", headers={"Accept-Language": "en-GB"})
        assert response.json()["locale"] == "en"

        response = client.get("/test", headers={"Accept-Language": "es-MX"})
        assert response.json()["locale"] == "es"

    def test_multiple_requests_independent_locale(self, app_with_middleware):
        """Chaque requête a sa propre locale (pas de contamination)"""
        client = TestClient(app_with_middleware)

        response1 = client.get("/test", headers={"Accept-Language": "fr"})
        response2 = client.get("/test", headers={"Accept-Language": "en"})
        response3 = client.get("/test", headers={"Accept-Language": "es"})

        assert response1.json()["locale"] == "fr"
        assert response2.json()["locale"] == "en"
        assert response3.json()["locale"] == "es"