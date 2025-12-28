# 🚀 Setup Rápido de GymAPI → Grafana Cloud

## NO necesitas un Prometheus local!

Grafana Cloud YA tiene Prometheus integrado. Solo necesitas enviar tus métricas.

## Paso 1: Obtén tus credenciales

1. Ve a la página principal de Grafana Cloud
2. Busca el panel de **Prometheus** (NO en Connections)
3. Click en **"Send Metrics"** o el ícono de configuración
4. Verás:
   - **Remote Write Endpoint**: `https://prometheus-prod-XX.grafana.net/api/prom/push`
   - **Username**: Un número como `1234567`
   - **API Key**: Click en "Generate Now" para crear uno

## Paso 2: Configura el Grafana Agent

```bash
# 1. Edita grafana-agent-config.yml
# Reemplaza SOLO estas 3 líneas con tus datos:

remote_write:
  - url: https://prometheus-prod-XX.grafana.net/api/prom/push  # Tu URL
    basic_auth:
      username: "1234567"     # Tu Username/Instance ID
      password: "glc_eyJ..."  # Tu API Key completo

# 2. Ejecuta el agent
docker run -d \
  --name grafana-agent \
  -v $(pwd)/grafana-agent-config.yml:/etc/agent/agent.yml \
  --add-host host.docker.internal:host-gateway \
  grafana/agent:latest \
  -config.file=/etc/agent/agent.yml
```

## Paso 3: Verifica que funciona

1. Espera 30 segundos
2. Ve a **Explore** en Grafana Cloud
3. Selecciona tu datasource de Prometheus (ya está configurado)
4. Escribe: `gymapi_app_info`
5. Click en "Run query"

Si ves resultados, ¡está funcionando!

## ❌ Errores Comunes

### "No necesitas configurar una conexión a Prometheus"
- Grafana Cloud YA TIENE Prometheus
- Solo necesitas ENVIAR métricas, no conectar otro Prometheus

### "No veo el panel de Prometheus"
- Ve a Home → My Account → Grafana Cloud Portal
- Ahí verás tu stack con Prometheus

### "No encuentro las credenciales"
- Busca el texto "Remote Write" en la interfaz
- O busca "Send Metrics"
- NO es en Connections → Data sources