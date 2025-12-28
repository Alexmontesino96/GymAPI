#!/bin/bash

echo "🚀 Iniciando Grafana Agent para GymAPI"
echo "======================================="

# Verificar que GymAPI está corriendo
echo "✅ Verificando GymAPI en puerto 8000..."
if curl -s http://localhost:8000/metrics > /dev/null; then
    echo "   ✓ GymAPI respondiendo correctamente"
else
    echo "   ⚠️  GymAPI no responde en puerto 8000"
    echo "   Asegúrate de ejecutar: python app_wrapper.py"
    exit 1
fi

# Limpiar contenedor anterior si existe
echo "🧹 Limpiando contenedores anteriores..."
docker rm -f grafana-agent 2>/dev/null

# Iniciar Grafana Agent
echo "🐳 Iniciando Grafana Agent con Docker..."
docker run -d \
  --name grafana-agent \
  -v $(pwd)/grafana-agent-final.yml:/etc/agent/agent.yml \
  -p 12345:12345 \
  --add-host host.docker.internal:host-gateway \
  grafana/agent:latest \
  -config.file=/etc/agent/agent.yml \
  -metrics.wal-directory=/tmp/wal

# Esperar un poco
sleep 3

# Verificar que está corriendo
if docker ps | grep grafana-agent > /dev/null; then
    echo ""
    echo "✅ Grafana Agent iniciado correctamente!"
    echo ""
    echo "📊 Verifica tus métricas en Grafana Cloud:"
    echo "   1. Ve a https://alexmontesino96.grafana.net"
    echo "   2. Click en 'Explore' (brújula en el menú)"
    echo "   3. Asegúrate de seleccionar el datasource 'grafanacloud-alexmontesino96-prom'"
    echo "   4. En el query builder, escribe: gymapi_app_info"
    echo "   5. Click en 'Run query'"
    echo ""
    echo "📝 Ver logs del agent:"
    echo "   docker logs -f grafana-agent"
    echo ""
    echo "🛑 Para detener el agent:"
    echo "   docker stop grafana-agent"
else
    echo ""
    echo "❌ Error al iniciar Grafana Agent"
    echo "Ver logs con: docker logs grafana-agent"
fi