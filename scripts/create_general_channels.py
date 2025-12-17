#!/usr/bin/env python3
"""
Script para crear canales generales para todos los gimnasios.

Usa el servicio GymChatService para crear/obtener el canal general
de cada gimnasio activo.

Uso:
    python scripts/create_general_channels.py                 # Todos los gyms
    python scripts/create_general_channels.py --gym-id 1      # Solo gym 1
"""

import sys
import os
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import argparse
from app.db.session import SessionLocal
from app.db.base import Base
from app.models.gym import Gym
from app.services.gym_chat import gym_chat_service

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_general_channels(gym_ids: list = None):
    """
    Crea canales generales para los gimnasios especificados.

    Args:
        gym_ids: Lista de IDs de gimnasios. Si es None, procesa todos los activos.
    """
    db = SessionLocal()
    try:
        logger.info("="*80)
        logger.info("🏋️  CREACIÓN DE CANALES GENERALES")
        logger.info("="*80)

        # Obtener gimnasios
        if gym_ids:
            gyms = db.query(Gym).filter(Gym.id.in_(gym_ids)).all()
        else:
            gyms = db.query(Gym).filter(Gym.is_active == True).all()

        if not gyms:
            logger.error("No se encontraron gimnasios para procesar")
            return

        logger.info(f"📍 Procesando {len(gyms)} gimnasio(s)\n")

        stats = {
            "total": len(gyms),
            "created": 0,
            "existing": 0,
            "failed": 0
        }

        for gym in gyms:
            logger.info(f"\n{'='*80}")
            logger.info(f"🏋️  Gimnasio {gym.id}: {gym.name}")
            logger.info(f"{'='*80}")

            try:
                # Usar el servicio existente para obtener/crear canal
                general_channel = gym_chat_service.get_or_create_general_channel(db, gym.id)

                if not general_channel:
                    logger.error(f"❌ No se pudo crear canal general para gym {gym.id}")
                    stats["failed"] += 1
                    continue

                # Verificar si se creó o ya existía
                # El servicio devuelve el canal pero no indica si lo creó
                # Vamos a consultar la BD para ver cuántos miembros tiene
                from app.models.chat import ChatMember
                member_count = db.query(ChatMember).filter(
                    ChatMember.room_id == general_channel.id
                ).count()

                logger.info(f"✅ Canal general disponible:")
                logger.info(f"   - ChatRoom ID: {general_channel.id}")
                logger.info(f"   - Stream Channel ID: {general_channel.stream_channel_id}")
                logger.info(f"   - Miembros en BD: {member_count}")

                # Consideramos "creado" si tiene miembros
                if member_count > 0:
                    stats["created"] += 1
                else:
                    stats["existing"] += 1

            except Exception as e:
                logger.error(f"❌ Error procesando gym {gym.id}: {e}")
                stats["failed"] += 1

        # Resumen
        logger.info("\n" + "="*80)
        logger.info("📊 RESUMEN")
        logger.info("="*80)
        logger.info(f"  Gimnasios procesados: {stats['total']}")
        logger.info(f"  Canales disponibles: {stats['created'] + stats['existing']}")
        logger.info(f"  Fallidos: {stats['failed']}")
        logger.info("="*80)

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description='Crear canales generales para gimnasios'
    )
    parser.add_argument(
        '--gym-id',
        type=int,
        help='Crear canal solo para un gimnasio específico'
    )

    args = parser.parse_args()

    gym_ids = [args.gym_id] if args.gym_id else None
    create_general_channels(gym_ids)


if __name__ == "__main__":
    main()
