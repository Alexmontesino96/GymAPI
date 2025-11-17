#!/usr/bin/env python3
"""Quick check de la tabla class_participation"""
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Cargar .env
load_dotenv()

# Agregar path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

database_url = os.getenv("DATABASE_URL")
if not database_url:
    print("❌ ERROR: DATABASE_URL no está configurado")
    sys.exit(1)

engine = create_engine(database_url)

with engine.connect() as conn:
    # Ver columnas de class_participation
    result = conn.execute(text("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'class_participation'
        ORDER BY ordinal_position
    """))

    print("Columnas de la tabla 'class_participation':")
    print("-" * 60)
    for row in result:
        print(f"  {row[0]:<30} {row[1]:<20} {row[2]}")

    # Ver un registro de ejemplo
    print("\nRegistro de ejemplo:")
    print("-" * 60)
    result = conn.execute(text("SELECT * FROM class_participation LIMIT 1"))
    if result.rowcount > 0:
        row = result.fetchone()
        for i, col in enumerate(result.keys()):
            print(f"  {col}: {row[i]}")
    else:
        print("  No hay registros en la tabla")
