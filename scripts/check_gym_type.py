#!/usr/bin/env python
"""
Script para verificar el estado del enum gym_type_enum
"""

import sys
import os
from sqlalchemy import create_engine, text

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings

settings = get_settings()

def check():
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

    with engine.connect() as conn:
        print("="*70)
        print("🔍 VERIFICACIÓN DEL ENUM gym_type_enum")
        print("="*70)
        print()

        # 1. Verificar valores del ENUM type en PostgreSQL
        print("1️⃣  DEFINICIÓN DEL ENUM en PostgreSQL:")
        print("   (Los valores PERMITIDOS por el tipo de dato)")
        print()

        result = conn.execute(text("""
            SELECT e.enumlabel
            FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = 'gym_type_enum'
            ORDER BY e.enumsortorder;
        """))

        enum_values = result.fetchall()
        if enum_values:
            for val in enum_values:
                print(f"   • '{val[0]}'")
        else:
            print("   ❌ El enum NO existe")

        print()
        print("-"*70)
        print()

        # 2. Verificar datos REALES en la tabla
        print("2️⃣  DATOS REALES en la tabla gyms:")
        print("   (Los valores ACTUALES almacenados)")
        print()

        try:
            result = conn.execute(text("""
                SELECT id, name, type::text
                FROM gyms
                LIMIT 10;
            """))

            rows = result.fetchall()
            if rows:
                for row in rows:
                    print(f"   ID: {row[0]:3d} | Nombre: {row[1]:30s} | Type: '{row[2]}'")
            else:
                print("   ℹ️  No hay datos en la tabla")
        except Exception as e:
            print(f"   ❌ Error al leer datos: {e}")

        print()
        print("="*70)
        print()

        # 3. Conclusión
        if enum_values:
            enum_vals = [v[0] for v in enum_values]
            expected = ['gym', 'personal_trainer']

            if set(enum_vals) == set(expected):
                print("✅ El ENUM tiene los valores correctos (minúsculas)")
            else:
                print("❌ PROBLEMA DETECTADO:")
                print(f"   Enum actual:  {enum_vals}")
                print(f"   Enum esperado: {expected}")
                print()
                print("   Para corregir, ejecuta:")
                print("   python scripts/fix_gym_type_enum.py --fix")

    engine.dispose()

if __name__ == "__main__":
    check()
