#!/usr/bin/env python3
"""
Script para migrar usuarios de metadata de Auth0 a roles de Auth0.

Este script:
1. Obtiene todos los usuarios de la base de datos local
2. Determina el rol más alto de cada usuario
3. Asigna el rol correspondiente en Auth0

Uso:
    python scripts/migrate_to_auth0_roles.py [--user_id USER_ID]

Argumentos:
    --user_id: ID opcional de un usuario específico para migrar. Si no se proporciona,
              se migrarán todos los usuarios.
    --verbose: Activa logs detallados
"""

import os
import sys
import asyncio
import argparse
import json
import logging
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List

# Agregar el directorio raíz al path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.user_gym import UserGym, GymRoleType
from app.services.auth0_mgmt import auth0_mgmt_service
from app.services.auth0_sync import determine_highest_role
from app.core.config import get_settings

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("auth0_roles_migration")

# Mapeo de nombres de roles internos a nombres de roles en Auth0
ROLE_NAME_MAPPING = {
    "SUPER_ADMIN": "SuperAdmin",
    "ADMIN": "Admin",
    "OWNER": "Owner",
    "TRAINER": "Trainer",
    "MEMBER": "Member"
}

async def initialize_auth0_service():
    """Inicializa el servicio de Auth0 Management si aún no se ha hecho."""
    # Verificar que tenemos las credenciales de Auth0
    settings = get_settings()
    
    if not settings.AUTH0_DOMAIN or not settings.AUTH0_CLIENT_ID or not settings.AUTH0_CLIENT_SECRET:
        logger.error("Faltan credenciales de Auth0. Verifique las variables de entorno.")
        logger.error(f"AUTH0_DOMAIN: {'Configurado' if settings.AUTH0_DOMAIN else 'Falta'}")
        logger.error(f"AUTH0_CLIENT_ID: {'Configurado' if settings.AUTH0_CLIENT_ID else 'Falta'}")
        logger.error(f"AUTH0_CLIENT_SECRET: {'Configurado (oculto)' if settings.AUTH0_CLIENT_SECRET else 'Falta'}")
        return False
    
    try:
        # Inicializar el servicio si es necesario
        if not auth0_mgmt_service.is_initialized():
            logger.info("Inicializando servicio Auth0 Management API")
            await auth0_mgmt_service.initialize()
            logger.info("Servicio Auth0 Management inicializado con éxito")
        
        return True
    except Exception as e:
        logger.error(f"Error al inicializar servicio Auth0 Management: {str(e)}")
        return False

async def migrate_user_to_auth0_role(db: Session, user_id: int) -> Optional[str]:
    """
    Migra un usuario de metadata a roles de Auth0.
    
    Args:
        db: Sesión de base de datos
        user_id: ID del usuario a migrar
        
    Returns:
        str: El rol asignado o None si hubo un error
    """
    try:
        # Obtener el usuario y su rol global
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"Usuario {user_id} no encontrado en la base de datos")
            return None
            
        if not user.auth0_id:
            logger.error(f"Usuario {user_id} no tiene auth0_id asignado")
            return None
            
        global_role = user.role
        logger.debug(f"Rol global del usuario {user_id}: {global_role}")
        
        # Obtener roles en todos los gimnasios
        gym_roles_query = db.query(UserGym.role).filter(UserGym.user_id == user_id).all()
        gym_roles = [r[0] for r in gym_roles_query]
        logger.debug(f"Roles de gimnasio del usuario {user_id}: {[r.name for r in gym_roles if r]}")
        
        # Determinar el rol más alto
        highest_role = determine_highest_role(global_role, gym_roles)
        logger.info(f"Rol más alto calculado para usuario {user_id}: {highest_role}")
        
        # Convertir el nombre del rol interno al formato de Auth0
        auth0_role_name = ROLE_NAME_MAPPING.get(highest_role)
        if not auth0_role_name:
            logger.error(f"No se encontró mapeo para el rol '{highest_role}'")
            return None
            
        logger.info(f"Rol mapeado para Auth0: {highest_role} -> {auth0_role_name}")
        
        # Asignar rol en Auth0
        success = await auth0_mgmt_service.assign_roles_to_user(user.auth0_id, [auth0_role_name])
        if success:
            logger.info(f"Rol {auth0_role_name} asignado a usuario {user.auth0_id} en Auth0")
            return auth0_role_name
        else:
            logger.error(f"Error asignando rol {auth0_role_name} a usuario {user.auth0_id} en Auth0")
            return None
        
    except Exception as e:
        logger.error(f"Error migrando rol para usuario {user_id}: {str(e)}", exc_info=True)
        return None

async def migrate_all_users(db: Session) -> Dict[str, Any]:
    """
    Migra todos los usuarios de metadata a roles de Auth0.
    
    Args:
        db: Sesión de base de datos
        
    Returns:
        Dict: Estadísticas de la migración
    """
    logger.info("Iniciando migración de usuarios a roles de Auth0")
    
    # Obtener todos los usuarios
    users = db.query(User).all()
    total = len(users)
    success = 0
    errors = 0
    
    logger.info(f"Se encontraron {total} usuarios para migrar")
    
    for i, user in enumerate(users):
        try:
            logger.info(f"Procesando usuario {i+1}/{total}: {user.id} (email: {user.email})")
            highest_role = await migrate_user_to_auth0_role(db, user.id)
            if highest_role:
                success += 1
            else:
                errors += 1
                
            # Pequeña pausa para evitar rate limits de Auth0
            await asyncio.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error procesando usuario {user.id}: {str(e)}")
            errors += 1
    
    result = {
        "success": success,
        "errors": errors,
        "total": total
    }
    
    logger.info(f"Migración completada. Éxito: {success}, Errores: {errors}, Total: {total}")
    return result

async def main(user_id: Optional[int] = None):
    """Función principal del script."""
    # Inicializar servicio Auth0
    auth0_initialized = await initialize_auth0_service()
    if not auth0_initialized:
        logger.error("No se pudo inicializar el servicio Auth0. Abortando.")
        return
    
    # Crear sesión de base de datos
    db = SessionLocal()
    try:
        if user_id:
            # Migrar usuario específico
            logger.info(f"Migrando usuario con ID: {user_id}")
            highest_role = await migrate_user_to_auth0_role(db, user_id)
            if highest_role:
                logger.info(f"Usuario {user_id} migrado con éxito. Rol asignado: {highest_role}")
            else:
                logger.error(f"Error al migrar usuario {user_id}")
        else:
            # Migrar todos los usuarios
            result = await migrate_all_users(db)
            logger.info(f"Resumen: {json.dumps(result, indent=2)}")
    finally:
        db.close()

if __name__ == "__main__":
    # Parsear argumentos de línea de comandos
    parser = argparse.ArgumentParser(description="Migra usuarios de metadata a roles de Auth0")
    parser.add_argument("--user_id", type=int, help="ID del usuario específico a migrar")
    parser.add_argument("--verbose", "-v", action="store_true", help="Modo verboso (debug)")
    args = parser.parse_args()
    
    # Configurar nivel de log según argumentos
    if args.verbose:
        logging.getLogger("auth0_roles_migration").setLevel(logging.DEBUG)
        logging.getLogger("app").setLevel(logging.DEBUG)
    
    # Ejecutar la función principal
    try:
        asyncio.run(main(args.user_id))
    except Exception as e:
        logger.critical(f"Error fatal en la ejecución: {str(e)}", exc_info=True) 