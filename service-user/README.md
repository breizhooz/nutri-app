# service-user

## Migrations Alembic

### Générer une nouvelle migration

```bash
docker compose exec service-user alembic revision --autogenerate -m "description_du_changement"
```

Le fichier généré se trouve dans `alembic/versions/`. Vérifier les fonctions `upgrade()` et `downgrade()` avant d'appliquer.

### Appliquer les migrations

```bash
docker compose exec service-user alembic upgrade head
```

### Autres commandes utiles

```bash
# État actuel de la base
docker compose exec service-user alembic current

# Historique des migrations
docker compose exec service-user alembic history

# Rollback d'une migration
docker compose exec service-user alembic downgrade -1
```
