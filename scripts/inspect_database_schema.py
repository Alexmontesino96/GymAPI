#!/usr/bin/env python3
"""
Script para inspeccionar el esquema de la base de datos.
Muestra todas las tablas y sus columnas.
"""

import os
import sys
from sqlalchemy import create_engine, inspect, text

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def inspect_database():
    """Inspeccionar esquema completo de la base de datos"""

    # Obtener DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ ERROR: DATABASE_URL no está configurado")
        sys.exit(1)

    print("🔍 Inspeccionando base de datos...")
    print("")

    # Crear engine e inspector
    engine = create_engine(database_url)
    inspector = inspect(engine)

    # Obtener todas las tablas
    tables = inspector.get_table_names()

    print(f"📊 Total de tablas encontradas: {len(tables)}")
    print("")

    # Tablas relevantes para feed ranking
    relevant_tables = [
        'classes', 'class_participation', 'class_session',
        'posts', 'post_likes', 'post_comments', 'post_tags', 'post_views',
        'user', 'user_follows',
        'trainermemberrelationship'
    ]

    print("=" * 80)
    print("TABLAS RELEVANTES PARA FEED RANKING")
    print("=" * 80)
    print("")

    for table_name in relevant_tables:
        if table_name in tables:
            print(f"✅ Tabla: {table_name}")
            columns = inspector.get_columns(table_name)

            print(f"   Columnas ({len(columns)}):")
            for col in columns:
                col_type = str(col['type'])
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                print(f"      - {col['name']:<30} {col_type:<20} {nullable}")
            print("")
        else:
            print(f"❌ Tabla NO EXISTE: {table_name}")
            print("")

    print("=" * 80)
    print("TODAS LAS TABLAS EN LA BASE DE DATOS")
    print("=" * 80)
    print("")

    for i, table_name in enumerate(sorted(tables), 1):
        print(f"{i:3}. {table_name}")

    print("")
    print("=" * 80)

    # Queries específicas para verificar datos
    print("")
    print("🔬 VERIFICANDO DATOS EN TABLAS CLAVE")
    print("=" * 80)
    print("")

    with engine.connect() as conn:
        # Verificar si existe la tabla classes
        if 'classes' in tables:
            result = conn.execute(text("SELECT COUNT(*) as count FROM classes LIMIT 1"))
            count = result.fetchone()[0]
            print(f"✓ classes: {count} registros")

            # Ver columnas de classes
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'classes' ORDER BY ordinal_position"))
            cols = [row[0] for row in result.fetchall()]
            print(f"  Columnas: {', '.join(cols)}")
        else:
            print("✗ Tabla 'classes' NO EXISTE")

        print("")

        # Verificar class_participation
        if 'class_participation' in tables:
            result = conn.execute(text("SELECT COUNT(*) as count FROM class_participation LIMIT 1"))
            count = result.fetchone()[0]
            print(f"✓ class_participation: {count} registros")

            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'class_participation' ORDER BY ordinal_position"))
            cols = [row[0] for row in result.fetchall()]
            print(f"  Columnas: {', '.join(cols)}")
        else:
            print("✗ Tabla 'class_participation' NO EXISTE")

        print("")

        # Verificar posts
        if 'posts' in tables:
            result = conn.execute(text("SELECT COUNT(*) as count FROM posts LIMIT 1"))
            count = result.fetchone()[0]
            print(f"✓ posts: {count} registros")

        print("")

        # Verificar post_views (nueva tabla)
        if 'post_views' in tables:
            result = conn.execute(text("SELECT COUNT(*) as count FROM post_views LIMIT 1"))
            count = result.fetchone()[0]
            print(f"✓ post_views: {count} registros (NUEVA TABLA ✨)")
        else:
            print("✗ Tabla 'post_views' NO EXISTE (debería estar creada)")

        print("")

        # Verificar user_follows (nueva tabla)
        if 'user_follows' in tables:
            result = conn.execute(text("SELECT COUNT(*) as count FROM user_follows LIMIT 1"))
            count = result.fetchone()[0]
            print(f"✓ user_follows: {count} registros (NUEVA TABLA ✨)")
        else:
            print("✗ Tabla 'user_follows' NO EXISTE (debería estar creada)")

    print("")
    print("=" * 80)
    print("✅ Inspección completada")
    print("")


if __name__ == "__main__":
    inspect_database()
