#!/usr/bin/env python
"""
Script para eliminar la tabla user_analytics de la base de datos.

Uso:
    python scripts/drop_analytics_table.py
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
import logging
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def drop_analytics_table():
    """Eliminar la tabla user_analytics y sus índices"""
    
    # Obtener DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("❌ DATABASE_URL no está configurada en el archivo .env")
        return False
    
    # Conectar a la base de datos
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            # Verificar si la tabla existe
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()
            
            if 'user_analytics' not in existing_tables:
                logger.info("✅ La tabla 'user_analytics' no existe, nada que eliminar")
                return True
            
            logger.info("🗑️  Eliminando tabla 'user_analytics' y sus índices...")
            
            # Eliminar índices primero
            indices_to_drop = [
                "idx_analytics_date",
                "idx_analytics_gym_date", 
                "idx_analytics_user_date"
            ]
            
            for index_name in indices_to_drop:
                try:
                    conn.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
                    logger.info(f"   ✓ Índice {index_name} eliminado")
                except Exception as e:
                    logger.warning(f"   ⚠️  No se pudo eliminar índice {index_name}: {e}")
            
            # Eliminar la tabla
            conn.execute(text("DROP TABLE IF EXISTS user_analytics CASCADE"))
            conn.commit()
            
            logger.info("✅ Tabla 'user_analytics' eliminada exitosamente")
            
            # Verificar que se eliminó
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()
            
            if 'user_analytics' in existing_tables:
                logger.error("❌ La tabla aún existe después de intentar eliminarla")
                return False
            
            return True
            
    except SQLAlchemyError as e:
        logger.error(f"❌ Error al eliminar la tabla: {e}")
        return False
    finally:
        engine.dispose()


def clean_alembic_reference():
    """Limpiar referencias en alembic_version si existen"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return
    
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            # Verificar si existe una migración relacionada con analytics
            result = conn.execute(text("""
                SELECT version_num 
                FROM alembic_version 
                WHERE version_num LIKE '%analytics%'
            """))
            
            analytics_version = result.fetchone()
            
            if analytics_version:
                logger.info(f"🧹 Limpiando referencia de migración: {analytics_version[0]}")
                
                # Volver a la versión anterior
                conn.execute(text("""
                    UPDATE alembic_version 
                    SET version_num = 'f7d3d99'
                    WHERE version_num = :version
                """), {"version": analytics_version[0]})
                
                conn.commit()
                logger.info("✅ Referencia de migración limpiada")
            else:
                logger.info("✅ No hay referencias de migración de analytics")
                
    except Exception as e:
        logger.warning(f"⚠️  No se pudo limpiar alembic_version: {e}")
    finally:
        engine.dispose()


def main():
    """Función principal"""
    logger.info("=" * 60)
    logger.info("🗑️  Script de eliminación de tabla user_analytics")
    logger.info("=" * 60)
    
    # Confirmación de seguridad
    response = input("\n⚠️  ¿Estás seguro de que quieres eliminar la tabla user_analytics? (yes/no): ")
    if response.lower() != 'yes':
        logger.info("Operación cancelada")
        return
    
    # Eliminar tabla
    if drop_analytics_table():
        # Limpiar referencias de Alembic
        clean_alembic_reference()
        
        logger.info("\n✨ Proceso completado exitosamente")
        logger.info("La tabla user_analytics ha sido eliminada de la base de datos")
    else:
        logger.error("\n❌ Hubo errores durante el proceso")
        sys.exit(1)


if __name__ == "__main__":
    main()