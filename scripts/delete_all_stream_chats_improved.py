#!/usr/bin/env python3
"""
Script mejorado para eliminar todos los canales de chat en Stream.io

Este script corrige los problemas encontrados en la versión anterior
y permite eliminar todos los canales de forma segura.
"""

import sys
import os
import time
import argparse
import logging
from typing import List, Dict, Any

# Añadir el directorio raíz al path para poder importar módulos de la aplicación
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar configuración y cliente de Stream
from app.core.config import get_settings
from app.core.stream_client import stream_client

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_all_channels(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Obtiene todos los canales de Stream.io
    
    Args:
        limit: Número máximo de canales a obtener por consulta
        offset: Índice desde donde comenzar la consulta
        
    Returns:
        Lista de canales encontrados
    """
    try:
        # Usar la API de Stream para obtener todos los canales
        response = stream_client.query_channels(
            filter_conditions={},
            sort=[{"field": "created_at", "direction": -1}],
            offset=offset,
            limit=limit
        )
        
        # Extraer información de canales de la respuesta
        result = []
        channels_data = response.get("channels", [])
        
        for channel_data in channels_data:
            # Extraer información del canal
            channel_info = channel_data.get("channel", {})
            
            # Obtener tipo y ID del canal
            channel_type = channel_info.get("type")
            channel_id = channel_info.get("id")
            cid = channel_info.get("cid")
            
            if channel_type and channel_id:
                result.append({
                    "type": channel_type,
                    "id": channel_id,
                    "cid": cid
                })
        
        return result
    except Exception as e:
        logger.error(f"Error al obtener canales: {e}")
        return []

def delete_channel(channel_type: str, channel_id: str) -> bool:
    """
    Elimina un canal específico
    
    Args:
        channel_type: Tipo del canal
        channel_id: ID del canal
        
    Returns:
        True si se eliminó correctamente, False en caso contrario
    """
    try:
        # Obtener referencia al canal
        channel = stream_client.channel(channel_type, channel_id)
        
        # Eliminar el canal
        response = channel.delete()
        
        logger.info(f"Canal {channel_type}:{channel_id} eliminado exitosamente")
        return True
    except Exception as e:
        logger.error(f"Error al eliminar canal {channel_type}:{channel_id}: {e}")
        return False

def delete_all_channels(batch_size: int = 25, dry_run: bool = True, quiet: bool = False) -> None:
    """
    Elimina todos los canales de Stream.io
    
    Args:
        batch_size: Número de canales a procesar por lote
        dry_run: Si es True, solo muestra los canales sin eliminarlos
        quiet: Si es True, reduce la cantidad de mensajes de log
    """
    offset = 0
    total_deleted = 0
    
    if not quiet:
        logger.info(f"Iniciando eliminación de canales en modo {'SIMULACIÓN' if dry_run else 'ELIMINACIÓN'}")
    
    while True:
        # Obtener un lote de canales
        channels = get_all_channels(limit=batch_size, offset=offset)
        
        # Si no hay más canales, terminar
        if not channels:
            if not quiet:
                logger.info(f"No se encontraron más canales. Total: {total_deleted}")
            break
        
        if not quiet:
            logger.info(f"Se encontraron {len(channels)} canales (offset: {offset})")
        
        # Procesar cada canal
        for channel in channels:
            channel_type = channel.get("type")
            channel_id = channel.get("id")
            cid = channel.get("cid")
            
            if not quiet:
                logger.info(f"Canal encontrado: {cid} (Tipo: {channel_type}, ID: {channel_id})")
            
            # Si no es dry_run, eliminar el canal
            if not dry_run:
                success = delete_channel(channel_type, channel_id)
                if success:
                    total_deleted += 1
                
                # Pequeña pausa para no sobrecargar la API
                time.sleep(0.5)
            else:
                if not quiet:
                    logger.info(f"[SIMULACIÓN] Se eliminaría canal: {cid}")
                total_deleted += 1
        
        # Avanzar al siguiente lote
        offset += batch_size
    
    logger.info(f"Proceso completado. Total de canales {'que se eliminarían' if dry_run else 'eliminados'}: {total_deleted}")

def main():
    """Función principal del script"""
    parser = argparse.ArgumentParser(description='Eliminar todos los canales de chat en Stream.io')
    parser.add_argument('--batch-size', type=int, default=10, help='Número de canales a procesar por lote')
    parser.add_argument('--dry-run', action='store_true', help='Simular la eliminación sin realizarla')
    parser.add_argument('--quiet', action='store_true', help='Reducir la cantidad de mensajes de log')
    parser.add_argument('--force', action='store_true', help='Eliminar sin solicitar confirmación')
    args = parser.parse_args()
    
    # Verificar credenciales
    settings = get_settings()
    if not args.quiet:
        logger.info(f"Conectando a Stream.io con API key: {settings.STREAM_API_KEY[:4]}***")
    
    # Solicitar confirmación si no es dry-run y no se forzó
    if not args.dry_run and not args.force:
        print("\n¡ADVERTENCIA! Este script eliminará TODOS los canales de chat de Stream.io.")
        print("Esta acción NO se puede deshacer.")
        confirmation = input("\nEscriba 'CONFIRMAR' para continuar: ")
        
        if confirmation != "CONFIRMAR":
            print("Operación cancelada.")
            return
    
    # Proceder con la eliminación
    delete_all_channels(
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        quiet=args.quiet
    )

if __name__ == "__main__":
    main() 