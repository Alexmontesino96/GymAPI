#!/bin/bash
# Script para aplicar las tablas de feed ranking manualmente en producción

echo "🔧 Aplicando tablas de feed ranking manualmente..."
echo ""

# Verificar que DATABASE_URL esté configurado
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL no está configurado"
    echo "Configura la variable de entorno antes de ejecutar este script"
    exit 1
fi

echo "📊 Conectando a la base de datos..."
echo ""

# Ejecutar el script SQL
psql "$DATABASE_URL" -f scripts/create_feed_ranking_tables.sql

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Tablas creadas exitosamente"
    echo ""
    echo "📊 Actualizando estado de Alembic..."
    alembic stamp 9268f18fc9bd

    echo ""
    echo "🎉 ¡Listo! Las tablas post_views y user_follows están creadas"
    echo ""
    echo "Ahora puedes probar el endpoint:"
    echo "GET /api/v1/posts/feed/ranked?page=1&debug=true"
else
    echo ""
    echo "❌ ERROR al crear las tablas"
    echo "Revisa los logs arriba para más detalles"
    exit 1
fi
