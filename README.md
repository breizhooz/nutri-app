# nutri-app
Lancer les Tu's
docker compose run service-recipe pytest tests/ -v


Exec d'une requete dans un container :
docker compose exec postgres-user psql -U nutriuser -d nutriplanner_user \\n  -c "SELECT email, hashed_password FROM users;"
docker compose exec postgres-recipe psql -U nutrirecipe -d nutriplanner_recipe \\n  -c "SELECT * FROM recipe;"

Lancer une migration:
docker compose exec service-recipe alembic init alembic
docker compose exec service-recipe alembic revision --autogenerate -m "Initial recipe models"

# service-user
docker compose exec service-user alembic upgrade head

# service-recipe
docker compose exec service-recipe alembic upgrade head

# service-menu
docker compose exec service-menu alembic upgrade head

# url:
URL	Contenu
http://traefik.localhost	Dashboard Traefik
http://api.localhost	Portail Swagger UI
http://api-users.localhost/docs	Swagger service-user
http://api-recipe.localhost/docs	Swagger service-recipe
http://api-menu.localhost/docs	Swagger service-menu
http://api-crawler.localhost/docs	Swagger service-crawler
http://api-nutrition.localhost/docs	Swagger service-nutrition
http://api-notification.localhost/docs	Swagger service-notification
http://api-profile.localhost/docs	Swagger service-profile