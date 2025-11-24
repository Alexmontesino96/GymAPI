"""
FastAPI Prometheus Instrumentator configuration.
"""
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from typing import Callable
import time
import logging
from .base import (
    track_request,
    track_business_event,
    active_users_gauge,
    metrics_registry_instance
)

logger = logging.getLogger(__name__)

# ============================================================================
# CUSTOM METRICS FOR INSTRUMENTATOR
# ============================================================================

def gym_id_metric() -> Callable[[metrics.Info], None]:
    """Métrica personalizada para trackear requests por gym_id."""

    METRIC = Counter(
        "gymapi_requests_by_gym",
        "Total requests by gym_id",
        labelnames=("gym_id", "method", "path", "status")
    )

    def instrumentation(info: metrics.Info) -> None:
        gym_id = "unknown"
        if hasattr(info.request, "state") and hasattr(info.request.state, "gym_id"):
            gym_id = str(info.request.state.gym_id)

        METRIC.labels(
            gym_id=gym_id,
            method=info.method,
            path=info.modified_handler,
            status=info.modified_status
        ).inc()

    return instrumentation

def auth_metrics() -> Callable[[metrics.Info], None]:
    """Métricas de autenticación."""

    AUTH_REQUESTS = Counter(
        "gymapi_auth_requests_total",
        "Total authentication requests",
        labelnames=("method", "status", "auth_type")
    )

    def instrumentation(info: metrics.Info) -> None:
        if "/auth/" in info.modified_handler:
            auth_type = "unknown"
            if "login" in info.modified_handler:
                auth_type = "login"
            elif "refresh" in info.modified_handler:
                auth_type = "refresh"
            elif "logout" in info.modified_handler:
                auth_type = "logout"

            AUTH_REQUESTS.labels(
                method=info.method,
                status=info.modified_status,
                auth_type=auth_type
            ).inc()

    return instrumentation

def slow_requests_metric() -> Callable[[metrics.Info], None]:
    """Métrica para requests lentos (> 1 segundo)."""

    SLOW_REQUESTS = Counter(
        "gymapi_slow_requests_total",
        "Requests slower than 1 second",
        labelnames=("method", "path", "gym_id")
    )

    def instrumentation(info: metrics.Info) -> None:
        if info.response.headers.get("X-Process-Time"):
            process_time = float(info.response.headers["X-Process-Time"])
            if process_time > 1.0:
                gym_id = "unknown"
                if hasattr(info.request, "state") and hasattr(info.request.state, "gym_id"):
                    gym_id = str(info.request.state.gym_id)

                SLOW_REQUESTS.labels(
                    method=info.method,
                    path=info.modified_handler,
                    gym_id=gym_id
                ).inc()

    return instrumentation

def error_rate_metric() -> Callable[[metrics.Info], None]:
    """Métrica para tasa de errores."""

    ERROR_COUNTER = Counter(
        "gymapi_errors_total",
        "Total errors by type",
        labelnames=("status_code", "path", "method")
    )

    def instrumentation(info: metrics.Info) -> None:
        if info.modified_status.startswith("4") or info.modified_status.startswith("5"):
            ERROR_COUNTER.labels(
                status_code=info.modified_status,
                path=info.modified_handler,
                method=info.method
            ).inc()

    return instrumentation

def business_metrics_middleware() -> Callable[[metrics.Info], None]:
    """Middleware para métricas de negocio."""

    def instrumentation(info: metrics.Info) -> None:
        # Trackear eventos de negocio basados en endpoints
        gym_id = getattr(info.request.state, "gym_id", None)
        if not gym_id:
            return

        # Eventos de nutrición
        if "/nutrition/" in info.modified_handler and info.modified_status == "200":
            if "meal" in info.modified_handler:
                track_business_event("meal_logged", gym_id, "success")
            elif "plan" in info.modified_handler:
                track_business_event("nutrition_plan_created", gym_id, "success")

        # Eventos de schedule
        elif "/schedule/" in info.modified_handler and info.modified_status == "200":
            if "booking" in info.modified_handler:
                if info.method == "POST":
                    track_business_event("class_booked", gym_id, "success")
                elif info.method == "DELETE":
                    track_business_event("class_cancelled", gym_id, "success")

        # Eventos de billing
        elif "/billing/" in info.modified_handler and info.modified_status == "200":
            if "payment" in info.modified_handler:
                track_business_event("payment_processed", gym_id, "success")
            elif "subscription" in info.modified_handler:
                track_business_event("subscription_created", gym_id, "success")

        # Eventos de chat
        elif "/chat/" in info.modified_handler and info.modified_status == "200":
            if "message" in info.modified_handler:
                track_business_event("message_sent", gym_id, "success")

    return instrumentation

# ============================================================================
# INSTRUMENTATOR FACTORY
# ============================================================================

def get_instrumentator() -> Instrumentator:
    """Crear y configurar el instrumentador de Prometheus."""

    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=[
            "/metrics",
            "/api/v1/metrics",
            "/health",
            "/api/v1/health",
            "/docs",
            "/api/v1/docs",
            "/openapi.json",
            "/api/v1/openapi.json",
            "/redoc",
            "/api/v1/redoc"
        ],
        env_var_name="ENABLE_METRICS",
        inprogress_name="gymapi_requests_inprogress",
        inprogress_labels=True
    )

    # Agregar métricas estándar
    instrumentator.add(
        metrics.default(
            metric_namespace="gymapi",
            metric_subsystem=""
        )
    )

    # Latencias con percentiles
    instrumentator.add(
        metrics.latency(
            metric_namespace="gymapi",
            metric_subsystem="",
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
        )
    )

    # Tamaño de requests
    instrumentator.add(
        metrics.request_size(
            metric_namespace="gymapi",
            metric_subsystem=""
        )
    )

    # Tamaño de responses
    instrumentator.add(
        metrics.response_size(
            metric_namespace="gymapi",
            metric_subsystem=""
        )
    )

    # Métricas personalizadas
    instrumentator.add(gym_id_metric())
    instrumentator.add(auth_metrics())
    instrumentator.add(slow_requests_metric())
    instrumentator.add(error_rate_metric())
    instrumentator.add(business_metrics_middleware())

    logger.info("Prometheus instrumentator configured successfully")

    return instrumentator

# ============================================================================
# MIDDLEWARE DE MÉTRICAS MANUAL
# ============================================================================

class PrometheusMiddleware:
    """Middleware manual para capturar métricas adicionales."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, request: Request, call_next):
        start_time = time.time()

        # Trackear usuarios activos
        if hasattr(request.state, "user") and hasattr(request.state, "gym_id"):
            user = request.state.user
            gym_id = request.state.gym_id
            role = getattr(user, "role", "unknown")

            # Actualizar gauge de usuarios activos
            active_users_gauge.labels(
                gym_id=str(gym_id),
                user_type=role
            ).inc()

        # Procesar request
        response = await call_next(request)

        # Calcular duración
        duration = time.time() - start_time

        # Trackear request manualmente si es necesario
        if hasattr(request.state, "gym_id"):
            track_request(
                method=request.method,
                endpoint=str(request.url.path),
                status_code=response.status_code,
                duration=duration,
                gym_id=request.state.gym_id
            )

        # Agregar headers de timing
        response.headers["X-Process-Time"] = str(duration)

        return response

# ============================================================================
# ENDPOINT DE MÉTRICAS
# ============================================================================

async def metrics_endpoint(request: Request) -> Response:
    """Endpoint personalizado para exponer métricas."""
    try:
        # Generar métricas en formato Prometheus
        metrics_output = generate_latest()

        return Response(
            content=metrics_output,
            media_type=CONTENT_TYPE_LATEST,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache"
            }
        )
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        return PlainTextResponse(
            content=f"Error generating metrics: {str(e)}",
            status_code=500
        )

def setup_metrics_endpoint(app: FastAPI):
    """Configurar endpoint de métricas en la aplicación."""
    app.add_api_route(
        "/metrics",
        metrics_endpoint,
        methods=["GET"],
        include_in_schema=False,
        response_class=PlainTextResponse
    )