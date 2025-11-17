"""
Script para migrar las columnas de timestamp en las tablas de stories
a timezone-aware (TIMESTAMPTZ en PostgreSQL).

Este script actualiza todas las columnas de DateTime en las tablas:
- stories
- story_views
- story_reactions
- story_reports
- story_highlights
- story_highlight_items

IMPORTANTE: Ejecutar este script DESPUÉS de haber actualizado el código
con los modelos que usan DateTime(timezone=True).
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path para poder importar app
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from sqlalchemy import text
from app.db.session import engine


async def migrate_story_timezones():
    """Migra todas las columnas de datetime a timezone-aware"""

    migrations = [
        # Tabla stories
        ("stories", [
            "created_at",
            "expires_at",
            "deleted_at",
            "updated_at"
        ]),

        # Tabla story_views
        ("story_views", [
            "viewed_at"
        ]),

        # Tabla story_reactions
        ("story_reactions", [
            "created_at"
        ]),

        # Tabla story_reports
        ("story_reports", [
            "created_at",
            "reviewed_at"
        ]),

        # Tabla story_highlights
        ("story_highlights", [
            "created_at",
            "updated_at"
        ]),

        # Tabla story_highlight_items
        ("story_highlight_items", [
            "added_at"
        ])
    ]

    with engine.connect() as conn:
        print("Iniciando migración de timezones...")

        for table_name, columns in migrations:
            print(f"\nActualizando tabla {table_name}...")

            for column_name in columns:
                try:
                    # Verificar si la columna existe
                    check_sql = text(f"""
                        SELECT column_name, data_type
                        FROM information_schema.columns
                        WHERE table_name = :table_name
                        AND column_name = :column_name
                    """)

                    result = conn.execute(
                        check_sql,
                        {"table_name": table_name, "column_name": column_name}
                    )
                    column_info = result.fetchone()

                    if not column_info:
                        print(f"  ⚠️  Columna {column_name} no existe, omitiendo...")
                        continue

                    current_type = column_info[1]

                    # Si ya es TIMESTAMPTZ, omitir
                    if current_type == 'timestamp with time zone':
                        print(f"  ✓  {column_name} ya es timezone-aware")
                        continue

                    # Convertir a TIMESTAMPTZ
                    # Asumimos que los timestamps sin timezone son UTC
                    alter_sql = text(f"""
                        ALTER TABLE {table_name}
                        ALTER COLUMN {column_name}
                        TYPE TIMESTAMP WITH TIME ZONE
                        USING {column_name} AT TIME ZONE 'UTC'
                    """)

                    conn.execute(alter_sql)
                    conn.commit()

                    print(f"  ✓  {column_name}: {current_type} -> timestamp with time zone")

                except Exception as e:
                    print(f"  ✗  Error en {column_name}: {str(e)}")
                    conn.rollback()

        print("\n✅ Migración completada!")


def main():
    """Punto de entrada del script"""
    import sys

    print("=" * 60)
    print("MIGRACIÓN DE TIMESTAMPS A TIMEZONE-AWARE")
    print("=" * 60)
    print("\nEste script convertirá todas las columnas de timestamp")
    print("en las tablas de stories a TIMESTAMPTZ (timezone-aware).")
    print("\n⚠️  IMPORTANTE: Hacer backup de la BD antes de ejecutar")
    print("=" * 60)

    # Verificar si se pasó --yes como argumento
    if '--yes' in sys.argv or '-y' in sys.argv:
        print("\n✓ Ejecución automática confirmada con --yes")
    else:
        try:
            response = input("\n¿Deseas continuar? (si/no): ")
            if response.lower() not in ['si', 'sí', 's', 'yes', 'y']:
                print("Operación cancelada.")
                return
        except EOFError:
            print("\n✗ No se puede pedir confirmación en modo no interactivo.")
            print("Usa --yes para ejecutar automáticamente: python scripts/fix_story_timezones.py --yes")
            return

    asyncio.run(migrate_story_timezones())


if __name__ == "__main__":
    main()
