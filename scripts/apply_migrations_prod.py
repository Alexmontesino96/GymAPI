#!/usr/bin/env python3
"""
Script para aplicar migraciones de Alembic en producción de forma segura.

Este script:
1. Verifica la conexión a la base de datos
2. Muestra el estado actual de las migraciones
3. Aplica todas las migraciones pendientes
4. Verifica que las migraciones se aplicaron correctamente

Uso:
    python scripts/apply_migrations_prod.py
    
Variables de entorno requeridas:
    DATABASE_URL - URL de conexión a la base de datos de producción
"""

import os
import sys
import logging
from pathlib import Path

# Añadir el directorio raíz del proyecto al path de Python
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from alembic.runtime.environment import EnvironmentContext
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_database_connection(database_url: str) -> bool:
    """Verifica la conexión a la base de datos."""
    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Conexión a la base de datos exitosa")
        return True
    except SQLAlchemyError as e:
        logger.error(f"❌ Error al conectar a la base de datos: {e}")
        return False

def get_current_revision(alembic_cfg: Config) -> str:
    """Obtiene la revisión actual de la base de datos."""
    try:
        def get_revision(rev, context):
            return rev
        
        script = ScriptDirectory.from_config(alembic_cfg)
        
        def get_current_head():
            with EnvironmentContext(alembic_cfg, script) as env_context:
                return env_context.get_current_revision()
        
        current_rev = get_current_head()
        return current_rev if current_rev else "base (sin migraciones)"
    except Exception as e:
        logger.error(f"Error al obtener revisión actual: {e}")
        return "unknown"

def get_pending_migrations(alembic_cfg: Config) -> list:
    """Obtiene las migraciones pendientes."""
    try:
        script = ScriptDirectory.from_config(alembic_cfg)
        
        def get_current_head():
            with EnvironmentContext(alembic_cfg, script) as env_context:
                return env_context.get_current_revision()
        
        current_rev = get_current_head()
        head_rev = script.get_current_head()
        
        if current_rev == head_rev:
            return []
        
        # Obtener todas las revisiones desde current hasta head
        revisions = []
        for revision in script.walk_revisions(head_rev, current_rev):
            if revision.revision != current_rev:
                revisions.append(revision)
        
        return list(reversed(revisions))
    except Exception as e:
        logger.error(f"Error al obtener migraciones pendientes: {e}")
        return []

def apply_migrations():
    """Función principal para aplicar migraciones."""
    
    # Verificar que DATABASE_URL esté configurada
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ Variable de entorno DATABASE_URL no configurada")
        return False
    
    logger.info(f"🔗 Conectando a: {database_url[:50]}...")
    
    # Verificar conexión
    if not check_database_connection(database_url):
        return False
    
    # Configurar Alembic
    alembic_cfg = Config('alembic.ini')
    alembic_cfg.set_main_option('sqlalchemy.url', database_url)
    
    try:
        # Mostrar estado actual
        current_rev = get_current_revision(alembic_cfg)
        logger.info(f"📋 Revisión actual en BD: {current_rev}")
        
        # Obtener migraciones pendientes
        pending = get_pending_migrations(alembic_cfg)
        
        if not pending:
            logger.info("✅ No hay migraciones pendientes. Base de datos actualizada.")
            return True
        
        logger.info(f"📦 Migraciones pendientes encontradas: {len(pending)}")
        for migration in pending:
            logger.info(f"  - {migration.revision}: {migration.doc}")
        
        # Confirmar aplicación
        response = input(f"\n¿Aplicar {len(pending)} migración(es) pendiente(s)? (y/N): ")
        if response.lower() not in ['y', 'yes', 'sí', 's']:
            logger.info("❌ Operación cancelada por el usuario")
            return False
        
        # Aplicar migraciones
        logger.info("🚀 Aplicando migraciones...")
        command.upgrade(alembic_cfg, 'head')
        
        # Verificar que se aplicaron correctamente
        new_rev = get_current_revision(alembic_cfg)
        logger.info(f"✅ Migraciones aplicadas exitosamente")
        logger.info(f"📋 Nueva revisión: {new_rev}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error al aplicar migraciones: {e}")
        return False

def main():
    """Función principal."""
    logger.info("🏥 Iniciando aplicación de migraciones en producción...")
    
    # Verificar que estamos en el directorio correcto
    if not os.path.exists('alembic.ini'):
        logger.error("❌ No se encontró alembic.ini. Ejecuta desde el directorio raíz del proyecto.")
        sys.exit(1)
    
    success = apply_migrations()
    
    if success:
        logger.info("✅ Proceso completado exitosamente")
        sys.exit(0)
    else:
        logger.error("❌ Proceso falló. Revisa los logs anteriores.")
        sys.exit(1)

if __name__ == "__main__":
    main()