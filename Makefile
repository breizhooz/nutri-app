# ── NutriPlanner backend — point d'entrée unique de l'infra ────────────────
# `make` ou `make help` liste les cibles. La définition compose vit dans
# infra/compose/*.yml (façade : docker-compose.yml), les env dans infra/env/.

COMPOSE := docker compose
PY      := python3

.DEFAULT_GOAL := help

.PHONY: help up down restart ps logs config check env-examples env-check certs monitoring

help: ## Liste les cibles disponibles
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

up: ## Démarre la stack (build si nécessaire)
	$(COMPOSE) up -d --build

down: ## Arrête la stack (les volumes sont conservés)
	$(COMPOSE) down

restart: ## Redémarre un service : make restart S=service-user
	$(COMPOSE) restart $(S)

ps: ## État des conteneurs
	$(COMPOSE) ps

logs: ## Logs suivis (tous, ou un service : make logs S=service-user)
	$(COMPOSE) logs -f --tail=100 $(S)

config: ## Rend la config compose résolue (sanity check des fragments + env)
	$(COMPOSE) config --quiet && echo "compose OK"

env-examples: ## (Re)génère infra/env/examples/*.env.example depuis les Settings pydantic
	$(PY) infra/scripts/gen_env_examples.py

env-check: ## Vérifie que la chaîne env_file couvre tous les champs requis des Settings
	$(PY) infra/scripts/gen_env_examples.py --check

check: config env-check ## Tous les contrôles statiques infra

certs: ## (Re)génère les certificats mkcert pour Traefik (HTTPS dev)
	cd infra/traefik && ./gen-certs.sh

monitoring: ## Démarre la stack avec le profil monitoring
	$(COMPOSE) --profile monitoring up -d
