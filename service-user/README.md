# service-user

Service d'authentification et de gestion des utilisateurs.

- **Port local** : `8001`
- **Domaine Traefik** : `http://api-users.localhost`
- **Swagger** : `http://api-users.localhost/docs`
- **Base de données** : PostgreSQL sur `localhost:5433`

---

## Routes

```
GET     /health
GET     /health/db
POST    /api/v1/auth/login            Connexion — retourne access_token + refresh_token
POST    /api/v1/auth/refresh          Rafraîchit le JWT
POST    /api/v1/users                 Créer un utilisateur
GET     /api/v1/users                 Lister les utilisateurs
GET     /api/v1/users/me             Utilisateur courant (JWT requis)
GET     /api/v1/users/{user_id}       Utilisateur par ID
GET     /api/v1/users/{user_id}/exists  Vérifier si l'utilisateur existe (appelé par d'autres services)
DELETE  /api/v1/users/{user_id}       Supprimer utilisateur
```

---

## Migrations Alembic

```bash
# Créer une migration depuis les modèles
docker compose exec service-user alembic revision --autogenerate -m "description"

# Appliquer toutes les migrations
docker compose exec service-user alembic upgrade head

# Rollback d'une migration
docker compose exec service-user alembic downgrade -1

# État actuel
docker compose exec service-user alembic current

# Historique
docker compose exec service-user alembic history --verbose
```

> Les migrations s'appliquent automatiquement au démarrage du conteneur.

---

## Tests

```bash
# Tests unitaires
docker compose exec service-user pytest --cov=app -m "not smoke" -v

# Tests smoke (stack complète requise)
docker compose exec service-user pytest tests/smoke_test.py -m smoke -v

# Fichier précis
docker compose exec service-user pytest tests/unit/test_routes_auth.py -v
```

---

## Requêtes SQL directes

```bash
docker compose exec postgres-user psql -U nutriuser -d nutriplanner_user \
  -c "SELECT email, hashed_password FROM users;"
```

---

## Structure

```
service-user/
├── app/
│   ├── main.py
│   ├── api/routes/
│   │   ├── auth.py         # /auth/login, /auth/refresh
│   │   └── users.py        # /users/*
│   ├── models/             # Modèles SQLAlchemy
│   ├── schemas/            # Schémas Pydantic
│   ├── db/                 # Session async
│   └── core/               # Config, JWT, auth middleware
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
| `DATABASE_URL` | `postgresql+asyncpg://...@postgres-user:5432/...` |
| `JWT_SECRET` | Clé de signature des tokens JWT |
