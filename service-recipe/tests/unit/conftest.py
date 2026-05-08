import pytest
import json
import tempfile
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.i18n.middleware import LocaleMiddleware

@pytest.fixture
def temp_locale_files():
    """Crée des fichiers de traduction temporaires pour les tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        locale_dir = Path(tmpdir) / "locales"
        locale_dir.mkdir()

        fr_data = {
            "enums": {
                "difficulty": {
                    "easy": "Facile",
                    "medium": "Moyen",
                    "hard": "Difficile"
                },
                "origin": {
                    "web": "Web",
                    "book": "Livre",
                    "tv": "Télévision",
                    "personal": "Personnel"
                }
            },
            "recipe": {
                "fields": {
                    "title": "Titre"
                },
                "errors": {
                    "not_found": "Recette non trouvée",
                    "validation": "Le champ {field} est invalide"
                }
            }
        }

        en_data = {
            "enums": {
                "difficulty": {
                    "easy": "Easy",
                    "medium": "Medium",
                    "hard": "Hard"
                },
                "origin": {
                    "web": "Web",
                    "book": "Book",
                    "tv": "TV",
                    "personal": "Personal"
                }
            },
            "recipe": {
                "fields": {
                    "title": "Title"
                },
                "errors": {
                    "not_found": "Recipe not found",
                    "validation": "Field {field} is invalid"
                }
            }
        }

        with open(locale_dir / "fr.json", "w", encoding="utf-8") as f:
            json.dump(fr_data, f, indent=2, ensure_ascii=False)

        with open(locale_dir / "en.json", "w", encoding="utf-8") as f:
            json.dump(en_data, f, indent=2, ensure_ascii=False)

        yield locale_dir
# <--- Vérifiez bien que le bloc suivant n'est pas indenté !

@pytest.fixture
def app_with_middleware():
    """Crée une app FastAPI avec le middleware locale pour les tests"""
    # Note : l'import est à l'intérieur pour éviter des soucis de circularité
    app = FastAPI()
    app.add_middleware(LocaleMiddleware)

    @app.get("/test")
    async def test_endpoint(request: Request): # Ajout du type Request ici
        # On utilise getattr au cas où le middleware n'aurait pas setté la valeur
        return {"locale": getattr(request.state, "locale", "unknown")}

    return app