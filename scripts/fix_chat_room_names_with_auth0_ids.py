#!/usr/bin/env python3
"""
Script para corregir nombres de chat rooms que contienen auth0_ids.

Este script:
1. Identifica chat rooms con nombres que contienen auth0_ids
2. Los actualiza para usar los nuevos formatos de nombre consistentes con user_X
3. Mantiene la consistencia entre nombres y stream_channel_ids

Uso:
    python scripts/fix_chat_room_names_with_auth0_ids.py
    
Argumentos opcionales:
    --dry-run: Solo simula la corrección sin realizar cambios
    --verbose: Muestra información detallada de cada cambio
"""

import sys
import os
import argparse
import logging
import re
from typing import List, Dict, Any
from datetime import datetime

# Añadir el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.chat import ChatRoom
from app.models.user import User

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fix_chat_names")

class ChatRoomNameFixer:
    def __init__(self, dry_run: bool = False, verbose: bool = False):
        self.dry_run = dry_run
        self.verbose = verbose
        self.db = SessionLocal()
        
        logger.info(f"🚀 Iniciando corrección de nombres de chat rooms (dry_run={dry_run}, verbose={verbose})")
        
    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()
    
    def find_problematic_rooms(self) -> List[ChatRoom]:
        """
        Encuentra chat rooms con nombres que contienen auth0_ids.
        """
        try:
            # Buscar salas con nombres que contienen 'auth0'
            rooms_with_auth0 = self.db.query(ChatRoom).filter(
                ChatRoom.name.like('%auth0%')
            ).all()
            
            logger.info(f"🔍 Encontradas {len(rooms_with_auth0)} salas con nombres auth0")
            
            if self.verbose:
                for room in rooms_with_auth0:
                    logger.info(f"   📝 ID: {room.id}, Name: '{room.name}', Stream: {room.stream_channel_id}, Direct: {room.is_direct}")
            
            return rooms_with_auth0
            
        except Exception as e:
            logger.error(f"❌ Error buscando salas problemáticas: {str(e)}", exc_info=True)
            return []
    
    def generate_correct_name(self, room: ChatRoom) -> str:
        """
        Genera el nombre correcto basado en el stream_channel_id y tipo de sala.
        
        Args:
            room: Chat room a corregir
            
        Returns:
            str: Nombre correcto para la sala
        """
        try:
            if room.is_direct:
                # Para chats directos, extraer user IDs del stream_channel_id
                if room.stream_channel_id and room.stream_channel_id.startswith('direct_'):
                    # Extraer user IDs del formato: direct_user_10_user_8
                    parts = room.stream_channel_id.split('_')
                    if len(parts) >= 4:  # ['direct', 'user', '10', 'user', '8']
                        try:
                            user1_id = int(parts[2])  # '10'
                            user2_id = int(parts[4]) if len(parts) > 4 else None  # '8'
                            
                            if user2_id:
                                # Buscar nombres reales de los usuarios
                                user1 = self.db.query(User).filter(User.id == user1_id).first()
                                user2 = self.db.query(User).filter(User.id == user2_id).first()
                                
                                if user1 and user2:
                                    user1_name = self._get_display_name_for_user(user1)
                                    user2_name = self._get_display_name_for_user(user2)
                                    return f"Chat {user1_name} - {user2_name}"
                                else:
                                    return f"Chat Usuario {user1_id} - Usuario {user2_id}"
                            else:
                                return f"Chat Usuario {user1_id}"
                        except (ValueError, IndexError):
                            pass
                
                # Fallback para chats directos
                return f"Chat Directo"
            else:
                # Para chats de grupo, usar el nombre actual si no contiene auth0, o generar uno nuevo
                if room.name and 'auth0' not in room.name.lower():
                    return room.name
                else:
                    # Generar nombre basado en el evento o stream channel
                    if room.event_id:
                        return f"Chat Evento {room.event_id}"
                    elif room.stream_channel_id:
                        # Extraer información del stream_channel_id
                        clean_id = room.stream_channel_id.replace('_', ' ').title()
                        return f"Chat {clean_id}"
                    else:
                        return f"Chat Sala {room.id}"
                        
        except Exception as e:
            logger.error(f"❌ Error generando nombre correcto para sala {room.id}: {str(e)}")
            return f"Chat Sala {room.id}"
    
    def _get_display_name_for_user(self, user: User) -> str:
        """
        Obtiene un nombre para mostrar del usuario basado en los datos disponibles.
        
        Args:
            user: Objeto de usuario de la BD
            
        Returns:
            str: Nombre para mostrar
        """
        if user.first_name and user.last_name:
            return f"{user.first_name} {user.last_name}"
        elif user.first_name:
            return user.first_name
        elif user.email:
            # Usar parte antes del @ y limpiarla
            email_part = user.email.split('@')[0]
            # Remover números y caracteres especiales para hacer más legible
            clean_name = re.sub(r'[0-9._-]', ' ', email_part).title().strip()
            return clean_name if clean_name else f"Usuario {user.id}"
        else:
            return f"Usuario {user.id}"
    
    def fix_room_name(self, room: ChatRoom) -> bool:
        """
        Corrige el nombre de una sala específica.
        
        Args:
            room: Sala a corregir
            
        Returns:
            bool: True si se corrigió exitosamente
        """
        try:
            old_name = room.name
            new_name = self.generate_correct_name(room)
            
            if old_name == new_name:
                if self.verbose:
                    logger.info(f"✓ Sala {room.id}: nombre ya correcto '{new_name}'")
                return True
            
            logger.info(f"🔄 Sala {room.id}: '{old_name}' → '{new_name}'")
            
            if self.dry_run:
                logger.info(f"🔍 [DRY-RUN] Simularía cambio de nombre para sala {room.id}")
                return True
            
            # Aplicar el cambio
            room.name = new_name
            self.db.commit()
            
            logger.info(f"✅ Sala {room.id}: nombre actualizado exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error corrigiendo sala {room.id}: {str(e)}", exc_info=True)
            self.db.rollback()
            return False
    
    def fix_all_problematic_rooms(self) -> Dict[str, int]:
        """
        Corrige todas las salas con nombres problemáticos.
        
        Returns:
            Dict: Estadísticas de la corrección
        """
        try:
            # Encontrar salas problemáticas
            problematic_rooms = self.find_problematic_rooms()
            
            if not problematic_rooms:
                logger.info("✅ No se encontraron salas con nombres problemáticos")
                return {"total": 0, "fixed": 0, "errors": 0}
            
            # Corregir cada sala
            fixed_count = 0
            error_count = 0
            
            for room in problematic_rooms:
                if self.fix_room_name(room):
                    fixed_count += 1
                else:
                    error_count += 1
            
            # Reporte final
            stats = {
                "total": len(problematic_rooms),
                "fixed": fixed_count,
                "errors": error_count
            }
            
            logger.info(f"📊 Corrección completada:")
            logger.info(f"   📋 Total salas procesadas: {stats['total']}")
            logger.info(f"   ✅ Exitosamente corregidas: {stats['fixed']}")
            logger.info(f"   ❌ Errores: {stats['errors']}")
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error en corrección masiva: {str(e)}", exc_info=True)
            return {"total": 0, "fixed": 0, "errors": 1}
    
    def fix_specific_room(self, room_id: int) -> bool:
        """
        Corrige una sala específica por ID.
        
        Args:
            room_id: ID de la sala a corregir
            
        Returns:
            bool: True si se corrigió exitosamente
        """
        try:
            room = self.db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
            
            if not room:
                logger.error(f"❌ Sala con ID {room_id} no encontrada")
                return False
            
            logger.info(f"🎯 Corrigiendo sala específica: {room_id}")
            return self.fix_room_name(room)
            
        except Exception as e:
            logger.error(f"❌ Error corrigiendo sala específica {room_id}: {str(e)}", exc_info=True)
            return False

def main():
    parser = argparse.ArgumentParser(
        description="Corrige nombres de chat rooms que contienen auth0_ids"
    )
    
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Solo simula la corrección sin realizar cambios"
    )
    
    parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Muestra información detallada de cada cambio"
    )
    
    parser.add_argument(
        "--room-id", 
        type=int, 
        help="Corrige una sala específica por ID"
    )
    
    args = parser.parse_args()
    
    # Crear corrector
    fixer = ChatRoomNameFixer(dry_run=args.dry_run, verbose=args.verbose)
    
    try:
        if args.room_id:
            # Modo de corrección de sala específica
            logger.info(f"🎯 Modo de corrección específica para sala: {args.room_id}")
            success = fixer.fix_specific_room(args.room_id)
        else:
            # Modo de corrección masiva
            logger.info("🌐 Modo de corrección masiva")
            stats = fixer.fix_all_problematic_rooms()
            success = stats["errors"] == 0
        
        if success:
            logger.info("🎉 Corrección completada exitosamente")
            sys.exit(0)
        else:
            logger.error("💥 Corrección falló")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("⏸️ Corrección interrumpida por el usuario")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Error inesperado: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()