# 🌩️ Conectar GymAPI con Grafana Cloud

## Opción A: Configuración Rápida con Docker

```bash
# 1. Edita el archivo grafana-agent-config.yml
# Reemplaza estos valores con los tuyos:

metrics:
  global:
    remote_write:
      - url: https://TU-PROMETHEUS-ENDPOINT.grafana.net/api/prom/push
        basic_auth:
          username: "TU-USER-ID"     # Ejemplo: 1234567
          password: "TU-API-KEY"      # El que generes en Grafana Cloud

# 2. Ejecuta el Grafana Agent
docker-compose -f docker-compose.grafana-agent.yml up -d

# 3. Verifica que esté enviando métricas
docker-compose -f docker-compose.grafana-agent.yml logs -f
```

## Opción B: Sin Docker (Instalación Local)

```bash
# 1. Descargar Grafana Agent
# Mac:
brew install grafana-agent

# Linux:
curl -O -L "https://github.com/grafana/agent/releases/latest/download/grafana-agent-linux-amd64.zip"
unzip grafana-agent-linux-amd64.zip
chmod a+x grafana-agent-linux-amd64

# 2. Ejecutar con tu configuración
./grafana-agent-linux-amd64 -config.file=grafana-agent-config.yml
```

## 🔍 Verificar en Grafana Cloud

1. **Ve a Explore** (icono de brújula en el menú izquierdo)
2. Selecciona **"grafanacloud-alexmontesino96-prom"** como datasource
3. En el **Metric browser**, busca: `gymapi`
4. Deberías ver métricas como:
   - `gymapi_app_info`
   - `gymapi_http_requests_total`
   - `gymapi_db_connections_active`
   - etc.

## 📊 Crear tu Primer Dashboard

1. Click en **"+"** → **"New Dashboard"**
2. **"Add visualization"**
3. Selecciona tu datasource de Prometheus
4. Queries de ejemplo:

```promql
# Panel 1: Info de la App
gymapi_app_info

# Panel 2: Request Rate
rate(gymapi_http_requests_total[5m])

# Panel 3: DB Connections
gymapi_db_connections_active

# Panel 4: Redis Errors
rate(gymapi_redis_connection_errors_total[5m])
```

## 🚨 Configurar Alertas

1. Ve a **Alerting** → **Alert rules**
2. **"New alert rule"**
3. Ejemplo de alerta:

```promql
# Alerta si la API no responde
up{job="gymapi"} == 0
```

## 📝 Troubleshooting

### No veo métricas en Grafana Cloud

```bash
# 1. Verifica que tu API expone métricas
curl http://localhost:8000/metrics | grep gymapi_

# 2. Verifica logs del Grafana Agent
docker logs gymapi_grafana_agent

# 3. Verifica conectividad
curl -X POST https://TU-PROMETHEUS-ENDPOINT.grafana.net/api/prom/push \
  -u "TU-USER-ID:TU-API-KEY" \
  -H "Content-Type: text/plain" \
  --data-binary @- <<EOF
# TYPE test_metric gauge
test_metric 1
EOF
```

### Error de autenticación

- Regenera el API Key en Grafana Cloud
- Asegúrate de que no hay espacios extra en las credenciales
- El username es el número (Instance ID), no tu email

## 🎯 Métricas Importantes a Monitorear

| Métrica | Query | Descripción |
|---------|-------|-------------|
| Request Rate | `rate(gymapi_http_requests_total[5m])` | Peticiones por segundo |
| Error Rate | `rate(gymapi_errors_total[5m])` | Errores por segundo |
| P95 Latency | `histogram_quantile(0.95, rate(gymapi_http_request_duration_seconds_bucket[5m]))` | Latencia percentil 95 |
| DB Connections | `gymapi_db_connections_active` | Conexiones activas a BD |
| Cache Hit Rate | `rate(gymapi_redis_cache_hits_total[5m]) / (rate(gymapi_redis_cache_hits_total[5m]) + rate(gymapi_redis_cache_misses_total[5m]))` | Eficiencia del cache |