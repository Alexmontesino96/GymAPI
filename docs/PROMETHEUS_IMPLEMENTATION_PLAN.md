# Plan de Implementación de Prometheus para GymAPI

## Resumen Ejecutivo

Este documento detalla la implementación completa de Prometheus para monitoreo de todas las funcionalidades de GymAPI, dividido en 7 fases progresivas con un timeline de 4-6 semanas.

## Arquitectura de Monitoreo

```
┌────────────────────────────────────────────────────────────────────┐
│                         GymAPI Components                          │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│  │   FastAPI   │  │  SQS Worker │  │  Scheduler  │               │
│  │  /metrics   │  │  /metrics   │  │  /metrics   │               │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │
│         │                 │                 │                      │
│         └─────────────────┼─────────────────┘                      │
│                           │                                        │
└───────────────────────────┼────────────────────────────────────────┘
                            │ :9090
                ┌───────────▼────────────┐
                │     Prometheus         │
                │   (Time Series DB)     │
                └───────────┬────────────┘
                            │ :3000
                ┌───────────▼────────────┐
                │       Grafana          │
                │     (Dashboards)       │
                └────────────────────────┘
```

---

## Fase 0: Preparación (2 días)

### Objetivos
- Configurar infraestructura base
- Instalar dependencias
- Crear estructura de métricas

### Implementación

#### 0.1 Dependencias

```python
# requirements.txt
prometheus-client==0.19.0
prometheus-fastapi-instrumentator==6.1.0
psutil==5.9.6  # Para métricas del sistema
```

#### 0.2 Estructura de Archivos

```
app/
├── core/
│   ├── metrics/
│   │   ├── __init__.py
│   │   ├── base.py          # Métricas base
│   │   ├── api.py           # Métricas de API
│   │   ├── nutrition.py     # Métricas de nutrición
│   │   ├── events.py        # Métricas de eventos
│   │   ├── chat.py          # Métricas de chat
│   │   ├── billing.py       # Métricas de billing
│   │   ├── schedule.py      # Métricas de schedule
│   │   └── database.py      # Métricas de BD
│   └── prometheus.py        # Configuración principal
```

#### 0.3 Configuración Base

```python
# app/core/prometheus.py
from prometheus_client import CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
from prometheus_fastapi_instrumentator import Instrumentator
from fastapi import FastAPI, Response
import logging

logger = logging.getLogger(__name__)

# Registry global para métricas custom
REGISTRY = CollectorRegistry()

def setup_prometheus(app: FastAPI):
    """
    Configurar Prometheus para FastAPI
    """
    # Instrumentación automática
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_group_untemplated=True,
        excluded_handlers=["/metrics", "/docs", "/redoc", "/openapi.json"],
    )

    instrumentator.instrument(app).expose(app, include_in_schema=False)

    # Endpoint para métricas custom
    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return Response(
            generate_latest(REGISTRY),
            media_type=CONTENT_TYPE_LATEST
        )

    logger.info("Prometheus metrics configured at /metrics")
```

---

## Fase 1: Métricas de API Base (3 días)

### Objetivos
- Instrumentar todos los endpoints
- Métricas de latencia y throughput
- Métricas de errores por endpoint

### Métricas a Implementar

```python
# app/core/metrics/api.py
from prometheus_client import Counter, Histogram, Gauge
from app.core.prometheus import REGISTRY

# Contador de requests
API_REQUESTS = Counter(
    'gymapi_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status', 'gym_id'],
    registry=REGISTRY
)

# Histograma de latencia
API_LATENCY = Histogram(
    'gymapi_http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
    registry=REGISTRY
)

# Requests activas
API_ACTIVE_REQUESTS = Gauge(
    'gymapi_http_requests_active',
    'Active HTTP requests',
    ['method', 'endpoint'],
    registry=REGISTRY
)

# Errores por tipo
API_ERRORS = Counter(
    'gymapi_http_errors_total',
    'Total HTTP errors',
    ['method', 'endpoint', 'error_type', 'gym_id'],
    registry=REGISTRY
)

# Rate limiting hits
RATE_LIMIT_HITS = Counter(
    'gymapi_rate_limit_hits_total',
    'Rate limit hits',
    ['endpoint', 'gym_id'],
    registry=REGISTRY
)
```

### Middleware de Métricas

```python
# app/middleware/metrics.py
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.metrics.api import API_REQUESTS, API_LATENCY, API_ACTIVE_REQUESTS
import time

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extraer información
        method = request.method
        endpoint = request.url.path
        gym_id = request.state.gym.id if hasattr(request.state, 'gym') else 'unknown'

        # Incrementar requests activas
        API_ACTIVE_REQUESTS.labels(method=method, endpoint=endpoint).inc()

        # Medir latencia
        start_time = time.time()

        try:
            response = await call_next(request)
            status = response.status_code

            # Registrar métricas
            API_REQUESTS.labels(
                method=method,
                endpoint=endpoint,
                status=status,
                gym_id=gym_id
            ).inc()

            return response

        except Exception as e:
            API_ERRORS.labels(
                method=method,
                endpoint=endpoint,
                error_type=type(e).__name__,
                gym_id=gym_id
            ).inc()
            raise

        finally:
            # Registrar latencia y decrementar activas
            duration = time.time() - start_time
            API_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)
            API_ACTIVE_REQUESTS.labels(method=method, endpoint=endpoint).dec()
```

---

## Fase 2: Métricas de Nutrición y Notificaciones (3 días)

### Objetivos
- Monitorear sistema de notificaciones
- Tracking de SQS
- Métricas de deduplicación

### Métricas Específicas

```python
# app/core/metrics/nutrition.py
from prometheus_client import Counter, Histogram, Gauge
from app.core.prometheus import REGISTRY

# ============================================================================
# NOTIFICACIONES
# ============================================================================

NOTIFICATIONS_SENT = Counter(
    'gymapi_nutrition_notifications_sent_total',
    'Total notifications sent',
    ['gym_id', 'meal_type', 'method', 'status'],
    registry=REGISTRY
)

NOTIFICATIONS_QUEUED = Counter(
    'gymapi_nutrition_notifications_queued_total',
    'Notifications queued to SQS',
    ['gym_id', 'meal_type'],
    registry=REGISTRY
)

NOTIFICATIONS_DUPLICATES_PREVENTED = Counter(
    'gymapi_nutrition_duplicates_prevented_total',
    'Duplicate notifications prevented by cache',
    ['gym_id', 'meal_type'],
    registry=REGISTRY
)

NOTIFICATION_DELIVERY_TIME = Histogram(
    'gymapi_nutrition_notification_delivery_seconds',
    'Time to deliver notification',
    ['method'],
    buckets=[0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60],
    registry=REGISTRY
)

# ============================================================================
# SQS
# ============================================================================

SQS_MESSAGES_SENT = Counter(
    'gymapi_sqs_messages_sent_total',
    'Messages sent to SQS',
    ['queue', 'message_type'],
    registry=REGISTRY
)

SQS_MESSAGES_RECEIVED = Counter(
    'gymapi_sqs_messages_received_total',
    'Messages received from SQS',
    ['queue', 'message_type'],
    registry=REGISTRY
)

SQS_MESSAGES_FAILED = Counter(
    'gymapi_sqs_messages_failed_total',
    'Messages failed to process',
    ['queue', 'message_type', 'reason'],
    registry=REGISTRY
)

SQS_QUEUE_DEPTH = Gauge(
    'gymapi_sqs_queue_depth',
    'Current queue depth',
    ['queue'],
    registry=REGISTRY
)

SQS_DLQ_MESSAGES = Gauge(
    'gymapi_sqs_dlq_messages',
    'Messages in Dead Letter Queue',
    ['queue'],
    registry=REGISTRY
)

# ============================================================================
# PLANES Y SEGUIDORES
# ============================================================================

NUTRITION_PLANS_ACTIVE = Gauge(
    'gymapi_nutrition_plans_active',
    'Active nutrition plans',
    ['gym_id', 'plan_type'],
    registry=REGISTRY
)

NUTRITION_FOLLOWERS = Gauge(
    'gymapi_nutrition_followers_total',
    'Total plan followers',
    ['gym_id', 'plan_type'],
    registry=REGISTRY
)

MEAL_COMPLETIONS = Counter(
    'gymapi_nutrition_meal_completions_total',
    'Meals marked as completed',
    ['gym_id', 'meal_type'],
    registry=REGISTRY
)

STREAK_MILESTONES = Counter(
    'gymapi_nutrition_streak_milestones_total',
    'Streak milestones achieved',
    ['gym_id', 'milestone_days'],
    registry=REGISTRY
)
```

### Implementación en Servicio

```python
# Modificar nutrition_notification_service.py
from app.core.metrics.nutrition import (
    NOTIFICATIONS_SENT,
    NOTIFICATION_DELIVERY_TIME,
    NOTIFICATIONS_DUPLICATES_PREVENTED
)

def send_meal_reminder(self, ...):
    with NOTIFICATION_DELIVERY_TIME.labels(method='direct').time():
        # ... código existente ...

    if self._check_notification_already_sent(...):
        NOTIFICATIONS_DUPLICATES_PREVENTED.labels(
            gym_id=gym_id,
            meal_type=meal_type
        ).inc()
        return False

    # ... enviar notificación ...

    NOTIFICATIONS_SENT.labels(
        gym_id=gym_id,
        meal_type=meal_type,
        method='sqs' if sqs_used else 'direct',
        status='success'
    ).inc()
```

---

## Fase 3: Métricas de Base de Datos y Redis (2 días)

### Objetivos
- Monitorear pool de conexiones
- Latencia de queries
- Cache hit ratio

### Métricas de Base de Datos

```python
# app/core/metrics/database.py
from prometheus_client import Counter, Histogram, Gauge
from app.core.prometheus import REGISTRY

# Pool de conexiones
DB_CONNECTIONS_ACTIVE = Gauge(
    'gymapi_db_connections_active',
    'Active database connections',
    registry=REGISTRY
)

DB_CONNECTIONS_IDLE = Gauge(
    'gymapi_db_connections_idle',
    'Idle database connections',
    registry=REGISTRY
)

# Queries
DB_QUERIES = Counter(
    'gymapi_db_queries_total',
    'Database queries executed',
    ['operation', 'table', 'status'],
    registry=REGISTRY
)

DB_QUERY_DURATION = Histogram(
    'gymapi_db_query_duration_seconds',
    'Database query duration',
    ['operation', 'table'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5],
    registry=REGISTRY
)

# Transacciones
DB_TRANSACTIONS = Counter(
    'gymapi_db_transactions_total',
    'Database transactions',
    ['status'],  # committed, rolled_back
    registry=REGISTRY
)

# Errores
DB_ERRORS = Counter(
    'gymapi_db_errors_total',
    'Database errors',
    ['error_type', 'operation'],
    registry=REGISTRY
)
```

### Métricas de Redis

```python
# app/core/metrics/cache.py
from prometheus_client import Counter, Histogram, Gauge
from app.core.prometheus import REGISTRY

REDIS_OPERATIONS = Counter(
    'gymapi_redis_operations_total',
    'Redis operations',
    ['operation', 'status'],
    registry=REGISTRY
)

REDIS_CACHE_HITS = Counter(
    'gymapi_redis_cache_hits_total',
    'Cache hits',
    ['cache_type'],
    registry=REGISTRY
)

REDIS_CACHE_MISSES = Counter(
    'gymapi_redis_cache_misses_total',
    'Cache misses',
    ['cache_type'],
    registry=REGISTRY
)

REDIS_LATENCY = Histogram(
    'gymapi_redis_operation_duration_seconds',
    'Redis operation latency',
    ['operation'],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1],
    registry=REGISTRY
)

REDIS_MEMORY_USAGE = Gauge(
    'gymapi_redis_memory_bytes',
    'Redis memory usage',
    registry=REGISTRY
)

REDIS_KEYS_COUNT = Gauge(
    'gymapi_redis_keys_total',
    'Total keys in Redis',
    ['pattern'],
    registry=REGISTRY
)
```

### Event Listener para SQLAlchemy

```python
# app/db/metrics_listener.py
from sqlalchemy import event
from sqlalchemy.engine import Engine
from app.core.metrics.database import DB_QUERIES, DB_QUERY_DURATION
import time

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault('query_start_time', []).append(time.time())

@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total_time = time.time() - conn.info['query_start_time'].pop(-1)

    # Extraer operación y tabla
    operation = statement.split()[0].upper() if statement else 'UNKNOWN'
    table = extract_table_name(statement)

    DB_QUERY_DURATION.labels(operation=operation, table=table).observe(total_time)
    DB_QUERIES.labels(operation=operation, table=table, status='success').inc()
```

---

## Fase 4: Métricas de Eventos y Chat (2 días)

### Objetivos
- Monitorear eventos activos
- Participación en eventos
- Actividad de chat

### Métricas de Eventos

```python
# app/core/metrics/events.py
from prometheus_client import Counter, Gauge
from app.core.prometheus import REGISTRY

EVENTS_CREATED = Counter(
    'gymapi_events_created_total',
    'Events created',
    ['gym_id', 'category', 'event_type'],
    registry=REGISTRY
)

EVENTS_ACTIVE = Gauge(
    'gymapi_events_active',
    'Currently active events',
    ['gym_id', 'status'],
    registry=REGISTRY
)

EVENT_PARTICIPANTS = Gauge(
    'gymapi_event_participants',
    'Event participants',
    ['gym_id', 'event_id'],
    registry=REGISTRY
)

EVENT_REGISTRATIONS = Counter(
    'gymapi_event_registrations_total',
    'Event registrations',
    ['gym_id', 'registration_type'],  # confirmed, cancelled
    registry=REGISTRY
)
```

### Métricas de Chat

```python
# app/core/metrics/chat.py
from prometheus_client import Counter, Gauge, Histogram
from app.core.prometheus import REGISTRY

CHAT_MESSAGES_SENT = Counter(
    'gymapi_chat_messages_sent_total',
    'Messages sent',
    ['gym_id', 'channel_type', 'user_role'],
    registry=REGISTRY
)

CHAT_ROOMS_ACTIVE = Gauge(
    'gymapi_chat_rooms_active',
    'Active chat rooms',
    ['gym_id', 'room_type'],
    registry=REGISTRY
)

CHAT_USERS_ONLINE = Gauge(
    'gymapi_chat_users_online',
    'Users currently online',
    ['gym_id'],
    registry=REGISTRY
)

STREAM_API_CALLS = Counter(
    'gymapi_stream_api_calls_total',
    'Stream.io API calls',
    ['operation', 'status'],
    registry=REGISTRY
)

STREAM_API_LATENCY = Histogram(
    'gymapi_stream_api_latency_seconds',
    'Stream.io API latency',
    ['operation'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
    registry=REGISTRY
)
```

---

## Fase 5: Métricas de Billing y Stripe (2 días)

### Objetivos
- Monitorear transacciones
- Suscripciones activas
- Fallos de pago

### Métricas

```python
# app/core/metrics/billing.py
from prometheus_client import Counter, Gauge, Histogram
from app.core.prometheus import REGISTRY

# Transacciones
PAYMENT_TRANSACTIONS = Counter(
    'gymapi_payment_transactions_total',
    'Payment transactions',
    ['gym_id', 'status', 'payment_method'],
    registry=REGISTRY
)

PAYMENT_AMOUNT = Counter(
    'gymapi_payment_amount_total',
    'Total payment amount in cents',
    ['gym_id', 'currency'],
    registry=REGISTRY
)

# Suscripciones
SUBSCRIPTIONS_ACTIVE = Gauge(
    'gymapi_subscriptions_active',
    'Active subscriptions',
    ['gym_id', 'plan', 'interval'],
    registry=REGISTRY
)

SUBSCRIPTION_CHANGES = Counter(
    'gymapi_subscription_changes_total',
    'Subscription changes',
    ['gym_id', 'change_type'],  # created, upgraded, downgraded, cancelled
    registry=REGISTRY
)

# Stripe API
STRIPE_API_CALLS = Counter(
    'gymapi_stripe_api_calls_total',
    'Stripe API calls',
    ['operation', 'status'],
    registry=REGISTRY
)

STRIPE_API_LATENCY = Histogram(
    'gymapi_stripe_api_latency_seconds',
    'Stripe API latency',
    ['operation'],
    buckets=[0.1, 0.25, 0.5, 1, 2.5, 5],
    registry=REGISTRY
)

# Webhooks
STRIPE_WEBHOOKS_RECEIVED = Counter(
    'gymapi_stripe_webhooks_received_total',
    'Stripe webhooks received',
    ['event_type', 'status'],
    registry=REGISTRY
)

# Revenue
MONTHLY_RECURRING_REVENUE = Gauge(
    'gymapi_mrr_cents',
    'Monthly Recurring Revenue in cents',
    ['gym_id'],
    registry=REGISTRY
)
```

---

## Fase 6: Métricas de Schedule y Classes (2 días)

### Objetivos
- Ocupación de clases
- Reservaciones
- Cancelaciones

### Métricas

```python
# app/core/metrics/schedule.py
from prometheus_client import Counter, Gauge, Histogram
from app.core.prometheus import REGISTRY

# Clases
CLASSES_SCHEDULED = Counter(
    'gymapi_classes_scheduled_total',
    'Classes scheduled',
    ['gym_id', 'class_type', 'trainer_id'],
    registry=REGISTRY
)

CLASS_ATTENDANCE_RATE = Gauge(
    'gymapi_class_attendance_rate',
    'Class attendance rate percentage',
    ['gym_id', 'class_type'],
    registry=REGISTRY
)

CLASS_CAPACITY_USAGE = Histogram(
    'gymapi_class_capacity_usage_ratio',
    'Class capacity usage ratio',
    ['gym_id', 'class_type'],
    buckets=[0.1, 0.25, 0.5, 0.75, 0.9, 1.0],
    registry=REGISTRY
)

# Reservaciones
RESERVATIONS_CREATED = Counter(
    'gymapi_reservations_created_total',
    'Reservations created',
    ['gym_id', 'class_type', 'status'],
    registry=REGISTRY
)

RESERVATIONS_CANCELLED = Counter(
    'gymapi_reservations_cancelled_total',
    'Reservations cancelled',
    ['gym_id', 'cancellation_reason'],
    registry=REGISTRY
)

NO_SHOWS = Counter(
    'gymapi_class_no_shows_total',
    'Class no-shows',
    ['gym_id', 'class_type'],
    registry=REGISTRY
)

# Waitlist
WAITLIST_ENTRIES = Gauge(
    'gymapi_waitlist_entries',
    'Current waitlist entries',
    ['gym_id', 'class_id'],
    registry=REGISTRY
)
```

---

## Fase 7: Métricas del Sistema y Business (3 días)

### Objetivos
- KPIs de negocio
- Métricas de sistema
- Health checks

### Métricas de Sistema

```python
# app/core/metrics/system.py
from prometheus_client import Gauge, Info
from app.core.prometheus import REGISTRY
import psutil

# Info del sistema
APP_INFO = Info(
    'gymapi_app_info',
    'Application information',
    registry=REGISTRY
)

# Recursos del sistema
SYSTEM_CPU_USAGE = Gauge(
    'gymapi_system_cpu_percent',
    'CPU usage percentage',
    registry=REGISTRY
)

SYSTEM_MEMORY_USAGE = Gauge(
    'gymapi_system_memory_bytes',
    'Memory usage in bytes',
    ['type'],  # used, available, percent
    registry=REGISTRY
)

# Health checks
HEALTH_CHECK_STATUS = Gauge(
    'gymapi_health_check_status',
    'Health check status',
    ['component'],  # api, database, redis, stream, stripe, sqs
    registry=REGISTRY
)

# Worker metrics
WORKER_TASKS_PROCESSED = Counter(
    'gymapi_worker_tasks_processed_total',
    'Tasks processed by workers',
    ['worker_type', 'status'],
    registry=REGISTRY
)

WORKER_PROCESSING_TIME = Histogram(
    'gymapi_worker_processing_seconds',
    'Worker task processing time',
    ['worker_type'],
    buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 300],
    registry=REGISTRY
)
```

### Métricas de Negocio

```python
# app/core/metrics/business.py
from prometheus_client import Gauge
from app.core.prometheus import REGISTRY

# Usuarios
USERS_ACTIVE = Gauge(
    'gymapi_users_active',
    'Active users in the last 30 days',
    ['gym_id', 'role'],
    registry=REGISTRY
)

USERS_REGISTERED = Counter(
    'gymapi_users_registered_total',
    'New user registrations',
    ['gym_id', 'registration_source'],
    registry=REGISTRY
)

USER_RETENTION_RATE = Gauge(
    'gymapi_user_retention_rate',
    'User retention rate',
    ['gym_id', 'period'],  # weekly, monthly
    registry=REGISTRY
)

# Engagement
DAILY_ACTIVE_USERS = Gauge(
    'gymapi_dau',
    'Daily Active Users',
    ['gym_id'],
    registry=REGISTRY
)

WEEKLY_ACTIVE_USERS = Gauge(
    'gymapi_wau',
    'Weekly Active Users',
    ['gym_id'],
    registry=REGISTRY
)

MONTHLY_ACTIVE_USERS = Gauge(
    'gymapi_mau',
    'Monthly Active Users',
    ['gym_id'],
    registry=REGISTRY
)

# Feature adoption
FEATURE_USAGE = Counter(
    'gymapi_feature_usage_total',
    'Feature usage count',
    ['gym_id', 'feature'],
    registry=REGISTRY
)

FEATURE_ADOPTION_RATE = Gauge(
    'gymapi_feature_adoption_rate',
    'Feature adoption rate percentage',
    ['gym_id', 'feature'],
    registry=REGISTRY
)
```

---

## Dashboards de Grafana

### Dashboard 1: Overview General

```yaml
panels:
  - title: "Request Rate"
    query: "rate(gymapi_http_requests_total[5m])"
    type: graph

  - title: "Error Rate"
    query: "rate(gymapi_http_errors_total[5m])"
    type: graph
    alert: > 5%

  - title: "P95 Latency"
    query: "histogram_quantile(0.95, rate(gymapi_http_request_duration_seconds_bucket[5m]))"
    type: gauge
    alert: > 500ms

  - title: "Active Users"
    query: "gymapi_dau"
    type: stat
```

### Dashboard 2: Nutrición y Notificaciones

```yaml
panels:
  - title: "Notifications Sent (24h)"
    query: "increase(gymapi_nutrition_notifications_sent_total[24h])"
    type: stat

  - title: "Notification Success Rate"
    query: |
      sum(rate(gymapi_nutrition_notifications_sent_total{status="success"}[5m]))
      /
      sum(rate(gymapi_nutrition_notifications_sent_total[5m]))
    type: gauge

  - title: "SQS Queue Depth"
    query: "gymapi_sqs_queue_depth"
    type: graph
    alert: > 1000

  - title: "Duplicates Prevented"
    query: "increase(gymapi_nutrition_duplicates_prevented_total[24h])"
    type: stat
```

### Dashboard 3: Database Performance

```yaml
panels:
  - title: "Query Rate by Operation"
    query: "rate(gymapi_db_queries_total[5m])"
    type: graph

  - title: "Database Connection Pool"
    query: |
      gymapi_db_connections_active
      gymapi_db_connections_idle
    type: graph

  - title: "Query P95 Latency"
    query: "histogram_quantile(0.95, rate(gymapi_db_query_duration_seconds_bucket[5m]))"
    type: gauge
    alert: > 100ms

  - title: "Cache Hit Ratio"
    query: |
      sum(rate(gymapi_redis_cache_hits_total[5m]))
      /
      (sum(rate(gymapi_redis_cache_hits_total[5m])) + sum(rate(gymapi_redis_cache_misses_total[5m])))
    type: gauge
```

### Dashboard 4: Business Metrics

```yaml
panels:
  - title: "Monthly Recurring Revenue"
    query: "sum(gymapi_mrr_cents) / 100"
    type: stat
    unit: "$"

  - title: "Active Subscriptions"
    query: "sum(gymapi_subscriptions_active)"
    type: stat

  - title: "User Growth (30d)"
    query: "increase(gymapi_users_registered_total[30d])"
    type: graph

  - title: "Feature Adoption"
    query: "gymapi_feature_adoption_rate"
    type: bar
```

---

## Alertas Configuradas

### Críticas (PagerDuty)

```yaml
- alert: HighErrorRate
  expr: rate(gymapi_http_errors_total[5m]) > 0.05
  for: 5m
  annotations:
    summary: "Error rate above 5%"

- alert: DatabaseDown
  expr: gymapi_health_check_status{component="database"} == 0
  for: 1m
  annotations:
    summary: "Database is down"

- alert: HighMemoryUsage
  expr: gymapi_system_memory_percent > 90
  for: 10m
  annotations:
    summary: "Memory usage above 90%"
```

### Importantes (Slack)

```yaml
- alert: SQSQueueBuildUp
  expr: gymapi_sqs_queue_depth > 1000
  for: 10m
  annotations:
    summary: "SQS queue has over 1000 messages"

- alert: LowCacheHitRate
  expr: |
    sum(rate(gymapi_redis_cache_hits_total[5m]))
    /
    (sum(rate(gymapi_redis_cache_hits_total[5m])) + sum(rate(gymapi_redis_cache_misses_total[5m])))
    < 0.8
  for: 15m
  annotations:
    summary: "Cache hit rate below 80%"

- alert: HighP95Latency
  expr: histogram_quantile(0.95, rate(gymapi_http_request_duration_seconds_bucket[5m])) > 1
  for: 10m
  annotations:
    summary: "P95 latency above 1 second"
```

---

## Timeline de Implementación

| Fase | Duración | Inicio | Fin | Entregable |
|------|----------|--------|-----|------------|
| 0. Preparación | 2 días | Semana 1 Lun | Semana 1 Mar | Infraestructura base |
| 1. API Base | 3 días | Semana 1 Mié | Semana 1 Vie | Métricas HTTP |
| 2. Nutrición | 3 días | Semana 2 Lun | Semana 2 Mié | Métricas notificaciones |
| 3. BD y Redis | 2 días | Semana 2 Jue | Semana 2 Vie | Métricas de datos |
| 4. Eventos y Chat | 2 días | Semana 3 Lun | Semana 3 Mar | Métricas sociales |
| 5. Billing | 2 días | Semana 3 Mié | Semana 3 Jue | Métricas financieras |
| 6. Schedule | 2 días | Semana 3 Vie | Semana 4 Lun | Métricas de clases |
| 7. Sistema y KPIs | 3 días | Semana 4 Mar | Semana 4 Jue | Métricas de negocio |
| Testing y Ajustes | 2 días | Semana 4 Vie | Semana 5 Lun | Dashboards finales |

**Total: 21 días laborables (4-5 semanas)**

---

## Configuración de Docker Compose

```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:v2.45.0
    container_name: gymapi_prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:10.0.0
    container_name: gymapi_grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
      - GF_INSTALL_PLUGINS=redis-datasource
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources
    restart: unless-stopped

  node_exporter:
    image: prom/node-exporter:v1.6.0
    container_name: gymapi_node_exporter
    ports:
      - "9100:9100"
    restart: unless-stopped

volumes:
  prometheus_data:
  grafana_data:
```

---

## Testing y Validación

### Test de Carga con Locust

```python
# tests/load_test.py
from locust import HttpUser, task, between

class GymAPIUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def get_nutrition_plans(self):
        self.client.get("/api/v1/nutrition/plans")

    @task
    def send_notification(self):
        self.client.post("/api/v1/nutrition/notifications/test")
```

### Queries de Validación

```promql
# Verificar que las métricas están llegando
up{job="gymapi"}

# Request rate
rate(gymapi_http_requests_total[5m])

# Error rate
rate(gymapi_http_errors_total[5m]) / rate(gymapi_http_requests_total[5m])

# P95 latency
histogram_quantile(0.95, rate(gymapi_http_request_duration_seconds_bucket[5m]))
```

---

## Consideraciones de Producción

### 1. Seguridad

```python
# Proteger endpoint /metrics
@app.get("/metrics")
@require_permission("admin")  # Solo admins pueden ver métricas
async def metrics():
    return Response(generate_latest(REGISTRY))
```

### 2. Performance

- Las métricas agregan ~1-2ms de overhead por request
- Usar sampling para high-volume endpoints
- Limitar cardinalidad de labels

### 3. Storage

- Prometheus retiene 30 días por defecto
- ~10MB/día para 100K series activas
- Considerar remote storage para largo plazo

### 4. Alta Disponibilidad

```yaml
# Prometheus HA setup
prometheus_primary:
  external_labels:
    replica: "A"

prometheus_secondary:
  external_labels:
    replica: "B"
```

---

## Conclusión

Esta implementación proporciona:

✅ **Observabilidad completa** de todas las funcionalidades
✅ **Alertas proactivas** antes de que los usuarios reporten problemas
✅ **KPIs de negocio** en tiempo real
✅ **Debugging rápido** con métricas detalladas
✅ **Capacity planning** basado en datos históricos

**ROI estimado:**
- 50% reducción en tiempo de debugging
- 90% reducción en tiempo de detección de problemas
- 100% visibilidad de la salud del sistema

**Costo mensual estimado:**
- Grafana Cloud Free: $0 (10K métricas)
- Grafana Cloud Pro: $49/mes (100K métricas)
- Self-hosted: ~$20/mes (servidor dedicado)