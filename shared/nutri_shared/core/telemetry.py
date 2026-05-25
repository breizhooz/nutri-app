import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor


def setup_telemetry(service_name: str, app=None) -> None:
    """Configure OTel → Tempo et Prometheus /metrics pour un service FastAPI."""
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=os.getenv("TEMPO_ENDPOINT", "http://tempo:4318/v1/traces")
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    HTTPXClientInstrumentor().instrument()

    if app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

        from prometheus_fastapi_instrumentator import Instrumentator
        Instrumentator().instrument(app).expose(app)