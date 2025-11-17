#!/bin/bash
# Script para ejecutar migraciones en producción (Render)

echo "🔄 Ejecutando migraciones de Alembic en producción..."
echo ""
echo "Este script ejecutará: alembic upgrade head"
echo ""

# Verificar que alembic esté instalado
if ! command -v alembic &> /dev/null; then
    echo "❌ ERROR: alembic no está instalado"
    exit 1
fi

# Mostrar estado actual
echo "📊 Estado actual de migraciones:"
alembic current

echo ""
echo "📋 Migraciones pendientes:"
alembic history --verbose | head -20

echo ""
read -p "¿Deseas aplicar las migraciones pendientes? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "⚡ Aplicando migraciones..."
    alembic upgrade head

    if [ $? -eq 0 ]; then
        echo "✅ Migraciones aplicadas exitosamente"
        echo ""
        echo "📊 Estado final:"
        alembic current
    else
        echo "❌ ERROR al aplicar migraciones"
        exit 1
    fi
else
    echo "❌ Operación cancelada"
    exit 0
fi
