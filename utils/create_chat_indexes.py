"""
Script para crear índices en la tabla chat_rooms.
Este script añade índices importantes para optimizar las consultas de chats de eventos.
"""

import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Añadir directorio raíz al path para importar config
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar settings para obtener la URL correcta
from app.core.config import settings

# Obtener la URL de la base de datos desde settings
DB_URL = str(settings.SQLALCHEMY_DATABASE_URI)

# URL de conexión a la base de datos (Usando la configuración)
# db_url = "postgresql://postgres:Jazdi0-cyhvan-pofduz@db.ueijlkythlkqadxymzqd.supabase.co:5432/postgres"

def create_indexes():
    """Crear índices manualmente mediante SQL"""
    print("Conectando a la base de datos...")
    
    # Usar directamente la URL de conexión
    engine = create_engine(DB_URL)
    
    # SQL para crear cada índice
    index_statements = [
        "CREATE INDEX IF NOT EXISTS ix_chat_rooms_event_id ON chat_rooms (event_id)",
        "CREATE INDEX IF NOT EXISTS ix_chat_rooms_is_direct ON chat_rooms (is_direct)",
        "CREATE INDEX IF NOT EXISTS ix_chat_rooms_event_id_type ON chat_rooms (event_id, stream_channel_type)"
    ]
    
    print("Creando índices para chat_rooms...")
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