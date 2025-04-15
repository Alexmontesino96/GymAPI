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

def check_and_install_dependencies():
    """Verifica las dependencias críticas e intenta instalar si faltan."""
    logger.info("Iniciando verificación de dependencias...")
    # Modulos críticos y sus paquetes pip correspondientes
    critical_modules = {
        'redis': 'redis==5.2.1',
        'redis.asyncio': 'redis==5.2.1', # Asegura que redis se instale para esto
        'fastapi': 'fastapi', 
        'sqlalchemy': 'sqlalchemy', 
        'gunicorn': 'gunicorn==21.2.0', 
        'uvicorn': 'uvicorn', 
        'supabase': 'supabase==2.15.0', 
        'stream_chat': 'stream-chat==4.23.0', # Actualizar a versión encontrada
        'apscheduler': 'apscheduler==3.11.0' # Añadir APScheduler
    }
    missing_install_failed = False
    
    for module, package in critical_modules.items():
        try:
            logger.debug(f"Verificando módulo: {module}")
            importlib.import_module(module)
            logger.info(f"✅ Módulo {module} encontrado.")
        except ImportError:
            logger.warning(f"⚠️ Módulo {module} no encontrado. Intentando instalar paquete: {package}...")
            try:
                # Usar el ejecutable de Python actual para llamar a pip
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                # Intentar importar de nuevo después de instalar
                importlib.import_module(module)
                logger.info(f"✅ Paquete {package} instalado y módulo {module} importado correctamente.")
            except Exception as install_error:
                logger.error(f"❌ FALLO al instalar/importar {package} para el módulo {module}: {install_error}")
                missing_install_failed = True
                
    return not missing_install_failed

# --- Ejecución Principal --- 
logger.info(f"===== INICIANDO app_wrapper.py ====")
logger.info(f"Python Executable: {sys.executable}")
logger.info(f"Python Version: {sys.version}")
logger.info(f"sys.path: {sys.path}")
logger.info(f"PYTHONPATH: {os.environ.get('PYTHONPATH')}")
logger.info(f"Working Directory: {os.getcwd()}")

# Verificar/instalar dependencias al inicio
if not check_and_install_dependencies():
    logger.critical("No se pudieron verificar/instalar todas las dependencias críticas. Saliendo.")
    sys.exit(1)

logger.info("Todas las dependencias críticas verificadas.")
logger.info("Procediendo a iniciar Uvicorn...")

# Iniciar la aplicación con Uvicorn directamente (Gunicorn lo llamará desde el CMD del Dockerfile)
# Necesitamos importar la app aquí, después de verificar dependencias
try:
    from app.main import app
    logger.info("app.main importado correctamente.")
except ImportError as e:
    logger.critical(f"Error final al importar app.main: {e}", exc_info=True)
    sys.exit(1)

if __name__ == "__main__":
    import uvicorn
    # Obtener el puerto de la variable de entorno o usar 8000 por defecto
    port = int(os.environ.get("PORT", 8000))
    # Ejecutar Uvicorn. Gunicorn manejará los workers y el binding.
    # Especificamos la app como "app_wrapper:app" si Gunicorn necesita este archivo
    # pero aquí Uvicorn se ejecuta directamente.
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=port, 
        log_level="debug",
        reload=False # El reload debe manejarse fuera (Render o Gunicorn)
    ) 