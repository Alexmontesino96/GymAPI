#!/usr/bin/env python3
"""
Script de migración para actualizar IDs de Stream Chat a formato multi-tenant.

Este script migra los canales existentes de Stream Chat del formato legacy
`user_{id}` al nuevo formato multi-tenant `gym_{gym_id}_user_{id}`.

IMPORTANTE: Este script es CRÍTICO para que la funcionalidad de chat funcione correctamente.

PROCESO:
1. Lee todos los ChatRooms de la base de datos
2. Por cada room:
   - Obtiene el canal existente en Stream.io
   - Crea nuevo canal con IDs multi-tenant
   - Migra miembros y configuración
   - Actualiza referencia en BD
   - (Opcional) Elimina canal legacy

USO:
    python scripts/migrate_stream_multitenant_ids.py [--dry-run] [--gym-id GYM_ID]

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


def migrate_channel_to_multitenant(
    db: Session,
    room: ChatRoom,
    dry_run: bool = False
) -> dict:
    """
    Migra un canal individual al formato multi-tenant.

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
        old_member_ids = []
        new_member_ids = []

        for member in members:
            user = db.query(User).filter(User.id == member.user_id).first()
            if user:
                # ID antiguo (sin gym_id)
                old_id = f"user_{user.id}"
                old_member_ids.append(old_id)

                # ID nuevo (con gym_id)
                new_id = get_stream_id_from_internal(user.id, gym_id=room.gym_id)
                new_member_ids.append(new_id)

        logger.info(
            f"Room {room.id}: {len(members)} miembros | "
            f"Old IDs: {old_member_ids[:3]}... | "
            f"New IDs: {new_member_ids[:3]}..."
        )

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

        logger.info(f"Room {room.id}: Channel ID: {room.stream_channel_id} → {new_channel_id}")

        if dry_run:
            result["success"] = True
            result["members_migrated"] = len(members)
            logger.info(f"[DRY-RUN] Room {room.id}: Migración simulada exitosamente")
            return result

        # 4. Crear nuevo canal en Stream con IDs multi-tenant
        try:
            new_channel = stream_client.channel(
                room.stream_channel_type,
                new_channel_id
            )

            # Crear el canal con el primer miembro (creator)
            channel_data = {
                "created_by_id": new_member_ids[0],
                "name": room.name or f"Chat {room.id}",
                "team": f"gym_{room.gym_id}",
                "gym_id": str(room.gym_id)
            }

            new_channel.create(user_id=new_member_ids[0], data=channel_data)
            logger.info(f"✓ Nuevo canal creado: {new_channel_id}")

            # Agregar los demás miembros
            if len(new_member_ids) > 1:
                new_channel.add_members(new_member_ids[1:])
                logger.info(f"✓ {len(new_member_ids)-1} miembros adicionales agregados")

        except Exception as e:
            if "already exists" in str(e):
                logger.warning(f"Canal {new_channel_id} ya existe, continuando...")
            else:
                raise

        # 5. Actualizar BD con nuevo channel_id
        room.stream_channel_id = new_channel_id
        db.commit()
        logger.info(f"✓ BD actualizada con nuevo channel_id")

        result["success"] = True
        result["members_migrated"] = len(members)

        return result

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"✗ Error migrando room {room.id}: {str(e)}", exc_info=True)
        db.rollback()
        return result


def main():
    parser = argparse.ArgumentParser(description='Migrar IDs de Stream Chat a formato multi-tenant')
    parser.add_argument('--dry-run', action='store_true', help='Simular migración sin hacer cambios')
    parser.add_argument('--gym-id', type=int, help='Migrar solo chats de este gimnasio')

    args = parser.parse_args()

    logger.info("="*80)
    logger.info("INICIANDO MIGRACIÓN DE STREAM IDS A FORMATO MULTI-TENANT")
    logger.info("="*80)

    if args.dry_run:
        logger.warning("⚠️  MODO DRY-RUN ACTIVADO - No se harán cambios reales")

    db = SessionLocal()
    try:
        # Obtener todos los chat rooms
        query = db.query(ChatRoom)
        if args.gym_id:
            query = query.filter(ChatRoom.gym_id == args.gym_id)
            logger.info(f"Filtrando por gym_id={args.gym_id}")

        rooms = query.all()
        logger.info(f"Se encontraron {len(rooms)} chat rooms para migrar")

        # Estadísticas
        stats = {
            "total": len(rooms),
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "members_total": 0
        }

        # Migrar cada room
        for i, room in enumerate(rooms, 1):
            logger.info(f"\n[{i}/{len(rooms)}] Procesando room {room.id}...")

            # Verificar si ya tiene formato multi-tenant
            if f"gym_{room.gym_id}" in room.stream_channel_id:
                logger.info(f"✓ Room {room.id} ya tiene formato multi-tenant, saltando...")
                stats["skipped"] += 1
                continue

            result = migrate_channel_to_multitenant(db, room, dry_run=args.dry_run)

            if result["success"]:
                stats["success"] += 1
                stats["members_total"] += result["members_migrated"]
                logger.info(f"✓ Room {room.id} migrado exitosamente")
            else:
                stats["failed"] += 1
                logger.error(f"✗ Room {room.id} falló: {result['error']}")

            # Pequeña pausa para no saturar la API de Stream
            time.sleep(0.5)

        # Resumen final
        logger.info("\n" + "="*80)
        logger.info("RESUMEN DE MIGRACIÓN")
        logger.info("="*80)
        logger.info(f"Total de rooms: {stats['total']}")
        logger.info(f"Migrados exitosamente: {stats['success']}")
        logger.info(f"Fallidos: {stats['failed']}")
        logger.info(f"Saltados (ya multi-tenant): {stats['skipped']}")
        logger.info(f"Total de miembros migrados: {stats['members_total']}")

        if args.dry_run:
            logger.warning("\n⚠️  MIGRACIÓN EN MODO DRY-RUN - No se hicieron cambios reales")
            logger.warning("Para aplicar los cambios, ejecuta sin --dry-run")
        else:
            logger.info("\n✓ MIGRACIÓN COMPLETADA")

        logger.info("="*80)

    except Exception as e:
        logger.error(f"Error fatal en migración: {str(e)}", exc_info=True)
        return 1
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
