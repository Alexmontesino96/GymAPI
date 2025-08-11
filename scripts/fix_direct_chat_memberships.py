#!/usr/bin/env python3
"""
Script para reparar membresías en canales directos existentes.

Este bug causaba que el creator de un canal directo no fuera agregado como miembro,
solo el usuario de destino. Este script identifica y corrige esos canales.

Uso:
    python scripts/fix_direct_chat_memberships.py [--dry-run] [--gym-id GYM_ID]
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
from sqlalchemy import and_

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
        logging.FileHandler(f'fix_direct_chats_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)

class DirectChatFixer:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.chat_service = ChatService()
        self.actions_taken = []
        
    def log_action(self, action_type: str, description: str, data: Dict[str, Any] = None):
        """Registra una acción realizada durante la reparación."""
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

    def get_direct_rooms_with_issues(self, db: Session, gym_id: int = None) -> List[Tuple[ChatRoom, Dict[str, Any]]]:
        """
        Encuentra canales directos que pueden tener problemas de membresía.
        Retorna salas directas junto con información de sus miembros en Stream.
        """
        query = db.query(ChatRoom).filter(ChatRoom.is_direct == True)
        if gym_id:
            query = query.filter(ChatRoom.gym_id == gym_id)
            
        direct_rooms = query.all()
        problematic_rooms = []
        
        logger.info(f"Verificando {len(direct_rooms)} canales directos...")
        
        for room in direct_rooms:
            try:
                # Obtener información del canal desde Stream
                channel = stream_client.channel(room.stream_channel_type, room.stream_channel_id)
                response = channel.query(
                    user_id="system_check",
                    messages_limit=0,
                    watch=False,
                    presence=False
                )
                
                stream_channel = response.get("channel", {})
                stream_members = stream_channel.get("members", [])
                
                # Obtener miembros locales desde BD
                local_members = db.query(ChatMember).filter(ChatMember.room_id == room.id).all()
                
                # Analizar discrepancias
                analysis = self._analyze_membership_discrepancies(room, local_members, stream_members, db)
                
                if analysis["has_issues"]:
                    problematic_rooms.append((room, analysis))
                    
            except Exception as e:
                logger.error(f"Error verificando canal {room.stream_channel_id}: {e}")
                # Aún incluimos el canal problemático para revisión manual
                problematic_rooms.append((room, {
                    "has_issues": True,
                    "issues": [f"Error accediendo canal Stream: {str(e)}"],
                    "stream_members": [],
                    "local_members_count": len(db.query(ChatMember).filter(ChatMember.room_id == room.id).all())
                }))
        
        logger.info(f"Encontrados {len(problematic_rooms)} canales con problemas potenciales")
        return problematic_rooms

    def _analyze_membership_discrepancies(self, room: ChatRoom, local_members: List[ChatMember], 
                                        stream_members: List[Dict], db: Session) -> Dict[str, Any]:
        """Analiza discrepancias entre membresías locales y de Stream."""
        issues = []
        
        # Obtener IDs de usuarios locales y de Stream
        local_user_ids = {member.user_id for member in local_members}
        stream_user_ids = set()
        
        for member in stream_members:
            user_data = member.get("user", {})
            stream_id = user_data.get("id", "")
            
            # Convertir stream_id a user_id interno
            if stream_id.startswith("user_"):
                try:
                    internal_id = int(stream_id.replace("user_", ""))
                    stream_user_ids.add(internal_id)
                except ValueError:
                    logger.warning(f"No se pudo convertir stream_id {stream_id} a ID interno")
        
        # Verificar discrepancias
        missing_in_stream = local_user_ids - stream_user_ids
        missing_in_local = stream_user_ids - local_user_ids
        
        if missing_in_stream:
            issues.append(f"Usuarios en BD local pero no en Stream: {missing_in_stream}")
            
        if missing_in_local:
            issues.append(f"Usuarios en Stream pero no en BD local: {missing_in_local}")
        
        # Para canales directos, esperamos exactamente 2 miembros
        if len(stream_user_ids) != 2:
            issues.append(f"Canal directo tiene {len(stream_user_ids)} miembros en Stream (esperado: 2)")
            
        if len(local_user_ids) != 2:
            issues.append(f"Canal directo tiene {len(local_user_ids)} miembros en BD local (esperado: 2)")
        
        return {
            "has_issues": len(issues) > 0,
            "issues": issues,
            "stream_members": stream_members,
            "local_members_count": len(local_members),
            "stream_members_count": len(stream_user_ids),
            "missing_in_stream": missing_in_stream,
            "missing_in_local": missing_in_local
        }

    def fix_membership_issues(self, db: Session, problematic_rooms: List[Tuple[ChatRoom, Dict[str, Any]]]):
        """Repara problemas de membresía en los canales identificados."""
        for room, analysis in problematic_rooms:
            self.log_action("ANALYZING_ROOM", f"Canal {room.stream_channel_id} (ID: {room.id})", {
                "room_id": room.id,
                "issues": analysis["issues"],
                "gym_id": room.gym_id
            })
            
            try:
                # Obtener los miembros que deberían estar en el canal
                expected_members = db.query(ChatMember).filter(ChatMember.room_id == room.id).all()
                expected_user_ids = [member.user_id for member in expected_members]
                
                if len(expected_user_ids) != 2:
                    self.log_action("SKIP_NON_DIRECT", f"Canal {room.id} no tiene exactamente 2 miembros locales: {len(expected_user_ids)}")
                    continue
                
                # Convertir a stream IDs
                expected_stream_ids = []
                for user_id in expected_user_ids:
                    user = db.query(User).filter(User.id == user_id).first()
                    if user:
                        stream_id = self.chat_service._get_stream_id_for_user(user)
                        expected_stream_ids.append(stream_id)
                    else:
                        logger.error(f"Usuario {user_id} no encontrado en BD")
                        
                if len(expected_stream_ids) != 2:
                    self.log_action("SKIP_MISSING_USERS", f"No se pudieron obtener todos los stream_ids para canal {room.id}")
                    continue
                
                # Reparar membresías en Stream
                self._fix_stream_memberships(room, expected_stream_ids, analysis)
                
            except Exception as e:
                self.log_action("ERROR_FIXING", f"Error reparando canal {room.id}: {str(e)}")

    def _fix_stream_memberships(self, room: ChatRoom, expected_stream_ids: List[str], analysis: Dict[str, Any]):
        """Repara las membresías en Stream para un canal específico."""
        try:
            channel = stream_client.channel(room.stream_channel_type, room.stream_channel_id)
            
            # Verificar miembros actuales
            current_response = channel.query(
                user_id=expected_stream_ids[0],  # Usar el primer usuario para hacer la query
                messages_limit=0,
                watch=False,
                presence=False
            )
            
            current_members = current_response.get("channel", {}).get("members", [])
            current_stream_ids = {member.get("user", {}).get("id", "") for member in current_members}
            current_stream_ids.discard("")  # Remover IDs vacíos
            
            # Identificar miembros faltantes
            missing_members = [sid for sid in expected_stream_ids if sid not in current_stream_ids]
            
            if missing_members:
                self.log_action("ADDING_MISSING_MEMBERS", 
                              f"Agregando miembros faltantes a canal {room.stream_channel_id}: {missing_members}")
                
                if not self.dry_run:
                    channel.add_members(missing_members)
                    
                self.log_action("MEMBERS_ADDED", f"Miembros agregados exitosamente a canal {room.stream_channel_id}")
            else:
                self.log_action("NO_MISSING_MEMBERS", f"Canal {room.stream_channel_id} ya tiene todos los miembros esperados")
                
        except Exception as e:
            self.log_action("ERROR_STREAM_FIX", f"Error reparando membresías Stream para canal {room.stream_channel_id}: {str(e)}")

    def generate_report(self) -> str:
        """Genera un reporte de todas las acciones realizadas."""
        report_lines = [
            f"=== REPORTE DE REPARACIÓN CANALES DIRECTOS ===",
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

    def run_fix(self, gym_id: int = None):
        """Ejecuta el proceso completo de reparación."""
        logger.info(f"Iniciando reparación de canales directos - Modo: {'DRY-RUN' if self.dry_run else 'EJECUCIÓN'}")
        
        with SessionLocal() as db:
            # Buscar canales con problemas
            problematic_rooms = self.get_direct_rooms_with_issues(db, gym_id)
            
            if not problematic_rooms:
                logger.info("No se encontraron canales con problemas de membresía")
                return
            
            # Reparar problemas encontrados
            self.fix_membership_issues(db, problematic_rooms)
            
        # Generar reporte
        report = self.generate_report()
        report_file = f"direct_chat_fix_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
            
        logger.info(f"Reporte guardado en: {report_file}")
        print("\n" + report)

def main():
    parser = argparse.ArgumentParser(description="Repara membresías en canales directos de Stream Chat")
    parser.add_argument("--dry-run", action="store_true", default=True,
                      help="Solo mostrar lo que se haría sin ejecutar cambios")
    parser.add_argument("--execute", action="store_true", 
                      help="Ejecutar cambios reales (sobrescribe --dry-run)")
    parser.add_argument("--gym-id", type=int,
                      help="Limitar reparación a un gimnasio específico")
    
    args = parser.parse_args()
    
    # Si se especifica --execute, desactivar dry-run
    dry_run = not args.execute if args.execute else args.dry_run
    
    if not dry_run:
        confirm = input("⚠️  ADVERTENCIA: Esto modificará membresías en Stream Chat. ¿Continuar? (escribir 'CONFIRMAR'): ")
        if confirm != "CONFIRMAR":
            print("Operación cancelada.")
            return
    
    fixer = DirectChatFixer(dry_run=dry_run)
    fixer.run_fix(gym_id=args.gym_id)

if __name__ == "__main__":
    main()