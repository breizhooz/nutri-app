# Rost.r — Architecture Microservices

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
## Flows d'authentification

### Login sans 2FA

```
POST /api/v1/auth/login
  └──→ { access_token, refresh_token, token_type }
```

### Login avec 2FA activé

```
POST /api/v1/auth/login
  └──→ { mfa_token, mfa_method }   ← token JWT court (5 min), stateless
             │
             ├── mfa_method = "totp"  → l'utilisateur ouvre son appli authenticator
             └── mfa_method = "email" → un code est envoyé automatiquement par mail

POST /api/v1/auth/2fa/verify  { mfa_token, code }
  └──→ { access_token, refresh_token, token_type }
```

### Activation du TOTP (setup)

```
POST /api/v1/auth/2fa/setup/totp
  └──→ { provisioning_uri }   ← URI otpauth:// à afficher en QR code côté client

POST /api/v1/auth/2fa/confirm/totp  { code }    ← l'utilisateur scanne le QR et saisit le premier code
  └──→ { access_token, refresh_token }           ← 2FA activé
```

### Login OAuth2

```
GET /api/v1/auth/oauth/google/authorize
  └──→ 302 redirect → Google (avec state JWT anti-CSRF)
             │
             │  (l'utilisateur autorise sur Google)
             ↓
GET /api/v1/auth/oauth/google/callback?code=...&state=...
  └──→ { access_token, refresh_token }   ← ou { mfa_token } si 2FA actif sur ce compte
```

**Règle de compte unifié** : si l'email renvoyé par le provider correspond à un compte local existant, les deux sont liés automatiquement. Un compte créé via OAuth peut fonctionner sans mot de passe local.

---

## OAuth2 — Configuration providers

### Google

**Console** : [console.cloud.google.com](https://console.cloud.google.com)

1. Créer ou sélectionner un projet Google Cloud
2. Menu **APIs & Services → Bibliothèque** → activer **"Google People API"**
3. Menu **APIs & Services → Identifiants → Créer des identifiants → ID client OAuth 2.0**
4. Type d'application : **Application Web**
5. **URI de redirection autorisés** — ajouter :

```
# Production
https://api.nutri-app.com/api/v1/auth/oauth/google/callback

# Développement local
http://localhost:8001/api/v1/auth/oauth/google/callback
```

6. Récupérer :
   - **Client ID** → `GOOGLE_CLIENT_ID`
   - **Client Secret** → `GOOGLE_CLIENT_SECRET`

---

### Facebook / Instagram

**Console** : [developers.facebook.com](https://developers.facebook.com)

1. **Mes applications → Créer une application** → type : **Consommateur**
2. Ajouter le produit **Facebook Login**
3. **Paramètres de Facebook Login → URI de redirection OAuth valides** — ajouter :

```
# Production
https://api.nutri-app.com/api/v1/auth/oauth/facebook/callback

# Développement local
http://localhost:8001/api/v1/auth/oauth/facebook/callback
```

4. **Paramètres → Basique** — récupérer :
   - **App ID** → `FACEBOOK_CLIENT_ID`
   - **App Secret** → `FACEBOOK_CLIENT_SECRET`

> Pour **Instagram Login**, ajouter le produit **Instagram** sur la même application Meta. Le `FACEBOOK_CLIENT_ID` et `FACEBOOK_CLIENT_SECRET` sont partagés.

---

## Double facteur (2FA)

### TOTP (Google Authenticator, Authy…)

Le secret TOTP est généré côté serveur, chiffré avec Fernet avant stockage en base, et jamais transmis en clair après l'étape de setup.

Applications compatibles : Google Authenticator, Authy, 1Password, Bitwarden, tout client TOTP RFC 6238.

### Email

Le code à 6 chiffres est généré avec `secrets.randbelow` (cryptographiquement sûr), hashé avec Argon2 avant stockage dans `mfa_pending_codes`, et envoyé via `service-notification`. Il expire après 5 minutes et ne peut être utilisé qu'une seule fois.

---

## Variables d'environnement

### PostgreSQL (une instance par service)

| Variable | Description |
|----------|-------------|
| `POSTGRES_USER_DB` | Nom de la base — service-user |
| `POSTGRES_USER_USER` | Utilisateur PostgreSQL — service-user |
| `POSTGRES_USER_PASSWORD` | Mot de passe — service-user |
| `POSTGRES_RECIPE_DB` | Nom de la base — service-recipe |
| `POSTGRES_RECIPE_USER` | Utilisateur PostgreSQL — service-recipe |
| `POSTGRES_RECIPE_PASSWORD` | Mot de passe — service-recipe |
| `POSTGRES_MENU_DB` | Nom de la base — service-menu |
| `POSTGRES_MENU_USER` | Utilisateur PostgreSQL — service-menu |
| `POSTGRES_MENU_PASSWORD` | Mot de passe — service-menu |
| `POSTGRES_CRAWLER_DB` | Nom de la base — service-crawler |
| `POSTGRES_CRAWLER_USER` | Utilisateur PostgreSQL — service-crawler |
| `POSTGRES_CRAWLER_PASSWORD` | Mot de passe — service-crawler |
| `POSTGRES_NOTIFICATION_DB` | Nom de la base — service-notification |
| `POSTGRES_NOTIFICATION_USER` | Utilisateur PostgreSQL — service-notification |
| `POSTGRES_NOTIFICATION_PASSWORD` | Mot de passe — service-notification |
| `POSTGRES_NUTRITION_DB` | Nom de la base — service-nutrition |
| `POSTGRES_NUTRITION_USER` | Utilisateur PostgreSQL — service-nutrition |
| `POSTGRES_NUTRITION_PASSWORD` | Mot de passe — service-nutrition |
| `POSTGRES_PROFILE_DB` | Nom de la base — service-profile |
| `POSTGRES_PROFILE_USER` | Utilisateur PostgreSQL — service-profile |
| `POSTGRES_PROFILE_PASSWORD` | Mot de passe — service-profile |

### Base

| Variable | Description | Exemple |
|----------|-------------|---------|
| `DATABASE_URL` | Connexion PostgreSQL async | `postgresql+asyncpg://user:pass@postgres-user:5432/user_db` |
| `JWT_SECRET` | Clé de signature JWT — garder secrète | chaîne aléatoire longue |
| `JWT_ACCESS_TOKEN_EXPIRES_MINUTES` | Durée de vie de l'access token | `30` |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Durée de vie du refresh token | `30` |
| `DEBUG` | Mode debug FastAPI | `false` |
| `LOG_LEVEL` | Niveau de log de tous les services (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `DEBUG` en dev, `INFO` en prod |

### OAuth2

| Variable | Description | Où la générer |
|----------|-------------|---------------|
| `GOOGLE_CLIENT_ID` | Client ID OAuth2 Google | Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | Client Secret OAuth2 Google | Google Cloud Console |
| `FACEBOOK_CLIENT_ID` | App ID Meta | Meta for Developers |
| `FACEBOOK_CLIENT_SECRET` | App Secret Meta | Meta for Developers |
| `OAUTH_REDIRECT_BASE_URL` | URL de base de l'API (sans slash final) | `https://api.nutri-app.com` en prod, `http://localhost:8001` en dev |

### 2FA

| Variable | Description | Comment la générer |
|----------|-------------|-------------------|
| `MFA_TOTP_ENCRYPTION_KEY` | Clé Fernet pour chiffrer les secrets TOTP en base | Voir section suivante |
| `MFA_TOKEN_EXPIRE_MINUTES` | Durée de vie du `mfa_token` | `5` (défaut) |
| `MFA_EMAIL_CODE_EXPIRE_MINUTES` | Durée de vie du code email 2FA | `5` (défaut) |

### Inter-services

| Variable | Description |
|----------|-------------|
| `NOTIFICATION_SERVICE_URL` | URL interne de service-notification (ex: `http://service-notification:8006`) |
| `NOTIFICATION_SERVICE_TOKEN` | Token partagé pour les appels inter-services |
| `SERVICE_RECIPE_URL` | URL interne de service-recipe (ex: `http://service-recipe:8000`) |
| `SERVICE_PROFILE_TOKEN` | Token partagé pour les appels vers service-profile |

### Infrastructure (Redis, Elasticsearch, MinIO)

| Variable | Description | Exemple |
|----------|-------------|---------|
| `CELERY_BROKER_URL` | URL du broker Celery | `redis://redis:6379/0` |
| `CELERY_RESULT_BACKEND` | Backend des résultats Celery | `redis://redis:6379/1` |
| `ELASTICSEARCH_URL` | URL Elasticsearch | `http://elasticsearch:9200` |
| `ELASTICSEARCH_INDEX_RECIPES` | Nom de l'index des recettes | `recipes` |
| `MINIO_ENDPOINT` | Endpoint MinIO (sans http://) | `minio:9000` |
| `MINIO_ACCESS_KEY` | Clé d'accès MinIO | — |
| `MINIO_SECRET_KEY` | Clé secrète MinIO | — |
| `MINIO_BUCKET_CRAWLER` | Bucket pour les médias du crawler | `crawler-media` |
| `MINIO_SECURE` | TLS vers MinIO | `False` en dev |

### Notifications (SMTP + Push VAPID)

| Variable | Description | Exemple |
|----------|-------------|---------|
| `SMTP_HOST` | Serveur SMTP sortant | `smtp.gmail.com` |
| `SMTP_PORT` | Port SMTP | `587` |
| `SMTP_USER` | Adresse d'authentification SMTP | `noreply@nutri-app.com` |
| `SMTP_PASSWORD` | Mot de passe SMTP | — |
| `SMTP_FROM` | Adresse expéditeur des emails | `noreply@nutri-app.com` |
| `SMTP_USE_TLS` | Activer STARTTLS | `true` |
| `VAPID_PRIVATE_KEY` | Clé privée VAPID (notifications push Web) | Voir section suivante |
| `VAPID_PUBLIC_KEY` | Clé publique VAPID (transmise au client JS) | Voir section suivante |
| `VAPID_CLAIMS_EMAIL` | Email de contact dans les claims VAPID | `admin@nutriplanner.app` |

---

## Générer les clés et secrets

### Clé Fernet (MFA_TOTP_ENCRYPTION_KEY)

La clé Fernet protège les secrets TOTP stockés en base. Elle doit être générée **une seule fois par environnement** et ne **jamais changer en production** (changer la clé invalide tous les secrets TOTP existants).

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Exemple de sortie :
```
bXlzZWNyZXRrZXkxMjM0NTY3ODkwMTIzNDU2Nzg=
```

### JWT_SECRET

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### NOTIFICATION_SERVICE_TOKEN

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Paire de clés VAPID (VAPID_PRIVATE_KEY / VAPID_PUBLIC_KEY)

Les clés VAPID authentifient les notifications push Web auprès des navigateurs. À générer **une seule fois par environnement**.

```bash
pip install py-vapid
vapid --gen
```

Ou en Python :

```python
from py_vapid import Vapid
vapid = Vapid()
vapid.generate_keys()
print("Private:", vapid.private_key_str)
print("Public: ", vapid.public_key_str)
```

> Stocker toutes ces valeurs dans un secret manager (HashiCorp Vault, AWS Secrets Manager, GitHub Secrets, Doppler…) — **jamais en clair dans le dépôt**.

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

## CI/CD

Le pipeline GitHub Actions est défini dans `.github/workflows/ci.yml`.

### Déclenchement

| Événement | Comportement |
|-----------|-------------|
| Push sur `main` | Lance uniquement le job du service mentionné dans le message de commit (ex: `feat(core): ... service-user`) |
| Pull Request vers `main` | Lance **tous** les jobs en parallèle |

### Jobs par service

Chaque service possède son propre job indépendant (`analyze-user`, `analyze-recipe`, …). Chaque job exécute dans l'ordre :

1. **Lint** — `ruff check .`
2. **Format** — `ruff format --check .`
3. **Sécurité** — `bandit -r .` (rapport JSON uploadé en artefact)
4. **SonarQube** — analyse statique + couverture (projet `sonar-nutri-app`)
5. **Tests unitaires** — `pytest --cov=app -m "not smoke"`

### Job smoke-tests

Déclenché après la réussite de **tous** les jobs par service. Spin up de la stack complète via `docker compose up`, attente des healthchecks sur chaque port (8001–8007), puis exécution des `smoke_test.py` de chaque service.

### Secrets GitHub requis

| Secret | Utilisation |
|--------|-------------|
| `SONAR_TOKEN` | Authentification SonarQube |
| `JWT_SECRET` | Stack smoke tests |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | Stack smoke tests |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | Stack smoke tests |
| `VAPID_PRIVATE_KEY` / `VAPID_PUBLIC_KEY` | Stack smoke tests |
| `POSTGRES_*` (×7) | Credentials PostgreSQL par service |

---

## Toutes les routes API

### service-user — `api-users.localhost`

```
GET     /health
GET     /health/db

# Auth
POST    /api/v1/auth/login                         Connexion (retourne tokens ou mfa_token si 2FA actif)
POST    /api/v1/auth/refresh                        Rafraîchit le JWT

# Utilisateurs
POST    /api/v1/users                               Créer un utilisateur
GET     /api/v1/users                               Lister les utilisateurs
GET     /api/v1/users/me                            Utilisateur courant (JWT requis)
GET     /api/v1/users/{user_id}                     Utilisateur par ID
GET     /api/v1/users/{user_id}/exists              Vérifier si l'utilisateur existe (inter-service)
DELETE  /api/v1/users/{user_id}                     Supprimer utilisateur

# Double facteur (2FA)
POST    /api/v1/auth/2fa/setup/totp                 Génère un secret TOTP + URI otpauth://
POST    /api/v1/auth/2fa/confirm/totp               Active le 2FA TOTP après vérification du premier code
POST    /api/v1/auth/2fa/setup/email                Active le 2FA par email
POST    /api/v1/auth/2fa/verify                     Échange un mfa_token + code OTP contre des tokens définitifs
DELETE  /api/v1/auth/2fa/disable                    Désactive le 2FA
POST    /api/v1/auth/setup/totp                     Génération de l'image qr code pour le TOTP

# OAuth2
GET     /api/v1/auth/oauth/{provider}/authorize     Redirige vers la page d'autorisation du provider
GET     /api/v1/auth/oauth/{provider}/callback      Reçoit le code OAuth2, crée ou lie le compte
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

---

## Bibliothèque partagée (`shared/`)

`nutri_shared` est une bibliothèque Python interne installée dans chaque conteneur via le Dockerfile. Elle centralise le code commun à tous les services.

### Contenu

| Module | Rôle |
|--------|------|
| `nutri_shared.errors` | Handlers d'erreurs globaux FastAPI |
| `nutri_shared.core.logger` | Configuration structlog (JSON vers stdout) |
| `nutri_shared.core.middleware` | `RequestLoggingMiddleware`, `LocaleMiddleware` |
| `nutri_shared.models` | Modèles SQLAlchemy partagés |
| `nutri_shared.schemas` | Schémas Pydantic partagés |

### Installation en développement local

```bash
pip install -e ./shared/
```

### Utilisation

```python
from nutri_shared.errors import register_error_handlers
from nutri_shared.core.middleware import RequestLoggingMiddleware
from nutri_shared.core.logger import get_logger

logger = get_logger(__name__)
```

---

## Monitoring

### Activer / désactiver la stack

La stack de monitoring (Prometheus, Grafana, Loki, Promtail, Tempo, exporters) est isolée derrière le profil Docker Compose `monitoring`. Elle ne démarre **pas** par défaut.

```bash
# Avec monitoring
docker compose --profile monitoring up -d

# Sans monitoring (prod allégée)
docker compose up -d
```

### Dashboards Grafana

| Dashboard | Description |
|-----------|-------------|
| Rost.r — Crawler | Taux HTTP, codes, tasks Celery, erreurs Instagram, logs payloads |

Accès : `http://grafana.localhost` → Dashboards

### Niveau de log

Configurable via `LOG_LEVEL` dans le `.env` racine — partagé par tous les services et workers.

| Valeur | Usage |
|--------|-------|
| `DEBUG` | Développement — logs détaillés, payloads des requêtes HTTP inclus |
| `INFO` | Production — requêtes HTTP, tâches Celery, erreurs |
| `WARNING` | Alertes et rate limits uniquement |
| `ERROR` | Erreurs critiques uniquement |

### Requêtes LogQL utiles (Grafana → Explore → Loki)

```logql
# Toutes les requêtes HTTP du crawler avec payload
{service="service-crawler"} | json | method != `` | path != `/metrics` | path != `/health`

# Requêtes POST uniquement
{service="service-crawler"} | json | method="POST"

# Logs du worker Celery Instagram
{service="celery-worker-crawler"} |= "instagram"

# Erreurs uniquement
{service="celery-worker-crawler"} | json | level="error"
```

---

## Instagram (service-crawler)

### Authentification

Instagram bloque les logins programmatiques. L'authentification repose sur un fichier de session généré depuis le navigateur et persisté dans le volume Docker `instagram-session`.

**Générer ou renouveler la session :**

1. Se connecter à Instagram dans le navigateur avec le compte configuré
2. Ouvrir DevTools → Application (Chrome) ou Stockage (Firefox) → Cookies → `instagram.com` → copier `sessionid`
3. Exécuter :

```bash
docker exec -i nutriplanner-service-crawler python3 scripts/generate_instagram_session.py
```

4. Redémarrer le worker :

```bash
docker compose restart celery-worker-crawler
```

> La session expire si le mot de passe change ou si Instagram la révoque. Régénérer le fichier avec la procédure ci-dessus.

### Rate limiting (HTTP 429)

- Le worker est libéré immédiatement sur 429 (pas de blocage)
- Celery replanifie le retry automatiquement après **30 minutes**
- Ne pas déclencher plusieurs crawls du même compte en rafale

---

## Logs

### Voir les logs en temps réel

```bash
# Tous les services
docker compose logs -f

# Un service spécifique
docker compose logs -f service-user

# Dernières 100 lignes
docker compose logs --tail=100 service-recipe
```

### Pipeline de centralisation

```
structlog (JSON) → stdout conteneur → Filebeat → Elasticsearch → Grafana
```

Filebeat collecte les logs de tous les conteneurs Docker et les envoie vers Elasticsearch. Les logs sont ensuite visualisables dans Grafana (`http://grafana.localhost`) via un index pattern `docker-*`.

Le fichier de configuration Filebeat est à la racine du projet : `filebeat.yml`.
