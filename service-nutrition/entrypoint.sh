#!/bin/sh

# On s'assure que le script s'arrête si une commande échoue
set -e

echo "Exécution des migrations Alembic..."
alembic upgrade head

if [ "$#" -gt 0 ]; then
    exec "$@"
else
    echo "Démarrage de Uvicorn..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi