#!/usr/bin/env python3
"""
Script para auditar la sincronización entre Stream Chat y la base de datos local.

Este script:
1. Lista todos los canales existentes en Stream Chat
2. Verifica cuáles tienen ChatRoom en la BD local
3. Identifica inconsistencias en ambas direcciones
4. Genera reporte detallado para análisis manual

Uso:
    python scripts/audit_stream_sync.py --gym-id 1
    python scripts/audit_stream_sync.py --gym-id 1 --only-issues
    python scripts/audit_stream_sync.py --gym-id 1 --type direct --verbose
"""

import os
import sys
import argparse
import logging
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

# Agregar el directorio raíz al path para importar módulos de la app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from sqlalchemy import and_, text

from app.db.session import SessionLocal
from app.core.stream_client import stream_client
from app.core.stream_utils import get_internal_id_from_stream, is_internal_id_format

# Importar TODOS los modelos para evitar errores de lazy loading
# Los modelos User, ChatRoom, etc. tienen referencias a modelos no importados
try:
    from app.models.story import Story, StoryHighlight
except ImportError:
    pass

try:
    from app.models.post import Post
except ImportError:
    pass

# Importar modelos principales
from app.models import ChatRoom, ChatMember, User, Event

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'audit_stream_sync_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)


class StreamSyncAuditor:
    """Audita la sincronización entre Stream Chat y la base de datos local."""

    def __init__(self, gym_id: int, verbose: bool = False):
        self.gym_id = gym_id
        self.verbose = verbose
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "gym_id": gym_id,
            "summary": {},
            "stream_only_channels": [],
            "db_only_chatrooms": [],
            "synced_channels": [],
            "recommendations": defaultdict(int)
        }

    def get_all_stream_channels(self) -> List[Dict[str, Any]]:
        """
        Obtiene todos los canales de Stream Chat para el gimnasio.

        Returns:
            Lista de diccionarios con información de canales
        """
        logger.info(f"🔍 Obteniendo canales de Stream Chat para gym_id={self.gym_id}...")

        channels = []
        try:
            # Query channels por team (multi-tenant)
            team_filter = f"gym_{self.gym_id}"

            # Obtener canales con filtros
            response = stream_client.query_channels(
                filter_conditions={
                    "team": team_filter
                },
                sort=[{"field": "created_at", "direction": -1}],
                options={"limit": 100}  # Ajustar si hay más de 100 canales
            )

            for item in response.get("channels", []):
                # Los datos del canal pueden estar en "channel" o directamente en el item
                channel_data = item.get("channel", item)

                # Extraer stream_channel_id correctamente
                # El formato es "tipo:id", ej: "messaging:direct_user_10_user_8"
                cid = channel_data.get("cid", "")
                channel_id = channel_data.get("id")

                # Si no hay 'id', extraerlo de 'cid'
                if not channel_id and cid:
                    # cid tiene formato "tipo:id", tomamos la parte después de ":"
                    parts = cid.split(":", 1)
                    if len(parts) == 2:
                        channel_id = parts[1]

                if not channel_id:
                    if self.verbose:
                        logger.warning(f"Canal sin ID válido, skipping...")
                    continue

                channel_info = {
                    "stream_channel_id": channel_id,
                    "type": channel_data.get("type", "messaging"),
                    "created_at": channel_data.get("created_at"),
                    "updated_at": channel_data.get("updated_at"),
                    "last_message_at": channel_data.get("last_message_at"),
                    "member_count": channel_data.get("member_count", 0),
                    "members": [m.get("user_id") or m.get("user", {}).get("id") for m in item.get("members", [])],
                    "name": channel_data.get("name"),
                    "team": channel_data.get("team"),
                    "raw_cid": cid  # Para debugging
                }
                channels.append(channel_info)

            logger.info(f"✅ Encontrados {len(channels)} canales en Stream Chat")

        except Exception as e:
            logger.error(f"❌ Error obteniendo canales de Stream: {e}", exc_info=True)

        return channels

    def get_all_chatrooms(self, db: Session) -> List[Dict[str, Any]]:
        """
        Obtiene todos los ChatRooms de la BD para el gimnasio usando SQL directo.

        Args:
            db: Sesión de base de datos

        Returns:
            Lista de diccionarios con información de ChatRooms
        """
        logger.info(f"🔍 Obteniendo ChatRooms de BD para gym_id={self.gym_id}...")

        try:
            # Usar SQL directo para evitar problemas de lazy loading de modelos
            query = text("""
                SELECT
                    id,
                    stream_channel_id,
                    stream_channel_type,
                    name,
                    gym_id,
                    created_at,
                    updated_at,
                    event_id,
                    is_direct,
                    status
                FROM chat_rooms
                WHERE gym_id = :gym_id
            """)

            result = db.execute(query, {"gym_id": self.gym_id})
            rows = result.fetchall()

            chatrooms = []
            for row in rows:
                chatrooms.append({
                    "id": row[0],
                    "stream_channel_id": row[1],
                    "stream_channel_type": row[2],
                    "name": row[3],
                    "gym_id": row[4],
                    "created_at": row[5],
                    "updated_at": row[6],
                    "event_id": row[7],
                    "is_direct": row[8],
                    "status": row[9]
                })

            logger.info(f"✅ Encontrados {len(chatrooms)} ChatRooms en BD")
            return chatrooms

        except Exception as e:
            logger.error(f"❌ Error obteniendo ChatRooms de BD: {e}", exc_info=True)
            return []

    def parse_channel_id(self, channel_id: str) -> Dict[str, Any]:
        """
        Analiza un stream_channel_id para extraer información.

        Args:
            channel_id: ID del canal de Stream

        Returns:
            Diccionario con categoría y datos extraídos
        """
        # Patrón para chat directo: direct_user_X_user_Y
        direct_pattern = r"direct_user_(\d+)_user_(\d+)"
        direct_match = re.match(direct_pattern, channel_id)
        if direct_match:
            return {
                "category": "direct_chat",
                "user1_id": int(direct_match.group(1)),
                "user2_id": int(direct_match.group(2))
            }

        # Patrón para evento: event_{event_id}_{hash}
        event_pattern = r"event_(\d+)_([a-f0-9]+)"
        event_match = re.match(event_pattern, channel_id)
        if event_match:
            return {
                "category": "event_chat",
                "event_id": int(event_match.group(1)),
                "hash": event_match.group(2)
            }

        # Patrón para grupo: room_{name}_{creator_id}
        room_pattern = r"room_(.+)_(\d+)"
        room_match = re.match(room_pattern, channel_id)
        if room_match:
            return {
                "category": "group_chat",
                "name": room_match.group(1),
                "creator_id": int(room_match.group(2))
            }

        # Formato desconocido
        return {
            "category": "unknown",
            "raw_id": channel_id
        }

    def check_users_exist(self, db: Session, user_ids: List[int]) -> Dict[int, bool]:
        """
        Verifica si usuarios existen en la BD usando SQL directo.

        Args:
            db: Sesión de base de datos
            user_ids: Lista de IDs internos de usuarios

        Returns:
            Diccionario {user_id: exists}
        """
        result = {}
        try:
            if not user_ids:
                return result

            # Usar SQL directo
            placeholders = ",".join([":id" + str(i) for i in range(len(user_ids))])
            query = text(f"SELECT id FROM \"user\" WHERE id IN ({placeholders})")
            params = {f"id{i}": uid for i, uid in enumerate(user_ids)}

            result_set = db.execute(query, params)
            existing_ids = {row[0] for row in result_set.fetchall()}

            for uid in user_ids:
                result[uid] = uid in existing_ids

        except Exception as e:
            logger.error(f"Error verificando usuarios: {e}")
            for uid in user_ids:
                result[uid] = False

        return result

    def check_event_exists(self, db: Session, event_id: int) -> bool:
        """
        Verifica si un evento existe en la BD usando SQL directo.

        Args:
            db: Sesión de base de datos
            event_id: ID del evento

        Returns:
            True si existe, False en caso contrario
        """
        try:
            query = text("SELECT COUNT(*) FROM events WHERE id = :event_id")
            result = db.execute(query, {"event_id": event_id})
            count = result.scalar()
            return count > 0
        except Exception as e:
            logger.error(f"Error verificando evento {event_id}: {e}")
            return False

    def analyze_stream_only_channel(self, db: Session, channel: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analiza un canal que existe solo en Stream (no en BD).

        Args:
            db: Sesión de base de datos
            channel: Información del canal de Stream

        Returns:
            Análisis del canal con recomendaciones
        """
        channel_id = channel["stream_channel_id"]
        parsed = self.parse_channel_id(channel_id)

        analysis = {
            "stream_channel_id": channel_id,
            "type": channel["type"],
            "created_at": channel.get("created_at"),
            "last_message_at": channel.get("last_message_at"),
            "members_count": channel.get("member_count", 0),
            "members": channel.get("members", []),
            "analysis": parsed.copy()
        }

        # Analizar según categoría
        if parsed["category"] == "direct_chat":
            user1_id = parsed["user1_id"]
            user2_id = parsed["user2_id"]

            users_exist = self.check_users_exist(db, [user1_id, user2_id])
            analysis["analysis"]["user1_exists"] = users_exist.get(user1_id, False)
            analysis["analysis"]["user2_exists"] = users_exist.get(user2_id, False)

            if users_exist.get(user1_id) and users_exist.get(user2_id):
                analysis["analysis"]["recommendation"] = "CREATE_CHATROOM"
                analysis["analysis"]["command"] = f"python scripts/sync_channel_to_db.py --channel-id {channel_id}"
                self.results["recommendations"]["create_chatrooms"] += 1
            else:
                analysis["analysis"]["recommendation"] = "DELETE_FROM_STREAM"
                analysis["analysis"]["reason"] = "Uno o ambos usuarios no existen"
                analysis["analysis"]["command"] = f"python scripts/delete_orphan_channel.py --channel-id {channel_id}"
                self.results["recommendations"]["delete_from_stream"] += 1

        elif parsed["category"] == "event_chat":
            event_id = parsed["event_id"]
            event_exists = self.check_event_exists(db, event_id)

            analysis["analysis"]["event_exists"] = event_exists
            analysis["analysis"]["has_messages"] = channel.get("last_message_at") is not None

            if event_exists:
                analysis["analysis"]["recommendation"] = "CREATE_CHATROOM"
                analysis["analysis"]["command"] = f"python scripts/sync_channel_to_db.py --channel-id {channel_id}"
                self.results["recommendations"]["create_chatrooms"] += 1
            else:
                analysis["analysis"]["recommendation"] = "DELETE_FROM_STREAM"
                analysis["analysis"]["reason"] = "Evento no existe en BD"
                analysis["analysis"]["command"] = f"python scripts/delete_orphan_channel.py --channel-id {channel_id}"
                self.results["recommendations"]["delete_from_stream"] += 1

        elif parsed["category"] == "group_chat":
            creator_id = parsed["creator_id"]
            creator_exists = self.check_users_exist(db, [creator_id]).get(creator_id, False)

            analysis["analysis"]["creator_exists"] = creator_exists
            analysis["analysis"]["recommendation"] = "CREATE_CHATROOM"
            analysis["analysis"]["command"] = f"python scripts/sync_channel_to_db.py --channel-id {channel_id}"
            self.results["recommendations"]["create_chatrooms"] += 1

        else:
            # Formato desconocido
            analysis["analysis"]["recommendation"] = "INVESTIGATE"
            analysis["analysis"]["reason"] = "Formato de canal desconocido"
            self.results["recommendations"]["investigate"] += 1

        return analysis

    def analyze_db_only_chatroom(self, chatroom: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analiza un ChatRoom que existe solo en BD (no en Stream).

        Args:
            chatroom: Diccionario con información del ChatRoom

        Returns:
            Análisis del ChatRoom con recomendaciones
        """
        return {
            "chatroom_id": chatroom["id"],
            "stream_channel_id": chatroom["stream_channel_id"],
            "type": chatroom.get("stream_channel_type", "messaging"),
            "name": chatroom.get("name"),
            "created_at": chatroom["created_at"].isoformat() if chatroom.get("created_at") else None,
            "is_direct": chatroom.get("is_direct", False),
            "event_id": chatroom.get("event_id"),
            "status": chatroom.get("status", "ACTIVE"),
            "recommendation": "DELETE_FROM_DB",
            "reason": "Canal no existe en Stream (eliminado manualmente)",
            "command": f"# Eliminar ChatRoom ID {chatroom['id']} de la BD"
        }

    def run_audit(self) -> Dict[str, Any]:
        """
        Ejecuta la auditoría completa.

        Returns:
            Resultados de la auditoría
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🔍 AUDITORÍA DE SINCRONIZACIÓN STREAM CHAT ↔ BD LOCAL")
        logger.info(f"{'='*60}")
        logger.info(f"Gym ID: {self.gym_id}")
        logger.info(f"Timestamp: {self.results['timestamp']}")
        logger.info(f"{'='*60}\n")

        db = SessionLocal()
        try:
            # 1. Obtener datos de Stream y BD
            stream_channels = self.get_all_stream_channels()
            db_chatrooms = self.get_all_chatrooms(db)

            # Crear mapas para comparación
            stream_map = {ch["stream_channel_id"]: ch for ch in stream_channels}
            db_map = {cr["stream_channel_id"]: cr for cr in db_chatrooms}

            # 2. Identificar canales solo en Stream
            logger.info("\n🔍 Analizando canales solo en Stream...")
            for channel_id, channel in stream_map.items():
                if channel_id not in db_map:
                    analysis = self.analyze_stream_only_channel(db, channel)
                    self.results["stream_only_channels"].append(analysis)

                    if self.verbose:
                        logger.info(f"  ⚠️  {channel_id} - {analysis['analysis'].get('category', 'unknown')}")

            # 3. Identificar ChatRooms solo en BD
            logger.info("\n🔍 Analizando ChatRooms solo en BD...")
            for channel_id, chatroom in db_map.items():
                if channel_id not in stream_map:
                    analysis = self.analyze_db_only_chatroom(chatroom)
                    self.results["db_only_chatrooms"].append(analysis)
                    self.results["recommendations"]["delete_from_db"] += 1

                    if self.verbose:
                        logger.info(f"  ⚠️  {channel_id} - No existe en Stream")

            # 4. Canales sincronizados
            synced_count = 0
            for channel_id in stream_map:
                if channel_id in db_map:
                    synced_count += 1
                    if self.verbose:
                        self.results["synced_channels"].append({
                            "stream_channel_id": channel_id,
                            "chatroom_id": db_map[channel_id]["id"]
                        })

            # 5. Generar resumen
            self.results["summary"] = {
                "total_stream_channels": len(stream_channels),
                "total_db_chatrooms": len(db_chatrooms),
                "synced": synced_count,
                "stream_only": len(self.results["stream_only_channels"]),
                "db_only": len(self.results["db_only_chatrooms"])
            }

            logger.info("\n✅ Auditoría completada")

        except Exception as e:
            logger.error(f"❌ Error durante auditoría: {e}", exc_info=True)
        finally:
            db.close()

        return self.results

    def print_summary(self):
        """Imprime resumen en consola con formato."""
        summary = self.results["summary"]

        print(f"\n{'='*60}")
        print(f"📊 RESUMEN:")
        print(f"  ✅ Canales sincronizados:        {summary.get('synced', 0)}")
        print(f"  ⚠️  Solo en Stream:               {summary.get('stream_only', 0)}")
        print(f"  ⚠️  Solo en BD:                   {summary.get('db_only', 0)}")
        print(f"  📈 Total canales Stream:         {summary.get('total_stream_channels', 0)}")
        print(f"  📈 Total ChatRooms BD:           {summary.get('total_db_chatrooms', 0)}")
        print(f"{'='*60}\n")

        # Canales solo en Stream
        if self.results["stream_only_channels"]:
            print(f"❌ CANALES EN STREAM SIN CHATROOM ({len(self.results['stream_only_channels'])}):\n")

            for i, channel in enumerate(self.results["stream_only_channels"], 1):
                print(f"{i}. {channel['stream_channel_id']}")

                category = channel["analysis"].get("category", "unknown")
                if category == "direct_chat":
                    print(f"   - Tipo: Chat Directo")
                    print(f"   - Miembros: usuarios {channel['analysis']['user1_id']}, {channel['analysis']['user2_id']}")
                    u1_exists = "✅" if channel['analysis'].get('user1_exists') else "❌"
                    u2_exists = "✅" if channel['analysis'].get('user2_exists') else "❌"
                    print(f"   - Estado usuarios: {u1_exists} Usuario {channel['analysis']['user1_id']}, {u2_exists} Usuario {channel['analysis']['user2_id']}")

                elif category == "event_chat":
                    print(f"   - Tipo: Canal de Evento")
                    print(f"   - Evento ID: {channel['analysis']['event_id']}")
                    event_status = "✅ Existe" if channel['analysis'].get('event_exists') else "❌ No existe"
                    print(f"   - Estado evento: {event_status}")
                    has_msgs = "Sí" if channel['analysis'].get('has_messages') else "Sin mensajes"
                    print(f"   - Mensajes: {has_msgs}")

                elif category == "group_chat":
                    print(f"   - Tipo: Grupo")
                    print(f"   - Nombre: {channel['analysis'].get('name', 'Sin nombre')}")
                    print(f"   - Creador: Usuario {channel['analysis']['creator_id']}")

                print(f"   - Creado: {channel.get('created_at', 'Desconocido')}")
                print(f"   - Último mensaje: {channel.get('last_message_at', 'Sin mensajes')}")
                print(f"   - Recomendación: {channel['analysis'].get('recommendation', 'INVESTIGATE')}")
                if 'command' in channel['analysis']:
                    print(f"   - Comando: {channel['analysis']['command']}")
                print()

        # ChatRooms solo en BD
        if self.results["db_only_chatrooms"]:
            print(f"\n⚠️  CHATROOMS EN BD SIN CANAL ({len(self.results['db_only_chatrooms'])}):\n")

            for i, chatroom in enumerate(self.results["db_only_chatrooms"], 1):
                print(f"{i}. {chatroom['stream_channel_id']}")
                print(f"   - ChatRoom ID: {chatroom['chatroom_id']}")
                print(f"   - Tipo: {'Directo' if chatroom.get('is_direct') else 'Grupo'}")
                if chatroom.get('event_id'):
                    print(f"   - Evento ID: {chatroom['event_id']}")
                print(f"   - Estado: {chatroom.get('status', 'UNKNOWN')}")
                print(f"   - Recomendación: {chatroom.get('recommendation', 'INVESTIGATE')}")
                print()

        # Recomendaciones
        print(f"\n{'='*60}")
        print(f"📋 RECOMENDACIONES:")
        recs = self.results["recommendations"]
        if recs["create_chatrooms"] > 0:
            print(f"  🔧 Crear ChatRooms: {recs['create_chatrooms']}")
        if recs["delete_from_stream"] > 0:
            print(f"  🗑️  Eliminar de Stream: {recs['delete_from_stream']}")
        if recs["delete_from_db"] > 0:
            print(f"  🗑️  Eliminar de BD: {recs['delete_from_db']}")
        if recs["investigate"] > 0:
            print(f"  🔍 Investigar: {recs['investigate']}")
        print(f"{'='*60}\n")

    def save_report(self, filename: Optional[str] = None):
        """Guarda el reporte en archivo JSON."""
        if not filename:
            filename = f"audit_stream_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False, default=str)

            logger.info(f"💾 Reporte completo guardado en: {filename}")
            return filename
        except Exception as e:
            logger.error(f"❌ Error guardando reporte: {e}")
            return None


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="Auditoría de sincronización Stream Chat ↔ BD local"
    )
    parser.add_argument(
        "--gym-id",
        type=int,
        required=True,
        help="ID del gimnasio a auditar"
    )
    parser.add_argument(
        "--only-issues",
        action="store_true",
        help="Mostrar solo inconsistencias (no canales sincronizados)"
    )
    parser.add_argument(
        "--type",
        choices=["direct", "event", "group", "all"],
        default="all",
        help="Filtrar por tipo de canal"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Mostrar información detallada"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Nombre del archivo de salida JSON"
    )

    args = parser.parse_args()

    # Crear auditor y ejecutar
    auditor = StreamSyncAuditor(gym_id=args.gym_id, verbose=args.verbose)
    results = auditor.run_audit()

    # Aplicar filtros si se especificaron
    if args.type != "all":
        type_map = {
            "direct": "direct_chat",
            "event": "event_chat",
            "group": "group_chat"
        }
        filter_category = type_map[args.type]
        results["stream_only_channels"] = [
            ch for ch in results["stream_only_channels"]
            if ch["analysis"].get("category") == filter_category
        ]

    # Mostrar resumen
    auditor.print_summary()

    # Guardar reporte
    output_file = auditor.save_report(args.output)

    if output_file:
        print(f"\n✅ Auditoría completada exitosamente")
        print(f"📄 Reporte: {output_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
