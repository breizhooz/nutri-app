# service-recipe

Service de gestion des recettes et des ingrédients, avec recherche plein texte PostgreSQL.

- **Port local** : `8002`
- **Domaine Traefik** : `http://api-recipe.localhost`
- **Swagger** : `http://api-recipe.localhost/docs`
- **Base de données** : PostgreSQL sur `localhost:5434`
- **Dépend de** : `service-user` (validation JWT)

---

## Routes

```
GET     /health
GET     /health/db
GET     /api/v1/search/recipes                 Recherche plein texte (PostgreSQL)
POST    /api/v1/recipe                          Créer une recette
PUT     /api/v1/recipe/id/{recipe_id}           Mettre à jour recette par ID
GET     /api/v1/recipe/{slug}                   Recette par slug
GET     /api/v1/recipe/id/{id}                  Recette par ID
DELETE  /api/v1/recipe/id/{recipe_id}           Supprimer recette
POST    /api/v1/ingredient                      Créer un ingrédient
GET     /api/v1/ingredient                      Lister les ingrédients
GET     /api/v1/ingredient/{ingredient_id}      Ingrédient par ID
PATCH   /api/v1/ingredient/{ingredient_id}      Modifier ingrédient
DELETE  /api/v1/ingredient/{ingredient_id}      Supprimer ingrédient
```

---

## Migrations Alembic

```bash
# Créer une migration depuis les modèles
docker compose exec service-recipe alembic revision --autogenerate -m "description"

# Appliquer toutes les migrations
docker compose exec service-recipe alembic upgrade head

# Rollback
docker compose exec service-recipe alembic downgrade -1

# État actuel
docker compose exec service-recipe alembic current

# Historique
docker compose exec service-recipe alembic history --verbose
```

> Les migrations s'appliquent automatiquement au démarrage du conteneur.

---

## Tests

```bash
# Tests unitaires
docker compose exec service-recipe pytest --cov=app -m "not smoke" -v

# Fichiers précis
docker compose exec service-recipe pytest tests/unit/test_routes_recipe.py -v
docker compose exec service-recipe pytest tests/unit/test_schemas_recipe.py -v

# Tests smoke (stack complète requise)
docker compose exec service-recipe pytest tests/smoke_test.py -m smoke -v

# Via run (sans conteneur préexistant)
docker compose run --rm service-recipe pytest tests/ -v
```

---

## Requêtes SQL directes

```bash
docker compose exec postgres-recipe psql -U nutrirecipe -d nutriplanner_recipe \
  -c "SELECT * FROM recipes;"

docker compose exec postgres-recipe psql -U nutrirecipe -d nutriplanner_recipe \
  -c "SELECT * FROM ingredients;"
```

---

## Structure

```
service-recipe/
├── app/
│   ├── main.py
│   ├── api/routes/
│   │   ├── recipe.py       # /recipe/*
│   │   ├── ingredient.py   # /ingredient/*
│   │   └── search.py       # /search/recipes
│   ├── models/
│   ├── schemas/
│   ├── db/
│   └── core/               # Config, clients HTTP inter-services
├── alembic/
│   └── versions/
├── tests/
│   ├── conftest.py
│   ├── smoke_test.py
│   └── unit/
├── Dockerfile
├── requirements.txt
└── pytest.ini
```

---

## Recherche plein texte

`GET /api/v1/search/recipes` interroge PostgreSQL directement (plus d'Elasticsearch) :

- **`recipes.search_vector`** (tsvector `french`, texte désaccentué) pondéré titre > ingrédients >
  description > instructions. Maintenu par **triggers** (création/édition de recette, ajout/retrait
  d'ingrédient, renommage d'ingrédient) : aucune réindexation à lancer, quel que soit le chemin d'écriture.
- **Préfixe** (« poul » trouve « poulet »), tous les mots requis ; **faute de frappe** sur le titre tolérée
  via `pg_trgm` (requêtes de 4 caractères et plus).
- **Allergènes / régimes / tags** lus en direct sur les ingrédients de la recette.
- **Règles nutritionnelles** : service-nutrition renvoie des `search_criteria` neutres (exclusions par tags
  et par noms d'ingrédient en mot entier, cibles de macros) que `RecipeSearchService` traduit en SQL.
- Extensions `unaccent` + `pg_trgm` créées par la migration `e5f6a7b8c9d0` (extensions « trusted » :
  le rôle propriétaire de la base suffit).
- Tests SQL réels : `TEST_POSTGRES_URL=postgresql+asyncpg://… pytest tests/integration/test_search_postgres.py`
  (ignorés sans cette variable).

---

## Variables d'environnement clés

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...@postgres-recipe:5432/...` |
| `SERVICE_USER_URL` | `http://service-user:8000` (validation JWT) |

## Script de lancement pour intégration de 150 recettes de base.

#  Le script tourne dans le conteneur, donc il hérite de sa config :

  ┌─────────────────────────┬────────────────────────────────────┬────────────────────────────────────────────┐
  │        Variable         │ Valeur effective dans le conteneur │                   Source                   │
  ├─────────────────────────┼────────────────────────────────────┼────────────────────────────────────────────┤
  │ DATABASE_URL            │ …@postgres-recipe:5432/…           │ override environment: du compose           │
  ├─────────────────────────┼────────────────────────────────────┼────────────────────────────────────────────┤
  │ SERVICE_NUTRITION_URL   │ http://service-nutrition:8000      │ défaut du script (DNS inter-conteneurs)    │
  ├─────────────────────────┼────────────────────────────────────┼────────────────────────────────────────────┤
  │ SERVICE_NUTRITION_TOKEN │ vide par défaut                    │ à définir si /api/v1/calculate est protégé │
  └─────────────────────────┴────────────────────────────────────┴────────────────────────────────────────────┘

  Si l'endpoint nutrition exige un token, passe-le à la volée :

  docker exec -it \
    -e SERVICE_NUTRITION_TOKEN="<token>" \
    nutriplanner-service-recipe \
    python -m scripts.import_recipes scripts/sample_recipes.json

  Points à noter pour la doc

  - Prérequis : service-nutrition doit tourner (même réseau nutriplanner) pour le calcul des macros ; sinon les
  *_per_serving restent null (le script ne plante pas).
  - Recherche : rien à indexer, le vecteur plein texte est maintenu par des triggers PostgreSQL.
  - Idempotence : un même titre relancé crée une recette avec slug suffixé (-1, -2…). Les ingrédients du catalogue
  sont en upsert (macros mises à jour).
  - Format du fichier : voir scripts/sample_recipes.json (clé racine created_by_user_id, catalogue ingredients avec
   macros, recipes référençant les ingrédients par nom).

# Dans le conteneur service-recipe (pour joindre service-nutrition + la BDD)
  python -m scripts.import_recipes scripts/sample_recipes.json 
