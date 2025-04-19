import sys
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

# Importamos la configuración para obtener la URL de la base de datos
from app.core.config import get_settings

def test_database_connection():
    settings = get_settings()
    db_url = settings.SQLALCHEMY_DATABASE_URI
    
    print(f"Intentando conectar a la base de datos usando: {db_url}")
    
    try:
        # Crear el motor de SQLAlchemy
        engine = create_engine(db_url)
        
        # Intentar conectarse a la base de datos
        with engine.connect() as connection:
            result = connection.execute("SELECT 1")
            print("Conexión exitosa a la base de datos!")
            print("Resultado de prueba:", result.fetchone())
            
        return True
    except SQLAlchemyError as e:
        print(f"Error al conectar a la base de datos: {e}")
        return False
    except Exception as e:
        print(f"Error inesperado: {e}")
        return False

if __name__ == "__main__":
    success = test_database_connection()
    sys.exit(0 if success else 1) 