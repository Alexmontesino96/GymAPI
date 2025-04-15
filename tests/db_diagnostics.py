"""
Script de diagnóstico para conexiones a bases de datos
"""
import sys
import os
import logging
import time
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Añadir directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Cargar variables de entorno
dotenv.load_dotenv()

# Heroku URL (explícita)
HEROKU_URL = "postgresql://u6chpjmhvbacn5:pcc8066ee2c146523c96e94ea9c289bdfb35af0a929c1c0243adbe5dd4ea85546@c6sfjnr30ch74e.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/d8mrfqhqd7jn4k"

def try_connection(name, url, display_url=None):
    """Prueba una conexión a la base de datos y muestra el resultado"""
    start_time = time.time()
    if not display_url:
        # Ocultar credenciales para el log
        display_url = url.split('@')[1] if '@' in url else url
    
    logger.info(f"Probando conexión a {name}: {display_url}")
    
    # Verificar y corregir el prefijo postgres:// a postgresql://
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
        logger.info(f"URL corregida a postgresql://")
    
    try:
        # Crear engine con timeout reducido para fallar rápido
        engine = create_engine(
            url, 
            connect_args={"connect_timeout": 5},
            pool_pre_ping=True
        )
        
        # Intentar conectar
        with engine.connect() as conn:
            # Ejecutar consulta simple
            result = conn.execute(text("SELECT current_database() as db_name"))
            row = result.fetchone()
            elapsed = time.time() - start_time
            logger.info(f"✅ Conexión a {name} EXITOSA. Base de datos: {row.db_name} ({elapsed:.2f}s)")
            
            # Probar algunas consultas adicionales
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                LIMIT 3
            """))
            tables = [row[0] for row in result]
            logger.info(f"   Tablas disponibles (muestra): {tables}")
            
            return True
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"❌ Error conectando a {name} ({elapsed:.2f}s): {e}")
        return False

def run_diagnostics():
    """Ejecuta diagnósticos completos de todas las posibles conexiones"""
    results = []
    
    # 1. Probar URL explícita de Heroku
    results.append(("Heroku (explícito)", try_connection(
        "Heroku (explícito)", 
        HEROKU_URL
    )))
    
    # 2. Probar URL desde variable de entorno DATABASE_URL
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        results.append(("DATABASE_URL env", try_connection(
            "DATABASE_URL env", 
            env_url,
            display_url="(desde variable de entorno)"
        )))
    else:
        logger.warning("⚠️ No se encontró variable de entorno DATABASE_URL")
        results.append(("DATABASE_URL env", False))
    
    # 3. Importar y probar desde el módulo session
    try:
        from app.db.session import engine as app_engine
        start_time = time.time()
        logger.info("Probando engine de la aplicación (app.db.session)")
        
        try:
            with app_engine.connect() as conn:
                result = conn.execute(text("SELECT current_database() as db_name"))
                row = result.fetchone()
                elapsed = time.time() - start_time
                logger.info(f"✅ Conexión al engine de la aplicación EXITOSA. Base de datos: {row.db_name} ({elapsed:.2f}s)")
                results.append(("Engine app", True))
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ Error conectando con el engine de la aplicación ({elapsed:.2f}s): {e}")
            results.append(("Engine app", False))
            
    except Exception as e:
        logger.error(f"❌ Error importando el engine de la aplicación: {e}")
        results.append(("Engine app", False))
    
    # 4. Probar conexión a Supabase (para ver si aún funciona)
    supabase_url = "postgresql://postgres:postgres@db.ueijlkythlkqadxymzqd.supabase.co:5432/postgres"
    results.append(("Supabase", try_connection(
        "Supabase", 
        supabase_url
    )))
    
    # Mostrar resumen
    print("\n" + "="*50)
    print("RESUMEN DE DIAGNÓSTICO DE CONEXIONES")
    print("="*50)
    for name, success in results:
        status = "✅ EXITOSO" if success else "❌ FALLIDO"
        print(f"{name:20} : {status}")
    print("="*50)
    
    # Sugerir soluciones
    print("\nRECOMENDACIONES:")
    if not any(success for _, success in results):
        print("❗ Ninguna conexión funciona. Verifica tu conexión a internet y los firewalls.")
    elif results[0][1]:  # Si Heroku explícito funciona
        if not results[1][1]:  # Pero env var no funciona
            print("✓ La conexión explícita a Heroku funciona, pero la variable de entorno no.")
            print("  → Asegúrate de que DATABASE_URL en .env tiene el formato correcto:")
            print(f"    DATABASE_URL={HEROKU_URL}")
    elif results[3][1]:  # Si Supabase funciona
        print("⚠️ Supabase funciona pero Heroku no. ¿Quieres seguir usando Supabase?")
        print("  → Para volver a Supabase, actualiza DATABASE_URL en .env.")
    else:
        print("⚠️ Situación mixta. Revisa el diagnóstico detallado arriba.")
    
    return results

if __name__ == "__main__":
    print("Ejecutando diagnóstico de conexiones a bases de datos...\n")
    run_diagnostics() 