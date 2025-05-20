#!/usr/bin/env python3
"""
Script para depurar la respuesta de la consulta de canales de Stream.io
"""

import sys
import os
import json
from typing import Dict, Any

# Añadir el directorio raíz al path para poder importar módulos de la aplicación
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar configuración y cliente de Stream
from app.core.config import get_settings
from app.core.stream_client import stream_client

def debug_channels_response():
    """
    Obtiene la respuesta de la consulta de canales y la imprime en formato legible
    """
    print("Conectando a Stream.io...")
    settings = get_settings()
    print(f"API Key: {settings.STREAM_API_KEY[:4]}***")
    
    try:
        # Consultar canales
        print("Consultando canales...")
        response = stream_client.query_channels(
            filter_conditions={},
            sort=[{"field": "created_at", "direction": -1}],
            limit=10
        )
        
        # Imprimir respuesta completa
        print("\n=== RESPUESTA COMPLETA ===")
        print(json.dumps(response, indent=2, default=str))
        
        # Extraer canales
        channels = response.get("channels", [])
        print(f"\n=== CANALES ENCONTRADOS: {len(channels)} ===")
        
        # Imprimir detalles de cada canal
        for i, channel in enumerate(channels):
            print(f"\n--- CANAL {i+1} ---")
            channel_id = channel.get("id")
            channel_type = channel.get("type")
            cid = channel.get("cid")
            
            print(f"ID: {channel_id}")
            print(f"Tipo: {channel_type}")
            print(f"CID: {cid}")
            
            # Imprimir miembros si existen
            members = channel.get("members", [])
            print(f"Miembros: {len(members)}")
            for j, member in enumerate(members[:3]):  # Mostrar solo los primeros 3 para brevedad
                print(f"  Miembro {j+1}: {member.get('user_id')}")
            
            if len(members) > 3:
                print(f"  ... y {len(members) - 3} más")
        
        # Explicar cómo utilizar estos datos para eliminar canales
        print("\n=== INSTRUCCIONES PARA ELIMINACIÓN DE CANALES ===")
        print("Para eliminar un canal específico, usa el siguiente comando:")
        print("python scripts/delete_channel.py --channel-type <tipo> --channel-id <id>")
        print("\nPara eliminar todos los canales, asegúrate de que el formato CID sea correcto en el script delete_all_stream_chats.py")
        
    except Exception as e:
        print(f"Error al consultar canales: {e}")
        
if __name__ == "__main__":
    debug_channels_response() 