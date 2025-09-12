#!/usr/bin/env python
"""
Script para agregar campos de tracking de uso de app a la tabla user_gyms.

Uso:
    python scripts/add_app_usage_tracking.py
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


def add_app_usage_fields():
    """Agregar campos de tracking de uso de app a user_gyms"""
    
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
            if 'user_gyms' not in inspector.get_table_names():
                logger.error("❌ La tabla 'user_gyms' no existe")
                return False
            
            # Obtener columnas existentes
            existing_columns = [col['name'] for col in inspector.get_columns('user_gyms')]
            logger.info(f"📋 Columnas actuales en user_gyms: {', '.join(existing_columns)}")
            
            # Campos a agregar
            fields_to_add = [
                ('last_app_access', 'TIMESTAMP'),
                ('total_app_opens', 'INTEGER DEFAULT 0'),
                ('monthly_app_opens', 'INTEGER DEFAULT 0'),
                ('monthly_reset_date', 'TIMESTAMP')
            ]
            
            added_fields = []
            skipped_fields = []
            
            for field_name, field_type in fields_to_add:
                if field_name in existing_columns:
                    logger.info(f"   ⏭️  Campo '{field_name}' ya existe, saltando...")
                    skipped_fields.append(field_name)
                else:
                    try:
                        alter_sql = f"ALTER TABLE user_gyms ADD COLUMN {field_name} {field_type}"
                        conn.execute(text(alter_sql))
                        conn.commit()
                        logger.info(f"   ✅ Campo '{field_name}' agregado exitosamente")
                        added_fields.append(field_name)
                    except Exception as e:
                        logger.error(f"   ❌ Error agregando campo '{field_name}': {e}")
                        return False
            
            # Crear índice para last_app_access si no existe
            if 'last_app_access' in added_fields or 'last_app_access' in existing_columns:
                try:
                    # Verificar si el índice ya existe
                    existing_indexes = inspector.get_indexes('user_gyms')
                    index_names = [idx['name'] for idx in existing_indexes]
                    
                    if 'idx_user_gyms_last_app_access' not in index_names:
                        conn.execute(text(
                            "CREATE INDEX idx_user_gyms_last_app_access ON user_gyms(last_app_access)"
                        ))
                        conn.commit()
                        logger.info("   ✅ Índice 'idx_user_gyms_last_app_access' creado")
                    else:
                        logger.info("   ⏭️  Índice 'idx_user_gyms_last_app_access' ya existe")
                except Exception as e:
                    logger.warning(f"   ⚠️  No se pudo crear índice: {e}")
            
            # Resumen
            logger.info("\n📊 Resumen:")
            if added_fields:
                logger.info(f"   ✅ Campos agregados: {', '.join(added_fields)}")
            if skipped_fields:
                logger.info(f"   ⏭️  Campos que ya existían: {', '.join(skipped_fields)}")
            
            return True
            
    except SQLAlchemyError as e:
        logger.error(f"❌ Error al modificar la tabla: {e}")
        return False
    finally:
        engine.dispose()


def verify_fields():
    """Verificar que los campos se agregaron correctamente"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return
    
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            # Verificar estructura
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'user_gyms'
                AND column_name IN ('last_app_access', 'total_app_opens', 'monthly_app_opens', 'monthly_reset_date')
                ORDER BY ordinal_position
            """))
            
            logger.info("\n📋 Campos de tracking de app en user_gyms:")
            logger.info("-" * 60)
            for row in result:
                logger.info(f"  {row[0]:20} {row[1]:15} NULL:{row[2]:5} DEFAULT:{row[3]}")
            
            # Verificar algunos registros
            result = conn.execute(text("""
                SELECT COUNT(*) as total,
                       COUNT(last_app_access) as with_access,
                       SUM(total_app_opens) as total_opens
                FROM user_gyms
            """))
            
            stats = result.fetchone()
            logger.info(f"\n📊 Estadísticas:")
            logger.info(f"   Total registros: {stats[0]}")
            logger.info(f"   Con último acceso registrado: {stats[1]}")
            logger.info(f"   Total de aperturas de app: {stats[2] or 0}")
            
    except Exception as e:
        logger.error(f"❌ Error verificando campos: {e}")
    finally:
        engine.dispose()


def main():
    """Función principal"""
    logger.info("=" * 60)
    logger.info("🚀 Script de agregación de campos de tracking de app")
    logger.info("=" * 60)
    
    # Agregar campos
    if add_app_usage_fields():
        # Verificar que se agregaron correctamente
        verify_fields()
        
        logger.info("\n✨ Proceso completado exitosamente")
        logger.info("Los campos de tracking de uso de app han sido agregados a user_gyms")
    else:
        logger.error("\n❌ Hubo errores durante el proceso")
        sys.exit(1)


if __name__ == "__main__":
    main()