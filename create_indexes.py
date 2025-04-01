"""
Script para crear índices en la tabla event_participations.
Este script añade índices importantes para optimizar las consultas de participación en eventos.
"""

from sqlalchemy import create_engine, text
import os

def create_indexes():
    """Crear índices manualmente mediante SQL"""
    print("Conectando a la base de datos...")
    
    # Usar directamente la URL de conexión
    db_url = "postgresql://postgres:Jazdi0-cyhvan-pofduz@db.ueijlkythlkqadxymzqd.supabase.co:5432/postgres"
    engine = create_engine(db_url)
    
    # SQL para crear cada índice
    index_statements = [
        "CREATE INDEX IF NOT EXISTS ix_event_participations_member_id ON event_participations (member_id)",
        "CREATE INDEX IF NOT EXISTS ix_event_participations_event_id ON event_participations (event_id)",
        "CREATE INDEX IF NOT EXISTS ix_event_participations_status ON event_participations (status)",
        "CREATE INDEX IF NOT EXISTS ix_event_participation_event_member ON event_participations (event_id, member_id)",
        "CREATE INDEX IF NOT EXISTS ix_event_participation_gym_status ON event_participations (gym_id, status)"
    ]
    
    print("Creando índices...")
    with engine.begin() as conn:
        for stmt in index_statements:
            try:
                print(f"Ejecutando: {stmt}")
                conn.execute(text(stmt))
                print("✅ Índice creado correctamente")
            except Exception as e:
                print(f"❌ Error creando índice: {e}")
    
    print("Proceso completado.")

if __name__ == "__main__":
    create_indexes() 