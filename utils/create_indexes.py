"""
Script para crear índices en la tabla event_participations.
Este script añade índices importantes para optimizar las consultas de participación en eventos.
"""

import sys
import os
from sqlalchemy import create_engine, MetaData, Index, text
from sqlalchemy.exc import SQLAlchemyError

# Añadir directorio raíz al path para importar config
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar settings para obtener la URL correcta
from app.core.config import get_settings

# Obtener la URL de la base de datos desde settings
DB_URL = str(get_settings().SQLALCHEMY_DATABASE_URI)

# URL de conexión a la base de datos (Usando la configuración)
# db_url = "postgresql://postgres:Jazdi0-cyhvan-pofduz@db.ueijlkythlkqadxymzqd.supabase.co:5432/postgres"

def create_indexes():
    """Crear índices manualmente mediante SQL"""
    print("Conectando a la base de datos...")
    
    # Usar directamente la URL de conexión
    engine = create_engine(DB_URL)
    
    # SQL para crear cada índice
    index_statements = [
        # Índices para event_participations
        "CREATE INDEX IF NOT EXISTS ix_event_participations_member_id ON event_participations (member_id)",
        "CREATE INDEX IF NOT EXISTS ix_event_participations_event_id ON event_participations (event_id)",
        "CREATE INDEX IF NOT EXISTS ix_event_participations_status ON event_participations (status)",
        "CREATE INDEX IF NOT EXISTS ix_event_participation_event_member ON event_participations (event_id, member_id)",
        "CREATE INDEX IF NOT EXISTS ix_event_participation_gym_status ON event_participations (gym_id, status)",
        
        # Índices para eventos
        "CREATE INDEX IF NOT EXISTS ix_events_dates ON events (start_time, end_time)",
        "CREATE INDEX IF NOT EXISTS ix_events_creator_status ON events (creator_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_events_title_gin ON events USING gin (to_tsvector('spanish', title))",
        
        # Índices para filtrado por ubicación
        "CREATE INDEX IF NOT EXISTS ix_events_location ON events (location)",
        
        # Índices para usuarios
        "CREATE INDEX IF NOT EXISTS ix_user_auth0_id ON user (auth0_id)",
        "CREATE INDEX IF NOT EXISTS ix_user_email ON user (email)",
        
        # Índices para relaciones entrenador-miembro
        "CREATE INDEX IF NOT EXISTS ix_trainer_member_trainer_id ON trainer_member_relationships (trainer_id)",
        "CREATE INDEX IF NOT EXISTS ix_trainer_member_member_id ON trainer_member_relationships (member_id)",
        "CREATE INDEX IF NOT EXISTS ix_trainer_member_status ON trainer_member_relationships (status)"
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