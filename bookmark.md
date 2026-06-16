# Bookmark — Rost.r

Aide-mémoire opérationnel : migrations, tests, routes.

---

## Migrations Alembic

### Workflow standard

```
1. Modifier le modèle SQLAlchemy dans app/models/
2. Générer la migration (autogenerate)
3. Vérifier le fichier généré dans alembic/versions/
4. Appliquer la migration
```

### Créer une migration (autogenerate depuis les modèles)

```bash
docker compose exec service-user        alembic revision --autogenerate -m "description"
docker compose exec service-recipe      alembic revision --autogenerate -m "description"
docker compose exec service-menu        alembic revision --autogenerate -m "description"
docker compose exec service-crawler     alembic revision --autogenerate -m "description"
docker compose exec service-nutrition   alembic revision --autogenerate -m "description"
docker compose exec service-notification alembic revision --autogenerate -m "description"
docker compose exec service-profile     alembic revision --autogenerate -m "description"
```

### Appliquer toutes les migrations en attente

```bash
docker compose exec service-user        alembic upgrade head
docker compose exec service-recipe      alembic upgrade head
docker compose exec service-menu        alembic upgrade head
docker compose exec service-crawler     alembic upgrade head
docker compose exec service-nutrition   alembic upgrade head
docker compose exec service-notification alembic upgrade head
docker compose exec service-profile     alembic upgrade head
```

> Les migrations s'appliquent aussi **automatiquement au démarrage du conteneur** via le CMD du Dockerfile :
> `alembic upgrade head && uvicorn app.main:app ...`

### Rollback

```bash
# Revenir d'une migration
docker compose exec service-user alembic downgrade -1

# Revenir à une révision précise
docker compose exec service-user alembic downgrade <revision_id>
```

### Diagnostiquer l'état des migrations

```bash
# Révision courante appliquée en base
docker compose exec service-user alembic current

# Historique complet
docker compose exec service-user alembic history --verbose

# Différence entre modèles et DB (dry-run)
docker compose exec service-user alembic check
```

### Migration vide (manuelle)

```bash
docker compose exec service-user alembic revision -m "description_manuelle"
```

---

## Tests unitaires (dans Docker)

### Lancer les tests d'un service

```bash
# Tests unitaires uniquement (exclut les smoke tests)
docker compose exec service-user pytest --cov=app --cov-report=xml:coverage.xml -m "not smoke" -v

# Sans couverture, plus rapide
docker compose exec service-user pytest -m "not smoke" -v

# Un fichier précis
docker compose exec service-user pytest tests/unit/test_routes_auth.py -v

# Une classe ou fonction précise
docker compose exec service-user pytest tests/unit/test_routes_auth.py::TestLogin::test_valid_credentials -v
```

### Lancer les tests de tous les services

```bash
for svc in service-user service-recipe service-menu service-crawler service-nutrition service-notification service-profile; do
  echo "====== $svc ======"
  docker compose exec $svc pytest --cov=app -m "not smoke" -q
done
```

### Avec docker compose run (sans conteneur déjà démarré)

```bash
docker compose run --rm service-recipe pytest tests/ -v
```

---

## Tests smoke (intégration — stack complète requise)

Les smoke tests vérifient que les services communiquent bien entre eux sur la stack Docker complète.

### Prérequis

```bash
docker compose up -d
# Attendre que tous les services soient healthy
docker compose ps
```

### Lancer les smoke tests

```bash
# Via exec (conteneur déjà démarré)
docker compose exec service-user pytest tests/smoke_test.py -m smoke -v

# Via run (sans conteneur préexistant, depuis l'hôte)
pytest service-user/tests/smoke_test.py --noconftest -m smoke -v
pytest service-recipe/tests/smoke_test.py --noconftest -m smoke -v
pytest service-menu/tests/smoke_test.py --noconftest -m smoke -v
pytest service-crawler/tests/smoke_test.py --noconftest -m smoke -v
pytest service-nutrition/tests/smoke_test.py --noconftest -m smoke -v
pytest service-notification/tests/smoke_test.py --noconftest -m smoke -v
pytest service-profile/tests/smoke_test.py --noconftest -m smoke -v
```

### Tous les smoke tests (comme en CI)

```bash
for svc in service-user service-recipe service-menu service-crawler service-nutrition service-notification service-profile; do
  echo "====== smoke: $svc ======"
  docker compose exec $svc pytest tests/smoke_test.py -m smoke -v
done
```

---

## Requêtes SQL directes

```bash
# Utilisateurs
docker compose exec postgres-user psql -U nutriuser -d nutriplanner_user \
  -c "SELECT email, hashed_password FROM users;"

# Recettes
docker compose exec postgres-recipe psql -U nutrirecipe -d nutriplanner_recipe \
  -c "SELECT * FROM recipes;"

# Menus
docker compose exec postgres-menu psql -U nutrimenu -d nutriplanner_menu \
  -c "SELECT * FROM menus;"
```

---

## Toutes les routes API

### service-user — `http://api-users.localhost`

```
GET     /health
GET     /health/db
POST    /api/v1/auth/login            Connexion, retourne JWT
POST    /api/v1/auth/refresh          Rafraîchit le token JWT
POST    /api/v1/users                 Créer un utilisateur
GET     /api/v1/users                 Lister les utilisateurs
GET     /api/v1/users/me             Utilisateur courant
GET     /api/v1/users/{user_id}       Utilisateur par ID
GET     /api/v1/users/{user_id}/exists  Vérifier existence
DELETE  /api/v1/users/{user_id}       Supprimer utilisateur
```

### service-recipe — `http://api-recipe.localhost`

```
GET     /health
GET     /health/db
GET     /api/v1/search/recipes                 Recherche Elasticsearch
POST    /api/v1/recipe                          Créer une recette
PUT     /api/v1/recipe/id/{recipe_id}           Mettre à jour recette
GET     /api/v1/recipe/{slug}                   Recette par slug
GET     /api/v1/recipe/id/{id}                  Recette par ID
DELETE  /api/v1/recipe/id/{recipe_id}           Supprimer recette
POST    /api/v1/ingredient                      Créer ingrédient
GET     /api/v1/ingredient                      Lister ingrédients
GET     /api/v1/ingredient/{ingredient_id}      Ingrédient par ID
PATCH   /api/v1/ingredient/{ingredient_id}      Modifier ingrédient
DELETE  /api/v1/ingredient/{ingredient_id}      Supprimer ingrédient
```

### service-menu — `http://api-menu.localhost`

```
GET     /health
GET     /health/db
POST    /api/v1/menus                           Créer un menu hebdomadaire
POST    /api/v1/menus/add-menu-item             Ajouter un item au menu
GET     /api/v1/menus                           Lister les menus
GET     /api/v1/menus/{menu_id}                 Menu par ID
PUT     /api/v1/menus/{menu_id}                 Mettre à jour menu
DELETE  /api/v1/menus/{menu_id}                 Supprimer menu
GET     /api/v1/menus/{menu_id}/shopping-list   Générer liste de courses
GET     /api/v1/menus/{menu_id}/shopping-list/export  Exporter liste
```

### service-crawler — `http://api-crawler.localhost`

```
GET     /health
GET     /health/db
POST    /api/v1/crawler/sources                 Créer une source à crawler
GET     /api/v1/crawler/sources                 Lister les sources
GET     /api/v1/crawler/sources/{source_id}     Source par ID
PATCH   /api/v1/crawler/sources/{source_id}     Modifier source
DELETE  /api/v1/crawler/sources/{source_id}     Supprimer source
POST    /api/v1/crawler/sources/{source_id}/crawl  Déclencher crawl (202)
GET     /api/v1/crawler/results                 Résultats paginés
GET     /api/v1/crawler/results/{result_id}     Résultat par ID
PATCH   /api/v1/crawler/results/{result_id}     Modifier résultat
PATCH   /api/v1/crawler/results/{result_id}/validate  Valider résultat
PATCH   /api/v1/crawler/results/{result_id}/reject    Rejeter résultat
GET     /api/v1/crawler/settings                Config du crawler
PATCH   /api/v1/crawler/settings                Modifier config
```

### service-nutrition — `http://api-nutrition.localhost`

```
GET     /health
GET     /health/db
GET     /api/v1/nutrition-items                 Parcourir base Ciqual
GET     /api/v1/nutrition-items/search          Rechercher aliment
GET     /api/v1/nutrition-items/{item_id}       Détail d'un aliment
POST    /api/v1/calculate                       Calculer macros/micros
PATCH   /api/v1/calculate/adjust                Ajuster le calcul
POST    /api/v1/macro-errors                    Signaler erreur macro
GET     /api/v1/stats/user                      Stats nutritionnelles utilisateur
GET     /api/v1/admin/import-ciqual             Admin: importer archive Ciqual (task)
```

### service-notification — `http://api-notification.localhost`

```
GET     /health
GET     /health/db
POST    /api/v1/subscriptions                   S'abonner aux notifications
GET     /api/v1/subscriptions/{slug}            Abonnement par slug
DELETE  /api/v1/subscriptions/{slug}            Se désabonner
POST    /api/v1/notify                          Envoyer notification
GET     /api/v1/users/{user_slug}/history       Historique notifications
```

### service-profile — `http://api-profile.localhost`

```
GET     /health
GET     /health/db
POST    /api/v1/profiles                        Créer profil
GET     /api/v1/profiles/me                     Profil courant
PATCH   /api/v1/profiles/me                     Modifier profil
GET     /api/v1/profiles/me/calculate           Calculs dérivés (IMC, etc.)
GET     /api/v1/profiles/{slug}                 Profil par slug
POST    /api/v1/profiles/me/composition         Ajouter mesure corporelle
GET     /api/v1/profiles/me/composition         Historique composition
DELETE  /api/v1/profiles/me/composition/{slug}  Supprimer entrée
POST    /api/v1/profiles/me/measurements        Ajouter mesures
GET     /api/v1/profiles/me/measurements        Historique mesures
DELETE  /api/v1/profiles/me/measurements/{slug} Supprimer mesure
POST    /api/v1/profiles/me/injuries            Ajouter blessure
GET     /api/v1/profiles/me/injuries            Historique blessures
DELETE  /api/v1/profiles/me/injuries/{slug}     Supprimer blessure
POST    /api/v1/profiles/me/conditions          Ajouter condition santé
DELETE  /api/v1/profiles/me/conditions/{slug}   Supprimer condition
POST    /api/v1/profiles/me/allergies           Ajouter allergie
GET     /api/v1/profiles/me/allergies           Lister allergies
DELETE  /api/v1/profiles/me/allergies/{slug}    Supprimer allergie
POST    /api/v1/profiles/me/preferences         Définir préférences alimentaires
```

---

## URLs infrastructure

| URL | Description | Auth |
|-----|-------------|------|
| http://traefik.localhost | Dashboard Traefik (routes, middlewares, upstreams) | aucune |
| http://prometheus.localhost | Prometheus (métriques, requêtes PromQL) | aucune |
| http://grafana.localhost | Grafana (dashboards) | `admin` / `${GRAFANA_ADMIN_PASSWORD}` |
| http://api.localhost | Portail Swagger UI multi-spec | aucune |

> Le monitoring nécessite `docker compose --profile monitoring up -d`

### Ports directs (sans Traefik, si besoin)

| Service | Port hôte |
|---------|-----------|
| service-user | `localhost:8001` |
| service-recipe | `localhost:8002` |
| service-menu | `localhost:8003` |
| service-crawler | `localhost:8004` |
| service-nutrition | `localhost:8005` |
| service-notification | `localhost:8006` |
| service-profile | `localhost:8007` |
| Elasticsearch | `localhost:9200` |
| Redis | `localhost:6379` |
| MinIO API | `localhost:9000` |
| MinIO Console | `localhost:9001` |
| Prometheus | `localhost:9090` |
| Grafana | `localhost:3000` |
| postgres-user | `localhost:5433` |
| postgres-recipe | `localhost:5434` |
| postgres-menu | `localhost:5435` |
| postgres-crawler | `localhost:5436` |
| postgres-notification | `localhost:5437` |
| postgres-nutrition | `localhost:5438` |
| postgres-profile | `localhost:5439` |

---

## CI/CD GitHub Actions

Le workflow `.github/workflows/ci.yml` tourne sur push/PR vers `main`.

### Étapes par service (7 jobs parallèles)

1. Checkout + Python 3.12
2. Install shared lib + requirements
3. `ruff check` (lint)
4. `ruff format --check` (format)
5. `bandit` (sécurité)
6. SonarQube
7. `pytest --cov=app -m "not smoke"` (tests unitaires)

### Job smoke tests (après les 7 jobs)

1. Crée `.env` depuis les secrets GitHub
2. `docker compose up -d`
3. Attend que les `/health` répondent 200
4. `pytest tests/smoke_test.py -m smoke -v` sur chaque service
