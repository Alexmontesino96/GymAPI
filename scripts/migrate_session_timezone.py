#!/usr/bin/env python3
"""
Script para migrar sesiones con timezone incorrecto.

Este script identifica sesiones que tienen tiempos almacenados como hora local
en lugar de UTC y los convierte correctamente.

Uso:
    python scripts/migrate_session_timezone.py [--dry-run] [--gym-id GYM_ID]
"""
import sys
import os
import asyncio
import argparse
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import logging

# Agregar el path raíz para imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import SessionLocal
from app.models.schedule import ClassSession
from app.models.gym import Gym
from app.repositories.gym import gym_repository
from app.repositories.schedule import class_session_repository
from app.core.timezone_utils import convert_gym_time_to_utc

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SessionTimezoneMigrator:
    """Migrador de timezone para sesiones"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.gyms_cache: Dict[int, Gym] = {}
        
    def get_gym(self, db: Session, gym_id: int) -> Optional[Gym]:
        """Obtiene un gimnasio con cache"""
        if gym_id not in self.gyms_cache:
            gym = gym_repository.get(db, id=gym_id)
            self.gyms_cache[gym_id] = gym
        return self.gyms_cache[gym_id]
    
    def identify_incorrect_sessions(self, db: Session, gym_id: Optional[int] = None) -> List[ClassSession]:
        """
        Identifica sesiones que probablemente tienen timezone incorrecto.
        
        Criterio: sesiones creadas después de la implementación del fix de timezone
        que tienen horas "sospechosas" (ej: exactamente en horas redondas en zona local).
        """
        query = db.query(ClassSession)
        
        if gym_id:
            query = query.filter(ClassSession.gym_id == gym_id)
            
        # Filtrar por sesiones recientes (después del 12 de agosto de 2024)
        cutoff_date = datetime(2024, 8, 12, tzinfo=timezone.utc)
        query = query.filter(ClassSession.created_at >= cutoff_date)
        
        sessions = query.all()
        
        suspicious_sessions = []
        for session in sessions:
            gym = self.get_gym(db, session.gym_id)
            if not gym or not gym.timezone:
                continue
                
            # Verificar si la hora de inicio es "sospechosa"
            # (ej: 18:00:00 exacto, que probablemente sea hora local mal guardada)
            start_time = session.start_time
            if start_time and start_time.tzinfo is None:
                # Si es naive datetime, es sospechoso
                suspicious_sessions.append(session)
            elif start_time and start_time.minute == 0 and start_time.second == 0:
                # Si es hora exacta, también es sospechoso
                suspicious_sessions.append(session)
                
        return suspicious_sessions
    
    def migrate_session(self, db: Session, session: ClassSession) -> bool:
        """
        Migra una sesión individual de hora local a UTC.
        
        Returns:
            bool: True si se migró exitosamente, False si no se pudo migrar
        """
        gym = self.get_gym(db, session.gym_id)
        if not gym or not gym.timezone:
            logger.warning(f"No se puede migrar sesión {session.id}: gimnasio {session.gym_id} sin timezone")
            return False
            
        try:
            # Solo migrar si el datetime es naive (sin timezone)
            if session.start_time and session.start_time.tzinfo is None:
                # Convertir de hora local del gym a UTC
                start_time_utc = convert_gym_time_to_utc(session.start_time, gym.timezone)
                
                end_time_utc = None
                if session.end_time and session.end_time.tzinfo is None:
                    end_time_utc = convert_gym_time_to_utc(session.end_time, gym.timezone)
                
                logger.info(f"Sesión {session.id} (Gym {gym.name}):")
                logger.info(f"  Antes: {session.start_time} -> {session.end_time}")
                logger.info(f"  Después: {start_time_utc} -> {end_time_utc}")
                
                if not self.dry_run:
                    session.start_time = start_time_utc
                    if end_time_utc:
                        session.end_time = end_time_utc
                    db.commit()
                    logger.info(f"  ✅ Migrada exitosamente")
                else:
                    logger.info(f"  🔍 DRY RUN - No se aplicaron cambios")
                    
                return True
            else:
                logger.info(f"Sesión {session.id} ya tiene timezone correcto")
                return False
                
        except Exception as e:
            logger.error(f"Error migrando sesión {session.id}: {e}")
            db.rollback()
            return False
    
    def migrate_gym_sessions(self, db: Session, gym_id: int) -> Dict[str, int]:
        """
        Migra todas las sesiones sospechosas de un gimnasio.
        
        Returns:
            dict: Estadísticas de la migración
        """
        gym = self.get_gym(db, gym_id)
        if not gym:
            logger.error(f"Gimnasio {gym_id} no encontrado")
            return {"error": 1}
            
        logger.info(f"Iniciando migración para gimnasio: {gym.name} (ID: {gym_id})")
        logger.info(f"Timezone del gimnasio: {gym.timezone}")
        
        suspicious_sessions = self.identify_incorrect_sessions(db, gym_id)
        logger.info(f"Encontradas {len(suspicious_sessions)} sesiones sospechosas")
        
        stats = {
            "total_found": len(suspicious_sessions),
            "migrated": 0,
            "skipped": 0,
            "errors": 0
        }
        
        for session in suspicious_sessions:
            try:
                if self.migrate_session(db, session):
                    stats["migrated"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as e:
                logger.error(f"Error procesando sesión {session.id}: {e}")
                stats["errors"] += 1
        
        logger.info(f"Migración completada para gimnasio {gym_id}:")
        logger.info(f"  Total encontradas: {stats['total_found']}")
        logger.info(f"  Migradas: {stats['migrated']}")
        logger.info(f"  Omitidas: {stats['skipped']}")
        logger.info(f"  Errores: {stats['errors']}")
        
        return stats
    
    def migrate_all_gyms(self, db: Session) -> Dict[str, Any]:
        """
        Migra todas las sesiones sospechosas en todos los gimnasios.
        
        Returns:
            dict: Estadísticas consolidadas
        """
        # Obtener todos los gimnasios que tienen timezone configurado
        gyms = db.query(Gym).filter(Gym.timezone.isnot(None)).all()
        
        logger.info(f"Iniciando migración global para {len(gyms)} gimnasios")
        
        global_stats = {
            "gyms_processed": 0,
            "total_found": 0,
            "migrated": 0,
            "skipped": 0,
            "errors": 0,
            "gym_details": {}
        }
        
        for gym in gyms:
            try:
                gym_stats = self.migrate_gym_sessions(db, gym.id)
                global_stats["gyms_processed"] += 1
                global_stats["total_found"] += gym_stats.get("total_found", 0)
                global_stats["migrated"] += gym_stats.get("migrated", 0)
                global_stats["skipped"] += gym_stats.get("skipped", 0)
                global_stats["errors"] += gym_stats.get("errors", 0)
                global_stats["gym_details"][gym.id] = gym_stats
            except Exception as e:
                logger.error(f"Error procesando gimnasio {gym.id}: {e}")
                global_stats["errors"] += 1
        
        logger.info("Migración global completada:")
        logger.info(f"  Gimnasios procesados: {global_stats['gyms_processed']}")
        logger.info(f"  Total sesiones encontradas: {global_stats['total_found']}")
        logger.info(f"  Total migradas: {global_stats['migrated']}")
        logger.info(f"  Total omitidas: {global_stats['skipped']}")
        logger.info(f"  Total errores: {global_stats['errors']}")
        
        return global_stats


def main():
    parser = argparse.ArgumentParser(description="Migrar sesiones con timezone incorrecto")
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Ejecutar en modo dry-run (no aplicar cambios)"
    )
    parser.add_argument(
        "--gym-id", 
        type=int, 
        help="ID del gimnasio específico a migrar (opcional)"
    )
    
    args = parser.parse_args()
    
    # Configurar modo
    mode = "DRY RUN" if args.dry_run else "PRODUCCIÓN"
    logger.info(f"Iniciando migración en modo: {mode}")
    
    if args.dry_run:
        logger.warning("⚠️  MODO DRY RUN - No se aplicarán cambios reales")
    else:
        logger.warning("🚨 MODO PRODUCCIÓN - Los cambios se aplicarán a la base de datos")
        response = input("¿Continuar? (y/N): ")
        if response.lower() != 'y':
            logger.info("Operación cancelada por el usuario")
            return
    
    migrator = SessionTimezoneMigrator(dry_run=args.dry_run)
    
    with SessionLocal() as db:
        try:
            if args.gym_id:
                # Migrar gimnasio específico
                stats = migrator.migrate_gym_sessions(db, args.gym_id)
            else:
                # Migrar todos los gimnasios
                stats = migrator.migrate_all_gyms(db)
            
            logger.info("Proceso completado exitosamente")
            
        except Exception as e:
            logger.error(f"Error durante la migración: {e}", exc_info=True)
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())