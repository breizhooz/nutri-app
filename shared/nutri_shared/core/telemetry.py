import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor


def setup_telemetry(service_name: str, app=None) -> None:
    """Configure OTel → Tempo et Prometheus /metrics pour un service FastAPI.

    L'export des traces est volontairement *fail-fast* : Tempo est optionnel
    (profil ``monitoring``), donc un collecteur absent ou lent ne doit jamais
    spammer les logs ni bloquer une requête/arrêt. Désactivable entièrement via
    ``OTEL_SDK_DISABLED=true`` (défaut côté compose quand monitoring est down).
    """
    if os.getenv("OTEL_SDK_DISABLED", "false").lower() == "true":
        return
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=os.getenv("TEMPO_ENDPOINT", "http://tempo:4318/v1/traces"),
        # POST OTLP borné : on abandonne vite plutôt que d'empiler les retries
        # de 10s quand Tempo est injoignable.
        timeout=int(os.getenv("OTEL_EXPORTER_OTLP_TIMEOUT", "5")),
    )
    provider.add_span_processor(
        BatchSpanProcessor(
            exporter,
            # File plus large pour encaisser les rafales (ex. import en masse
            # qui fait un appel HTTPX instrumenté par recette).
            max_queue_size=int(os.getenv("OTEL_BSP_MAX_QUEUE_SIZE", "4096")),
            max_export_batch_size=int(
                os.getenv("OTEL_BSP_MAX_EXPORT_BATCH_SIZE", "512")
            ),
        )
    )
    trace.set_tracer_provider(provider)

    HTTPXClientInstrumentor().instrument()

    if app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

        from prometheus_fastapi_instrumentator import Instrumentator
        Instrumentator().instrument(app).expose(app)