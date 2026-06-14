import json
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

try:
    from opentelemetry import trace as otel_trace
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

_log = structlog.get_logger()

_BODY_MAX_BYTES = 4096
_SKIP_PATHS = {"/health", "/health/db", "/metrics"}

_REDACTED = "[REDACTED]"
# Rédaction des champs sensibles avant journalisation (RGPD art. 32). Match par
# fragment de nom de clé, insensible à la casse : couvre données de santé (notes
# médicales, contre-indications) et secrets (mots de passe, tokens, clés push).
_SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "notes",
    "medical_contraindication",
    "totp",
    "mfa",
    "recovery",
    "p256dh",
    "auth",
)


def _is_sensitive_key(key: str) -> bool:
    k = key.lower()
    return any(part in k for part in _SENSITIVE_KEY_PARTS)


def _redact(value):
    """Copie de la valeur avec les champs sensibles masqués (récursif)."""
    if isinstance(value, dict):
        return {
            k: (_REDACTED if _is_sensitive_key(str(k)) else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()

        ctx: dict = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
        }

        trace_id: str | None = None
        if _OTEL_AVAILABLE:
            span = otel_trace.get_current_span()
            span_ctx = span.get_span_context()
            if span_ctx.is_valid:
                trace_id = format(span_ctx.trace_id, "032x")
                ctx["trace_id"] = trace_id
                ctx["span_id"] = format(span_ctx.span_id, "016x")

        if request.url.path not in _SKIP_PATHS:
            if request.query_params:
                ctx["query_params"] = _redact(dict(request.query_params))

            body_bytes = await request.body()
            if body_bytes:
                truncated = len(body_bytes) > _BODY_MAX_BYTES
                sample = body_bytes[:_BODY_MAX_BYTES]
                try:
                    parsed = json.loads(sample)
                    # Masque les champs sensibles (santé/secrets) avant log.
                    ctx["request_body"] = _redact(parsed)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Corps non-JSON : impossible de cibler les champs sensibles
                    # → on ne journalise pas le contenu brut (fuite potentielle).
                    ctx["request_body"] = "[non-JSON body omitted]"
                if truncated:
                    ctx["request_body_truncated"] = True

        structlog.contextvars.bind_contextvars(**ctx)
        response = await call_next(request)
        _log.info("request", status_code=response.status_code)
        response.headers["X-Request-ID"] = request_id
        # Exposé au front (admin) pour proposer une recherche Loki ciblée
        # `{trace_id="…"}` quand une requête plante. `trace_id` est un label
        # Loki (extrait par promtail), donc directement requêtable dans Grafana.
        if trace_id is not None:
            response.headers["X-Trace-Id"] = trace_id
        return response