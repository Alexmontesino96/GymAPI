#!/usr/bin/env python3
"""
Script mejorado de migración para Stream Chat con creación de usuarios.

Este script:
1. Crea/actualiza usuarios en Stream.io con IDs multi-tenant
2. Asigna usuarios a sus teams (gyms)
3. Migra canales al formato multi-tenant

IMPORTANTE: Los usuarios DEBEN existir en Stream.io antes de crear canales.

USO:
    python scripts/migrate_stream_with_users.py [--dry-run] [--gym-id GYM_ID]

OPCIONES:
    --dry-run: Simula la migración sin hacer cambios reales
    --gym-id: Migra solo los chats de un gimnasio específico
"""

import sys
import os
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.base import Base  # Importar Base para cargar todos los modelos
from app.models.chat import ChatRoom, ChatMember
from app.models.user import User
from app.core.stream_client import stream_client
from app.core.stream_utils import get_stream_id_from_internal
import argparse
import time

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_or_update_stream_user(
    user: User,
    gym_id: int,
    dry_run: bool = False
) -> dict:
    """
    Crea o actualiza un usuario en Stream.io con ID multi-tenant.

    Args:
        user: Usuario de la BD
        gym_id: ID del gimnasio
        dry_run: Si es True, simula sin hacer cambios

    Returns:
        dict con resultado de la operación
    """
    result = {
        "user_id": user.id,
        "stream_id": None,
        "success": False,
        "error": None
    }

    try:
        # Generar stream_id multi-tenant
        stream_id = get_stream_id_from_internal(user.id, gym_id=gym_id)
        result["stream_id"] = stream_id

        if dry_run:
            logger.info(f"  [DRY-RUN] Crearía usuario: {stream_id}")
            result["success"] = True
            return result

        # Datos del usuario para Stream
        user_data = {
            "id": stream_id,
            "name": user.full_name or f"User {user.id}",
            "role": "user",
            "teams": [f"gym_{gym_id}"]  # Asignar al team del gimnasio
        }

        # Agregar email si existe
        if user.email:
            user_data["email"] = user.email

        # Agregar imagen de perfil si existe
        if hasattr(user, 'profile_picture') and user.profile_picture:
            user_data["image"] = user.profile_picture

        # Crear/actualizar usuario en Stream.io
        stream_client.upsert_user(user_data)

        logger.info(f"  ✓ Usuario creado/actualizado: {stream_id} (team: gym_{gym_id})")
        result["success"] = True

        return result

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"  ✗ Error creando usuario {user.id}: {str(e)}")
        return result


def get_all_users_for_rooms(db: Session, gym_id: int = None) -> list:
    """
    Obtiene todos los usuarios únicos que participan en chat rooms.

    Args:
        db: Sesión de base de datos
        gym_id: Filtrar por gimnasio (opcional)

    Returns:
        Lista de tuplas (user, gym_id)
    """
    query = db.query(ChatMember).join(ChatRoom)

    if gym_id:
        query = query.filter(ChatRoom.gym_id == gym_id)

    members = query.all()

    # Crear set de (user_id, gym_id) para evitar duplicados
    user_gym_pairs = set()
    for member in members:
        room = db.query(ChatRoom).filter(ChatRoom.id == member.room_id).first()
        if room:
            user_gym_pairs.add((member.user_id, room.gym_id))

    # Obtener objetos User completos
    result = []
    for user_id, gym_id in user_gym_pairs:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            result.append((user, gym_id))

    return result


def migrate_channel_to_multitenant(
    db: Session,
    room: ChatRoom,
    dry_run: bool = False
) -> dict:
    """
    Migra un canal individual al formato multi-tenant.
    PREREQUISITO: Los usuarios ya deben existir en Stream.io

    Args:
        db: Sesión de base de datos
        room: ChatRoom a migrar
        dry_run: Si es True, simula sin hacer cambios

    Returns:
        dict con resultado de la migración
    """
    result = {
        "room_id": room.id,
        "gym_id": room.gym_id,
        "old_channel_id": room.stream_channel_id,
        "new_channel_id": None,
        "success": False,
        "error": None,
        "members_migrated": 0
    }

    try:
        # 1. Obtener miembros del canal
        members = db.query(ChatMember).filter(ChatMember.room_id == room.id).all()

        if not members:
            result["error"] = "No members found"
            return result

        # 2. Construir nuevos stream IDs para cada miembro
        new_member_ids = []

        for member in members:
            user = db.query(User).filter(User.id == member.user_id).first()
            if user:
                # ID nuevo (con gym_id)
                new_id = get_stream_id_from_internal(user.id, gym_id=room.gym_id)
                new_member_ids.append(new_id)

        # 3. Generar nuevo channel_id (mantener formato si es directo)
        if room.is_direct and len(new_member_ids) == 2:
            # Para chats directos, ordenar IDs para consistencia
            sorted_ids = sorted(new_member_ids)
            new_channel_id = f"direct_{'_'.join(sorted_ids)}"
        else:
            # Para grupos, mantener el ID existente si no contiene user_
            if "user_" not in room.stream_channel_id:
                new_channel_id = room.stream_channel_id
            else:
                # Generar uno nuevo basado en room.id
                new_channel_id = f"room_{room.gym_id}_{room.id}"

        result["new_channel_id"] = new_channel_id

        logger.info(f"    Channel: {room.stream_channel_id} → {new_channel_id}")
        logger.info(f"    Miembros: {new_member_ids}")

        if dry_run:
            result["success"] = True
            result["members_migrated"] = len(members)
            logger.info(f"    [DRY-RUN] Canal migrado")
            return result

        # 4. Crear nuevo canal en Stream con IDs multi-tenant
        try:
            new_channel = stream_client.channel(
                room.stream_channel_type,
                new_channel_id
            )

            # Crear el canal con todos los miembros
            channel_data = {
                "created_by_id": new_member_ids[0],
                "members": new_member_ids,  # Agregar todos de una vez
                "team": f"gym_{room.gym_id}",
                "gym_id": str(room.gym_id)
            }

            if room.name:
                channel_data["name"] = room.name

            new_channel.create(user_id=new_member_ids[0], data=channel_data)
            logger.info(f"    ✓ Canal creado con {len(new_member_ids)} miembros")

        except Exception as e:
            if "already exists" in str(e):
                logger.warning(f"    ⚠ Canal ya existe: {new_channel_id}")
                # Intentar actualizar miembros
                try:
                    new_channel.add_members(new_member_ids)
                    logger.info(f"    ✓ Miembros actualizados")
                except:
                    pass
            else:
                raise

        # 5. Actualizar BD con nuevo channel_id
        room.stream_channel_id = new_channel_id
        db.commit()
        logger.info(f"    ✓ BD actualizada")

        result["success"] = True
        result["members_migrated"] = len(members)

        return result

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"    ✗ Error: {str(e)}")
        db.rollback()
        return result


def main():
    parser = argparse.ArgumentParser(description='Migrar Stream Chat a formato multi-tenant')
    parser.add_argument('--dry-run', action='store_true', help='Simular migración sin hacer cambios')
    parser.add_argument('--gym-id', type=int, help='Migrar solo chats de este gimnasio')

    args = parser.parse_args()

    logger.info("="*80)
    logger.info("MIGRACIÓN COMPLETA DE STREAM CHAT A MULTI-TENANT")
    logger.info("="*80)

    if args.dry_run:
        logger.warning("⚠️  MODO DRY-RUN ACTIVADO - No se harán cambios reales")

    db = SessionLocal()
    try:
        # FASE 1: CREAR/ACTUALIZAR USUARIOS
        logger.info("\n" + "="*80)
        logger.info("FASE 1: CREAR/ACTUALIZAR USUARIOS EN STREAM.IO")
        logger.info("="*80)

        user_gym_pairs = get_all_users_for_rooms(db, gym_id=args.gym_id)
        logger.info(f"Encontrados {len(user_gym_pairs)} usuarios únicos para crear/actualizar")

        user_stats = {
            "total": len(user_gym_pairs),
            "success": 0,
            "failed": 0
        }

        for i, (user, gym_id) in enumerate(user_gym_pairs, 1):
            logger.info(f"\n[{i}/{len(user_gym_pairs)}] Usuario {user.id} (gym {gym_id}):")

            result = create_or_update_stream_user(user, gym_id, dry_run=args.dry_run)

            if result["success"]:
                user_stats["success"] += 1
            else:
                user_stats["failed"] += 1

            # Pequeña pausa para no saturar API
            time.sleep(0.2)

        logger.info("\n" + "-"*80)
        logger.info(f"Usuarios: {user_stats['success']} exitosos, {user_stats['failed']} fallidos")
        logger.info("-"*80)

        # FASE 2: MIGRAR CANALES
        logger.info("\n" + "="*80)
        logger.info("FASE 2: MIGRAR CANALES")
        logger.info("="*80)

        # Obtener todos los chat rooms
        query = db.query(ChatRoom)
        if args.gym_id:
            query = query.filter(ChatRoom.gym_id == args.gym_id)

        rooms = query.all()
        logger.info(f"Encontrados {len(rooms)} chat rooms para migrar\n")

        # Estadísticas
        channel_stats = {
            "total": len(rooms),
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "members_total": 0
        }

        # Migrar cada room
        for i, room in enumerate(rooms, 1):
            logger.info(f"\n[{i}/{len(rooms)}] Room {room.id} (gym {room.gym_id}):")

            # Verificar si ya tiene formato multi-tenant
            if f"gym_{room.gym_id}" in room.stream_channel_id:
                logger.info(f"  ✓ Ya tiene formato multi-tenant, saltando...")
                channel_stats["skipped"] += 1
                continue

            result = migrate_channel_to_multitenant(db, room, dry_run=args.dry_run)

            if result["success"]:
                channel_stats["success"] += 1
                channel_stats["members_total"] += result["members_migrated"]
            else:
                channel_stats["failed"] += 1
                logger.error(f"  ✗ Error: {result['error']}")

            # Pequeña pausa para no saturar API
            time.sleep(0.5)

        # Resumen final
        logger.info("\n" + "="*80)
        logger.info("RESUMEN FINAL DE MIGRACIÓN")
        logger.info("="*80)
        logger.info(f"\nFASE 1 - USUARIOS:")
        logger.info(f"  Total: {user_stats['total']}")
        logger.info(f"  Exitosos: {user_stats['success']}")
        logger.info(f"  Fallidos: {user_stats['failed']}")

        logger.info(f"\nFASE 2 - CANALES:")
        logger.info(f"  Total: {channel_stats['total']}")
        logger.info(f"  Migrados: {channel_stats['success']}")
        logger.info(f"  Fallidos: {channel_stats['failed']}")
        logger.info(f"  Saltados: {channel_stats['skipped']}")
        logger.info(f"  Miembros totales: {channel_stats['members_total']}")

        if args.dry_run:
            logger.warning("\n⚠️  MIGRACIÓN EN MODO DRY-RUN - No se hicieron cambios reales")
            logger.warning("Para aplicar los cambios, ejecuta sin --dry-run")
        else:
            logger.info("\n✓ MIGRACIÓN COMPLETADA")

        logger.info("="*80)

        return 0

    except Exception as e:
        logger.error(f"Error fatal en migración: {str(e)}", exc_info=True)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
