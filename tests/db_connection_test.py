"""
Script de prueba para verificar la conexión a la base de datos Heroku
"""
import sys
import os
import logging
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Configurar logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Añadir directorio raíz al path 
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importar después de configurar el path
from app.db.session import SessionLocal, engine

def test_database_connection():
    """Prueba la conexión a la base de datos Heroku"""
    logger.info("Probando conexión a la base de datos...")
    
    try:
        # Intentar conectar usando el engine directamente
        with engine.connect() as connection:
            logger.info("✅ Conexión establecida correctamente usando engine.")
            
            # Ejecutar una consulta simple para verificar que todo funciona
            result = connection.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            logger.info(f"Resultado de prueba: {row.test}")
            
        # Probar usando SessionLocal
        db = SessionLocal()
        try:
            result = db.execute(text("SELECT current_database() as db_name"))
            row = result.fetchone()
            logger.info(f"✅ Conexión a la base de datos establecida: {row.db_name}")
            
            # Mostrar algunas tablas si existen
            result = db.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                LIMIT 5
            """))
            tables = [row[0] for row in result]
            logger.info(f"Tablas disponibles (hasta 5): {tables}")
            
            return True
        except SQLAlchemyError as e:
            logger.error(f"❌ Error ejecutando consulta: {e}")
            return False
        finally:
            db.close()
            
    except SQLAlchemyError as e:
        logger.error(f"❌ Error conectando a la base de datos: {e}", exc_info=True)
        return False
        
if __name__ == "__main__":
    success = test_database_connection()
    if success:
        print("\n✅ La conexión a la base de datos funciona correctamente")
    else:
        print("\n❌ Hubo problemas con la conexión a la base de datos") 