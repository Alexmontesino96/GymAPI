import os
import sys
import importlib
import subprocess
import logging

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger("app_wrapper")

# Log inicial importante
logger.info(f"===== INICIANDO app_wrapper.py ====")
logger.info(f"Python Executable: {sys.executable}")
logger.info(f"Python Version: {sys.version}")
logger.info(f"sys.path: {sys.path}")
logger.info(f"PYTHONPATH: {os.environ.get('PYTHONPATH')}")
logger.info(f"Working Directory: {os.getcwd()}")

def check_dependencies():
    """Verifica las dependencias críticas e intenta corregir problemas."""
    logger.info("Iniciando verificación de dependencias...")
    try:
        # Intentar importar redis
        logger.debug("Intentando importar redis...")
        import redis
        logger.debug("Intentando importar redis.asyncio.Redis...")
        from redis.asyncio import Redis
        logger.info(f"✅ Redis {redis.__version__} importado correctamente")
        return True
    except ImportError as e:
        logger.error(f"❌ Error importando Redis: {e}")
        
        # Intentar instalar Redis
        logger.info("Intentando instalar Redis...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "redis==5.0.1", "hiredis==2.2.3"])
            
            # Intentar importar de nuevo
            import redis
            from redis.asyncio import Redis
            logger.info(f"Redis {redis.__version__} instalado e importado correctamente")
            return True
        except Exception as install_error:
            logger.error(f"Error instalando Redis: {install_error}")
            return False

# Verificar módulos esenciales
if not check_dependencies():
    logger.critical("No se pudieron instalar las dependencias necesarias. Saliendo...")
    sys.exit(1)

# Importar la aplicación principal
logger.info("Importando la aplicación principal...")
from app.main import app

# Este archivo se puede usar como punto de entrada para gunicorn o uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app_wrapper:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), log_level="debug") 