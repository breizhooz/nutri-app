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


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()

        ctx: dict = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
        }

        if _OTEL_AVAILABLE:
            span = otel_trace.get_current_span()
            span_ctx = span.get_span_context()
            if span_ctx.is_valid:
                ctx["trace_id"] = format(span_ctx.trace_id, "032x")
                ctx["span_id"] = format(span_ctx.span_id, "016x")

        if request.url.path not in _SKIP_PATHS:
            if request.query_params:
                ctx["query_params"] = dict(request.query_params)

            body_bytes = await request.body()
            if body_bytes:
                truncated = len(body_bytes) > _BODY_MAX_BYTES
                sample = body_bytes[:_BODY_MAX_BYTES]
                try:
                    parsed = json.loads(sample)
                    ctx["request_body"] = parsed
                except (json.JSONDecodeError, UnicodeDecodeError):
                    ctx["request_body"] = sample.decode("utf-8", errors="replace")
                if truncated:
                    ctx["request_body_truncated"] = True

        structlog.contextvars.bind_contextvars(**ctx)
        response = await call_next(request)
        _log.info("request", status_code=response.status_code)
        response.headers["X-Request-ID"] = request_id
        return response