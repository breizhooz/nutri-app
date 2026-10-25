# ══════════════════════════════════════════════════════════════════════
# Dockerfile UNIQUE des 7 services FastAPI (+ leurs workers Celery).
# Contexte de build = racine du backend (compose : `context: ../..`).
#
#   --build-arg SERVICE=user            → service-user/
#   --build-arg APT_PACKAGES="…"        → paquets système propres au service (menu)
#   --target dev   (compose)            → --reload + watchdog (workers auto-restart)
#   --target prod                       → utilisateur non-root, sans --reload
#
# Les couches « base » (Python + nutri_shared) sont IDENTIQUES pour tous les
# services → construites une fois, stockées une fois (cache BuildKit).
# Versions Python : shared/constraints.txt (cf. make deps-check).
# ══════════════════════════════════════════════════════════════════════

FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# python:slim est livré sans les .pyc de la stdlib, et PYTHONDONTWRITEBYTECODE
# empêche de les écrire à l'exécution : chaque processus Python (healthcheck
# toutes les 5 s, alembic, celery…) recompilait ses imports — 234 ms de CPU pour
# `import urllib.request`, 40 ms une fois précompilé (+20 Mo, couche partagée).
RUN python -m compileall -q -j 0 "$(python -c 'import sysconfig; print(sysconfig.get_path("stdlib"))')"

# Point de montage des volumes de données (session Instagram du crawler).
# Propriétaire = uid de l'utilisateur prod (10001) : un volume neuf monté ici en
# hérite, qu'il soit créé par un conteneur dev (root) ou prod.
RUN mkdir -p /data && chown 10001 /data

# ── Commun à tous les services (couches partagées) ───────────────────
COPY shared/ /shared/
RUN pip install -c /shared/constraints.txt /shared/

# ── Propre au service ────────────────────────────────────────────────
ARG APT_PACKAGES=""
RUN if [ -n "$APT_PACKAGES" ]; then \
        apt-get update \
        && apt-get install -y --no-install-recommends $APT_PACKAGES \
        && rm -rf /var/lib/apt/lists/*; \
    fi

ARG SERVICE
# requirements.txt commence par `-c ../shared/constraints.txt` (→ /shared).
# requirements-nodeps.txt (optionnel) : paquets installés sans leurs dépendances
# (ex. rapidocr, cf. service-crawler).
COPY service-${SERVICE}/requirements*.txt ./
RUN pip install -r requirements.txt \
    && if [ -f requirements-nodeps.txt ]; then \
        pip install --no-deps -r requirements-nodeps.txt; \
    fi

COPY service-${SERVICE}/ .

EXPOSE 8000

# ── dev : code monté depuis l'hôte, rechargement à chaud ─────────────
FROM base AS dev
# watchdog : `watchmedo auto-restart` des workers Celery (compose).
RUN pip install -c /shared/constraints.txt watchdog
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]

# ── prod : non-root, sans rechargement ───────────────────────────────
FROM base AS prod
# Code embarqué : précompilé aussi (démarrage des workers uvicorn / celery).
RUN python -m compileall -q -j 0 /app
# /app appartient à l'utilisateur applicatif (celery beat y écrit son schedule).
RUN useradd --system --uid 10001 --home-dir /app app && chown -R app /app
USER app
# Nombre de processus uvicorn : WEB_CONCURRENCY (lu par uvicorn, 1 par défaut).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
