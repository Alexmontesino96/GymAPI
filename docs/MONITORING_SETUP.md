# 🔍 Configuración del Stack de Monitoreo

## Inicio Rápido

### 1. Iniciar el Stack de Monitoreo

```bash
# Iniciar Prometheus y Grafana
docker-compose -f docker-compose.monitoring.yml up -d

# Verificar que los servicios estén corriendo
docker-compose -f docker-compose.monitoring.yml ps
```

### 2. Acceder a las Interfaces

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000
  - Usuario: `admin`
  - Contraseña: `admin123`
- **Métricas de la App**: http://localhost:8000/metrics

### 3. Verificar Targets en Prometheus

1. Abrir Prometheus: http://localhost:9090
2. Ir a Status → Targets
3. Verificar que todos los targets estén UP:
   - `gymapi` (aplicación principal)
   - `prometheus` (self-monitoring)
   - `node` (métricas del sistema)
   - `postgresql` (métricas de BD)
   - `redis` (métricas de cache)

## Métricas Disponibles

### Métricas HTTP (prefijo: `gymapi_`)

```promql
# Requests totales por endpoint
gymapi_http_requests_total

# Latencia de requests (percentil 95)
histogram_quantile(0.95, rate(gymapi_http_request_duration_seconds_bucket[5m]))

# Tasa de errores
sum(rate(gymapi_errors_total[5m])) / sum(rate(gymapi_http_requests_total[5m]))

# Requests por gimnasio
gymapi_requests_by_gym
```

### Métricas de Base de Datos

```promql
# Duración de queries
gymapi_db_query_duration_seconds

# Conexiones activas
gymapi_db_connections_active

# Transacciones por estado
gymapi_db_transactions_total
```

### Métricas de Redis

```promql
# Operaciones totales
gymapi_redis_operations_total

# Hit rate del cache
gymapi_redis_cache_hits_total / (gymapi_redis_cache_hits_total + gymapi_redis_cache_misses_total)

# Latencia de operaciones
gymapi_redis_operation_duration_seconds
```

### Métricas de Negocio

```promql
# Eventos de negocio por tipo
gymapi_business_events_total

# Usuarios activos por gimnasio
gymapi_active_users

# Planes de nutrición activos
gymapi_nutrition_active_plans

# Eventos activos
gymapi_events_active

# Suscripciones activas
gymapi_billing_active_subscriptions
```

## Dashboards en Grafana

### Dashboard Principal de GymAPI

1. **Overview**
   - Request rate
   - Error rate
   - P95 latency
   - Active users

2. **Performance**
   - Response time distribution
   - Slow queries
   - Cache performance

3. **Business Metrics**
   - Events por gimnasio
   - Revenue tracking
   - User engagement

4. **Infrastructure**
   - CPU usage
   - Memory usage
   - Disk I/O

## Alertas Configuradas

Las alertas están definidas en `prometheus/alerts.yml`:

- **GymAPIDown**: API no responde por más de 1 minuto
- **HighErrorRate**: Tasa de errores > 5%
- **HighResponseTime**: P95 latency > 1 segundo
- **DatabaseConnectionFailures**: Fallas de conexión a BD
- **RedisConnectionErrors**: Errores de conexión a Redis
- **LowCacheHitRate**: Hit rate < 80%
- **HighMemoryUsage**: Memoria > 90%
- **HighCPUUsage**: CPU > 80%

## Queries Útiles

### Top 10 endpoints más lentos
```promql
topk(10,
  histogram_quantile(0.95,
    sum by (endpoint) (
      rate(gymapi_http_request_duration_seconds_bucket[5m])
    )
  )
)
```

### Gimnasios más activos
```promql
topk(5,
  sum by (gym_id) (
    rate(gymapi_requests_by_gym[5m])
  )
)
```

### Tasa de éxito de notificaciones
```promql
sum(rate(gymapi_business_events_total{event_type="nutrition_notification",status="success"}[5m]))
/
sum(rate(gymapi_business_events_total{event_type="nutrition_notification"}[5m]))
```

## Troubleshooting

### Prometheus no puede alcanzar la aplicación

Si Prometheus no puede conectar con `host.docker.internal:8000`:

1. En Linux, agregar al docker-compose:
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

2. Verificar que la app esté escuchando en `0.0.0.0:8000`

### Grafana no muestra datos

1. Verificar datasource en Grafana
2. Confirmar que Prometheus está recibiendo métricas
3. Revisar logs: `docker-compose -f docker-compose.monitoring.yml logs grafana`

### Métricas no aparecen

1. Verificar endpoint: `curl http://localhost:8000/metrics`
2. Revisar logs de la aplicación
3. Confirmar que el instrumentator está activo

## Próximos Pasos

1. **Fase 1**: Agregar más métricas específicas de negocio
2. **Fase 2**: Configurar Alertmanager para notificaciones
3. **Fase 3**: Implementar distributed tracing con Jaeger
4. **Fase 4**: Agregar logs centralizados con Loki