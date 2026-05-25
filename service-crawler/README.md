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

Le service pilote **celery-beat** pour les crawls périodiques et **celery-worker-crawler** pour l'exécution des tâches.

```bash
# Logs du scheduler
docker compose logs -f celery-beat

# Logs du worker
docker compose logs -f celery-worker-crawler

# Relancer le beat scheduler
docker compose restart celery-beat

# Relancer le worker
docker compose restart celery-worker-crawler
```

---

## Instagram

### Authentification

Instagram bloque les logins programmatiques depuis 2024. L'authentification repose sur un fichier de session généré **une seule fois** depuis un navigateur, stocké dans un volume Docker partagé (`instagram-session:/data`).

**Générer ou renouveler la session :**

1. Se connecter à Instagram dans Firefox ou Chrome avec le compte configuré
2. Ouvrir DevTools → Application (Chrome) ou Stockage (Firefox) → Cookies → `instagram.com`
3. Copier la valeur du cookie `sessionid`
4. Lancer le script depuis le container :

```bash
docker exec -i nutriplanner-service-crawler python3 - << 'EOF'
import instaloader, os, urllib.parse

session_id = urllib.parse.unquote("COLLER_LE_SESSIONID_ICI")
username = "nom_utilisateur_instagram"
session_file = "/data/instagram_session"

loader = instaloader.Instaloader(download_pictures=False, download_videos=False, quiet=True)
loader.context._session.cookies.set("sessionid", session_id, domain=".instagram.com")
loader.context.username = username

check = loader.test_login()
if not check:
    print("Session invalide")
    exit(1)
print(f"Session valide — connecté en tant que : {check}")

os.makedirs("/data", exist_ok=True)
loader.save_session_to_file(session_file)
print(f"Session sauvegardée dans {session_file}")
EOF
```

5. Redémarrer le worker pour prendre en compte la nouvelle session :

```bash
docker compose restart celery-worker-crawler
```

> La session expire si le mot de passe change ou si Instagram la révoque. Régénérer le fichier avec la procédure ci-dessus.

### Rate limiting

Instagram applique un rate limit par IP (`HTTP 429`). En cas de 429 :
- Le worker est libéré immédiatement (pas de blocage)
- Celery replanifie automatiquement le retry **30 minutes** plus tard
- Ne pas déclencher plusieurs crawls du même compte en rafale

### Variables d'environnement

| Variable | Description |
|----------|-------------|
| `INSTAGRAM_USERNAME` | Nom d'utilisateur du compte Instagram |
| `INSTAGRAM_PASSWORD` | Mot de passe (utilisé uniquement si la session expire) |
| `INSTAGRAM_SESSION_FILE` | Chemin du fichier de session (`/data/instagram_session`) |

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
