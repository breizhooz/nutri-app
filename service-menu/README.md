# service-menu

Service de planification des menus hebdomadaires et de génération de listes de courses.

- **Port local** : `8003`
- **Domaine Traefik** : `http://api-menu.localhost`
- **Swagger** : `http://api-menu.localhost/docs`
- **Base de données** : PostgreSQL sur `localhost:5435`
- **Dépend de** : `service-user` (JWT), `service-recipe` (données recettes)

---

## Routes

```
GET     /health
GET     /health/db
POST    /api/v1/menus                           Créer un menu hebdomadaire
POST    /api/v1/menus/add-menu-item             Ajouter une recette au menu
GET     /api/v1/menus                           Lister les menus
GET     /api/v1/menus/{menu_id}                 Menu par ID
PUT     /api/v1/menus/{menu_id}                 Mettre à jour un menu
DELETE  /api/v1/menus/{menu_id}                 Supprimer un menu
GET     /api/v1/menus/{menu_id}/shopping-list   Générer la liste de courses
GET     /api/v1/menus/{menu_id}/shopping-list/export  Exporter la liste de courses
```

---

## Migrations Alembic

```bash
# Créer une migration
docker compose exec service-menu alembic revision --autogenerate -m "description"

# Appliquer
docker compose exec service-menu alembic upgrade head

# Rollback
docker compose exec service-menu alembic downgrade -1

# État actuel
docker compose exec service-menu alembic current

# Historique
docker compose exec service-menu alembic history --verbose
```

> Les migrations s'appliquent automatiquement au démarrage du conteneur.

---

## Tests

```bash
# Tests unitaires
docker compose exec service-menu pytest --cov=app -m "not smoke" -v

# Tests smoke (stack complète requise)
docker compose exec service-menu pytest tests/smoke_test.py -m smoke -v
```

---

## Requêtes SQL directes

```bash
docker compose exec postgres-menu psql -U nutrimenu -d nutriplanner_menu \
  -c "SELECT * FROM menus;"
```

---

## Structure

```
service-menu/
├── app/
│   ├── main.py
│   ├── api/routes/
│   │   └── menus.py        # /menus/*
│   ├── models/
│   ├── schemas/
│   ├── db/
│   └── core/
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

## Variables d'environnement clés

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...@postgres-menu:5432/...` |
| `SERVICE_USER_URL` | `http://service-user:8000` |
| `SERVICE_RECIPE_URL` | `http://service-recipe:8000` |
