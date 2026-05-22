# service-profile

Service de gestion du profil utilisateur : données anthropométriques, composition corporelle, mesures, blessures, conditions de santé, allergies et préférences alimentaires.

- **Port local** : `8007`
- **Domaine Traefik** : `http://api-profile.localhost`
- **Swagger** : `http://api-profile.localhost/docs`
- **Base de données** : PostgreSQL sur `localhost:5439`

---

## Routes

```
GET     /health
GET     /health/db

# Profil
POST    /api/v1/profiles                        Créer un profil
GET     /api/v1/profiles/me                     Profil de l'utilisateur courant
PATCH   /api/v1/profiles/me                     Modifier le profil
GET     /api/v1/profiles/me/calculate           Calculs dérivés (IMC, besoins caloriques, etc.)
GET     /api/v1/profiles/{slug}                 Profil par slug

# Composition corporelle
POST    /api/v1/profiles/me/composition         Ajouter une mesure corporelle
GET     /api/v1/profiles/me/composition         Historique composition corporelle
DELETE  /api/v1/profiles/me/composition/{slug}  Supprimer une entrée

# Mesures corporelles
POST    /api/v1/profiles/me/measurements        Ajouter des mesures
GET     /api/v1/profiles/me/measurements        Historique des mesures
DELETE  /api/v1/profiles/me/measurements/{slug} Supprimer une mesure

# Blessures
POST    /api/v1/profiles/me/injuries            Ajouter une blessure
GET     /api/v1/profiles/me/injuries            Historique des blessures
DELETE  /api/v1/profiles/me/injuries/{slug}     Supprimer une blessure

# Conditions de santé
POST    /api/v1/profiles/me/conditions          Ajouter une condition de santé
DELETE  /api/v1/profiles/me/conditions/{slug}   Supprimer une condition

# Allergies
POST    /api/v1/profiles/me/allergies           Ajouter une allergie alimentaire
GET     /api/v1/profiles/me/allergies           Lister les allergies
DELETE  /api/v1/profiles/me/allergies/{slug}    Supprimer une allergie

# Préférences
POST    /api/v1/profiles/me/preferences         Définir les préférences alimentaires
```

---

## Migrations Alembic

```bash
# Créer une migration
docker compose exec service-profile alembic revision --autogenerate -m "description"

# Appliquer
docker compose exec service-profile alembic upgrade head

# Rollback
docker compose exec service-profile alembic downgrade -1

# État actuel
docker compose exec service-profile alembic current

# Historique
docker compose exec service-profile alembic history --verbose
```

> Les migrations s'appliquent automatiquement au démarrage du conteneur.

---

## Tests

```bash
# Tests unitaires
docker compose exec service-profile pytest --cov=app -m "not smoke" -v

# Tests smoke (stack complète requise)
docker compose exec service-profile pytest tests/smoke_test.py -m smoke -v
```

---

## Requêtes SQL directes

```bash
docker compose exec postgres-profile psql -U nutriprofile -d nutriplanner_profile \
  -c "SELECT * FROM profiles;"
```

---

## Structure

```
service-profile/
├── app/
│   ├── main.py
│   ├── api/routes/
│   │   ├── profiles.py        # /profiles/*
│   │   ├── composition.py     # /profiles/me/composition
│   │   ├── measurements.py    # /profiles/me/measurements
│   │   ├── injuries.py        # /profiles/me/injuries
│   │   ├── conditions.py      # /profiles/me/conditions
│   │   ├── allergies.py       # /profiles/me/allergies
│   │   └── preferences.py     # /profiles/me/preferences
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
| `DATABASE_URL` | `postgresql+asyncpg://...@postgres-profile:5432/...` |
