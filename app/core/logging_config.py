import logging
import sys
import os
from datetime import datetime

def setup_logging():
    """Configura el logging básico para la aplicación."""
    # Obtener el logger raíz
    log = logging.getLogger()
    log.setLevel(logging.DEBUG)  # Cambiar a DEBUG para ver todos los logs
    
    # Asegurarse que existe el directorio de logs
    os.makedirs("logs", exist_ok=True)
    
    # Crear un handler para la consola (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)  # Mostrar todo en consola
    
    # Crear un handler para archivo
    log_file = f"logs/app_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)  # Guardar todo en archivo
    
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
    log.info("Configuración de logging detallado aplicada. Nivel DEBUG activado.")
    log.debug("Logs de nivel DEBUG ahora son visibles.") 