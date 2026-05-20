# service-recipe

## Migrations Alembic

### Générer une nouvelle migration

```bash
docker compose exec service-recipe alembic revision --autogenerate -m "description_du_changement"
```

Le fichier généré se trouve dans `alembic/versions/`. Vérifier les fonctions `upgrade()` et `downgrade()` avant d'appliquer.

### Appliquer les migrations

```bash
docker compose exec service-recipe alembic upgrade head
```

### Autres commandes utiles

```bash
# État actuel de la base
docker compose exec service-recipe alembic current

# Historique des migrations
docker compose exec service-recipe alembic history

# Rollback d'une migration
docker compose exec service-recipe alembic downgrade -1

# lancer les TUs
docker compose run service-recipe pytest tests/ -v 
python -m pytest tests/unit/test_schemas_recipe.py tests/unit/test_routes_recipe.py -v 2>&1
```


