import logging
import sys

def setup_logging():
    """Configura el logging básico para la aplicación."""
    # Obtener el logger raíz
    log = logging.getLogger()
    log.setLevel(logging.INFO) # Establecer nivel INFO para el raíz

    # Crear un handler para la consola (stdout)
    handler = logging.StreamHandler(sys.stdout) 

    # Crear un formateador
    formatter = logging.Formatter(
        fmt="%(levelname)-8s %(name)-15s %(message)s" # Formato consistente
    )

    # Añadir formateador al handler
    handler.setFormatter(formatter)

    # Añadir handler al logger raíz
    # Limpiar handlers existentes si Uvicorn/otro añadió alguno antes
    if log.hasHandlers():
        log.handlers.clear()
    log.addHandler(handler)
    
    # Log de confirmación
    log.info("Configuración de logging básica aplicada.") 