# service-nutrition

Service de calcul nutritionnel basé sur la base de données Ciqual (ANSES). Traitement asynchrone via Celery.

- **Port local** : `8005`
- **Domaine Traefik** : `http://api-nutrition.localhost`
- **Swagger** : `http://api-nutrition.localhost/docs`
- **Base de données** : PostgreSQL sur `localhost:5438`
- **Dépend de** : `redis`, `service-notification`

---

## Routes

```
GET     /health
GET     /health/db
GET     /api/v1/nutrition-items?q=…             Rapprochement approximatif d'un ingrédient (pg_trgm)
GET     /api/v1/nutrition-items/search          Rechercher un aliment
GET     /api/v1/nutrition-items/{item_id}       Détail nutritionnel d'un aliment
POST    /api/v1/calculate                       Calculer macros & micros pour une recette
PATCH   /api/v1/calculate/adjust                Ajuster un calcul existant
POST    /api/v1/macro-errors                    Signaler une erreur de calcul
GET     /api/v1/stats/user                      Statistiques nutritionnelles utilisateur
GET     /api/v1/admin/import-ciqual             Admin: déclencher l'import de l'archive Ciqual (tâche Celery)
```

---

## Rapprochement ingrédient → Ciqual

`LookupService` (utilisé par `/calculate`) cherche dans `nutrition_items` en PostgreSQL
(`pg_trgm` + `unaccent`, plus d'Elasticsearch) :

- score = `word_similarity(requête, nom_fr)` + bonus si un mot de la requête est la **tête** du nom Ciqual
  (« tomates » → « Tomate, crue » plutôt que « Caviar de tomates ») ; à score égal, le nom le plus court gagne ;
- candidat accepté seulement si la similarité est ≥ 0,8 **ou** si la tête correspond : mieux vaut une
  MacroError visible qu'un faux ami (« crème fraîche » ↛ « Criste marine, fraîche ») ;
- `nom_en` sert de repli (pondéré 0,8).

Mesuré sur la base réelle (37 ingrédients courants) : 36/37 corrects, contre 24/36 avec la similarité seule.

---

## Migrations Alembic

```bash
# Créer une migration
docker compose exec service-nutrition alembic revision --autogenerate -m "description"

# Appliquer
docker compose exec service-nutrition alembic upgrade head

# Rollback
docker compose exec service-nutrition alembic downgrade -1

# État actuel
docker compose exec service-nutrition alembic current

# Historique
docker compose exec service-nutrition alembic history --verbose
```

> Les migrations s'appliquent automatiquement au démarrage du conteneur.

---

## Celery (tâches asynchrones)

Ce service pilote deux workers Celery :

- **celery-beat-nutrition** : planificateur de tâches périodiques
- **celery-worker-nutrition** : exécuteur des tâches (queue `celery`)

```bash
# Voir les logs du worker
docker compose logs -f celery-worker-nutrition

# Voir les logs du beat scheduler
docker compose logs -f celery-beat-nutrition

# Relancer le worker manuellement
docker compose restart celery-worker-nutrition
```

---

## Tests

```bash
# Tests unitaires
docker compose exec service-nutrition pytest --cov=app -m "not smoke" -v

# Tests smoke (stack complète requise)
docker compose exec service-nutrition pytest tests/smoke_test.py -m smoke -v
```

---

## Requêtes SQL directes

```bash
docker compose exec postgres-nutrition psql -U nutrinutrition -d nutriplanner_nutrition \
  -c "SELECT * FROM nutrition_items LIMIT 10;"
```

---

## Structure

```
service-nutrition/
├── app/
│   ├── main.py
│   ├── api/routes/
│   │   ├── nutrition_items.py  # /nutrition-items/*
│   │   ├── calculate.py        # /calculate/*
│   │   ├── stats.py            # /stats/*
│   │   └── admin.py            # /admin/*
│   ├── models/
│   ├── schemas/
│   ├── db/
│   ├── tasks/                  # Tâches Celery
│   └── core/
├── alembic/
│   └── versions/
├── tests/
├── Dockerfile
├── requirements.txt
└── pytest.ini
```

---

## Variables d'environnement clés

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...@postgres-nutrition:5432/...` |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/1` |
| `SERVICE_NOTIFICATION_URL` | `http://service-notification:8000` |
