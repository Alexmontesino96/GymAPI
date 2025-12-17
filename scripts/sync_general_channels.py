#!/usr/bin/env python3
"""
Script para sincronizar canales generales con usuarios multi-tenant.

Este script:
1. Encuentra todos los canales generales de cada gimnasio
2. Obtiene todos los usuarios activos del gimnasio
3. Los agrega al canal general con formato multi-tenant (gym_{gym_id}_user_{user_id})
4. Remueve usuarios legacy que ya no existen

Uso:
    python scripts/sync_general_channels.py                    # Todos los gyms
    python scripts/sync_general_channels.py --gym-id 4         # Solo gym 4
    python scripts/sync_general_channels.py --gym-id 4 --dry-run  # Simular
"""

import sys
import os
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import argparse
from typing import List, Dict, Any, Set
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.base import Base  # Importar Base para cargar todos los modelos
from app.models.chat import ChatRoom, ChatMember
from app.models.user import User
from app.models.user_gym import UserGym
from app.models.gym import Gym
from app.core.stream_client import stream_client
from app.core.stream_utils import get_stream_id_from_internal

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_general_channel(db: Session, gym_id: int) -> ChatRoom:
    """
    Obtiene el canal general de un gimnasio.

    Returns:
        ChatRoom o None si no existe
    """
    return db.query(ChatRoom).filter(
        ChatRoom.gym_id == gym_id,
        ChatRoom.name == "General",
        ChatRoom.is_direct == False,
        ChatRoom.event_id.is_(None)
    ).first()


def get_gym_members(db: Session, gym_id: int) -> List[int]:
    """
    Obtiene todos los user_id de miembros activos de un gimnasio.

    Returns:
        Lista de user_id
    """
    memberships = db.query(UserGym).filter(
        UserGym.gym_id == gym_id
    ).all()

    return [m.user_id for m in memberships]


def get_stream_channel_members(channel_id: str, channel_type: str = "messaging") -> Set[str]:
    """
    Obtiene los miembros actuales de un canal en Stream.

    Returns:
        Set de stream_user_ids
    """
    try:
        channel = stream_client.channel(channel_type, channel_id)
        state = channel.query()

        members = state.get('members', [])
        member_ids = {m.get('user', {}).get('id') for m in members if m.get('user')}

        return member_ids
    except Exception as e:
        logger.error(f"Error obteniendo miembros de Stream para {channel_id}: {e}")
        return set()


def sync_general_channel(
    db: Session,
    gym_id: int,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Sincroniza el canal general de un gimnasio con sus miembros multi-tenant.

    Returns:
        Dict con estadísticas de la sincronización
    """
    stats = {
        "gym_id": gym_id,
        "channel_found": False,
        "members_to_add": 0,
        "members_added": 0,
        "members_to_remove": 0,
        "members_removed": 0,
        "errors": []
    }

    try:
        # 1. Obtener canal general
        general_channel = get_general_channel(db, gym_id)

        if not general_channel:
            logger.warning(f"❌ Gym {gym_id}: No tiene canal general")
            return stats

        stats["channel_found"] = True
        logger.info(f"\n{'='*80}")
        logger.info(f"🏋️  GIMNASIO {gym_id}: {general_channel.name}")
        logger.info(f"{'='*80}")
        logger.info(f"Canal ID (BD): {general_channel.id}")
        logger.info(f"Stream Channel ID: {general_channel.stream_channel_id}")

        # 2. Obtener miembros del gimnasio (user_id internos)
        gym_member_ids = get_gym_members(db, gym_id)
        logger.info(f"👥 Total miembros del gym: {len(gym_member_ids)}")

        # 3. Convertir a stream_ids multi-tenant
        expected_stream_ids = set()
        for user_id in gym_member_ids:
            stream_id = get_stream_id_from_internal(user_id, gym_id=gym_id)
            expected_stream_ids.add(stream_id)

        logger.info(f"🎯 Stream IDs esperados: {len(expected_stream_ids)}")

        # 4. Obtener miembros actuales en Stream
        current_stream_ids = get_stream_channel_members(
            general_channel.stream_channel_id,
            general_channel.stream_channel_type
        )
        logger.info(f"📊 Miembros actuales en Stream: {len(current_stream_ids)}")

        # 5. Calcular diferencias
        to_add = expected_stream_ids - current_stream_ids
        to_remove = current_stream_ids - expected_stream_ids

        stats["members_to_add"] = len(to_add)
        stats["members_to_remove"] = len(to_remove)

        logger.info(f"\n📋 PLAN:")
        logger.info(f"  ➕ Agregar: {len(to_add)} usuarios")
        logger.info(f"  ➖ Remover: {len(to_remove)} usuarios")

        if dry_run:
            logger.warning(f"\n⚠️  MODO DRY-RUN - No se harán cambios")
            if to_add:
                logger.info(f"\n➕ Usuarios a agregar:")
                for stream_id in sorted(to_add)[:10]:
                    logger.info(f"   - {stream_id}")
                if len(to_add) > 10:
                    logger.info(f"   ... y {len(to_add) - 10} más")

            if to_remove:
                logger.info(f"\n➖ Usuarios a remover (legacy/huérfanos):")
                for stream_id in sorted(to_remove)[:10]:
                    logger.info(f"   - {stream_id}")
                if len(to_remove) > 10:
                    logger.info(f"   ... y {len(to_remove) - 10} más")

            return stats

        # 6. AGREGAR usuarios faltantes
        if to_add:
            logger.info(f"\n➕ Agregando {len(to_add)} usuarios...")

            # Primero crear/actualizar usuarios en Stream
            for stream_id in to_add:
                try:
                    stream_client.upsert_user({
                        "id": stream_id,
                        "name": stream_id,
                        "teams": [f"gym_{gym_id}"]
                    })
                except Exception as e:
                    logger.warning(f"  ⚠️  No se pudo crear usuario {stream_id}: {e}")

            # Luego agregar al canal
            try:
                channel = stream_client.channel(
                    general_channel.stream_channel_type,
                    general_channel.stream_channel_id
                )

                # Stream permite agregar múltiples usuarios a la vez
                result = channel.add_members(list(to_add))
                stats["members_added"] = len(to_add)
                logger.info(f"  ✓ Agregados {len(to_add)} usuarios al canal")

            except Exception as e:
                logger.error(f"  ✗ Error agregando usuarios en batch: {e}")
                stats["errors"].append(f"Error agregando usuarios: {e}")

                # Intentar uno por uno como fallback
                for stream_id in to_add:
                    try:
                        channel.add_members([stream_id])
                        stats["members_added"] += 1
                        logger.info(f"  ✓ {stream_id}")
                    except Exception as e2:
                        logger.error(f"  ✗ Error agregando {stream_id}: {e2}")
                        stats["errors"].append(f"Error agregando {stream_id}: {e2}")

        # 7. REMOVER usuarios que ya no pertenecen (legacy/huérfanos)
        if to_remove:
            logger.info(f"\n➖ Removiendo {len(to_remove)} usuarios legacy/huérfanos...")

            try:
                channel = stream_client.channel(
                    general_channel.stream_channel_type,
                    general_channel.stream_channel_id
                )

                # Remover en batch
                result = channel.remove_members(list(to_remove))
                stats["members_removed"] = len(to_remove)
                logger.info(f"  ✓ Removidos {len(to_remove)} usuarios del canal")

            except Exception as e:
                logger.error(f"  ✗ Error removiendo usuarios en batch: {e}")
                stats["errors"].append(f"Error removiendo usuarios: {e}")

                # Intentar uno por uno como fallback
                for stream_id in to_remove:
                    try:
                        channel.remove_members([stream_id])
                        stats["members_removed"] += 1
                        logger.info(f"  ✓ Removido {stream_id}")
                    except Exception as e2:
                        logger.error(f"  ✗ Error removiendo {stream_id}: {e2}")
                        stats["errors"].append(f"Error removiendo {stream_id}: {e2}")

        # 8. Verificar resultado final
        final_stream_ids = get_stream_channel_members(
            general_channel.stream_channel_id,
            general_channel.stream_channel_type
        )

        logger.info(f"\n✅ RESULTADO FINAL:")
        logger.info(f"  📊 Miembros en Stream: {len(final_stream_ids)}")
        logger.info(f"  🎯 Esperados: {len(expected_stream_ids)}")

        if final_stream_ids == expected_stream_ids:
            logger.info(f"  ✅ 100% SINCRONIZADO")
        else:
            missing = expected_stream_ids - final_stream_ids
            extra = final_stream_ids - expected_stream_ids
            if missing:
                logger.warning(f"  ⚠️  Faltan {len(missing)} usuarios")
            if extra:
                logger.warning(f"  ⚠️  Sobran {len(extra)} usuarios")

    except Exception as e:
        logger.error(f"❌ Error sincronizando gym {gym_id}: {e}")
        stats["errors"].append(str(e))

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Sincronizar canales generales con usuarios multi-tenant'
    )
    parser.add_argument(
        '--gym-id',
        type=int,
        help='Sincronizar solo un gimnasio específico'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simular sin hacer cambios reales'
    )

    args = parser.parse_args()

    logger.info("="*80)
    logger.info("🔄 SINCRONIZACIÓN DE CANALES GENERALES")
    logger.info("="*80)

    if args.dry_run:
        logger.warning("⚠️  MODO DRY-RUN - No se harán cambios reales\n")

    db = SessionLocal()
    try:
        # Obtener gimnasios a procesar
        if args.gym_id:
            gyms = db.query(Gym).filter(Gym.id == args.gym_id).all()
        else:
            gyms = db.query(Gym).filter(Gym.is_active == True).all()

        if not gyms:
            logger.error("No se encontraron gimnasios para procesar")
            return 1

        logger.info(f"📍 Procesando {len(gyms)} gimnasio(s)\n")

        # Sincronizar cada gimnasio
        all_stats = []
        for gym in gyms:
            stats = sync_general_channel(db, gym.id, dry_run=args.dry_run)
            all_stats.append(stats)

        # Resumen final
        logger.info("\n" + "="*80)
        logger.info("📊 RESUMEN FINAL")
        logger.info("="*80)

        total_found = sum(1 for s in all_stats if s["channel_found"])
        total_to_add = sum(s["members_to_add"] for s in all_stats)
        total_added = sum(s["members_added"] for s in all_stats)
        total_to_remove = sum(s["members_to_remove"] for s in all_stats)
        total_removed = sum(s["members_removed"] for s in all_stats)
        total_errors = sum(len(s["errors"]) for s in all_stats)

        logger.info(f"  🏋️  Gimnasios procesados: {len(gyms)}")
        logger.info(f"  ✅ Canales generales encontrados: {total_found}")
        logger.info(f"  ➕ Usuarios agregados: {total_added}/{total_to_add}")
        logger.info(f"  ➖ Usuarios removidos: {total_removed}/{total_to_remove}")
        logger.info(f"  ❌ Errores: {total_errors}")

        if args.dry_run:
            logger.warning("\n⚠️  MODO DRY-RUN - No se hicieron cambios reales")
        else:
            logger.info("\n✅ SINCRONIZACIÓN COMPLETADA")

        logger.info("="*80)

        return 0

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
