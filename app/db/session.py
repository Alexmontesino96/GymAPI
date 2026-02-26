# app/db/session.py - FIX PARA RENDER + SUPABASE
import os
from sqlalchemy import create_engine, event, exc, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool  # CRÍTICO: Usar NullPool para Supabase!
import logging

logger = logging.getLogger(__name__)

# Obtener DATABASE_URL de Supabase
DATABASE_URL = os.getenv("DATABASE_URL")

# CRÍTICO: Detectar si es Supabase Transaction Pooler
is_supabase = DATABASE_URL and ("supabase" in DATABASE_URL or "pooler" in DATABASE_URL or "6543" in DATABASE_URL)

if is_supabase:
    # CONFIGURACIÓN PARA SUPABASE (Transaction Pooler)
    logger.info("🔧 Usando configuración optimizada para Supabase/PgBouncer")

    engine = create_engine(
        DATABASE_URL,
        # CRÍTICO: NullPool para PgBouncer - NO mantener pool local!
        poolclass=NullPool,

        # Configuración de conexión para Supabase
        connect_args={
            "keepalives": 1,
            "keepalives_idle": 10,  # Más agresivo para Supabase
            "keepalives_interval": 5,
            "keepalives_count": 3,
            "connect_timeout": 10,
            "options": "-c statement_timeout=30000"  # 30 segundos
        },

        # Echo para debug (desactivar en producción final)
        echo=False,

        # Importante para Supabase
        pool_pre_ping=False,  # No hacer ping con NullPool

        # Execution options
        execution_options={
            "isolation_level": "AUTOCOMMIT"  # Para evitar transacciones largas
        }
    )
else:
    # Configuración para PostgreSQL directo (desarrollo local)
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=300
    )

# Event listener para configurar cada conexión nueva
@event.listens_for(engine, "connect")
def set_search_path(dbapi_conn, connection_record):
    """Configurar search_path al conectar (una sola vez)"""
    with dbapi_conn.cursor() as cursor:
        cursor.execute("SET search_path TO public")
        # Para Supabase, también configurar el statement timeout
        if is_supabase:
            cursor.execute("SET statement_timeout = '30s'")

# Crear SessionLocal
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Obtener sesión de BD con manejo de errores mejorado"""
    db = SessionLocal()
    try:
        # Ya no necesitamos SET search_path aquí (se hace en connect)
        yield db
    except exc.OperationalError as e:
        logger.error(f"❌ Database connection lost: {e}")
        db.rollback()
        db.close()
        # Crear nueva sesión
        db = SessionLocal()
        yield db
    finally:
        db.close()
