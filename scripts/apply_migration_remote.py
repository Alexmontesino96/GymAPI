"""
Script para aplicar migración de columnas de cancelación de eventos directamente a la BD de producción.

Este script agrega las columnas necesarias para auditoría de cancelaciones:
- cancellation_date
- cancelled_by_user_id
- cancellation_reason
- total_refunded_cents

Uso:
    python scripts/apply_migration_remote.py
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def apply_cancellation_columns():
    """Aplicar columnas de auditoría de cancelación a la tabla events."""

    # Obtener DATABASE_URL
    database_url = os.environ.get('DATABASE_URL')

    if not database_url:
        print("❌ ERROR: DATABASE_URL no encontrada en variables de entorno")
        print("Asegúrate de tener un archivo .env con DATABASE_URL de producción")
        sys.exit(1)

    print("🔗 Conectando a base de datos de producción...")
    print(f"   URL: {database_url[:30]}...")

    try:
        # Crear conexión
        engine = create_engine(database_url)

        with engine.connect() as conn:
            print("\n📋 Iniciando aplicación de migración...")

            with conn.begin():
                # 1. Agregar columna cancellation_date
                print("   ➕ Agregando columna: cancellation_date")
                conn.execute(text("""
                    ALTER TABLE events
                    ADD COLUMN IF NOT EXISTS cancellation_date TIMESTAMP WITH TIME ZONE;
                """))

                # 2. Agregar columna cancelled_by_user_id
                print("   ➕ Agregando columna: cancelled_by_user_id")
                conn.execute(text("""
                    ALTER TABLE events
                    ADD COLUMN IF NOT EXISTS cancelled_by_user_id INTEGER;
                """))

                # 3. Agregar columna cancellation_reason
                print("   ➕ Agregando columna: cancellation_reason")
                conn.execute(text("""
                    ALTER TABLE events
                    ADD COLUMN IF NOT EXISTS cancellation_reason TEXT;
                """))

                # 4. Agregar columna total_refunded_cents
                print("   ➕ Agregando columna: total_refunded_cents")
                conn.execute(text("""
                    ALTER TABLE events
                    ADD COLUMN IF NOT EXISTS total_refunded_cents INTEGER;
                """))

                # 5. Agregar comentarios a las columnas
                print("   📝 Agregando comentarios a columnas...")
                conn.execute(text("""
                    COMMENT ON COLUMN events.cancellation_date IS 'Fecha en que el evento fue cancelado';
                    COMMENT ON COLUMN events.cancelled_by_user_id IS 'ID del usuario que canceló el evento (admin/owner)';
                    COMMENT ON COLUMN events.cancellation_reason IS 'Razón de la cancelación del evento';
                    COMMENT ON COLUMN events.total_refunded_cents IS 'Total de dinero reembolsado en cancelación masiva (en centavos)';
                """))

                # 6. Crear foreign key constraint
                print("   🔗 Creando foreign key constraint...")
                try:
                    conn.execute(text("""
                        ALTER TABLE events
                        ADD CONSTRAINT fk_events_cancelled_by_user_id
                        FOREIGN KEY (cancelled_by_user_id) REFERENCES "user"(id);
                    """))
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print("      ℹ️  Foreign key ya existe, saltando...")
                    else:
                        raise

                # 7. Crear índice
                print("   📇 Creando índice ix_events_cancelled_by_user_id...")
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_events_cancelled_by_user_id
                    ON events (cancelled_by_user_id);
                """))

                print("\n✅ Migración aplicada exitosamente!")

        # Verificar que las columnas existen
        print("\n🔍 Verificando columnas agregadas...")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'events'
                AND column_name IN ('cancellation_date', 'cancelled_by_user_id', 'cancellation_reason', 'total_refunded_cents')
                ORDER BY column_name;
            """))

            columns = result.fetchall()
            if len(columns) == 4:
                print("✅ Todas las columnas verificadas:")
                for col in columns:
                    print(f"   • {col[0]}: {col[1]} (nullable: {col[2]})")
            else:
                print(f"⚠️  Solo se encontraron {len(columns)} de 4 columnas")
                for col in columns:
                    print(f"   • {col[0]}")

        print("\n🎉 ¡Migración completada con éxito!")
        print("   La API debería estar funcionando ahora.")

    except Exception as e:
        print(f"\n❌ ERROR al aplicar migración: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 70)
    print("  APLICAR MIGRACIÓN DE AUDITORÍA DE CANCELACIÓN DE EVENTOS")
    print("=" * 70)
    print()

    # Confirmar antes de ejecutar
    response = input("⚠️  Esto modificará la base de datos de PRODUCCIÓN. ¿Continuar? (yes/no): ")

    if response.lower() in ['yes', 'y', 'si', 's']:
        apply_cancellation_columns()
    else:
        print("❌ Operación cancelada por el usuario")
        sys.exit(0)
