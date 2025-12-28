#!/bin/bash

echo "🌩️  Configuración de Grafana Cloud para GymAPI"
echo "============================================="
echo ""

# Verificar que la API está corriendo
echo "1️⃣  Verificando que GymAPI está corriendo en puerto 8000..."
if curl -s http://localhost:8000/metrics > /dev/null; then
    echo "   ✅ GymAPI está respondiendo en http://localhost:8000/metrics"
else
    echo "   ⚠️  No se puede conectar a GymAPI en puerto 8000"
    echo "   Asegúrate de que tu aplicación está corriendo: python app_wrapper.py"
    exit 1
fi

echo ""
echo "2️⃣  Necesitas obtener tus credenciales de Grafana Cloud:"
echo "   1. Ve a https://alexmontesino96.grafana.net"
echo "   2. Click en 'My Account' → 'Grafana Cloud Portal'"
echo "   3. En tu stack, busca 'Prometheus' → 'Details'"
echo "   4. Copia el 'Username/Instance ID' y genera un 'API Key'"
echo ""

# Solicitar credenciales
read -p "📝 Ingresa tu Metrics User ID (Username): " METRICS_USER_ID
read -sp "🔐 Ingresa tu API Key (Password): " API_KEY
echo ""

# URL del endpoint (puede variar según la región)
read -p "🌍 Ingresa tu Remote Write URL (ej: https://prometheus-prod-24-prod-eu-west-2.grafana.net/api/prom/push): " REMOTE_URL

# Actualizar el archivo de configuración
echo ""
echo "3️⃣  Actualizando configuración..."
sed -i.bak "s|YOUR_METRICS_USER_ID|$METRICS_USER_ID|g" grafana-agent-config.yml
sed -i.bak "s|YOUR_API_KEY|$API_KEY|g" grafana-agent-config.yml
sed -i.bak "s|https://prometheus-prod-24-prod-eu-west-2.grafana.net/api/prom/push|$REMOTE_URL|g" grafana-agent-config.yml

echo "   ✅ Configuración actualizada"

# Preguntar si quiere iniciar el agent
echo ""
read -p "4️⃣  ¿Quieres iniciar el Grafana Agent ahora? (s/n): " START_AGENT

if [[ $START_AGENT == "s" || $START_AGENT == "S" ]]; then
    echo ""
    echo "🚀 Iniciando Grafana Agent..."
    docker-compose -f docker-compose.grafana-agent.yml up -d

    # Esperar un poco
    sleep 5

    # Verificar estado
    if docker ps | grep -q gymapi_grafana_agent; then
        echo "   ✅ Grafana Agent iniciado correctamente"
        echo ""
        echo "📊 Verifica tus métricas en Grafana Cloud:"
        echo "   1. Ve a https://alexmontesino96.grafana.net"
        echo "   2. Explore → Metrics browser"
        echo "   3. Busca métricas que empiecen con 'gymapi_'"
        echo ""
        echo "🔍 Ver logs del agent:"
        echo "   docker-compose -f docker-compose.grafana-agent.yml logs -f"
    else
        echo "   ❌ Error al iniciar Grafana Agent"
        echo "   Revisa los logs con: docker-compose -f docker-compose.grafana-agent.yml logs"
    fi
else
    echo ""
    echo "📝 Para iniciar el agent manualmente:"
    echo "   docker-compose -f docker-compose.grafana-agent.yml up -d"
fi

echo ""
echo "✅ Configuración completa!"