# nutri-app
Lancer les Tu's
docker compose run service-recipe pytest tests/ -v


Exec d'une requete dans un container :
docker compose exec postgres-user psql -U nutriuser -d nutriplanner_user \\n  -c "SELECT email, hashed_password FROM users;"
