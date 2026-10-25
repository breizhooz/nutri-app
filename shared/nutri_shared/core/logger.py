import logging
import os
import sys

import structlog

_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}

# Bibliothèques dont le niveau DEBUG ne décrit que leur mécanique interne
# (transport HTTP, polling de fichiers, boucle asyncio) : bornées à WARNING,
# sinon LOG_LEVEL=DEBUG noie les logs applicatifs.
_NOISY_LOGGERS = (
    "asyncio",
    "botocore",
    "h2",
    "hpack",
    "httpcore",
    "multipart",
    "python_multipart",
    "s3transfer",
    "urllib3",
    "watchfiles",
)

# Communs aux logs structlog et aux logs « étrangers » (stdlib : uvicorn,
# sqlalchemy, celery…), pour que les deux aient les mêmes champs.
_SHARED_PROCESSORS = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso"),
]


def _add_service(service_name: str):
    """Champ `service` sur chaque log. Pas via les contextvars : le middleware
    de requête les vide à chaque requête (clear_contextvars)."""

    def processor(_logger, _method, event_dict):
        event_dict.setdefault("service", service_name)
        return event_dict

    return processor


def configure_logging(service_name: str, level: int | None = None) -> None:
    shared_processors = [*_SHARED_PROCESSORS, _add_service(service_name)]
    if level is None:
        raw = os.getenv("LOG_LEVEL", "INFO").upper()
        level = _LEVELS.get(raw, logging.INFO)
    # Rendu JSON unique, dans le handler stdlib : structlog lui transmet le
    # dictionnaire d'événement (wrap_for_formatter) au lieu d'une chaîne déjà
    # rendue, qui était ré-encodée en JSON (« event » contenant tout le JSON).
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.ExceptionRenderer(),
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(max(level, logging.WARNING))

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.ExceptionRenderer(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    return structlog.get_logger(name)
