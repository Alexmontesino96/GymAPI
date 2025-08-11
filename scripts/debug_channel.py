#!/usr/bin/env python3
"""
Script para investigar un canal específico de Stream Chat.
"""

import sys
import os

# Añadir el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.core.stream_client import stream_client

def debug_channel(channel_type: str, channel_id: str):
    """Investiga información detallada de un canal específico."""
    print(f"🔍 Investigando canal: {channel_type}:{channel_id}")
    
    try:
        # Obtener referencia al canal
        channel = stream_client.channel(channel_type, channel_id)
        
        # Intentar hacer query del canal
        try:
            response = channel.query()
            print(f"✅ Canal encontrado via query:")
            
            # Información básica del canal
            channel_data = response.get('channel', {})
            print(f"  - ID: {channel_data.get('id')}")
            print(f"  - Tipo: {channel_data.get('type')}")
            print(f"  - CID: {channel_data.get('cid')}")
            print(f"  - Nombre: {channel_data.get('name', 'Sin nombre')}")
            print(f"  - Team: {channel_data.get('team', 'Sin team')}")
            print(f"  - Creado: {channel_data.get('created_at')}")
            print(f"  - Actualizado: {channel_data.get('updated_at')}")
            print(f"  - Miembros: {channel_data.get('member_count', 0)}")
            
            # Miembros del canal
            members = response.get('members', [])
            print(f"\n👥 Miembros ({len(members)}):")
            for member in members:
                user_data = member.get('user', {})
                print(f"  - {user_data.get('id')} ({user_data.get('name', 'Sin nombre')})")
                print(f"    Teams: {user_data.get('teams', [])}")
            
            # Mensajes recientes
            messages = response.get('messages', [])
            print(f"\n💬 Mensajes recientes ({len(messages)}):")
            for msg in messages[-3:]:  # Últimos 3 mensajes
                print(f"  - {msg.get('created_at')}: {msg.get('text', 'Sin texto')}")
            
        except Exception as query_error:
            print(f"❌ Error en query: {query_error}")
            
            # Intentar obtener info básica del canal
            try:
                # Usar la API directamente para obtener información
                print(f"\n🔄 Intentando obtener info directa...")
                
                # Query manual usando el client
                filter_conditions = {
                    "type": channel_type,
                    "id": channel_id
                }
                
                channels_response = stream_client.query_channels(
                    filter_conditions=filter_conditions,
                    limit=1
                )
                
                channels = channels_response.get('channels', [])
                if channels:
                    channel_info = channels[0].get('channel', {})
                    print(f"✅ Canal encontrado via query_channels:")
                    print(f"  - ID: {channel_info.get('id')}")
                    print(f"  - Team: {channel_info.get('team', 'Sin team')}")
                    print(f"  - Miembros: {channel_info.get('member_count', 0)}")
                else:
                    print(f"❌ Canal no encontrado via query_channels")
                    
            except Exception as direct_error:
                print(f"❌ Error en query directo: {direct_error}")
    
    except Exception as e:
        print(f"❌ Error general: {e}")

def main():
    print("🔗 Conectando a Stream Chat...")
    settings = get_settings()
    print(f"🔑 API Key: {settings.STREAM_API_KEY[:4]}***")
    
    # Investigar el canal problemático
    debug_channel("messaging", "direct_user_10_user_8")

if __name__ == "__main__":
    main()