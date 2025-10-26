#!/usr/bin/env python
"""
Script para diagnosticar y corregir el problema del ENUM gym_type_enum

El problema:
- El modelo Python espera valores: 'gym', 'personal_trainer' (minúsculas)
- El enum PostgreSQL en producción tiene: 'GYM', 'PERSONAL_TRAINER' (mayúsculas)

Este script:
1. Diagnostica el estado actual del enum
2. Corrige los valores en la tabla gyms
3. Recrea el enum con los valores correctos
"""

import sys
import os
from sqlalchemy import create_engine, text
import logging

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


def diagnose_enum():
    """Diagnosticar el estado actual del enum"""
    print("="*70)
    print("🔍 DIAGNÓSTICO DEL ENUM gym_type_enum")
    print("="*70)
    print()

    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

    try:
        with engine.connect() as conn:
            # 1. Verificar si el enum existe
            print("1️⃣  Verificando existencia del enum...")
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_type WHERE typname = 'gym_type_enum'
                );
            """))
            exists = result.scalar()

            if not exists:
                print("   ❌ El enum gym_type_enum NO existe")
                return False

            print("   ✅ El enum gym_type_enum existe")

            # 2. Obtener valores del enum
            print("\n2️⃣  Obteniendo valores del enum...")
            result = conn.execute(text("""
                SELECT e.enumlabel
                FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'gym_type_enum'
                ORDER BY e.enumsortorder;
            """))

            enum_values = [row[0] for row in result.fetchall()]
            print(f"   📊 Valores actuales: {enum_values}")

            # 3. Verificar datos en la tabla gyms
            print("\n3️⃣  Verificando datos en tabla gyms...")
            result = conn.execute(text("""
                SELECT type, COUNT(*) as count
                FROM gyms
                WHERE type IS NOT NULL
                GROUP BY type;
            """))

            data_values = result.fetchall()
            if data_values:
                print("   📊 Valores en la tabla:")
                for val, count in data_values:
                    print(f"      • '{val}': {count} registros")
            else:
                print("   ℹ️  No hay datos con valores de type")

            # 4. Verificar incompatibilidad
            print("\n4️⃣  Análisis de compatibilidad...")
            expected_values = ['gym', 'personal_trainer']
            current_values = enum_values

            if set(current_values) == set(expected_values):
                print("   ✅ El enum tiene los valores correctos (minúsculas)")
                return True
            else:
                print("   ❌ El enum tiene valores INCORRECTOS")
                print(f"      Esperados: {expected_values}")
                print(f"      Actuales:  {current_values}")
                return False

    except Exception as e:
        logger.error(f"Error en diagnóstico: {e}", exc_info=True)
        return False
    finally:
        engine.dispose()


def fix_enum():
    """Corregir el enum y los datos"""
    print("\n" + "="*70)
    print("🔧 CORRECCIÓN DEL ENUM gym_type_enum")
    print("="*70)
    print()

    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

    try:
        with engine.connect() as conn:

            # 1. Crear enum temporal con valores correctos
            print("1️⃣  Creando enum temporal con valores correctos...")
            try:
                conn.execute(text("""
                    CREATE TYPE gym_type_enum_temp AS ENUM ('gym', 'personal_trainer');
                """))
                conn.commit()
                print("   ✅ Enum temporal creado")
            except Exception as e:
                print(f"   ⚠️  {str(e)}")
                conn.rollback()

            # 2. Convertir columna type a tipo temporal
            print("\n2️⃣  Convirtiendo columna type al enum temporal...")
            try:
                # Primero, convertir a VARCHAR para hacer el mapeo
                conn.execute(text("""
                    ALTER TABLE gyms
                    ALTER COLUMN type TYPE VARCHAR(50) USING type::text;
                """))
                conn.commit()
                print("   ✅ Columna convertida a VARCHAR")

                # Convertir valores a minúsculas si están en mayúsculas
                result = conn.execute(text("""
                    UPDATE gyms
                    SET type = CASE
                        WHEN type = 'GYM' THEN 'gym'
                        WHEN type = 'PERSONAL_TRAINER' THEN 'personal_trainer'
                        ELSE LOWER(type)
                    END
                    WHERE type IS NOT NULL;
                """))
                rows_updated = result.rowcount
                conn.commit()
                print(f"   ✅ {rows_updated} registros normalizados a minúsculas")

                # Ahora convertir a enum temporal
                conn.execute(text("""
                    ALTER TABLE gyms
                    ALTER COLUMN type TYPE gym_type_enum_temp
                    USING type::gym_type_enum_temp;
                """))
                conn.commit()
                print("   ✅ Columna convertida al enum temporal")

            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
                conn.rollback()
                raise

            # 3. Eliminar enum viejo
            print("\n3️⃣  Eliminando enum viejo...")
            try:
                conn.execute(text("DROP TYPE IF EXISTS gym_type_enum CASCADE;"))
                conn.commit()
                print("   ✅ Enum viejo eliminado")
            except Exception as e:
                print(f"   ⚠️  {str(e)}")
                conn.rollback()

            # 4. Renombrar enum temporal al nombre correcto
            print("\n4️⃣  Renombrando enum temporal...")
            try:
                conn.execute(text("""
                    ALTER TYPE gym_type_enum_temp RENAME TO gym_type_enum;
                """))
                conn.commit()
                print("   ✅ Enum renombrado correctamente")
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
                conn.rollback()
                raise

            # 5. Actualizar la columna para usar el tipo correcto
            print("\n5️⃣  Actualizando definición de columna...")
            try:
                conn.execute(text("""
                    ALTER TABLE gyms
                    ALTER COLUMN type TYPE gym_type_enum
                    USING type::text::gym_type_enum;
                """))
                conn.commit()
                print("   ✅ Columna actualizada")
            except Exception as e:
                print(f"   ⚠️  {str(e)}")
                conn.rollback()

            # 6. Recrear índice si es necesario
            print("\n6️⃣  Recreando índice...")
            try:
                conn.execute(text("DROP INDEX IF EXISTS idx_gyms_type;"))
                conn.execute(text("CREATE INDEX idx_gyms_type ON gyms(type);"))
                conn.commit()
                print("   ✅ Índice recreado")
            except Exception as e:
                print(f"   ⚠️  {str(e)}")
                conn.rollback()

            # 7. Verificar resultado
            print("\n7️⃣  Verificando corrección...")
            result = conn.execute(text("""
                SELECT e.enumlabel
                FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'gym_type_enum'
                ORDER BY e.enumsortorder;
            """))

            enum_values = [row[0] for row in result.fetchall()]
            print(f"   📊 Valores del enum: {enum_values}")

            result = conn.execute(text("""
                SELECT type, COUNT(*) as count
                FROM gyms
                GROUP BY type;
            """))

            data_values = result.fetchall()
            print("   📊 Valores en la tabla:")
            for val, count in data_values:
                print(f"      • '{val}': {count} registros")

        print("\n" + "="*70)
        print("✅ CORRECCIÓN COMPLETADA EXITOSAMENTE")
        print("="*70)
        print()
        print("🎉 El enum gym_type_enum ahora tiene los valores correctos:")
        print("   • 'gym'")
        print("   • 'personal_trainer'")
        print()
        print("📝 IMPORTANTE: Reinicia el servidor FastAPI para que los cambios surtan efecto")
        print()

        return True

    except Exception as e:
        logger.error(f"Error corrigiendo enum: {e}", exc_info=True)
        print("\n" + "="*70)
        print("❌ ERROR EN LA CORRECCIÓN")
        print("="*70)
        print(f"\n{str(e)}\n")
        return False
    finally:
        engine.dispose()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Diagnosticar y corregir el enum gym_type_enum"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Aplicar la corrección (sin esto solo hace diagnóstico)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="No pedir confirmación"
    )

    args = parser.parse_args()

    # Primero siempre hacer diagnóstico
    is_correct = diagnose_enum()

    if is_correct:
        print("\n✅ El enum está correcto, no se necesita corrección")
        sys.exit(0)

    if not args.fix:
        print("\n" + "="*70)
        print("ℹ️  Para corregir el problema, ejecuta:")
        print("   python scripts/fix_gym_type_enum.py --fix")
        print("="*70)
        sys.exit(1)

    # Pedir confirmación
    if not args.force:
        print("\n⚠️  ADVERTENCIA: Este script modificará la estructura de la base de datos")
        print("   Se recomienda hacer un backup antes de continuar")
        print()
        confirm = input("¿Continuar con la corrección? (s/n): ")
        if confirm.lower() != 's':
            print("Operación cancelada")
            sys.exit(0)

    # Aplicar corrección
    success = fix_enum()
    sys.exit(0 if success else 1)
