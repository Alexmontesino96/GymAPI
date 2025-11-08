#!/usr/bin/env python3
"""
Script para corregir los nombres de canales en Stream Chat.

Este script:
1. Busca todos los canales de eventos en la BD local
2. Verifica si el canal existe en Stream Chat
3. Actualiza el nombre del canal en Stream con el nombre correcto de la BD

Uso:
    python scripts/fix_stream_channel_names.py [--dry-run] [--gym-id GYM_ID]
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from typing import Dict, Any

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.chat import ChatRoom, ChatRoomStatus
from app.models.event import Event
from app.core.stream_client import stream_client

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'fix_stream_names_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)


def update_channel_name(channel_type: str, channel_id: str, name: str, dry_run: bool = False) -> bool:
    """
    Actualiza el nombre de un canal en Stream Chat.

    Args:
        channel_type: Tipo del canal (generalmente 'messaging')
        channel_id: ID del canal
        name: Nuevo nombre para el canal
        dry_run: Si es True, no hace cambios reales

    Returns:
        True si se actualizó correctamente, False en caso contrario
    """
    try:
        channel = stream_client.channel(channel_type, channel_id)

        # Primero verificar que el canal existe
        try:
            response = channel.query(
                messages_limit=0,
                watch=False,
                presence=False
            )

            if not response or 'channel' not in response:
                logger.warning(f"Canal {channel_id} no existe en Stream")
                return False

        except Exception as e:
            logger.warning(f"Canal {channel_id} no encontrado: {e}")
            return False

        # Actualizar el nombre del canal
        if not dry_run:
            update_data = {"name": name}
            channel.update(update_data)
            logger.info(f"✅ Actualizado: {channel_id} -> '{name}'")
        else:
            logger.info(f"[DRY-RUN] Actualizaría: {channel_id} -> '{name}'")

        return True

    except Exception as e:
        logger.error(f"Error actualizando {channel_id}: {e}")
        return False


def main(dry_run: bool = True, gym_id: int = None):
    """
    Función principal del script.

    Args:
        dry_run: Si es True, simula los cambios sin ejecutarlos
        gym_id: ID del gimnasio a procesar (None para todos)
    """
    db = SessionLocal()

    try:
        logger.info("=" * 60)
        logger.info("INICIANDO CORRECCIÓN DE NOMBRES DE CANALES EN STREAM CHAT")
        logger.info(f"Modo: {'DRY-RUN (simulación)' if dry_run else 'EJECUCIÓN REAL'}")
        logger.info(f"Gimnasio: {gym_id if gym_id else 'Todos'}")
        logger.info("=" * 60)

        # Buscar todas las salas de chat de eventos activas
        query = db.query(ChatRoom).filter(
            ChatRoom.event_id.isnot(None),
            ChatRoom.status == ChatRoomStatus.ACTIVE
        )

        if gym_id:
            query = query.filter(ChatRoom.gym_id == gym_id)

        rooms = query.all()

        logger.info(f"\n📊 Encontradas {len(rooms)} salas de eventos activas\n")

        total_actualizados = 0
        total_errores = 0

        for room in rooms:
            # Obtener información del evento
            event = db.query(Event).filter(Event.id == room.event_id).first()

            if not event:
                logger.warning(f"⚠️ Evento {room.event_id} no encontrado para sala {room.id}")
                continue

            # El nombre correcto debería estar en la BD local
            expected_name = room.name

            logger.info(f"\n🔍 Procesando sala {room.id}:")
            logger.info(f"   - Stream Channel: {room.stream_channel_id}")
            logger.info(f"   - Evento: {event.title}")
            logger.info(f"   - Nombre esperado: {expected_name}")

            # Actualizar el canal en Stream
            success = update_channel_name(
                room.stream_channel_type,
                room.stream_channel_id,
                expected_name,
                dry_run
            )

            if success:
                total_actualizados += 1
            else:
                total_errores += 1

        # Resumen
        logger.info("\n" + "=" * 60)
        logger.info("RESUMEN DE LA OPERACIÓN")
        logger.info("=" * 60)
        logger.info(f"Total de salas procesadas: {len(rooms)}")
        logger.info(f"✅ Canales actualizados: {total_actualizados}")
        logger.info(f"❌ Errores: {total_errores}")

        if dry_run:
            logger.info("\n⚠️ MODO DRY-RUN: No se realizaron cambios reales")
            logger.info("Para aplicar los cambios, ejecuta sin --dry-run")

    except Exception as e:
        logger.error(f"Error general: {e}", exc_info=True)

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Corregir nombres de canales en Stream Chat")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Simular cambios sin ejecutarlos (default: True)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Ejecutar cambios reales (desactiva dry-run)"
    )
    parser.add_argument(
        "--gym-id",
        type=int,
        help="ID del gimnasio a procesar (opcional)"
    )

    args = parser.parse_args()

    # Si se especifica --execute, desactivar dry-run
    dry_run = not args.execute if args.execute else args.dry_run

    main(dry_run=dry_run, gym_id=args.gym_id)