#!/bin/bash

echo "📦 Instalando Grafana Agent localmente (sin Docker)"
echo "===================================================="

# Detectar sistema operativo
OS=$(uname -s)
ARCH=$(uname -m)

if [[ "$OS" == "Darwin" ]]; then
    # macOS
    if command -v brew &> /dev/null; then
        echo "🍺 Instalando con Homebrew..."
        brew install grafana-agent

        echo "✅ Grafana Agent instalado!"
    else
        echo "📥 Descargando Grafana Agent para macOS..."

        # Determinar arquitectura
        if [[ "$ARCH" == "arm64" ]]; then
            # Apple Silicon (M1/M2)
            DOWNLOAD_URL="https://github.com/grafana/agent/releases/latest/download/grafana-agent-darwin-arm64.zip"
        else
            # Intel Mac
            DOWNLOAD_URL="https://github.com/grafana/agent/releases/latest/download/grafana-agent-darwin-amd64.zip"
        fi

        curl -L -O $DOWNLOAD_URL
        unzip -o grafana-agent-*.zip
        chmod +x grafana-agent-*

        # Mover al directorio actual
        mv grafana-agent-* grafana-agent
        rm -f *.zip

        echo "✅ Grafana Agent descargado!"
    fi
else
    # Linux
    echo "📥 Descargando Grafana Agent para Linux..."
    curl -L -O "https://github.com/grafana/agent/releases/latest/download/grafana-agent-linux-amd64.zip"
    unzip -o grafana-agent-linux-amd64.zip
    chmod +x grafana-agent-linux-amd64
    mv grafana-agent-linux-amd64 grafana-agent
    rm -f *.zip

    echo "✅ Grafana Agent descargado!"
fi

echo ""
echo "🚀 Iniciando Grafana Agent..."
echo "================================"

# Verificar que GymAPI está corriendo
if curl -s http://localhost:8000/metrics > /dev/null; then
    echo "✓ GymAPI respondiendo en puerto 8000"
else
    echo "⚠️ GymAPI no responde. Asegúrate de ejecutar: python app_wrapper.py"
fi

echo ""
echo "📊 Ejecutando Grafana Agent..."
echo "Presiona Ctrl+C para detener"
echo ""

# Ejecutar Grafana Agent
if command -v grafana-agent &> /dev/null; then
    # Si se instaló con brew
    grafana-agent -config.file=grafana-agent-final.yml
else
    # Si se descargó manualmente
    ./grafana-agent -config.file=grafana-agent-final.yml
fi