from sqlalchemy import create_engine, text
from app.core.config import get_settings
import os

def main():
    try:
        # Obtener la configuración
        settings = get_settings()
        
        # URL directa de Supabase (en caso de que la configuración no se cargue correctamente)
        DB_URL = "postgresql://postgres:Mezjo9-gezrox-guggop@db.ueijlkythlkqadxymzqd.supabase.co:5432/postgres"
        
        # Mostrar qué URL se está usando
        print(f"Usando URL de la base de datos: {settings.SQLALCHEMY_DATABASE_URI}")
        
        # Crear conexión a la base de datos
        engine = create_engine(DB_URL)
        
        # Conectar y ejecutar la sentencia ALTER TABLE
        with engine.connect() as conn:
            try:
                # Verificar si la columna existe
                try:
                    result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'class_session' AND column_name = 'override_capacity'"))
                    rows = result.fetchall()
                    if rows:
                        print("La columna override_capacity ya existe.")
                        return
                    else:
                        print("La columna override_capacity no existe, añadiéndola...")
                except Exception as e:
                    print(f"Error al verificar la columna: {e}")
                    print("Intentando añadir la columna de todos modos...")
                
                # Añadir la columna con 'IF NOT EXISTS' para evitar errores
                conn.execute(text("ALTER TABLE class_session ADD COLUMN IF NOT EXISTS override_capacity INTEGER"))
                conn.commit()
                print("Columna override_capacity añadida con éxito.")
            except Exception as e:
                print(f"Error al añadir la columna: {e}")
    except Exception as e:
        print(f"Error de conexión: {e}")

if __name__ == "__main__":
    main() 