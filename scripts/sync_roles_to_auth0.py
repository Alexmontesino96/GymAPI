#!/usr/bin/env python3
"""
Script para sincronizar los roles de usuarios con Auth0.

Este script se conecta con Auth0 y actualiza el app_metadata de cada usuario con su rol más alto,
permitiendo que la Action de Auth0 asigne los permisos correspondientes en los tokens.

Uso:
    python scripts/sync_roles_to_auth0.py [--user_id USER_ID]

Argumentos:
    --user_id: ID opcional de un usuario específico para sincronizar. Si no se proporciona,
              se sincronizarán todos los usuarios.
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
logger = logging.getLogger("sync_roles_script")

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

async def sync_user_role(db: Session, user_id: int) -> Optional[str]:
    """
    Sincroniza el rol más alto de un usuario con Auth0.
    
    Args:
        db: Sesión de base de datos
        user_id: ID del usuario a sincronizar
        
    Returns:
        str: El rol más alto asignado o None si hubo un error
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
        
        # Actualizar en Auth0
        try:
            logger.info(f"Actualizando metadata en Auth0 para usuario {user.auth0_id}")
            metadata = {"highest_role": highest_role}
            await auth0_mgmt_service.update_user_metadata(user.auth0_id, metadata)
            logger.info(f"Usuario {user_id} (Auth0: {user.auth0_id}) actualizado con rol {highest_role}")
            return highest_role
        except Exception as auth0_error:
            logger.error(f"Error al actualizar metadata en Auth0: {str(auth0_error)}")
            return None
        
    except Exception as e:
        logger.error(f"Error sincronizando rol para usuario {user_id}: {str(e)}", exc_info=True)
        return None

async def sync_all_users(db: Session) -> Dict[str, Any]:
    """
    Sincroniza el rol más alto de todos los usuarios con Auth0.
    
    Args:
        db: Sesión de base de datos
        
    Returns:
        Dict: Estadísticas de la sincronización
    """
    logger.info("Iniciando sincronización de roles de todos los usuarios con Auth0")
    
    # Obtener todos los usuarios
    users = db.query(User).all()
    total = len(users)
    success = 0
    errors = 0
    
    logger.info(f"Se encontraron {total} usuarios para sincronizar")
    
    for i, user in enumerate(users):
        try:
            logger.info(f"Procesando usuario {i+1}/{total}: {user.id} (email: {user.email})")
            highest_role = await sync_user_role(db, user.id)
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
    
    logger.info(f"Sincronización completada. Éxito: {success}, Errores: {errors}, Total: {total}")
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
            # Sincronizar usuario específico
            logger.info(f"Sincronizando usuario con ID: {user_id}")
            highest_role = await sync_user_role(db, user_id)
            if highest_role:
                logger.info(f"Usuario {user_id} sincronizado con éxito. Rol asignado: {highest_role}")
            else:
                logger.error(f"Error al sincronizar usuario {user_id}")
        else:
            # Sincronizar todos los usuarios
            result = await sync_all_users(db)
            logger.info(f"Resumen: {json.dumps(result, indent=2)}")
    finally:
        db.close()

if __name__ == "__main__":
    # Parsear argumentos de línea de comandos
    parser = argparse.ArgumentParser(description="Sincroniza roles de usuarios con Auth0")
    parser.add_argument("--user_id", type=int, help="ID del usuario específico a sincronizar")
    parser.add_argument("--verbose", "-v", action="store_true", help="Modo verboso (debug)")
    args = parser.parse_args()
    
    # Configurar nivel de log según argumentos
    if args.verbose:
        logging.getLogger("sync_roles_script").setLevel(logging.DEBUG)
        logging.getLogger("app").setLevel(logging.DEBUG)
    
    # Ejecutar la función principal
    try:
        asyncio.run(main(args.user_id))
    except Exception as e:
        logger.critical(f"Error fatal en la ejecución: {str(e)}", exc_info=True) 