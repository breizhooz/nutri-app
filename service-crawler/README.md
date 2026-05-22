# service-crawler

Service de crawling web pour l'import automatique de recettes. Tâches planifiées via Celery Beat.

- **Port local** : `8004`
- **Domaine Traefik** : `http://api-crawler.localhost`
- **Swagger** : `http://api-crawler.localhost/docs`
- **Base de données** : PostgreSQL sur `localhost:5436`
- **Dépend de** : `redis` (broker Celery), `minio` (stockage médias)

---

## Routes

```
GET     /health
GET     /health/db
POST    /api/v1/crawler/sources                 Créer une source (site à crawler)
GET     /api/v1/crawler/sources                 Lister les sources
GET     /api/v1/crawler/sources/{source_id}     Source par ID
PATCH   /api/v1/crawler/sources/{source_id}     Modifier source
DELETE  /api/v1/crawler/sources/{source_id}     Supprimer source
POST    /api/v1/crawler/sources/{source_id}/crawl  Déclencher crawl manuellement (202 Accepted)
GET     /api/v1/crawler/results                 Résultats paginés
GET     /api/v1/crawler/results/{result_id}     Résultat par ID
PATCH   /api/v1/crawler/results/{result_id}     Modifier résultat
PATCH   /api/v1/crawler/results/{result_id}/validate  Valider (approuver) un résultat
PATCH   /api/v1/crawler/results/{result_id}/reject    Rejeter un résultat
GET     /api/v1/crawler/settings                Configuration du crawler
PATCH   /api/v1/crawler/settings                Modifier la configuration
```

---

## Migrations Alembic

```bash
# Créer une migration
docker compose exec service-crawler alembic revision --autogenerate -m "description"

# Appliquer
docker compose exec service-crawler alembic upgrade head

# Rollback
docker compose exec service-crawler alembic downgrade -1

# État actuel
docker compose exec service-crawler alembic current

# Historique
docker compose exec service-crawler alembic history --verbose
```

> Les migrations s'appliquent automatiquement au démarrage du conteneur.

---

## Celery (tâches planifiées)

Le service pilote **celery-beat** pour les crawls périodiques.

```bash
# Logs du scheduler
docker compose logs -f celery-beat

# Relancer le beat scheduler
docker compose restart celery-beat
```

---

## Tests

```bash
# Tests unitaires
docker compose exec service-crawler pytest --cov=app -m "not smoke" -v

# Tests smoke (stack complète requise)
docker compose exec service-crawler pytest tests/smoke_test.py -m smoke -v
```

---

## Requêtes SQL directes

```bash
docker compose exec postgres-crawler psql -U nutricrawler -d nutriplanner_crawler \
  -c "SELECT * FROM crawler_sources;"

docker compose exec postgres-crawler psql -U nutricrawler -d nutriplanner_crawler \
  -c "SELECT id, status, url FROM crawler_results LIMIT 20;"
```

---

## Structure

```
service-crawler/
├── app/
│   ├── main.py
│   ├── api/routes/
│   │   ├── sources.py      # /crawler/sources/*
│   │   ├── results.py      # /crawler/results/*
│   │   └── settings.py     # /crawler/settings
│   ├── models/
│   ├── schemas/
│   ├── db/
│   ├── tasks/              # Tâches Celery
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
| `DATABASE_URL` | `postgresql+asyncpg://...@postgres-crawler:5432/...` |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/1` |
| `MINIO_ENDPOINT` | `minio:9000` |
| `MINIO_ROOT_USER` | Credentials MinIO |
| `MINIO_ROOT_PASSWORD` | Credentials MinIO |
