# shared — nutri_shared

Bibliothèque Python partagée entre tous les microservices. Contient les handlers d'erreurs, le logging, les middlewares et les schémas communs.

---

## Installation

La librairie est installée dans chaque conteneur via le Dockerfile :

```dockerfile
COPY shared/ /shared/
RUN pip install --no-cache-dir -c /shared/constraints.txt /shared/
```

En développement local (depuis `backend/`, un venv pour tous les services) :

```bash
pip install -c shared/constraints.txt -e ./shared/
pip install -r service-<nom>/requirements-dev.txt   # prod + outils de test
```

### Versions : `constraints.txt` (source unique)

`shared/constraints.txt` épingle **toutes** les versions Python du backend.
Les `requirements.txt` (prod, dans l'image) et `requirements-dev.txt` (tests, CI,
jamais dans l'image) des services ne listent que des noms ; ils commencent par
`-c ../shared/constraints.txt` (resp. `-r requirements.txt`), donc tout
`pip install -r …` est épinglé automatiquement.

Pour monter une lib : modifier **uniquement** sa ligne dans `constraints.txt`.
`make deps-check` (inclus dans `make check` et le job CI `infra-check`) refuse
toute version écrite ailleurs ou toute lib non épinglée.

---

## Contenu

```
shared/
├── nutri_shared/
│   ├── errors.py           # Handlers d'erreurs globaux FastAPI
│   ├── core/
│   │   ├── logger.py       # Configuration structlog
│   │   └── middleware.py   # RequestLoggingMiddleware
│   ├── models/             # Modèles SQLAlchemy partagés
│   └── schemas/            # Schémas Pydantic partagés
├── pyproject.toml      # dépendances de nutri_shared (bornes minimales)
└── constraints.txt     # versions épinglées de tout le backend
```

---

## Middlewares inclus dans tous les services

| Middleware | Rôle |
|-----------|------|
| `LocaleMiddleware` | Parsing de l'header `Accept-Language` (fr/en, défaut: fr) |
| `RequestLoggingMiddleware` | Log structuré de chaque requête/réponse |
| `ErrorHandlers` | Gestion globale des exceptions FastAPI |

---

## Logging

Le logging est centralisé via **structlog** :

```
structlog → stdout JSON → Promtail → Loki → Grafana
```

Les logs sont collectés par Promtail depuis les conteneurs Docker et envoyés vers Loki pour visualisation dans Grafana.

---

## Utilisation dans un service

```python
from nutri_shared.errors import register_error_handlers
from nutri_shared.core.middleware import RequestLoggingMiddleware
from nutri_shared.core.logger import get_logger

logger = get_logger(__name__)
```
