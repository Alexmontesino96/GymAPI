#!/usr/bin/env python3
"""
Script para listar y migrar todos los usuarios de Stream Chat a formato multi-tenant.

Identifica usuarios legacy (user_X) y los migra a formato gym_{gym_id}_user_{id}.

Uso:
    python scripts/list_and_migrate_stream_users.py --list
    python scripts/list_and_migrate_stream_users.py --migrate --dry-run
    python scripts/list_and_migrate_stream_users.py --migrate
"""

import sys
import os
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import argparse
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User
from app.models.user_gym import UserGym
from app.core.stream_client import stream_client
from app.core.stream_utils import get_stream_id_from_internal, is_internal_id_format

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def list_all_stream_users() -> List[Dict[str, Any]]:
    """
    Lista todos los usuarios existentes en Stream.

    Returns:
        Lista de usuarios con sus datos
    """
    try:
        # Obtener todos los usuarios (limit máximo)
        response = stream_client.query_users(
            filter_conditions={},
            sort=[{"field": "created_at", "direction": -1}],
            limit=1000  # Ajustar si tienes más usuarios
        )

        users = response.get('users', [])

        logger.info(f"📊 Total de usuarios en Stream: {len(users)}")

        return users
    except Exception as e:
        logger.error(f"Error listando usuarios: {e}")
        return []


def categorize_users(stream_users: List[Dict[str, Any]]) -> Dict[str, List]:
    """
    Categoriza usuarios por tipo de formato.

    Returns:
        Dict con categorías: legacy, multi_tenant, auth0, otros
    """
    categories = {
        "legacy": [],       # user_X
        "multi_tenant": [], # gym_X_user_Y
        "auth0": [],        # auth0|xxx
        "otros": []         # Cualquier otro formato
    }

    for user in stream_users:
        user_id = user.get('id', '')

        if user_id.startswith('gym_') and '_user_' in user_id:
            categories["multi_tenant"].append(user)
        elif user_id.startswith('user_') and user_id[5:].isdigit():
            categories["legacy"].append(user)
        elif user_id.startswith('auth0'):
            categories["auth0"].append(user)
        else:
            categories["otros"].append(user)

    return categories


def get_user_from_db(user_id_str: str, db: Session) -> tuple:
    """
    Obtiene usuario de BD a partir de stream_id.

    Returns:
        (User object, internal_id, gym_ids)
    """
    # Extraer ID interno del stream_id
    if user_id_str.startswith('gym_') and '_user_' in user_id_str:
        # Formato: gym_4_user_10
        parts = user_id_str.split('_user_')
        if len(parts) == 2:
            internal_id = int(parts[1])
        else:
            return None, None, []
    elif user_id_str.startswith('user_'):
        # Formato: user_10
        internal_id = int(user_id_str.replace('user_', ''))
    else:
        # Formato auth0 u otro
        user = db.query(User).filter(User.auth0_id == user_id_str).first()
        if user:
            internal_id = user.id
        else:
            return None, None, []

    # Obtener usuario de BD
    user = db.query(User).filter(User.id == internal_id).first()
    if not user:
        return None, internal_id, []

    # Obtener gimnasios del usuario
    user_gyms = db.query(UserGym).filter(UserGym.user_id == internal_id).all()
    gym_ids = [ug.gym_id for ug in user_gyms]

    return user, internal_id, gym_ids


def migrate_user_to_multitenant(
    user_data: Dict[str, Any],
    db: Session,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Migra un usuario legacy a formato multi-tenant.

    Args:
        user_data: Datos del usuario en Stream
        db: Sesión de BD
        dry_run: Si True, solo simula

    Returns:
        Dict con resultado de la migración
    """
    result = {
        "old_id": user_data.get('id'),
        "new_ids": [],
        "success": False,
        "error": None,
        "created": 0
    }

    try:
        # Obtener datos del usuario de BD
        user, internal_id, gym_ids = get_user_from_db(user_data['id'], db)

        if not user or not gym_ids:
            result["error"] = f"Usuario no encontrado en BD o sin gimnasios"
            return result

        # Crear usuario multi-tenant para cada gimnasio
        for gym_id in gym_ids:
            new_id = get_stream_id_from_internal(internal_id, gym_id=gym_id)

            if dry_run:
                logger.info(f"  [DRY-RUN] Crearía: {new_id} (gym {gym_id})")
                result["new_ids"].append(new_id)
                result["created"] += 1
            else:
                # Crear usuario en Stream
                user_payload = {
                    "id": new_id,
                    "name": f"Usuario {internal_id}",  # Nombre genérico
                    "role": "user",
                    "teams": [f"gym_{gym_id}"]
                }

                # Agregar email si existe
                if hasattr(user, 'email') and user.email:
                    user_payload["email"] = user.email

                stream_client.upsert_user(user_payload)

                logger.info(f"  ✓ Creado: {new_id} (gym {gym_id})")
                result["new_ids"].append(new_id)
                result["created"] += 1

        result["success"] = True

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"  ✗ Error: {str(e)}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Listar y migrar usuarios de Stream Chat'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='Listar todos los usuarios y categorizarlos'
    )
    parser.add_argument(
        '--migrate',
        action='store_true',
        help='Migrar usuarios legacy a multi-tenant'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simular migración sin hacer cambios'
    )
    parser.add_argument(
        '--delete-legacy',
        action='store_true',
        help='Eliminar usuarios legacy después de migrar (PELIGROSO)'
    )

    args = parser.parse_args()

    if not args.list and not args.migrate:
        parser.print_help()
        return 1

    logger.info("="*80)
    logger.info("GESTIÓN DE USUARIOS STREAM CHAT")
    logger.info("="*80)

    # Listar usuarios
    stream_users = list_all_stream_users()

    if not stream_users:
        logger.error("No se pudieron obtener usuarios de Stream")
        return 1

    # Categorizar
    categories = categorize_users(stream_users)

    logger.info("\n" + "="*80)
    logger.info("📊 CATEGORIZACIÓN DE USUARIOS")
    logger.info("="*80)
    logger.info(f"  Legacy (user_X):           {len(categories['legacy'])}")
    logger.info(f"  Multi-tenant (gym_X_user_Y): {len(categories['multi_tenant'])}")
    logger.info(f"  Auth0:                     {len(categories['auth0'])}")
    logger.info(f"  Otros:                     {len(categories['otros'])}")
    logger.info(f"  TOTAL:                     {len(stream_users)}")

    if args.list:
        # Mostrar detalles
        logger.info("\n" + "-"*80)
        logger.info("USUARIOS LEGACY:")
        for user in categories['legacy'][:10]:  # Primeros 10
            logger.info(f"  - {user['id']}")
        if len(categories['legacy']) > 10:
            logger.info(f"  ... y {len(categories['legacy']) - 10} más")

        logger.info("\n" + "-"*80)
        logger.info("USUARIOS MULTI-TENANT:")
        for user in categories['multi_tenant'][:10]:
            logger.info(f"  - {user['id']}")
        if len(categories['multi_tenant']) > 10:
            logger.info(f"  ... y {len(categories['multi_tenant']) - 10} más")

    if args.migrate:
        if args.dry_run:
            logger.warning("\n⚠️  MODO DRY-RUN - No se harán cambios reales")

        logger.info("\n" + "="*80)
        logger.info("🔄 MIGRANDO USUARIOS LEGACY A MULTI-TENANT")
        logger.info("="*80)

        db = SessionLocal()
        try:
            stats = {
                "total": len(categories['legacy']),
                "success": 0,
                "failed": 0,
                "users_created": 0
            }

            for i, user in enumerate(categories['legacy'], 1):
                logger.info(f"\n[{i}/{stats['total']}] Usuario: {user['id']}")

                result = migrate_user_to_multitenant(user, db, dry_run=args.dry_run)

                if result["success"]:
                    stats["success"] += 1
                    stats["users_created"] += result["created"]
                else:
                    stats["failed"] += 1
                    if result["error"]:
                        logger.error(f"  Error: {result['error']}")

            logger.info("\n" + "="*80)
            logger.info("📊 RESUMEN DE MIGRACIÓN")
            logger.info("="*80)
            logger.info(f"  Usuarios procesados:  {stats['total']}")
            logger.info(f"  Exitosos:             {stats['success']}")
            logger.info(f"  Fallidos:             {stats['failed']}")
            logger.info(f"  Usuarios creados:     {stats['users_created']}")

            if args.dry_run:
                logger.warning("\n⚠️  MODO DRY-RUN - No se hicieron cambios reales")
            else:
                logger.info("\n✓ MIGRACIÓN COMPLETADA")

            # Eliminar usuarios legacy si se solicita
            if args.delete_legacy and not args.dry_run and stats['success'] > 0:
                logger.warning("\n" + "="*80)
                logger.warning("🗑️  ELIMINANDO USUARIOS LEGACY")
                logger.warning("="*80)

                for user in categories['legacy']:
                    try:
                        stream_client.delete_user(user['id'], mark_messages_deleted=False)
                        logger.info(f"  ✓ Eliminado: {user['id']}")
                    except Exception as e:
                        logger.error(f"  ✗ Error eliminando {user['id']}: {e}")

        finally:
            db.close()

    logger.info("\n" + "="*80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
