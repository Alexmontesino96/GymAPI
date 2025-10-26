#!/usr/bin/env python
"""
Script para listar TODOS los enums en PostgreSQL
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
        print("🔍 TODOS LOS ENUMS EN POSTGRESQL")
        print("="*70)
        print()

        # Obtener todos los enums
        result = conn.execute(text("""
            SELECT
                t.typname as enum_name,
                STRING_AGG(e.enumlabel, ', ' ORDER BY e.enumsortorder) as values
            FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            GROUP BY t.typname
            ORDER BY t.typname;
        """))

        enums = result.fetchall()

        if enums:
            print(f"📊 Se encontraron {len(enums)} enum(s):")
            print()
            for enum_name, values in enums:
                print(f"   {enum_name}:")
                print(f"      Valores: {values}")
                print()
        else:
            print("   ℹ️  No se encontraron enums")

        print("="*70)

    engine.dispose()

if __name__ == "__main__":
    check()
