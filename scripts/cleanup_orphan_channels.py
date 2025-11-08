#!/usr/bin/env python3
"""
Script para eliminar canales huérfanos de Stream Chat.

Este script:
1. Identifica canales en Stream que no existen en la BD local
2. Verifica que no tengan mensajes
3. Los elimina de Stream Chat

Uso:
    python scripts/cleanup_orphan_channels.py [--dry-run] [--force]
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Set

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.chat import ChatRoom
from app.core.stream_client import stream_client

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'cleanup_orphans_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)


def get_channels_from_db(db: Session) -> Set[str]:
    """
    Obtiene todos los IDs de canales que existen en la BD local.

    Returns:
        Set de stream_channel_id que existen en la BD
    """
    rooms = db.query(ChatRoom.stream_channel_id).all()
    return {room[0] for room in rooms if room[0]}


def get_orphan_event_channels() -> List[Dict]:
    """
    Identifica canales de eventos huérfanos basándose en los logs.

    Returns:
        Lista de canales huérfanos con su información
    """
    # IDs de eventos huérfanos detectados en los logs (645-655)
    orphan_event_ids = [
        645, 646, 647, 648, 649, 650, 651, 652, 653, 654, 655
    ]

    orphan_channels = []
    for event_id in orphan_event_ids:
        channel_id = f"event_{event_id}_d3d94468"
        orphan_channels.append({
            "channel_id": channel_id,
            "channel_type": "messaging",
            "event_id": event_id
        })

    return orphan_channels


def delete_channel(channel_type: str, channel_id: str, force: bool = False) -> bool:
    """
    Elimina un canal de Stream Chat.

    Args:
        channel_type: Tipo del canal (messaging)
        channel_id: ID del canal
        force: Si True, elimina aunque tenga mensajes

    Returns:
        True si se eliminó correctamente
    """
    try:
        channel = stream_client.channel(channel_type, channel_id)

        # Verificar que el canal existe
        try:
            response = channel.query(
                messages_limit=1,
                watch=False,
                presence=False
            )

            if not response or 'channel' not in response:
                logger.info(f"   ⚠️ Canal {channel_id} no existe en Stream")
                return False

            # Verificar si tiene mensajes
            messages = response.get('messages', [])
            if messages and not force:
                logger.warning(f"   ⚠️ Canal {channel_id} tiene {len(messages)} mensajes. Use --force para eliminar")
                return False

        except Exception as e:
            logger.info(f"   ⚠️ Canal {channel_id} no encontrado: {e}")
            return False

        # Eliminar el canal
        channel.delete()
        logger.info(f"   ✅ Canal {channel_id} eliminado exitosamente")
        return True

    except Exception as e:
        logger.error(f"   ❌ Error eliminando {channel_id}: {e}")
        return False


def main(dry_run: bool = True, force: bool = False):
    """
    Función principal del script.

    Args:
        dry_run: Si True, solo simula las eliminaciones
        force: Si True, elimina canales aunque tengan mensajes
    """
    db = SessionLocal()

    try:
        logger.info("=" * 70)
        logger.info("LIMPIEZA DE CANALES HUÉRFANOS EN STREAM CHAT")
        logger.info(f"Modo: {'DRY-RUN (simulación)' if dry_run else 'EJECUCIÓN REAL'}")
        logger.info(f"Forzar eliminación: {'SÍ' if force else 'NO (solo canales vacíos)'}")
        logger.info("=" * 70)

        # Obtener canales que existen en la BD
        db_channels = get_channels_from_db(db)
        logger.info(f"\n📊 Canales en BD local: {len(db_channels)}")

        # Obtener canales huérfanos conocidos
        orphan_channels = get_orphan_event_channels()
        logger.info(f"🔍 Canales huérfanos identificados: {len(orphan_channels)}\n")

        # Filtrar solo los que no están en la BD
        channels_to_delete = []
        for channel in orphan_channels:
            if channel["channel_id"] not in db_channels:
                channels_to_delete.append(channel)

        logger.info(f"🗑️ Canales a eliminar: {len(channels_to_delete)}\n")

        if not channels_to_delete:
            logger.info("✅ No hay canales huérfanos para eliminar")
            return

        # Procesar cada canal
        deleted_count = 0
        skipped_count = 0

        for channel in channels_to_delete:
            logger.info(f"📍 Procesando: {channel['channel_id']} (evento {channel['event_id']})")

            if dry_run:
                logger.info(f"   [DRY-RUN] Eliminaría canal {channel['channel_id']}")
                deleted_count += 1
            else:
                success = delete_channel(
                    channel["channel_type"],
                    channel["channel_id"],
                    force
                )
                if success:
                    deleted_count += 1
                else:
                    skipped_count += 1

        # Resumen
        logger.info("\n" + "=" * 70)
        logger.info("RESUMEN DE LA OPERACIÓN")
        logger.info("=" * 70)
        logger.info(f"Total procesados: {len(channels_to_delete)}")
        logger.info(f"✅ Eliminados: {deleted_count}")
        logger.info(f"⚠️ Omitidos: {skipped_count}")

        if dry_run:
            logger.info("\n⚠️ MODO DRY-RUN: No se realizaron cambios reales")
            logger.info("Para eliminar los canales, ejecuta con --execute")

    except Exception as e:
        logger.error(f"Error general: {e}", exc_info=True)

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Limpiar canales huérfanos en Stream Chat")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Simular cambios sin ejecutarlos (default: True)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Ejecutar eliminaciones reales (desactiva dry-run)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Eliminar canales aunque tengan mensajes"
    )

    args = parser.parse_args()

    # Si se especifica --execute, desactivar dry-run
    dry_run = not args.execute if args.execute else args.dry_run

    main(dry_run=dry_run, force=args.force)