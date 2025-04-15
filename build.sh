#!/usr/bin/env bash
# Script de construcción para Render

# Salir en caso de error
set -e

# Instalar dependencias
pip install -r requirements.txt

# Asegurar que los directorios necesarios existen
mkdir -p logs

# Potenciales migraciones de base de datos 
# (deshabilitado por defecto; activar solo si estás seguro)
# python -m alembic upgrade head

echo "¡Construcción completada!" 