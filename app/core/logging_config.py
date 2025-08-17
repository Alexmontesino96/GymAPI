import logging
import sys
import os
from datetime import datetime
from app.core.config import get_settings

def setup_logging():
    """Configura el logging básico para la aplicación, respetando DEBUG_MODE."""
    settings = get_settings()
    # Obtener el logger raíz
    log = logging.getLogger()
    level = logging.DEBUG if settings.DEBUG_MODE else logging.INFO
    log.setLevel(level)
    
    # Asegurarse que existe el directorio de logs
    os.makedirs("logs", exist_ok=True)
    
    # Crear un handler para la consola (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Crear un handler para archivo
    log_file = f"logs/app_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)
    
    # Crear un formateador más detallado
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Añadir formateador a los handlers
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # Añadir handlers al logger raíz
    # Limpiar handlers existentes si Uvicorn/otro añadió alguno antes
    if log.hasHandlers():
        log.handlers.clear()
    log.addHandler(console_handler)
    log.addHandler(file_handler)
    
    # Configurar niveles específicos para algunos loggers ruidosos
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    
    # Log de confirmación
    log.info("Configuración de logging aplicada. Nivel %s.", logging.getLevelName(level))
    if settings.DEBUG_MODE:
        log.debug("Logs de nivel DEBUG habilitados (entorno de desarrollo).") 
