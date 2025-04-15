#!/usr/bin/env bash
# Script de inicio para Render

# Esperar 5 segundos para asegurar que los servicios estén listos
sleep 5

# Mostrar información de depuración
echo "DEBUG: Iniciando aplicación en modo depuración"
echo "DEBUG: Entorno Python: $(which python) ($(python --version))"
echo "DEBUG: Variables de entorno disponibles: PORT=$PORT, DEBUG_MODE=$DEBUG_MODE"

# Verificación de dependencias críticas
echo "DEBUG: Verificando módulos críticos..."
python -c "
import sys
print('Python version:', sys.version)
critical_modules = ['redis', 'redis.asyncio', 'fastapi', 'sqlalchemy', 'gunicorn', 'uvicorn']
missing = []
for module in critical_modules:
    try:
        __import__(module)
        print(f'✅ {module} importado correctamente')
    except ImportError as e:
        missing.append(f'{module}: {e}')
        print(f'❌ Error importando {module}: {e}')
if missing:
    print('ERRORES DE IMPORTACIÓN DETECTADOS:')
    for error in missing:
        print(f' - {error}')
    sys.exit(1)
else:
    print('Todos los módulos críticos verificados correctamente')
"

# Si la verificación falla, el script se detendrá aquí debido al sys.exit(1)

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