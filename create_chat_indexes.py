"""
Script para crear índices en la tabla chat_rooms.
Este script añade índices importantes para optimizar las consultas de chats de eventos.
"""

from sqlalchemy import create_engine, text

def create_indexes():
    """Crear índices manualmente mediante SQL"""
    print("Conectando a la base de datos...")
    
    # Usar directamente la URL de conexión
    db_url = "postgresql://postgres:Jazdi0-cyhvan-pofduz@db.ueijlkythlkqadxymzqd.supabase.co:5432/postgres"
    engine = create_engine(db_url)
    
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