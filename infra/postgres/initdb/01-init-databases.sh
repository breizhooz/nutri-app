#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────
# Initialisation du moteur Postgres unique (multi-bases).
#
# Exécuté UNE SEULE FOIS par l'entrypoint officiel de l'image postgres, au
# tout premier démarrage quand le volume de données est vide
# (/docker-entrypoint-initdb.d/*.sh). À ce stade le serveur écoute uniquement
# sur le socket local en auth "trust" → psql/createdb sans mot de passe.
#
# Crée pour chaque service son ROLE (LOGIN) + sa DATABASE (OWNER = ce rôle).
# Chaque base reste une frontière d'isolation DURE : un rôle n'a aucun droit
# sur la base d'un autre service (pas de fusion, pas de JOIN cross-base).
# Le superuser du moteur ($POSTGRES_USER) sert à l'admin et au postgres_exporter.
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail

# Tous les clients (psql, createdb) se connectent en superuser du moteur via le
# socket local. Sans ça, ils tenteraient le rôle OS "postgres" (inexistant ici).
export PGUSER="$POSTGRES_USER"
export PGDATABASE="$POSTGRES_DB"

create_role_and_db() {
  local db="$1" role="$2" pass="$3"

  if [ -z "$db" ] || [ -z "$role" ] || [ -z "$pass" ]; then
    echo "[init-db] SKIP: variable manquante (db='$db' role='$role')" >&2
    return 0
  fi

  echo "[init-db] rôle '$role' + base '$db'"

  # Rôle (idempotent). Identifiant entre guillemets → casse préservée (ex. nutriMENU).
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
	DO \$do\$
	BEGIN
	   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${role}') THEN
	      CREATE ROLE "${role}" LOGIN PASSWORD '${pass}';
	   END IF;
	END
	\$do\$;
	EOSQL

  # Base (CREATE DATABASE interdit dans une transaction/DO → on teste puis createdb).
  if ! psql -tAc "SELECT 1 FROM pg_database WHERE datname = '${db}'" | grep -q 1; then
    createdb --owner "${role}" "${db}"
  fi
}

create_role_and_db "${POSTGRES_USER_DB}"         "${POSTGRES_USER_USER}"         "${POSTGRES_USER_PASSWORD}"
create_role_and_db "${POSTGRES_RECIPE_DB}"       "${POSTGRES_RECIPE_USER}"       "${POSTGRES_RECIPE_PASSWORD}"
create_role_and_db "${POSTGRES_MENU_DB}"         "${POSTGRES_MENU_USER}"         "${POSTGRES_MENU_PASSWORD}"
create_role_and_db "${POSTGRES_CRAWLER_DB}"      "${POSTGRES_CRAWLER_USER}"      "${POSTGRES_CRAWLER_PASSWORD}"
create_role_and_db "${POSTGRES_NOTIFICATION_DB}" "${POSTGRES_NOTIFICATION_USER}" "${POSTGRES_NOTIFICATION_PASSWORD}"
create_role_and_db "${POSTGRES_NUTRITION_DB}"    "${POSTGRES_NUTRITION_USER}"    "${POSTGRES_NUTRITION_PASSWORD}"
create_role_and_db "${POSTGRES_PROFILE_DB}"      "${POSTGRES_PROFILE_USER}"      "${POSTGRES_PROFILE_PASSWORD}"

echo "[init-db] terminé : 7 bases initialisées."
