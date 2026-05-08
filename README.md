# nutri-app
Lancer les Tu's
docker compose run service-recipe pytest tests/ -v


Exec d'une requete dans un container :
docker compose exec postgres-user psql -U nutriuser -d nutriplanner_user \\n  -c "SELECT email, hashed_password FROM users;"
docker compose exec postgres-recipe psql -U nutrirecipe -d nutriplanner_recipe \\n  -c "SELECT * FROM recipe;"

Lancer une migration:
docker compose exec service-recipe alembic init alembic
docker compose exec service-recipe alembic revision --autogenerate -m "Initial recipe models"
docker compose exec service-recipe alembic upgrade head
