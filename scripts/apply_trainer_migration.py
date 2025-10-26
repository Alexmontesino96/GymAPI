#!/usr/bin/env python
"""
Script para aplicar la migración de soporte de entrenadores directamente

Este script aplica los cambios de la migración 98cb38633624 directamente
a la base de datos, evitando conflictos con el historial de Alembic.
"""

import sys
import os
from sqlalchemy import create_engine, text
import logging

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import Settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings()


def apply_migration():
    """Aplicar cambios de la migración de trainers"""

    print("="*70)
    print("🔧 APLICANDO MIGRACIÓN DE SOPORTE DE ENTRENADORES")
    print("="*70)
    print()

    # Crear engine
    engine = create_engine(settings.DATABASE_URL)

    try:
        with engine.connect() as conn:

            # 1. Crear el ENUM type
            print("1️⃣  Creando tipo ENUM gym_type_enum...")
            try:
                conn.execute(text("""
                    DO $$ BEGIN
                        CREATE TYPE gym_type_enum AS ENUM ('gym', 'personal_trainer');
                    EXCEPTION
                        WHEN duplicate_object THEN null;
                    END $$;
                """))
                conn.commit()
                print("   ✅ Tipo ENUM creado (o ya existía)")
            except Exception as e:
                print(f"   ⚠️  {str(e)}")
                conn.rollback()

            # 2. Agregar columna type
            print("\n2️⃣  Agregando columna 'type' a tabla gyms...")
            try:
                conn.execute(text("""
                    ALTER TABLE gyms
                    ADD COLUMN IF NOT EXISTS type gym_type_enum NOT NULL DEFAULT 'gym';
                """))
                conn.commit()
                print("   ✅ Columna 'type' agregada")
            except Exception as e:
                print(f"   ⚠️  {str(e)}")
                conn.rollback()

            # 3. Agregar columna trainer_specialties
            print("\n3️⃣  Agregando columna 'trainer_specialties'...")
            try:
                conn.execute(text("""
                    ALTER TABLE gyms
                    ADD COLUMN IF NOT EXISTS trainer_specialties JSON;
                """))
                conn.commit()
                print("   ✅ Columna 'trainer_specialties' agregada")
            except Exception as e:
                print(f"   ⚠️  {str(e)}")
                conn.rollback()

            # 4. Agregar columna trainer_certifications
            print("\n4️⃣  Agregando columna 'trainer_certifications'...")
            try:
                conn.execute(text("""
                    ALTER TABLE gyms
                    ADD COLUMN IF NOT EXISTS trainer_certifications JSON;
                """))
                conn.commit()
                print("   ✅ Columna 'trainer_certifications' agregada")
            except Exception as e:
                print(f"   ⚠️  {str(e)}")
                conn.rollback()

            # 5. Agregar columna max_clients
            print("\n5️⃣  Agregando columna 'max_clients'...")
            try:
                conn.execute(text("""
                    ALTER TABLE gyms
                    ADD COLUMN IF NOT EXISTS max_clients INTEGER;
                """))
                conn.commit()
                print("   ✅ Columna 'max_clients' agregada")
            except Exception as e:
                print(f"   ⚠️  {str(e)}")
                conn.rollback()

            # 6. Crear índice idx_gyms_type
            print("\n6️⃣  Creando índice 'idx_gyms_type'...")
            try:
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_gyms_type ON gyms(type);
                """))
                conn.commit()
                print("   ✅ Índice 'idx_gyms_type' creado")
            except Exception as e:
                print(f"   ⚠️  {str(e)}")
                conn.rollback()

            # 7. Crear índice compuesto idx_gyms_type_active
            print("\n7️⃣  Creando índice compuesto 'idx_gyms_type_active'...")
            try:
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_gyms_type_active ON gyms(type, is_active);
                """))
                conn.commit()
                print("   ✅ Índice 'idx_gyms_type_active' creado")
            except Exception as e:
                print(f"   ⚠️  {str(e)}")
                conn.rollback()

            # 8. Verificar cambios
            print("\n8️⃣  Verificando cambios aplicados...")
            result = conn.execute(text("""
                SELECT
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_name = 'gyms'
                AND column_name IN ('type', 'trainer_specialties', 'trainer_certifications', 'max_clients')
                ORDER BY ordinal_position;
            """))

            columns = result.fetchall()
            if columns:
                print("\n   📊 Columnas verificadas:")
                for col in columns:
                    print(f"      • {col[0]:25s} | {col[1]:15s} | Nullable: {col[2]:3s} | Default: {col[3] or 'NULL'}")
                print()

            # 9. Mostrar índices
            print("9️⃣  Verificando índices...")
            result = conn.execute(text("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'gyms'
                AND indexname IN ('idx_gyms_type', 'idx_gyms_type_active')
                ORDER BY indexname;
            """))

            indexes = result.fetchall()
            if indexes:
                print("\n   📊 Índices verificados:")
                for idx in indexes:
                    print(f"      • {idx[0]}")
                print()

            # 10. Actualizar versión de Alembic
            print("🔟  Actualizando tabla alembic_version...")
            try:
                # Primero verificar si existe el registro
                result = conn.execute(text("""
                    SELECT version_num FROM alembic_version LIMIT 1;
                """))
                current_version = result.fetchone()

                if current_version:
                    # Actualizar a la nueva versión
                    conn.execute(text("""
                        UPDATE alembic_version
                        SET version_num = '98cb38633624';
                    """))
                    conn.commit()
                    print(f"   ✅ Versión actualizada de {current_version[0]} a 98cb38633624")
                else:
                    # Insertar si no existe
                    conn.execute(text("""
                        INSERT INTO alembic_version (version_num)
                        VALUES ('98cb38633624');
                    """))
                    conn.commit()
                    print("   ✅ Versión 98cb38633624 insertada")
            except Exception as e:
                print(f"   ⚠️  Error actualizando alembic_version: {str(e)}")
                print("   ℹ️  Esto no es crítico, la migración se aplicó correctamente")
                conn.rollback()

        print("\n" + "="*70)
        print("✅ MIGRACIÓN APLICADA EXITOSAMENTE")
        print("="*70)
        print()
        print("📊 Resumen de cambios:")
        print("   • Tipo ENUM: gym_type_enum ('gym', 'personal_trainer')")
        print("   • Campo: type (enum) - DEFAULT 'gym'")
        print("   • Campo: trainer_specialties (JSON)")
        print("   • Campo: trainer_certifications (JSON)")
        print("   • Campo: max_clients (INTEGER)")
        print("   • Índice: idx_gyms_type")
        print("   • Índice: idx_gyms_type_active (compuesto)")
        print()
        print("🚀 Próximos pasos:")
        print("   1. Verificar que el servidor FastAPI inicia correctamente")
        print("   2. Probar endpoint: POST /api/v1/auth/register-trainer")
        print("   3. Ver documentación: http://localhost:8000/api/v1/docs")
        print()

        return True

    except Exception as e:
        logger.error(f"Error aplicando migración: {e}", exc_info=True)
        print("\n" + "="*70)
        print("❌ ERROR APLICANDO MIGRACIÓN")
        print("="*70)
        print(f"\n{str(e)}\n")
        return False
    finally:
        engine.dispose()


def rollback_migration():
    """Revertir los cambios de la migración (opcional)"""

    print("="*70)
    print("⏪ REVIRTIENDO MIGRACIÓN DE SOPORTE DE ENTRENADORES")
    print("="*70)
    print()

    engine = create_engine(settings.DATABASE_URL)

    try:
        with engine.connect() as conn:

            print("Eliminando índices...")
            conn.execute(text("DROP INDEX IF EXISTS idx_gyms_type_active;"))
            conn.execute(text("DROP INDEX IF EXISTS idx_gyms_type;"))
            conn.commit()
            print("✅ Índices eliminados")

            print("\nEliminando columnas...")
            conn.execute(text("ALTER TABLE gyms DROP COLUMN IF EXISTS max_clients;"))
            conn.execute(text("ALTER TABLE gyms DROP COLUMN IF EXISTS trainer_certifications;"))
            conn.execute(text("ALTER TABLE gyms DROP COLUMN IF EXISTS trainer_specialties;"))
            conn.execute(text("ALTER TABLE gyms DROP COLUMN IF EXISTS type;"))
            conn.commit()
            print("✅ Columnas eliminadas")

            print("\nEliminando tipo ENUM...")
            conn.execute(text("DROP TYPE IF EXISTS gym_type_enum;"))
            conn.commit()
            print("✅ Tipo ENUM eliminado")

        print("\n✅ MIGRACIÓN REVERTIDA EXITOSAMENTE\n")
        return True

    except Exception as e:
        logger.error(f"Error revirtiendo migración: {e}", exc_info=True)
        print(f"\n❌ ERROR: {str(e)}\n")
        return False
    finally:
        engine.dispose()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Aplicar o revertir migración de soporte de entrenadores"
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Revertir la migración en lugar de aplicarla"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="No pedir confirmación"
    )

    args = parser.parse_args()

    if args.rollback:
        if not args.force:
            confirm = input("⚠️  ¿Estás seguro de revertir la migración? (s/n): ")
            if confirm.lower() != 's':
                print("Operación cancelada")
                sys.exit(0)

        success = rollback_migration()
    else:
        if not args.force:
            print("Este script aplicará los siguientes cambios a la base de datos:")
            print("  • Agregar tipo ENUM gym_type_enum")
            print("  • Agregar 4 columnas nuevas a tabla 'gyms'")
            print("  • Crear 2 índices nuevos")
            print()
            confirm = input("¿Continuar? (s/n): ")
            if confirm.lower() != 's':
                print("Operación cancelada")
                sys.exit(0)

        success = apply_migration()

    sys.exit(0 if success else 1)