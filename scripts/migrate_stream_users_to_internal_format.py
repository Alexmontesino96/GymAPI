#!/usr/bin/env python3
"""
Script para migrar usuarios de Stream Chat del formato legacy (auth0_id) al nuevo formato interno (user_X).

Este script:
1. Identifica usuarios en Stream con formato auth0_id
2. Los migra al nuevo formato user_X
3. Actualiza sus membresías en canales existentes
4. Corrige inconsistencias específicas como el canal direct_user_10_user_8

Uso:
    python scripts/migrate_stream_users_to_internal_format.py
    
Argumentos opcionales:
    --dry-run: Solo simula la migración sin realizar cambios
    --fix-channel CHANNEL_ID: Corrige un canal específico
    --force: Fuerza la migración incluso si hay errores
"""

import sys
import os
import argparse
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# Añadir el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.core.stream_client import stream_client
from app.core.stream_utils import (
    get_stream_id_from_internal, 
    get_internal_id_from_stream,
    is_internal_id_format,
    is_legacy_id_format
)
from app.db.session import SessionLocal
from app.models.user import User
from app.models.user_gym import UserGym

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("stream_migration")

class StreamUserMigrator:
    def __init__(self, dry_run: bool = False, force: bool = False):
        self.dry_run = dry_run
        self.force = force
        self.settings = get_settings()
        self.db = SessionLocal()
        
        logger.info(f"🚀 Iniciando migración de usuarios Stream (dry_run={dry_run}, force={force})")
        
    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()
    
    def get_all_stream_users(self) -> List[Dict[str, Any]]:
        """
        Obtiene todos los usuarios de Stream Chat.
        """
        try:
            logger.info("📋 Obteniendo lista de usuarios de Stream...")
            
            # Usar la API de Stream para obtener usuarios
            response = stream_client.query_users(
                filter_conditions={},
                limit=1000,  # Ajustar según necesidad
                offset=0
            )
            
            users = response.get('users', [])
            logger.info(f"📊 Encontrados {len(users)} usuarios en Stream")
            
            return users
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo usuarios de Stream: {str(e)}", exc_info=True)
            return []
    
    def identify_legacy_users(self, stream_users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identifica usuarios que están usando el formato legacy (auth0_id).
        """
        legacy_users = []
        
        for user in stream_users:
            user_id = user.get('id', '')
            
            if is_legacy_id_format(user_id):
                # Buscar el usuario correspondiente en nuestra BD
                db_user = self.db.query(User).filter(User.auth0_id == user_id).first()
                
                if db_user:
                    legacy_users.append({
                        'stream_user': user,
                        'db_user': db_user,
                        'old_stream_id': user_id,
                        'new_stream_id': get_stream_id_from_internal(db_user.id)
                    })
                else:
                    logger.warning(f"⚠️ Usuario {user_id} existe en Stream pero no en BD local")
        
        logger.info(f"🔍 Identificados {len(legacy_users)} usuarios legacy para migrar")
        return legacy_users
    
    def migrate_user(self, user_data: Dict[str, Any]) -> bool:
        """
        Migra un usuario individual del formato legacy al nuevo formato.
        """
        old_id = user_data['old_stream_id']
        new_id = user_data['new_stream_id']
        db_user = user_data['db_user']
        
        try:
            logger.info(f"👤 Migrando usuario: {old_id} → {new_id}")
            
            if self.dry_run:
                logger.info(f"🔍 [DRY-RUN] Simularía migración de {old_id} → {new_id}")
                return True
            
            # 1. Crear nuevo usuario con el formato correcto
            # Obtener teams del usuario para mantener la configuración multi-tenant
            user_gyms = self.db.query(UserGym).filter(UserGym.user_id == db_user.id).all()
            user_teams = [f"gym_{ug.gym_id}" for ug in user_gyms]
            
            new_user_data = {
                "id": new_id,
                "name": user_data['stream_user'].get('name', f"Usuario {db_user.id}"),
                "email": user_data['stream_user'].get('email', db_user.email),
                "image": user_data['stream_user'].get('image')
            }
            
            if user_teams:
                new_user_data["teams"] = user_teams
            
            # Crear/actualizar el nuevo usuario
            stream_client.update_user(new_user_data)
            logger.info(f"✅ Usuario {new_id} creado/actualizado en Stream")
            
            # 2. Obtener canales donde el usuario legacy es miembro
            try:
                channels_response = stream_client.query_channels(
                    filter_conditions={"members": {"$in": [old_id]}},
                    limit=100
                )
                
                channels = channels_response.get('channels', [])
                logger.info(f"📺 Usuario {old_id} es miembro de {len(channels)} canales")
                
                # 3. Migrar membresía a cada canal
                for channel_data in channels:
                    channel_info = channel_data.get('channel', {})
                    channel_type = channel_info.get('type')
                    channel_id = channel_info.get('id')
                    
                    if channel_type and channel_id:
                        try:
                            # Obtener objeto canal
                            channel = stream_client.channel(channel_type, channel_id)
                            
                            # Agregar nuevo usuario al canal
                            channel.add_members([new_id])
                            
                            # Remover usuario legacy del canal
                            channel.remove_members([old_id])
                            
                            logger.info(f"🔄 Canal {channel_id}: {old_id} → {new_id}")
                            
                        except Exception as e:
                            logger.error(f"❌ Error migrando canal {channel_id}: {str(e)}")
                            if not self.force:
                                return False
                
                # 4. Eliminar usuario legacy de Stream (opcional)
                # Comentado por seguridad - se puede activar después de verificar que todo funciona
                # try:
                #     stream_client.delete_user(old_id, mark_messages_deleted=False)
                #     logger.info(f"🗑️ Usuario legacy {old_id} eliminado de Stream")
                # except Exception as e:
                #     logger.warning(f"⚠️ No se pudo eliminar usuario legacy {old_id}: {str(e)}")
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Error obteniendo canales para usuario {old_id}: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error migrando usuario {old_id}: {str(e)}", exc_info=True)
            return False
    
    def fix_specific_channel(self, channel_id: str) -> bool:
        """
        Corrige un canal específico asegurando que todos sus miembros usen el formato correcto.
        """
        try:
            logger.info(f"🔧 Corrigiendo canal específico: {channel_id}")
            
            # Inferir tipo de canal (por defecto messaging para canales directos)
            channel_type = "messaging"
            
            if self.dry_run:
                logger.info(f"🔍 [DRY-RUN] Simularía corrección del canal {channel_id}")
                return True
            
            # Obtener canal
            channel = stream_client.channel(channel_type, channel_id)
            
            try:
                # Query del canal para obtener miembros actuales
                response = channel.query(
                    messages_limit=0,
                    watch=False,
                    presence=False
                )
                
                members = response.get("members", [])
                logger.info(f"📊 Canal {channel_id} tiene {len(members)} miembros")
                
                # Identificar miembros con formato legacy y sus equivalentes nuevos
                members_to_migrate = []
                
                for member in members:
                    member_id = member.get("user_id", "")
                    
                    if is_legacy_id_format(member_id):
                        # Buscar usuario correspondiente en BD
                        db_user = self.db.query(User).filter(User.auth0_id == member_id).first()
                        
                        if db_user:
                            new_id = get_stream_id_from_internal(db_user.id)
                            members_to_migrate.append({
                                "old_id": member_id,
                                "new_id": new_id,
                                "db_user": db_user
                            })
                            logger.info(f"🔄 Miembro a migrar: {member_id} → {new_id}")
                
                # Ejecutar migración de miembros
                for migration in members_to_migrate:
                    old_id = migration["old_id"]
                    new_id = migration["new_id"]
                    db_user = migration["db_user"]
                    
                    try:
                        # Crear/actualizar usuario con nuevo formato si no existe
                        user_gyms = self.db.query(UserGym).filter(UserGym.user_id == db_user.id).all()
                        user_teams = [f"gym_{ug.gym_id}" for ug in user_gyms]
                        
                        new_user_data = {
                            "id": new_id,
                            "name": f"Usuario {db_user.id}",
                            "email": db_user.email
                        }
                        
                        if user_teams:
                            new_user_data["teams"] = user_teams
                        
                        stream_client.update_user(new_user_data)
                        
                        # Agregar nuevo miembro al canal
                        channel.add_members([new_id])
                        logger.info(f"✅ Agregado {new_id} al canal {channel_id}")
                        
                        # Remover miembro legacy
                        channel.remove_members([old_id])
                        logger.info(f"🗑️ Removido {old_id} del canal {channel_id}")
                        
                    except Exception as e:
                        logger.error(f"❌ Error migrando miembro {old_id} en canal {channel_id}: {str(e)}")
                        if not self.force:
                            return False
                
                logger.info(f"✅ Canal {channel_id} corregido exitosamente")
                return True
                
            except Exception as e:
                logger.error(f"❌ Error consultando canal {channel_id}: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error corrigiendo canal {channel_id}: {str(e)}", exc_info=True)
            return False
    
    def run_full_migration(self) -> bool:
        """
        Ejecuta la migración completa de todos los usuarios legacy.
        """
        try:
            logger.info("🚀 Iniciando migración completa de usuarios...")
            
            # 1. Obtener todos los usuarios de Stream
            stream_users = self.get_all_stream_users()
            if not stream_users:
                logger.error("❌ No se pudieron obtener usuarios de Stream")
                return False
            
            # 2. Identificar usuarios legacy
            legacy_users = self.identify_legacy_users(stream_users)
            if not legacy_users:
                logger.info("✅ No hay usuarios legacy para migrar")
                return True
            
            # 3. Migrar cada usuario
            success_count = 0
            error_count = 0
            
            for user_data in legacy_users:
                if self.migrate_user(user_data):
                    success_count += 1
                else:
                    error_count += 1
                    if not self.force:
                        logger.error("❌ Deteniendo migración debido a errores. Use --force para continuar.")
                        break
            
            # 4. Reporte final
            logger.info(f"📊 Migración completada:")
            logger.info(f"   ✅ Exitosos: {success_count}")
            logger.info(f"   ❌ Errores: {error_count}")
            logger.info(f"   📋 Total: {len(legacy_users)}")
            
            return error_count == 0 or self.force
            
        except Exception as e:
            logger.error(f"❌ Error en migración completa: {str(e)}", exc_info=True)
            return False

def main():
    parser = argparse.ArgumentParser(
        description="Migra usuarios de Stream Chat del formato legacy al nuevo formato interno"
    )
    
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Solo simula la migración sin realizar cambios"
    )
    
    parser.add_argument(
        "--fix-channel", 
        type=str, 
        help="Corrige un canal específico (ej: direct_user_10_user_8)"
    )
    
    parser.add_argument(
        "--force", 
        action="store_true", 
        help="Continúa la migración incluso si hay errores"
    )
    
    args = parser.parse_args()
    
    # Crear migrador
    migrator = StreamUserMigrator(dry_run=args.dry_run, force=args.force)
    
    try:
        if args.fix_channel:
            # Modo de corrección de canal específico
            logger.info(f"🎯 Modo de corrección específica para canal: {args.fix_channel}")
            success = migrator.fix_specific_channel(args.fix_channel)
        else:
            # Modo de migración completa
            logger.info("🌐 Modo de migración completa")
            success = migrator.run_full_migration()
        
        if success:
            logger.info("🎉 Migración completada exitosamente")
            sys.exit(0)
        else:
            logger.error("💥 Migración falló")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("⏸️ Migración interrumpida por el usuario")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Error inesperado: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()