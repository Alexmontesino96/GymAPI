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
pip install --upgrade pip  # Actualizar pip primero
pip install -r requirements.txt

# Verificar que el paquete redis está instalado correctamente
echo "======== VERIFICANDO DEPENDENCIA CRÍTICA: REDIS ========"
if python -c "import redis; print(f'Redis instalado correctamente: version {redis.__version__}')"; then
    echo "✅ Verificación de redis exitosa"
else
    echo "❌ REDIS NO INSTALADO CORRECTAMENTE - Intentando instalar directamente"
    pip install redis==5.0.1 hiredis==2.2.3
    if python -c "import redis; print(f'Redis instalado correctamente: version {redis.__version__}')"; then
        echo "✅ Instalación directa de redis exitosa"
    else
        echo "❌ FALLO CRÍTICO: No se pudo instalar redis"
        exit 1  # Fallar el build explícitamente
    fi
fi

# Asegurar que los directorios necesarios existen
mkdir -p logs

# Verificar que start.sh sea ejecutable
chmod +x start.sh
echo "Script de inicio (start.sh) es ejecutable: $(test -x start.sh && echo 'Sí' || echo 'No')"

# Listar paquetes instalados para verificación final
echo "======== PAQUETES INSTALADOS ========"
pip freeze | grep -E 'redis|gunicorn|supabase'
echo "======================================"

# Potenciales migraciones de base de datos 
# (deshabilitado por defecto; activar solo si estás seguro)
# python -m alembic upgrade head

echo "¡Construcción completada!" 