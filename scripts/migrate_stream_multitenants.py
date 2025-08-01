#!/usr/bin/env python3
"""
Script de migración para Stream Chat Multi-tenancy.
Migra usuarios existentes a sus gimnasios (teams) y actualiza canales.
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz al PATH
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from stream_chat import StreamChat
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging
from typing import Dict, List, Set
import time
from collections import defaultdict

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cargar configuración
from app.core.config import get_settings
settings = get_settings()
from app.core.stream_client import stream_client
from app.models.user import User
from app.models.user_gym import UserGym
from app.models.chat import ChatRoom
from app.db.session import SessionLocal


class StreamMultiTenantMigration:
    def __init__(self):
        self.stream_client = stream_client
        self.db = SessionLocal()
        self.migrated_users = set()
        self.migrated_channels = set()
        self.errors = []
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()
        
    def get_user_gyms_mapping(self) -> Dict[int, List[int]]:
        """Obtiene el mapeo de usuarios a sus gimnasios."""
        logger.info("Obteniendo mapeo de usuarios a gimnasios...")
        
        from sqlalchemy import text
        result = self.db.execute(text("SELECT user_id, gym_id FROM public.user_gyms"))
        
        mapping = defaultdict(list)
        for row in result:
            mapping[row[0]].append(row[1])
            
        logger.info(f"Encontrados {len(mapping)} usuarios con membresías en gimnasios")
        return dict(mapping)
    
    def migrate_user_to_teams(self, user_id: int, gym_ids: List[int]) -> bool:
        """Migra un usuario a sus teams (gimnasios) en Stream."""
        try:
            # Obtener usuario de la BD usando SQL directo
            from sqlalchemy import text
            result = self.db.execute(text("SELECT id, email FROM public.user WHERE id = :user_id"), {"user_id": user_id})
            user_row = result.first()
            
            if not user_row:
                logger.warning(f"Usuario {user_id} no encontrado en BD")
                return False
            
            # Determinar el ID de Stream del usuario
            stream_user_id = f"user_{user_id}"
            
            # Preparar datos del usuario con teams
            user_email = user_row[1] if user_row[1] else f"user{user_id}@example.com"
            user_data = {
                "id": stream_user_id,
                "name": user_email.split('@')[0] if user_email else f"Usuario {user_id}",
                "email": user_email,
                "teams": [f"gym_{gym_id}" for gym_id in gym_ids]
            }
            
            # Actualizar usuario en Stream
            self.stream_client.update_user(user_data)
            
            logger.info(f"Usuario {stream_user_id} migrado a teams: {user_data['teams']}")
            self.migrated_users.add(user_id)
            return True
            
        except Exception as e:
            error_msg = f"Error migrando usuario {user_id}: {str(e)}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return False
    
    def migrate_channel_to_team(self, channel_data: dict) -> bool:
        """Migra un canal para incluir información del team."""
        try:
            if not channel_data['stream_channel_id'] or not channel_data['gym_id']:
                return False
            
            # Obtener el canal de Stream
            stream_channel = self.stream_client.channel(
                channel_data['stream_channel_type'],
                channel_data['stream_channel_id']
            )
            
            # Actualizar el canal con el team
            stream_channel.update({
                "team": f"gym_{channel_data['gym_id']}",
                "gym_id": str(channel_data['gym_id'])
            })
            
            logger.info(f"Canal {channel_data['stream_channel_id']} migrado al team gym_{channel_data['gym_id']}")
            self.migrated_channels.add(channel_data['id'])
            return True
            
        except Exception as e:
            error_msg = f"Error migrando canal {channel_data['id']}: {str(e)}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return False
    
    def verify_channel_id_format(self, channel: dict) -> bool:
        """Verifica si el ID del canal tiene el formato correcto con prefijo de gimnasio."""
        if not channel['stream_channel_id'] or not channel['gym_id']:
            return False
            
        expected_prefix = f"gym_{channel['gym_id']}_"
        return channel['stream_channel_id'].startswith(expected_prefix)
    
    def run_migration(self):
        """Ejecuta la migración completa."""
        logger.info("=== Iniciando migración de Stream Chat a Multi-tenancy ===")
        
        # 1. Migrar usuarios a sus teams
        logger.info("\n1. Migrando usuarios a teams...")
        user_gyms_mapping = self.get_user_gyms_mapping()
        
        for user_id, gym_ids in user_gyms_mapping.items():
            self.migrate_user_to_teams(user_id, gym_ids)
            # Pequeña pausa para no sobrecargar la API
            if len(self.migrated_users) % 10 == 0:
                time.sleep(0.1)
        
        logger.info(f"Usuarios migrados: {len(self.migrated_users)}")
        
        # 2. Migrar canales existentes
        logger.info("\n2. Migrando canales a teams...")
        from sqlalchemy import text
        
        result = self.db.execute(text(
            "SELECT id, stream_channel_id, stream_channel_type, gym_id, name "
            "FROM public.chat_rooms "
            "WHERE stream_channel_id IS NOT NULL AND gym_id IS NOT NULL"
        ))
        
        channels = [
            {
                'id': row[0],
                'stream_channel_id': row[1], 
                'stream_channel_type': row[2],
                'gym_id': row[3],
                'name': row[4]
            } 
            for row in result
        ]
        
        channels_with_wrong_format = []
        
        for channel in channels:
            # Verificar formato del ID
            if not self.verify_channel_id_format(channel):
                channels_with_wrong_format.append(channel)
                logger.warning(f"Canal {channel['id']} tiene formato incorrecto: {channel['stream_channel_id']}")
            
            # Migrar el canal
            self.migrate_channel_to_team(channel)
            
            # Pequeña pausa
            if len(self.migrated_channels) % 10 == 0:
                time.sleep(0.1)
        
        logger.info(f"Canales migrados: {len(self.migrated_channels)}")
        logger.info(f"Canales con formato incorrecto: {len(channels_with_wrong_format)}")
        
        # 3. Crear canales generales para gimnasios que no los tengan
        logger.info("\n3. Verificando canales generales de gimnasios...")
        from app.services.gym_chat import gym_chat_service
        
        # Obtener todos los gimnasios con miembros
        gym_ids_with_members = set()
        for gym_ids in user_gyms_mapping.values():
            gym_ids_with_members.update(gym_ids)
        
        for gym_id in gym_ids_with_members:
            try:
                general_channel = gym_chat_service.get_or_create_general_channel(self.db, gym_id)
                if general_channel:
                    logger.info(f"Canal general verificado para gimnasio {gym_id}")
            except Exception as e:
                logger.error(f"Error verificando canal general para gimnasio {gym_id}: {e}")
        
        # 4. Resumen
        logger.info("\n=== Resumen de migración ===")
        logger.info(f"Usuarios migrados: {len(self.migrated_users)}")
        logger.info(f"Canales migrados: {len(self.migrated_channels)}")
        logger.info(f"Errores encontrados: {len(self.errors)}")
        
        if channels_with_wrong_format:
            logger.warning(f"\nCanales que necesitan actualizar su ID:")
            for channel in channels_with_wrong_format[:10]:  # Mostrar máximo 10
                logger.warning(f"- Canal {channel['id']}: {channel['stream_channel_id']} (Gimnasio {channel['gym_id']})")
            if len(channels_with_wrong_format) > 10:
                logger.warning(f"... y {len(channels_with_wrong_format) - 10} más")
        
        if self.errors:
            logger.error("\nErrores durante la migración:")
            for error in self.errors[:10]:  # Mostrar máximo 10 errores
                logger.error(f"- {error}")
            if len(self.errors) > 10:
                logger.error(f"... y {len(self.errors) - 10} errores más")
        
        return len(self.errors) == 0


def main():
    """Función principal del script."""
    try:
        # Confirmar antes de ejecutar
        print("\n⚠️  ADVERTENCIA: Este script migrará todos los usuarios y canales de Stream Chat")
        print("para usar el sistema multi-tenant con teams.")
        print("\nEsto actualizará:")
        print("- Todos los usuarios serán asignados a sus gimnasios como teams")
        print("- Todos los canales serán asignados a sus gimnasios correspondientes")
        print("- Se crearán canales generales para gimnasios que no los tengan")
        
        # Permitir auto-confirmación con variable de entorno
        if os.getenv('AUTO_CONFIRM_MIGRATION') == 'true':
            print("\nAuto-confirmación activada, procediendo con la migración...")
            response = 's'
        else:
            response = input("\n¿Desea continuar? (s/N): ")
            
        if response.lower() != 's':
            print("Migración cancelada.")
            return
        
        # Ejecutar migración
        with StreamMultiTenantMigration() as migration:
            success = migration.run_migration()
            
        if success:
            logger.info("\n✅ Migración completada exitosamente!")
        else:
            logger.error("\n❌ La migración completó con errores. Revise los logs.")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error fatal durante la migración: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()