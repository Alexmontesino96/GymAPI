from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import re
import logging
import os

# Importar get_settings
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Obtener la instancia de configuración
settings_instance = get_settings()

# Obtener la URL directamente de la instancia de configuración
db_url = settings_instance.SQLALCHEMY_DATABASE_URI

# Log EXPLICITO de la URL que se usará para crear el engine
# Asegurarse de ocultar credenciales en el log
display_url = str(db_url)
if '@' in display_url:
    parts = display_url.split('@')
    credentials = parts[0].split('://')[1] # Obtener user:pass
    host_info = parts[1]
    display_url = f"postgresql://***@{host_info}" # Ocultar credenciales
else:
    display_url = "URL sin credenciales (o formato inesperado)"

logger.info(f"URL FINAL utilizada para crear el engine: {display_url}")

try:
    # Crear el motor con la URL obtenida de la instancia
    engine = create_engine(
        str(db_url), # Asegurarse de que es string
        echo=settings_instance.DEBUG_MODE, # Usar DEBUG_MODE de la instancia
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        connect_args={"connect_timeout": 10} # Timeout de conexión explícito
    )

    # Verificar la conexión al crear el engine
    with engine.connect() as conn:
        logger.info(f"Verificación de conexión inicial EXITOSA con: {display_url}")

except Exception as e:
    logger.critical(f"¡¡¡FALLO CRÍTICO AL CREAR ENGINE CON URL: {display_url}!!! Error: {e}", exc_info=True)

# Crear clase de sesión
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependencia para obtener la sesión de DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Error de SQLAlchemy en la sesión: {e}", exc_info=True)
        db.rollback() # Hacer rollback en caso de error
        raise # Relanzar la excepción para que FastAPI la maneje
    except Exception as e:
        # No capturar HTTPException ya que es parte del flujo normal de FastAPI
        from fastapi import HTTPException
        if isinstance(e, HTTPException):
            raise  # Dejar que FastAPI maneje las HTTPException normalmente
        logger.error(f"Error inesperado en get_db: {e}", exc_info=True)
        raise
    finally:
        # Asegurarse siempre de cerrar la sesión
        if db:
            db.close() 