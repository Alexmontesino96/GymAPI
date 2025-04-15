#!/usr/bin/env bash
# Script de inicio para Render

# Esperar 5 segundos para asegurar que los servicios estén listos
sleep 5

# Mostrar información de depuración
echo "DEBUG: Iniciando aplicación en modo depuración"
echo "DEBUG: Entorno Python: $(which python) ($(python --version))"
echo "DEBUG: Variables de entorno disponibles: PORT=$PORT, DEBUG_MODE=$DEBUG_MODE"

# Ejecutar migraciones de base de datos (descomenta si usas Alembic)
# python -m alembic upgrade head

# Iniciar la aplicación con gunicorn en modo debug
exec gunicorn app.main:app \
    --bind 0.0.0.0:$PORT \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --access-logfile - \
    --error-logfile - \
    --log-level debug \
    --capture-output \
    --enable-stdio-inheritance 