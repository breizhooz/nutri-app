# service-notification

Service de notifications push (Web Push / VAPID). Gère les abonnements et l'envoi de notifications aux utilisateurs.

- **Port local** : `8006`
- **Domaine Traefik** : `http://api-notification.localhost`
- **Swagger** : `http://api-notification.localhost/docs`
- **Base de données** : PostgreSQL sur `localhost:5437`

---

## Routes

```
GET     /health
GET     /health/db
POST    /api/v1/subscriptions                   S'abonner aux notifications push
GET     /api/v1/subscriptions/{slug}            Récupérer un abonnement par slug
DELETE  /api/v1/subscriptions/{slug}            Se désabonner
POST    /api/v1/notify                          Envoyer une notification à un utilisateur
GET     /api/v1/users/{user_slug}/history       Historique des notifications d'un utilisateur
```

---

## Migrations Alembic

```bash
# Créer une migration
docker compose exec service-notification alembic revision --autogenerate -m "description"

# Appliquer
docker compose exec service-notification alembic upgrade head

# Rollback
docker compose exec service-notification alembic downgrade -1

# État actuel
docker compose exec service-notification alembic current

# Historique
docker compose exec service-notification alembic history --verbose
```

> Les migrations s'appliquent automatiquement au démarrage du conteneur.

---

## Tests

```bash
# Tests unitaires
docker compose exec service-notification pytest --cov=app -m "not smoke" -v

# Tests smoke (stack complète requise)
# Les URLs sont configurables via env vars pour s'adapter au contexte d'exécution
docker compose exec \
  -e SERVICE_NOTIFICATION_URL=http://172.18.0.1:8006 \
  -e SERVICE_USER_URL=http://172.18.0.1:8001 \
  service-notification \
  pytest tests/smoke_test.py -m smoke -v
```

---

## Requêtes SQL directes

```bash
docker compose exec postgres-notification psql -U nutrinotification -d nutriplanner_notification \
  -c "SELECT * FROM subscriptions;"
```

---

## Structure

```
service-notification/
├── app/
│   ├── main.py
│   ├── api/routes/
│   │   ├── subscriptions.py  # /subscriptions/*
│   │   ├── notify.py         # /notify
│   │   └── history.py        # /users/{slug}/history
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
| `DATABASE_URL` | `postgresql+asyncpg://...@postgres-notification:5432/...` |
| `VAPID_PRIVATE_KEY` | Clé privée VAPID pour Web Push |
| `VAPID_PUBLIC_KEY` | Clé publique VAPID |
| `VAPID_CLAIMS_EMAIL` | Email dans les claims VAPID |
