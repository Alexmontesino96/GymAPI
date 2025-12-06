from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from contextlib import asynccontextmanager
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
        pool_pre_ping=False,  # ✅ DESACTIVADO para pgbouncer (igual que async)
        pool_size=10,  # Aumentado de 5 a 10 para manejar más concurrencia
        max_overflow=20,  # Aumentado de 10 a 20 para picos de tráfico
        pool_timeout=30,
        pool_recycle=180,  # ✅ Reducido a 3min para prevenir SSL connection closed
        connect_args={
            "connect_timeout": 10,  # Timeout de conexión explícito
            "options": "-c statement_timeout=30000 -c search_path=public",  # ✅ search_path configurado aquí
            "sslmode": "require",  # ✅ NUEVO: Forzar SSL desde inicio
            "keepalives": 1,  # ✅ NUEVO: Mantener conexiones vivas
            "keepalives_idle": 30,  # ✅ NUEVO: Intervalo keepalive (30s)
            # NOTA: prepare_threshold es solo para psycopg3, no psycopg2
            # Para pgbouncer con psycopg2, las prepared statements se manejan automáticamente
        },
        execution_options={
            "isolation_level": "READ COMMITTED",  # ✅ NUEVO: Evitar checks extras
        }
    )

    # ✅ ELIMINADO: Verificación inicial con engine.connect()
    # La verificación causaba error SSL con type introspection (hstore)
    # El engine se valida automáticamente en el primer uso real
    logger.info(f"✅ Sync engine creado correctamente (psycopg2) - sin verificación inicial: {display_url}")

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
            # ✅ CRÍTICO: Deshabilitar prepared statements para pgbouncer (Supabase)
            # pgbouncer en modo transaction/statement NO soporta prepared statements
            "statement_cache_size": 0,
            "server_settings": {
                "search_path": "public",  # Configurar schema por defecto (una vez por conexión)
                "application_name": "gymapi_async",
                "statement_timeout": "30000"  # asyncpg usa server_settings
            }
        },
        # ✅ IMPORTANTE: Configuración a nivel de engine para asyncpg
        # https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#disabling-the-postgresql-jit-to-improve-schema-caching
        execution_options={
            "compiled_cache": None  # Deshabilitar compiled cache para evitar statement name conflicts
        }
    )

    logger.info(f"✅ Async engine creado correctamente (asyncpg) con statement_cache_size=0 para pgbouncer")

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
        # ✅ search_path ya está configurado en connect_args options
        # No es necesario ejecutar SET en cada sesión (optimización)
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
            # ✅ search_path ya está configurado en server_settings del engine
            # No es necesario ejecutar SET search_path en cada request
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


# Async DB context manager for background jobs (NUEVO - Fase 2)
@asynccontextmanager
async def get_async_db_for_jobs():
    """
    Context manager async para background jobs y scheduled tasks.

    ⚠️ SOLO para background jobs (APScheduler, tasks, etc).
    Para endpoints FastAPI usar get_async_db() con Depends().

    Uso:
        async with get_async_db_for_jobs() as db:
            result = await db.execute(select(User))
            users = result.scalars().all()

    CRÍTICO: Usa async context manager para garantizar que la sesión se cierra,
    evitando session leaks y connection exhaustion.

    Yields:
        AsyncSession: Sesión async de base de datos
    """
    if async_engine is None:
        raise RuntimeError("Async engine no inicializado")

    if AsyncSessionLocal is None:
        raise RuntimeError("AsyncSessionLocal no inicializado")

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except SQLAlchemyError as e:
            logger.error(f"Error SQLAlchemy en background job async DB: {e}", exc_info=True)
            await session.rollback()
            raise
        except Exception as e:
            logger.error(f"Error inesperado en background job async DB: {e}", exc_info=True)
            await session.rollback()
            raise
        finally:
            # ✅ CRÍTICO: Cerrar sesión para devolver conexión al pool
            await session.close()
            logger.debug("Sesión async DB cerrada correctamente en background job") 
