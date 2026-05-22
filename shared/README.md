# shared — nutri_shared

Bibliothèque Python partagée entre tous les microservices. Contient les handlers d'erreurs, le logging, les middlewares et les schémas communs.

---

## Installation

La librairie est installée dans chaque conteneur via le Dockerfile :

```dockerfile
COPY shared/ /tmp/shared/
RUN pip install /tmp/shared/
```

En développement local :

```bash
pip install -e ./shared/
```

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
├── setup.py
├── pyproject.toml
└── requirements.txt
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
structlog → stdout JSON → Filebeat → Elasticsearch → Grafana
```

Les logs sont collectés par Filebeat depuis les conteneurs Docker et envoyés vers Elasticsearch pour visualisation dans Grafana.

---

## Utilisation dans un service

```python
from nutri_shared.errors import register_error_handlers
from nutri_shared.core.middleware import RequestLoggingMiddleware
from nutri_shared.core.logger import get_logger

logger = get_logger(__name__)
```
