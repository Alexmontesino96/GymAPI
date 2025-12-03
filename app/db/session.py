from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
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

# URL async (asyncpg) - convertir postgresql:// a postgresql+asyncpg://
db_url_async = str(db_url).replace("postgresql://", "postgresql+asyncpg://")

logger.info(f"Database URLs configuradas: sync (psycopg2) y async (asyncpg)")

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
        echo=False, # SIEMPRE False en producción para mejor rendimiento
        pool_pre_ping=True,
        pool_size=10,  # Aumentado de 5 a 10 para manejar más concurrencia
        max_overflow=20,  # Aumentado de 10 a 20 para picos de tráfico
        pool_timeout=30,
        pool_recycle=280,  # Reciclar conexiones cada 4m40s (antes del timeout de pgbouncer ~5min)
        connect_args={
            "connect_timeout": 10,  # Timeout de conexión explícito
            "options": "-c statement_timeout=30000"  # 30s timeout por query
        }
    )

    # Verificar la conexión al crear el engine y establecer search_path para Supabase
    with engine.connect() as conn:
        # Establecer search_path para Supabase
        from sqlalchemy import text
        conn.execute(text("SET search_path TO public"))
        logger.info(f"Verificación de conexión inicial EXITOSA con search_path=public: {display_url}")

except Exception as e:
    logger.critical(f"¡¡¡FALLO CRÍTICO AL CREAR ENGINE CON URL: {display_url}!!! Error: {e}", exc_info=True)

# Crear clase de sesión
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ==========================================
# ASYNC ENGINE (NUEVO - Fase 2)
# ==========================================
try:
    async_engine = create_async_engine(
        db_url_async,
        echo=False,
        pool_pre_ping=False,  # Desactivado para asyncpg (usa su propio health check)
        pool_size=20,  # Más alto para async
        max_overflow=40,
        pool_timeout=30,
        pool_recycle=280,
        connect_args={
            "statement_cache_size": 0,  # Requerido para pgbouncer (Supabase Transaction Pooler)
            "server_settings": {
                "application_name": "gymapi_async",
                "statement_timeout": "30000"  # asyncpg usa server_settings
            }
        }
    )

    logger.info(f"✅ Async engine creado correctamente (asyncpg)")

except Exception as e:
    logger.critical(f"❌ FALLO CRÍTICO AL CREAR ASYNC ENGINE: {e}", exc_info=True)
    async_engine = None

# Async session maker
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
) if async_engine else None


# ==========================================
# DEPENDENCIAS
# ==========================================

# Dependencia para obtener la sesión de DB
def get_db():
    db = SessionLocal()
    try:
        # Establecer search_path para cada sesión en Supabase
        from sqlalchemy import text
        db.execute(text("SET search_path TO public"))
        db.commit()  # Commit para que el SET tenga efecto
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


# Async DB dependency (NUEVO - Fase 2)
async def get_async_db():
    """
    Dependencia async para obtener sesión de base de datos.

    Uso en endpoints:
        @router.get("/endpoint")
        async def my_endpoint(db: AsyncSession = Depends(get_async_db)):
            result = await db.execute(select(User))
            users = result.scalars().all()
    """
    if async_engine is None:
        raise RuntimeError("Async engine no inicializado")

    if AsyncSessionLocal is None:
        raise RuntimeError("AsyncSessionLocal no inicializado")

    async with AsyncSessionLocal() as session:
        try:
            # SET search_path no requiere commit - es un comando de sesión
            # Usar execution_options para evitar prepared statements con pgbouncer
            await session.execute(
                text("SET search_path TO public").execution_options(
                    compiled_cache=None
                )
            )
            yield session
        except SQLAlchemyError as e:
            logger.error(f"Error SQLAlchemy en sesión async: {e}", exc_info=True)
            await session.rollback()
            raise
        except Exception as e:
            from fastapi import HTTPException
            if isinstance(e, HTTPException):
                raise
            logger.error(f"Error inesperado en get_async_db: {e}", exc_info=True)
            raise
        finally:
            await session.close() 