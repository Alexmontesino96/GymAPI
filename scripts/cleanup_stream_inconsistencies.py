#!/usr/bin/env python3
"""
Script para limpiar inconsistencias entre BD local y Stream Chat.

Este script:
1. Identifica salas duplicadas en BD local
2. Verifica consistencia con Stream Chat
3. Limpia registros huérfanos o inconsistentes
4. Genera reporte de acciones realizadas

Uso:
    python scripts/cleanup_stream_inconsistencies.py [--dry-run] [--gym-id GYM_ID]
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple

# Agregar el directorio raíz al path para importar módulos de la app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.db.session import SessionLocal
from app.models.chat import ChatRoom, ChatMember
from app.models.user import User
from app.core.stream_client import stream_client
from app.services.chat import ChatService

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'cleanup_stream_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)

class StreamCleanup:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.chat_service = ChatService()
        self.actions_taken = []
        
    def log_action(self, action_type: str, description: str, data: Dict[str, Any] = None):
        """Registra una acción realizada durante la limpieza."""
        action = {
            "timestamp": datetime.now().isoformat(),
            "type": action_type,
            "description": description,
            "data": data or {},
            "dry_run": self.dry_run
        }
        self.actions_taken.append(action)
        
        status = "DRY-RUN" if self.dry_run else "EJECUTADO"
        logger.info(f"[{status}] {action_type}: {description}")

    def find_duplicate_rooms(self, db: Session, gym_id: int = None) -> List[Tuple[str, List[ChatRoom]]]:
        """Encuentra salas duplicadas por stream_channel_id."""
        query = db.query(ChatRoom.stream_channel_id, func.count(ChatRoom.id).label('count'))
        
        if gym_id:
            query = query.filter(ChatRoom.gym_id == gym_id)
            
        duplicates = query.group_by(ChatRoom.stream_channel_id).having(func.count(ChatRoom.id) > 1).all()
        
        duplicate_rooms = []
        for stream_id, count in duplicates:
            rooms = db.query(ChatRoom).filter(ChatRoom.stream_channel_id == stream_id)
            if gym_id:
                rooms = rooms.filter(ChatRoom.gym_id == gym_id)
            rooms = rooms.all()
            duplicate_rooms.append((stream_id, rooms))
            
        logger.info(f"Encontradas {len(duplicate_rooms)} salas duplicadas")
        return duplicate_rooms

    def verify_stream_channel_exists(self, stream_channel_type: str, stream_channel_id: str) -> bool:
        """Verifica si un canal existe en Stream Chat."""
        try:
            channel = stream_client.channel(stream_channel_type, stream_channel_id)
            # Usar un usuario del sistema para hacer la query
            response = channel.query(
                user_id="system_user",  # Usuario especial para verificaciones
                messages_limit=0,
                watch=False,
                presence=False
            )
            return bool(response.get("channel", {}).get("id"))
        except Exception as e:
            logger.debug(f"Canal {stream_channel_id} no existe en Stream: {e}")
            return False

    def cleanup_duplicate_rooms(self, db: Session, duplicate_rooms: List[Tuple[str, List[ChatRoom]]]):
        """Limpia salas duplicadas manteniendo la más reciente."""
        for stream_id, rooms in duplicate_rooms:
            self.log_action("DUPLICATES_FOUND", f"Canal {stream_id} tiene {len(rooms)} duplicados", {
                "stream_channel_id": stream_id,
                "room_ids": [room.id for room in rooms]
            })
            
            # Verificar si el canal existe en Stream
            exists_in_stream = self.verify_stream_channel_exists(rooms[0].stream_channel_type, stream_id)
            
            if not exists_in_stream:
                # Si no existe en Stream, eliminar todos los registros locales
                self.log_action("STREAM_MISSING", f"Canal {stream_id} no existe en Stream, eliminando todos los registros locales")
                for room in rooms:
                    self._delete_room_and_members(db, room)
            else:
                # Si existe en Stream, mantener solo el más reciente
                rooms.sort(key=lambda x: x.created_at, reverse=True)
                room_to_keep = rooms[0]
                rooms_to_delete = rooms[1:]
                
                self.log_action("KEEP_RECENT", f"Manteniendo sala más reciente: {room_to_keep.id} (creada: {room_to_keep.created_at})", {
                    "kept_room_id": room_to_keep.id,
                    "deleted_room_ids": [room.id for room in rooms_to_delete]
                })
                
                for room in rooms_to_delete:
                    self._delete_room_and_members(db, room)

    def find_orphan_rooms(self, db: Session, gym_id: int = None) -> List[ChatRoom]:
        """Encuentra salas sin correspondencia en Stream Chat."""
        query = db.query(ChatRoom)
        if gym_id:
            query = query.filter(ChatRoom.gym_id == gym_id)
            
        all_rooms = query.all()
        orphan_rooms = []
        
        logger.info(f"Verificando {len(all_rooms)} salas...")
        for room in all_rooms:
            if not self.verify_stream_channel_exists(room.stream_channel_type, room.stream_channel_id):
                orphan_rooms.append(room)
                
        logger.info(f"Encontradas {len(orphan_rooms)} salas huérfanas")
        return orphan_rooms

    def cleanup_orphan_rooms(self, db: Session, orphan_rooms: List[ChatRoom]):
        """Limpia salas que no existen en Stream Chat."""
        for room in orphan_rooms:
            self.log_action("ORPHAN_ROOM", f"Sala {room.id} no existe en Stream", {
                "room_id": room.id,
                "stream_channel_id": room.stream_channel_id,
                "gym_id": room.gym_id
            })
            self._delete_room_and_members(db, room)

    def _delete_room_and_members(self, db: Session, room: ChatRoom):
        """Elimina una sala y sus miembros asociados."""
        if not self.dry_run:
            # Eliminar miembros primero (relación FK)
            db.query(ChatMember).filter(ChatMember.room_id == room.id).delete()
            # Eliminar la sala
            db.delete(room)
            db.commit()
            
        self.log_action("DELETE_ROOM", f"Sala {room.id} eliminada", {
            "room_id": room.id,
            "stream_channel_id": room.stream_channel_id
        })

    def generate_report(self) -> str:
        """Genera un reporte de todas las acciones realizadas."""
        report_lines = [
            f"=== REPORTE DE LIMPIEZA STREAM CHAT ===",
            f"Fecha: {datetime.now().isoformat()}",
            f"Modo: {'DRY-RUN' if self.dry_run else 'EJECUCIÓN'}",
            f"Total acciones: {len(self.actions_taken)}",
            "",
            "RESUMEN POR TIPO:",
        ]
        
        # Agrupar acciones por tipo
        action_summary = {}
        for action in self.actions_taken:
            action_type = action["type"]
            action_summary[action_type] = action_summary.get(action_type, 0) + 1
            
        for action_type, count in action_summary.items():
            report_lines.append(f"  {action_type}: {count}")
            
        report_lines.extend([
            "",
            "DETALLE DE ACCIONES:",
        ])
        
        for i, action in enumerate(self.actions_taken, 1):
            report_lines.append(f"{i}. [{action['timestamp']}] {action['type']}: {action['description']}")
            
        return "\n".join(report_lines)

    def run_cleanup(self, gym_id: int = None):
        """Ejecuta el proceso completo de limpieza."""
        logger.info(f"Iniciando limpieza Stream Chat - Modo: {'DRY-RUN' if self.dry_run else 'EJECUCIÓN'}")
        
        with SessionLocal() as db:
            # Paso 1: Limpiar duplicados
            logger.info("=== PASO 1: Limpieza de duplicados ===")
            duplicate_rooms = self.find_duplicate_rooms(db, gym_id)
            self.cleanup_duplicate_rooms(db, duplicate_rooms)
            
            # Paso 2: Limpiar huérfanos
            logger.info("=== PASO 2: Limpieza de huérfanos ===")
            orphan_rooms = self.find_orphan_rooms(db, gym_id)
            self.cleanup_orphan_rooms(db, orphan_rooms)
            
        # Generar reporte
        report = self.generate_report()
        report_file = f"cleanup_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
            
        logger.info(f"Reporte guardado en: {report_file}")
        print("\n" + report)

def main():
    parser = argparse.ArgumentParser(description="Limpia inconsistencias entre BD local y Stream Chat")
    parser.add_argument("--dry-run", action="store_true", default=True,
                      help="Solo mostrar lo que se haría sin ejecutar cambios")
    parser.add_argument("--execute", action="store_true", 
                      help="Ejecutar cambios reales (sobrescribe --dry-run)")
    parser.add_argument("--gym-id", type=int,
                      help="Limitar limpieza a un gimnasio específico")
    
    args = parser.parse_args()
    
    # Si se especifica --execute, desactivar dry-run
    dry_run = not args.execute if args.execute else args.dry_run
    
    if not dry_run:
        confirm = input("⚠️  ADVERTENCIA: Esto eliminará datos reales. ¿Continuar? (escribir 'CONFIRMAR'): ")
        if confirm != "CONFIRMAR":
            print("Operación cancelada.")
            return
    
    cleanup = StreamCleanup(dry_run=dry_run)
    cleanup.run_cleanup(gym_id=args.gym_id)

if __name__ == "__main__":
    main()