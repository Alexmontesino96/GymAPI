#!/usr/bin/env python3
"""
Script para verificar el esquema de la base de datos.
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz al PATH
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from sqlalchemy import inspect, text
from app.db.session import engine, SessionLocal

def check_schema():
    """Verifica las tablas existentes en la base de datos."""
    inspector = inspect(engine)
    
    # Obtener esquemas
    schemas = inspector.get_schema_names()
    print(f"Esquemas disponibles: {schemas}")
    
    # Obtener todas las tablas
    for schema in schemas:
        if schema not in ['information_schema', 'pg_catalog']:
            tables = inspector.get_table_names(schema=schema)
            if tables:
                print(f"\nTablas en esquema '{schema}':")
                for table in tables:
                    print(f"  - {table}")
    
    # Verificar tablas en esquema por defecto
    print("\nTablas en esquema por defecto:")
    default_tables = inspector.get_table_names()
    for table in default_tables:
        print(f"  - {table}")
    
    # Verificar algunas consultas básicas
    print("\n=== Verificando consultas básicas ===")
    with SessionLocal() as db:
        try:
            # Intentar consultas con diferentes formatos
            queries = [
                "SELECT COUNT(*) FROM public.user",
                "SELECT COUNT(*) FROM public.user_gyms", 
                "SELECT COUNT(*) FROM public.gyms",
                "SELECT COUNT(*) FROM public.chat_rooms",
                "SELECT COUNT(*) FROM public.events"
            ]
            
            for query in queries:
                try:
                    result = db.execute(text(query))
                    count = result.scalar()
                    print(f"✓ {query}: {count} registros")
                except Exception as e:
                    print(f"✗ {query}: Error - {str(e).split('DETAIL')[0].strip()}")
        
        except Exception as e:
            print(f"Error general: {e}")

if __name__ == "__main__":
    check_schema()