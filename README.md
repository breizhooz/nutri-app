# NutriPlanner — Architecture Microservices

Application de planification nutritionnelle et de gestion de recettes, construite sur une architecture microservices Python/FastAPI.

---

## Architecture

```
                         ┌─────────────────┐
                         │     Traefik      │  :80
                         │  Reverse Proxy   │
                         └────────┬────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
   ┌──────▼──────┐        ┌──────▼──────┐        ┌──────▼──────┐
   │ service-user│        │service-recipe│        │ service-menu│
   │   :8001     │        │    :8002     │        │    :8003    │
   └──────┬──────┘        └──────┬──────┘        └──────┬──────┘
          │                      │                       │
   ┌──────▼──────┐        ┌──────▼──────┐        ┌──────▼──────┐
   │  postgres   │        │  postgres   │        │  postgres   │
   │  user :5433 │        │ recipe:5434 │        │ menu  :5435 │
   └─────────────┘        └─────────────┘        └─────────────┘

   ┌──────────────┐   ┌────────────────┐   ┌─────────────────┐
   │service-nutri-│   │service-crawler │   │service-notifica-│
   │tion :8005    │   │    :8004       │   │tion     :8006   │
   └──────┬───────┘   └──────┬─────────┘   └─────────────────┘
          │                  │
   ┌──────▼────────────────┐ │ ┌──────────────────┐
   │  Celery + Redis       │ │ │  Celery Beat     │
   │  (async tasks)        │ │ │  (scheduled jobs)│
   └───────────────────────┘ │ └──────────────────┘
                             │
                      ┌──────▼──────┐
                      │    MinIO    │  S3-compatible
                      │  :9000/9001 │
                      └─────────────┘

   ┌──────────────────────────────────────────────────┐
   │  Monitoring Stack  (profile: monitoring)          │
   │  Prometheus :9090  •  Grafana :3000              │
   │  7x postgres-exporter  •  redis-exporter          │
   │  elasticsearch-exporter                           │
   └──────────────────────────────────────────────────┘
```

---

## Services

| Service | Port local | Domaine Traefik | Rôle |
|---------|-----------|-----------------|------|
| service-user | 8001 | `api-users.localhost` | Authentification JWT, gestion des utilisateurs |
| service-recipe | 8002 | `api-recipe.localhost` | Gestion des recettes, recherche Elasticsearch |
| service-menu | 8003 | `api-menu.localhost` | Planification de menus hebdomadaires |
| service-crawler | 8004 | `api-crawler.localhost` | Crawling web, import de recettes |
| service-nutrition | 8005 | `api-nutrition.localhost` | Calcul nutritionnel, base Ciqual |
| service-notification | 8006 | `api-notification.localhost` | Notifications push (VAPID) |
| service-profile | 8007 | `api-profile.localhost` | Profil utilisateur, composition corporelle |

---

## URLs d'accès

### APIs & Documentation

| URL | Description |
|-----|-------------|
| http://api.localhost | Portail Swagger UI (multi-spec) |
| http://api-users.localhost/docs | OpenAPI service-user |
| http://api-recipe.localhost/docs | OpenAPI service-recipe |
| http://api-menu.localhost/docs | OpenAPI service-menu |
| http://api-crawler.localhost/docs | OpenAPI service-crawler |
| http://api-nutrition.localhost/docs | OpenAPI service-nutrition |
| http://api-notification.localhost/docs | OpenAPI service-notification |
| http://api-profile.localhost/docs | OpenAPI service-profile |

### Infrastructure & Monitoring

| URL | Description | Credentials |
|-----|-------------|-------------|
| http://traefik.localhost | Dashboard Traefik | aucune (insecure mode) |
| http://prometheus.localhost | Interface Prometheus | aucune |
| http://grafana.localhost | Dashboards Grafana | `admin` / `${GRAFANA_ADMIN_PASSWORD}` |
| `localhost:9200` | Elasticsearch (interne) | aucune (xpack désactivé) |
| `localhost:9001` | Console MinIO | `${MINIO_ROOT_USER}` / `${MINIO_ROOT_PASSWORD}` |

---

## Démarrage rapide

### Prérequis

- Docker >= 24
- Docker Compose v2
- Résolution DNS locale pour `*.localhost` (nativement supportée sur la plupart des systèmes)

### Configuration

```bash
cp .env.example .env
# Remplir les variables dans .env
```

### Lancer la stack

```bash
# Services principaux
docker compose up -d

# Avec le monitoring (Prometheus + Grafana)
docker compose --profile monitoring up -d

# Vérifier l'état
docker compose ps
```

### Arrêter

```bash
docker compose down

# Reset complet (supprime les volumes)
docker compose down -v
```

---

## Migrations (Alembic)

Les migrations s'exécutent **automatiquement au démarrage** de chaque conteneur.

### Créer une migration

```bash
docker compose exec service-user alembic revision --autogenerate -m "description"
```

### Appliquer

```bash
docker compose exec service-user alembic upgrade head
```

### Rollback

```bash
docker compose exec service-user alembic downgrade -1
```

### Historique

```bash
docker compose exec service-user alembic history --verbose
docker compose exec service-user alembic current
```

Remplacer `service-user` par : `service-recipe`, `service-menu`, `service-crawler`, `service-notification`, `service-nutrition`, `service-profile`.

---

## Tests

### Tests unitaires (dans Docker)

```bash
docker compose exec service-user pytest --cov=app -m "not smoke" -v
```

### Tests smoke (stack complète requise)

```bash
docker compose exec service-user pytest tests/smoke_test.py -m smoke -v
```

### Tous les services

```bash
for svc in service-user service-recipe service-menu service-crawler service-nutrition service-notification service-profile; do
  echo "=== $svc ==="
  docker compose exec $svc pytest --cov=app -m "not smoke" -q
done
```

---

## Toutes les routes API

### service-user — `api-users.localhost`

```
GET     /health
GET     /health/db
POST    /api/v1/auth/login
POST    /api/v1/auth/refresh
POST    /api/v1/users
GET     /api/v1/users
GET     /api/v1/users/me
GET     /api/v1/users/{user_id}
GET     /api/v1/users/{user_id}/exists
DELETE  /api/v1/users/{user_id}
```

### service-recipe — `api-recipe.localhost`

```
GET     /health
GET     /health/db
GET     /api/v1/search/recipes
POST    /api/v1/recipe
PUT     /api/v1/recipe/id/{recipe_id}
GET     /api/v1/recipe/{slug}
GET     /api/v1/recipe/id/{id}
DELETE  /api/v1/recipe/id/{recipe_id}
POST    /api/v1/ingredient
GET     /api/v1/ingredient
GET     /api/v1/ingredient/{ingredient_id}
PATCH   /api/v1/ingredient/{ingredient_id}
DELETE  /api/v1/ingredient/{ingredient_id}
```

### service-menu — `api-menu.localhost`

```
GET     /health
GET     /health/db
POST    /api/v1/menus
POST    /api/v1/menus/add-menu-item
GET     /api/v1/menus
GET     /api/v1/menus/{menu_id}
PUT     /api/v1/menus/{menu_id}
DELETE  /api/v1/menus/{menu_id}
GET     /api/v1/menus/{menu_id}/shopping-list
GET     /api/v1/menus/{menu_id}/shopping-list/export
```

### service-crawler — `api-crawler.localhost`

```
GET     /health
GET     /health/db
POST    /api/v1/crawler/sources
GET     /api/v1/crawler/sources
GET     /api/v1/crawler/sources/{source_id}
PATCH   /api/v1/crawler/sources/{source_id}
DELETE  /api/v1/crawler/sources/{source_id}
POST    /api/v1/crawler/sources/{source_id}/crawl
GET     /api/v1/crawler/results
GET     /api/v1/crawler/results/{result_id}
PATCH   /api/v1/crawler/results/{result_id}
PATCH   /api/v1/crawler/results/{result_id}/validate
PATCH   /api/v1/crawler/results/{result_id}/reject
GET     /api/v1/crawler/settings
PATCH   /api/v1/crawler/settings
```

### service-nutrition — `api-nutrition.localhost`

```
GET     /health
GET     /health/db
GET     /api/v1/nutrition-items
GET     /api/v1/nutrition-items/search
GET     /api/v1/nutrition-items/{item_id}
POST    /api/v1/calculate
PATCH   /api/v1/calculate/adjust
POST    /api/v1/macro-errors
GET     /api/v1/stats/user
GET     /api/v1/admin/import-ciqual
```

### service-notification — `api-notification.localhost`

```
GET     /health
GET     /health/db
POST    /api/v1/subscriptions
GET     /api/v1/subscriptions/{slug}
DELETE  /api/v1/subscriptions/{slug}
POST    /api/v1/notify
GET     /api/v1/users/{user_slug}/history
```

### service-profile — `api-profile.localhost`

```
GET     /health
GET     /health/db
POST    /api/v1/profiles
GET     /api/v1/profiles/me
PATCH   /api/v1/profiles/me
GET     /api/v1/profiles/me/calculate
GET     /api/v1/profiles/{slug}
POST    /api/v1/profiles/me/composition
GET     /api/v1/profiles/me/composition
DELETE  /api/v1/profiles/me/composition/{slug}
POST    /api/v1/profiles/me/measurements
GET     /api/v1/profiles/me/measurements
DELETE  /api/v1/profiles/me/measurements/{slug}
POST    /api/v1/profiles/me/injuries
GET     /api/v1/profiles/me/injuries
DELETE  /api/v1/profiles/me/injuries/{slug}
POST    /api/v1/profiles/me/conditions
DELETE  /api/v1/profiles/me/conditions/{slug}
POST    /api/v1/profiles/me/allergies
GET     /api/v1/profiles/me/allergies
DELETE  /api/v1/profiles/me/allergies/{slug}
POST    /api/v1/profiles/me/preferences
```

---

## Requêtes SQL directes dans les conteneurs

```bash
# Utilisateurs
docker compose exec postgres-user psql -U nutriuser -d nutriplanner_user \
  -c "SELECT email, hashed_password FROM users;"

# Recettes
docker compose exec postgres-recipe psql -U nutrirecipe -d nutriplanner_recipe \
  -c "SELECT * FROM recipes;"
```

---

## Stack technique

| Composant | Technologie |
|-----------|------------|
| Language | Python 3.12 |
| Framework API | FastAPI + Uvicorn |
| ORM | SQLAlchemy (asyncio) |
| Bases de données | PostgreSQL 16 (7 instances isolées) |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Recherche | Elasticsearch 8.11 |
| Cache / Queue | Redis 7 |
| Tâches async | Celery |
| Stockage objet | MinIO |
| Reverse proxy | Traefik v3.7 |
| Monitoring | Prometheus + Grafana |
| Logs | structlog → Filebeat → Elasticsearch |
| Tests | pytest + pytest-cov |
| Lint | Ruff |
| Sécurité | Bandit |
| CI/CD | GitHub Actions |

---

## Structure du projet

```
nutri-app/
├── service-user/           # Auth & utilisateurs
├── service-recipe/         # Recettes & ingrédients
├── service-menu/           # Menus hebdomadaires
├── service-crawler/        # Crawling web
├── service-nutrition/      # Calcul nutritionnel
├── service-notification/   # Notifications push
├── service-profile/        # Profils utilisateurs
├── shared/                 # Bibliothèque partagée (nutri_shared)
├── traefik/                # Config Traefik + middlewares
├── monitoring/             # Prometheus + Grafana
├── portal/                 # Portail Swagger UI (nginx)
├── docker-compose.yml
├── .env.example
└── filebeat.yml
```

Chaque service suit la même structure interne :

```
service-{name}/
├── app/
│   ├── main.py             # Point d'entrée FastAPI
│   ├── api/routes/         # Routeurs FastAPI
│   ├── models/             # Modèles SQLAlchemy
│   ├── schemas/            # Schémas Pydantic
│   ├── db/                 # Session DB
│   └── core/               # Config, auth, elasticsearch
├── alembic/                # Migrations Alembic
│   └── versions/
├── tests/
│   ├── conftest.py
│   ├── smoke_test.py
│   ├── unit/
│   └── integration/
├── Dockerfile
├── requirements.txt
├── pyproject.toml
└── pytest.ini
```
