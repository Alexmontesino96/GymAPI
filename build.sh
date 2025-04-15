#!/usr/bin/env bash
# Script de construcción para Render

# Salir en caso de error
set -e

# Información de depuración
echo "======== INFORMACIÓN DE ENTORNO ========"
echo "Python version: $(python --version)"
echo "Pip version: $(pip --version)"
echo "Directorio de trabajo: $(pwd)"
echo "Contenido del directorio:"
ls -la
echo "========================================"

# Instalar dependencias
echo "Instalando dependencias..."
pip install -r requirements.txt

# Asegurar que los directorios necesarios existen
mkdir -p logs

# Verificar que start.sh sea ejecutable
chmod +x start.sh
echo "Script de inicio (start.sh) es ejecutable: $(test -x start.sh && echo 'Sí' || echo 'No')"

# Potenciales migraciones de base de datos 
# (deshabilitado por defecto; activar solo si estás seguro)
# python -m alembic upgrade head

echo "¡Construcción completada!" 